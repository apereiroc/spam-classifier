import argparse
import os
import random
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, insert, select, text

from src.db.schema import test_set
from src.logging import get_logger

logger = get_logger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--n-spam", type=int, default=100, help="Number of spam samples for test set"
    )
    p.add_argument(
        "--n-ham", type=int, default=200, help="Number of ham samples for test set"
    )
    p.add_argument("--seed", type=int, default=42, help="Seed passed to the RNG")
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing test set without prompting",
    )
    return p.parse_args()


def fetch_ids_by_label(conn, label: str) -> list[str]:
    query = text("""
        WITH ranked_labels AS (
            SELECT
                lh.email_id,
                lh.label,
                ROW_NUMBER() OVER (
                    PARTITION BY lh.email_id
                    ORDER BY lh.labeled_at DESC
                ) AS rn
            FROM label_history lh
        )
        SELECT rl.email_id
        FROM ranked_labels rl
        WHERE rl.rn = 1
          AND rl.label = :label
        ORDER BY rl.email_id
    """)
    ids = [row[0] for row in conn.execute(query, {"label": label}).fetchall()]
    return ids


def main():
    args = parse_args()
    rng = random.Random(args.seed)

    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("❌ DATABASE_URL is not set. Check your .env file.")

    engine = create_engine(db_url)

    try:
        with engine.begin() as conn:
            existing = conn.execute(
                select(test_set.c.email_id)
            ).fetchone()
            if existing and not args.force:
                sys.exit(
                    "❌ Test set already exists. Use --force to overwrite or remove it manually."
                )

            if existing and args.force:
                conn.execute(delete(test_set))
                logger.info("Existing test set will be overwritten")

            spam_ids = fetch_ids_by_label(conn, "spam")
            ham_ids = fetch_ids_by_label(conn, "ham")

            logger.info(f"Available: {len(spam_ids)} spam, {len(ham_ids)} ham")

            if len(spam_ids) < args.n_spam:
                sys.exit(
                    f"❌ Need {args.n_spam} spam but only {len(spam_ids)} available"
                )
            if len(ham_ids) < args.n_ham:
                sys.exit(f"❌ Need {args.n_ham} ham but only {len(ham_ids)} available")

            spam_sample = rng.sample(spam_ids, args.n_spam)
            ham_sample = rng.sample(ham_ids, args.n_ham)

            rows = []
            for email_id in spam_sample:
                rows.append({"email_id": email_id, "label": "spam"})
            for email_id in ham_sample:
                rows.append({"email_id": email_id, "label": "ham"})

            conn.execute(insert(test_set), rows)

            logger.info(f"Test set created")
            logger.info(f"   spam: {len(spam_sample)}")
            logger.info(f"   ham: {len(ham_sample)}")
            logger.info(f"   seed: {args.seed}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
