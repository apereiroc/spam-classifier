import pandas as pd
from sqlalchemy import inspect, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from gmail_client import get_gmail_service
from logging_utils import get_logger
from parser import clean_body, extract_auth_status, extract_body
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
from db_schema import emails, label_history, metadata

logger = get_logger(__name__)


def get_existing_ids(engine, email_ids: list[str]) -> set[str]:
    """
    Return ids that already exist in the emails table for one id batch
    """
    if not email_ids:
        return set()

    if not inspect(engine).has_table("emails"):
        return set()

    with engine.begin() as conn:
        existing = conn.execute(select(emails.c.id).where(emails.c.id.in_(email_ids)))
        return {row[0] for row in existing}


def iter_message_batches(
    api_query: str,
    max_results: int = 500,
    page_size: int = 500,
    engine=None,
):
    """
    Stream gmail messages in pages, enrich each message, and yield normalized dataframe batches

    strategy:
    - first request message ids page by page using gmail list
    - if engine is provided, skip ids already present in the database for each page
    - fetch, for each remaining id, the message in full format to extract headers, body, and auth signals
    - normalize records into a database table model and yield each non-empty batch
    """
    logger.info(f"Calling API with query '{api_query}' ...")

    try:
        service = get_gmail_service()
        fetched = 0
        page_token = None

        while fetched < max_results:
            current_page_size = min(page_size, max_results - fetched)
            # fetch one page of message ids
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q=api_query,
                    maxResults=current_page_size,
                    pageToken=page_token,
                )
                .execute()
            )
            messages = results.get("messages", [])

            if not messages:
                if fetched == 0:
                    logger.info("No messages found.")
                break

            existing_ids = set()
            if engine is not None:
                page_ids = [message["id"] for message in messages]
                existing_ids = get_existing_ids(engine=engine, email_ids=page_ids)
                if existing_ids:
                    logger.info(
                        f"Skipping {len(existing_ids)} already stored messages for query ´{api_query}´"
                    )

            messages_list = []

            for message in messages:
                email_id = message["id"]

                # skip emails that already exist in database
                if email_id in existing_ids:
                    continue

                # get full payload for each id to extract all required fields
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=email_id, format="full")
                    .execute()
                )

                # get snippet (similar to subject?)
                snippet = msg.get("snippet", "")
                if not snippet:
                    logger.warning("snippet not found")

                # get timestamp
                timestamp: int = msg["internalDate"]

                # get payload and headers
                payload = msg.get("payload", {})
                headers = payload.get("headers", [])

                # get subject
                subject = ""
                for header in headers:
                    if header["name"].lower() == "subject":
                        subject = header["value"]

                if not subject:
                    logger.warning("subject not found")

                # get body
                body = extract_body(payload)
                if not body:
                    logger.warning(f"body not found for snippet '{snippet}'")

                # clean body before saving to database
                cleaned_body = clean_body(body)
                spf, dkim, dmarc = extract_auth_status(headers)

                # add to batch, following the table model
                messages_list.append(
                    {
                        "id": email_id,
                        "timestamp": timestamp,
                        "subject": subject,
                        "clean_body": cleaned_body,
                        "spf": spf,
                        "dkim": dkim,
                        "dmarc": dmarc,
                    }
                )

            # submit
            if messages_list:
                # yield batches so callers can process incrementally
                yield pd.DataFrame(messages_list)

            fetched += len(messages)
            page_token = results.get("nextPageToken")
            if not page_token:
                break

    except Exception as e:
        logger.error(f"An exception occurred: {e}")


def stream_insert_messages(
    api_query: str, max_results: int, engine, label: str, batch_size: int = 500
) -> int:
    """Consume streamed batches and insert them while tracking progress

    strategy:
    - iterate over message batches produced by the gmail extractor
    - skip messages that are already stored based on id checks (by page)
    - annotate each batch with the target spam label
    - insert each batch immediately to avoid holding all rows in memory
    """
    total_inserted = 0
    for df_batch in iter_message_batches(
        api_query=api_query,
        max_results=max_results,
        page_size=batch_size,
        engine=engine,
    ):
        if df_batch.empty:
            continue
        insert_emails_if_new(
            df=df_batch, engine=engine, label=label, source="gmail_initial"
        )
        total_inserted += len(df_batch)
        logger.info(f"Inserted {total_inserted} rows for query '{api_query}'")
    return total_inserted


def insert_emails_if_new(df: pd.DataFrame, engine, label: str, source: str) -> None:
    """Insert email rows into database and ignore ids that already exist

    strategy:
    - define/create the target table schema
    - build insert statement from the dataframe records
    - on id conflict, do nothing to preserve previously stored records
    """
    if df.empty:
        return

    metadata.create_all(engine)

    records = df.to_dict(orient="records")
    stmt = sqlite_insert(emails).values(records)
    label_records = [
        {
            "email_id": row["id"],
            "label": label,
            "source": source,
        }
        for row in records
    ]
    label_stmt = sqlite_insert(label_history).values(label_records)

    with engine.begin() as conn:
        conn.execute(stmt.on_conflict_do_nothing(index_elements=[emails.c.id]))
        conn.execute(label_stmt)


if __name__ == "__main__":
    load_dotenv()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("Please set the environment variable DATABASE_URL")

    engine = create_engine(database_url, echo=False)

    total_no_spam = stream_insert_messages(
        api_query="label:INBOX -label:SPAM",
        max_results=25_000,
        engine=engine,
        label="ham",
        batch_size=2000,
    )
    total_spam = stream_insert_messages(
        api_query="label:SPAM",
        max_results=100,
        engine=engine,
        label="spam",
        batch_size=100,
    )
    logger.info(f"Finished. no_spam={total_no_spam}, spam={total_spam}")
