import argparse
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, select

from src.db.schema import train_set, train_versions
from src.logging import get_logger

logger = get_logger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True, help="Version identifier to be removed")
    return p.parse_args()


def main():
    args = parse_args()

    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("❌ DATABASE_URL is not set. Check your .env file.")

    engine = create_engine(db_url)

    try:
        with engine.begin() as conn:
            # first check whether the version exists in DB
            existing = conn.execute(
                select(train_versions.c.version).where(
                    train_versions.c.version == args.version
                )
            ).fetchone()

            if not existing:
                sys.exit(f"❌ Version '{args.version}' does not exist.")

            # delete splits for the version passed in args
            deleted_splits = conn.execute(
                delete(train_set).where(train_set.c.version == args.version)
            ).rowcount

            # delete version for the version passed in args
            deleted_versions = conn.execute(
                delete(train_versions).where(
                    train_versions.c.version == args.version
                )
            ).rowcount

            if not deleted_versions:
                logger.error(f"❌ Failed to remove version '{args.version}'.")
            else:
                logger.info(f"✅ Version '{args.version}' removed")
                logger.info(f"   removed splits: {deleted_splits or 0}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
