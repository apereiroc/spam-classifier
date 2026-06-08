import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

from db_schema import metadata
from src.gmail import get_gmail_service
from src.logging import get_logger
from src.data.gmail_el import stream_insert_messages

logger = get_logger(__name__)


def main() -> None:
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
            max_results=100,
            label="spam",
            batch_size=100,
        )
        total_ham = stream_insert_messages(
            service=service,
            engine=engine,
            api_query="label:INBOX -label:SPAM",
            max_results=25_000,
            label="ham",
            batch_size=2000,
        )
        logger.info(f"Finished. ham={total_ham}, spam={total_spam}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
