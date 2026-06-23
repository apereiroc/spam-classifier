import argparse
import os
import random
import sys
from typing import Literal

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, insert, select
from sqlalchemy.exc import IntegrityError

from src.db.schema import train_versions, train_set
from src.logging import get_logger

logger = get_logger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--version", required=True, help="Version identifier, e.g. v1.0-train"
    )
    p.add_argument(
        "--n-spam", type=int, default=50, help="Number of spam samples for training"
    )
    p.add_argument(
        "--n-ham", type=int, default=200, help="Number of ham samples for training"
    )
    p.add_argument("--seed", type=int, default=42, help="Seed passed to the RNG")
    p.add_argument(
        "--notes",
        default="",
        help="Notes describing the version. If null, the numbers describing the version will be used",
    )
    return p.parse_args()


def fetch_ids_by_label(conn, label: Literal["spam", "ham"]) -> list[str]:
    """
    Return email_ids whose current (most recent) label matches `label` and are not in test_set_fixed
    """
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
          AND rl.email_id NOT IN (SELECT email_id FROM test_set)
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
            # make sure the version doesn't already exist
            existing = conn.execute(
                select(train_versions.c.version).where(
                    train_versions.c.version == args.version
                )
            ).fetchone()
            if existing:
                sys.exit(
                    f"❌ Version '{args.version}' already exists. Pick a different name."
                )

            # fetch email IDs for spam and ham
            spam_ids = fetch_ids_by_label(conn, "spam")
            ham_ids = fetch_ids_by_label(conn, "ham")

            logger.info(f"Available: {len(spam_ids)} spam, {len(ham_ids)} ham")

            if len(spam_ids) < args.n_spam:
                sys.exit(
                    f"❌ Need {args.n_spam} spam but only {len(spam_ids)} available"
                )
            if len(ham_ids) < args.n_ham:
                sys.exit(f"❌ Need {args.n_ham} ham but only {len(ham_ids)} available")

            # sample
            spam_sample = rng.sample(spam_ids, args.n_spam)
            ham_sample = rng.sample(ham_ids, args.n_ham)

            # insert train_version row
            notes = args.notes or (
                f"Training set: {args.n_ham} ham + {args.n_spam} spam, "
                f"seed={args.seed}"
            )
            conn.execute(
                insert(train_versions).values(
                    version=args.version,
                    notes=notes,
                    n_spam=args.n_spam,
                    n_ham=args.n_ham,
                    seed=args.seed,
                )
            )

            # insert train splits
            rows = []
            for email_id in spam_sample:
                rows.append(
                    {
                        "version": args.version,
                        "email_id": email_id,
                        "label": "spam",
                    }
                )
            for email_id in ham_sample:
                rows.append(
                    {
                        "version": args.version,
                        "email_id": email_id,
                        "label": "ham",
                    }
                )

            try:
                conn.execute(insert(train_set), rows)
            except IntegrityError as e:
                sys.exit(f"❌ Failed to insert splits: {e}")

            # operation summary
            logger.info(f"Version '{args.version}' created")
            logger.info(
                f"   train: {len(spam_sample)} spam + {len(ham_sample)} ham"
            )
            logger.info(f"   seed: {args.seed}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
