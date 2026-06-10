import argparse
import os
import random
import sys
from typing import Literal

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, insert, select
from sqlalchemy.exc import IntegrityError

from src.db.schema import dataset_versions, dataset_splits
from src.logging import get_logger

logger = get_logger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--version", required=True, help="Version identifier, e.g. v0.1-sandbox"
    )
    p.add_argument(
        "--n-spam", type=int, default=50, help="Number of total spam samples"
    )
    p.add_argument("--n-ham", type=int, default=200, help="Number of total ham samples")
    p.add_argument(
        "--test-ratio",
        type=float,
        default=0.15,
        help="Fraction of total samples dedicated to the test set",
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
    Return email_ids whose current (most recent) label matches `label`
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
        ORDER BY rl.email_id
    """)
    ids = [row[0] for row in conn.execute(query, {"label": label}).fetchall()]
    return ids


def stratified_split(
    ids: list[str], test_ratio: float, rng: random.Random
) -> dict[str, list[str]]:
    """
    Split into train/test. CV will be performed inside dev
    """
    shuffled = ids.copy()
    rng.shuffle(shuffled)
    n_test = max(1, int(round(len(shuffled) * test_ratio)))
    return {
        "test": shuffled[:n_test],
        "train": shuffled[n_test:],
    }


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
                select(dataset_versions.c.version).where(
                    dataset_versions.c.version == args.version
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

            # stratified split per class
            spam_splits = stratified_split(spam_sample, args.test_ratio, rng)
            ham_splits = stratified_split(ham_sample, args.test_ratio, rng)

            # insert dataset_version row
            notes = args.notes or (
                f"Sandbox: {args.n_ham} ham + {args.n_spam} spam, "
                f"test_ratio={args.test_ratio}, seed={args.seed}"
            )
            conn.execute(
                insert(dataset_versions).values(
                    version=args.version,
                    notes=notes,
                    n_spam=args.n_spam,
                    n_ham=args.n_ham,
                    test_ratio=args.test_ratio,
                    seed=args.seed,
                )
            )

            # insert train and test splits for spam and ham
            rows = []
            for split_name, email_ids in spam_splits.items():
                rows.extend(
                    {
                        "version": args.version,
                        "email_id": email_id,
                        "label": "spam",
                        "split": split_name,
                    }
                    for email_id in email_ids
                )
            for split_name, email_ids in ham_splits.items():
                rows.extend(
                    {
                        "version": args.version,
                        "email_id": email_id,
                        "label": "ham",
                        "split": split_name,
                    }
                    for email_id in email_ids
                )

            try:
                conn.execute(insert(dataset_splits), rows)
            except IntegrityError as e:
                sys.exit(f"❌ Failed to insert splits: {e}")

            # operation summary
            logger.info(f"Version '{args.version}' created")
            logger.info(
                f"   train: {len(spam_splits['train'])} spam + {len(ham_splits['train'])} ham"
            )
            logger.info(
                f"   test:  {len(spam_splits['test'])} spam + {len(ham_splits['test'])} ham"
            )
            logger.info(f"   seed: {args.seed}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
