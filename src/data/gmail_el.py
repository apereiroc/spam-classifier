from dataclasses import asdict, dataclass
from email.utils import parseaddr
from typing import Any, Iterator

from googleapiclient.errors import HttpError
from sqlalchemy import Engine, inspect, insert, select

from db_schema import emails, label_history
from logging_utils import get_logger
from parser import clean_body, extract_auth_status, extract_body

logger = get_logger(__name__)


@dataclass
class EmailRecord:
    """Model for an email fetched with the gmail API"""

    id: str
    timestamp: int
    sender_email: str
    subject: str
    clean_body: str
    spf: str
    dkim: str
    dmarc: str


def get_existing_ids(engine: Engine, email_ids: list[str]) -> set[str]:
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
    service: Any,
    engine: Engine,
    api_query: str,
    max_results: int = 500,
    page_size: int = 500,
) -> Iterator[list[EmailRecord]]:
    """
    Stream gmail messages in pages, enrich each message, and yield normalized record batches

    strategy:
    - first request message ids page by page using gmail list
    - if engine is provided, skip ids already present in the database for each page
    - fetch, for each remaining id, the message in full format to extract headers, body, and auth signals
    - normalize records into a database table model and yield each non-empty batch
    """
    logger.info(f"Calling API with query '{api_query}' ...")
    fetched = 0
    page_token = None
    while fetched < max_results:
        current_page_size = min(page_size, max_results - fetched)
        # fetch one page of message ids
        try:
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
        except HttpError:
            logger.exception(
                f"Failed to list messages for query '{api_query}' and page token '{page_token}'"
            )
            raise
        messages = results.get("messages", [])
        if not messages:
            if fetched == 0:
                logger.info("No messages found.")
            break
        page_ids = [message["id"] for message in messages]
        existing_ids = get_existing_ids(engine=engine, email_ids=page_ids)
        if existing_ids:
            logger.info(
                f"Skipping {len(existing_ids)} already stored messages for query '{api_query}'"
            )
        messages_list: list[EmailRecord] = []
        missing_snippet = 0
        missing_subject = 0
        missing_sender = 0
        missing_body = 0
        for message in messages:
            email_id = message["id"]
            # skip emails that already exist in database
            if email_id in existing_ids:
                continue
            # get full payload for each id to extract all required fields
            try:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=email_id, format="full")
                    .execute()
                )
            except HttpError:
                logger.exception(f"Failed to fetch message '{email_id}'")
                continue
            # get snippet (similar to subject?)
            snippet = msg.get("snippet", "")
            if not snippet:
                missing_snippet += 1
            # get timestamp
            timestamp_raw = msg.get("internalDate")
            try:
                timestamp = int(timestamp_raw)
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid timestamp for message '{email_id}': {timestamp_raw}. Using 0"
                )
                timestamp = 0
            # get payload and headers
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            # get subject and sender email
            subject = ""
            sender_email = ""
            for header in headers:
                header_name = header.get("name", "").lower()
                header_value = header.get("value", "")
                if header_name == "subject":
                    subject = header_value
                elif header_name == "from":
                    sender_email = parseaddr(header_value)[1]
            if not subject:
                logger.warning(f"Missing subject for email id {email_id}")
                missing_subject += 1
            if not sender_email:
                logger.warning(f"Missing sender email for email id {email_id}")
                missing_sender += 1
            # get body
            body = extract_body(payload)
            if not body:
                logger.warning(f"Missing body for email id {email_id}")
                missing_body += 1
            # clean body before saving to database
            cleaned_body = clean_body(body)
            spf, dkim, dmarc = extract_auth_status(headers)
            # add to batch, following the table model
            messages_list.append(
                EmailRecord(
                    id=email_id,
                    timestamp=timestamp,
                    sender_email=sender_email,
                    subject=subject,
                    clean_body=cleaned_body,
                    spf=spf,
                    dkim=dkim,
                    dmarc=dmarc,
                )
            )
        # submit
        if messages_list:
            logger.info(
                f"Prepared {len(messages_list)} messages for query '{api_query}' (missing snippet={missing_snippet}, subject={missing_subject}, sender={missing_sender}, body={missing_body})"
            )
            # yield batches so callers can process incrementally
            yield messages_list
        fetched += len(messages)
        page_token = results.get("nextPageToken")
        if not page_token:
            break


def insert_emails_if_new(
    records: list[EmailRecord], engine: Engine, label: str, source: str
) -> int:
    if not records:
        return 0
    all_ids = [row.id for row in records]
    existing_ids = get_existing_ids(engine=engine, email_ids=all_ids)
    inserted_ids = {email_id for email_id in all_ids if email_id not in existing_ids}
    if not inserted_ids:
        return 0
    records_to_insert = [asdict(row) for row in records if row.id in inserted_ids]
    label_records = [
        {"email_id": email_id, "label": label, "source": source}
        for email_id in inserted_ids
    ]
    with engine.begin() as conn:
        conn.execute(insert(emails), records_to_insert)
        conn.execute(insert(label_history), label_records)
    return len(inserted_ids)


def stream_insert_messages(
    service: Any,
    engine: Engine,
    api_query: str,
    max_results: int,
    label: str,
    batch_size: int = 500,
) -> int:
    total_inserted = 0
    for record_batch in iter_message_batches(
        service=service,
        engine=engine,
        api_query=api_query,
        max_results=max_results,
        page_size=batch_size,
    ):
        if not record_batch:
            continue
        inserted_now = insert_emails_if_new(
            records=record_batch, engine=engine, label=label, source="gmail_initial"
        )
        total_inserted += inserted_now
        logger.info(
            f"Inserted {inserted_now} new rows in current batch, total {total_inserted} for query '{api_query}'"
        )
    return total_inserted
