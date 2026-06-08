from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    TIMESTAMP,
    Table,
    Text,
    func,
)

metadata = MetaData()
emails = Table(
    "emails",
    metadata,
    Column("id", String, primary_key=True),
    Column("timestamp", BigInteger),
    Column("sender_email", String),
    Column("subject", Text),
    Column("clean_body", Text),
    Column("spf", String),
    Column("dkim", String),
    Column("dmarc", String),
    Column("inserted_at", TIMESTAMP, server_default=func.current_timestamp()),
)
label_history = Table(
    "label_history",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email_id", String, ForeignKey("emails.id"), nullable=False),
    Column("label", String, nullable=False),
    Column("source", String, nullable=False),
    Column("labeled_at", TIMESTAMP, server_default=func.current_timestamp()),
    CheckConstraint("label IN ('spam','ham','graymail','unknown')"),
)
dataset_versions = Table(
    "dataset_versions",
    metadata,
    Column("version", String, primary_key=True),
    Column("created_at", TIMESTAMP, server_default=func.current_timestamp()),
    Column("notes", Text),
)
dataset_members = Table(
    "dataset_members",
    metadata,
    Column("version", String, ForeignKey("dataset_versions.version"), primary_key=True),
    Column("email_id", String, ForeignKey("emails.id"), primary_key=True),
    Column("label", String, nullable=False),
    Column("split", String, nullable=False),
    CheckConstraint("split IN ('train','val','test')"),
)

__all__ = [
    "metadata",
    "emails",
    "label_history",
    "dataset_versions",
    "dataset_members",
]
