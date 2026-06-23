from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    Index,
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
Index("idx_email_id_labeled_at", label_history.c.email_id, label_history.c.labeled_at)
Index("idx_label_email_id", label_history.c.label, label_history.c.email_id)
dataset_versions = Table(
    "dataset_versions",
    metadata,
    Column("version", String, primary_key=True),
    Column("created_at", TIMESTAMP, server_default=func.current_timestamp()),
    Column("notes", Text),
    Column("n_spam", Integer),
    Column("n_ham", Integer),
    Column("test_ratio", Float),
    Column("seed", Integer),
)
dataset_splits = Table(
    "dataset_splits",
    metadata,
    Column("version", String, ForeignKey("dataset_versions.version"), primary_key=True),
    Column("email_id", String, ForeignKey("emails.id"), primary_key=True),
    Column("label", String, nullable=False),
    Column("split", String, nullable=False),
    CheckConstraint("split IN ('train','val','test')"),
)
test_set_fixed = Table(
    "test_set_fixed",
    metadata,
    Column("email_id", String, ForeignKey("emails.id"), primary_key=True),
    Column("label", String, nullable=False),
    Column("created_at", TIMESTAMP, server_default=func.current_timestamp()),
)
