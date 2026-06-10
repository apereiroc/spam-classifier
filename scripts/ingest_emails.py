import os
import argparse

from dotenv import load_dotenv
from sqlalchemy import create_engine

from src.db.schema import metadata
from src.gmail import get_gmail_service
from src.logging import get_logger
from src.data import stream_insert_messages

logger = get_logger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--spam-max-results",
        type=int,
        default=100,
        help="Maximum number of spam IDs to be searched",
    )
    p.add_argument("--spam-batch-size", type=int, default=100, help="Spam batch size")
    p.add_argument(
        "--ham-max-results",
        type=int,
        default=25_000,
        help="Maximum number of ham IDs to be searched",
    )
    p.add_argument("--ham-batch-size", type=int, default=2_000, help="Ham batch size")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    # dependency injection for engine and gmail api service
    engine = create_engine(db_url, echo=False, pool_pre_ping=True)
    service = get_gmail_service()
    try:
        metadata.create_all(engine)
        total_spam = stream_insert_messages(
            service=service,
            engine=engine,
            api_query="label:SPAM",
            max_results=args.spam_max_results,
            label="spam",
            batch_size=args.spam_batch_size,
        )
        total_ham = stream_insert_messages(
            service=service,
            engine=engine,
            api_query="label:INBOX -label:SPAM",
            max_results=args.ham_max_results,
            label="ham",
            batch_size=args.ham_batch_size,
        )
        logger.info(f"Finished. ham={total_ham}, spam={total_spam}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
