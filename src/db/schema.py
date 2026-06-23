from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
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
train_versions = Table(
    "train_versions",
    metadata,
    Column("version", String, primary_key=True),
    Column("created_at", TIMESTAMP, server_default=func.current_timestamp()),
    Column("notes", Text),
    Column("n_spam", Integer),
    Column("n_ham", Integer),
    Column("seed", Integer),
)
train_set = Table(
    "train_set",
    metadata,
    Column("version", String, ForeignKey("train_versions.version"), primary_key=True),
    Column("email_id", String, ForeignKey("emails.id"), primary_key=True),
    Column("label", String, nullable=False),
)
test_set = Table(
    "test_set",
    metadata,
    Column("email_id", String, ForeignKey("emails.id"), primary_key=True),
    Column("label", String, nullable=False),
    Column("created_at", TIMESTAMP, server_default=func.current_timestamp()),
)
