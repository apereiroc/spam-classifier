import pandas as pd
from typing import Literal
from sqlalchemy import text, Engine


def load_split(
    engine: Engine, version: str | None = None, split: Literal["train", "test"] = "test"
) -> pd.DataFrame:
    """Load a dataset split. For training splits, provide version and split='train'.
    For the fixed test set, use split='test' (version is ignored)."""

    if split == "test":
        query = text("""
            SELECT
                e.id,
                e.timestamp,
                e.sender_email,
                e.subject,
                e.clean_body,
                e.spf,
                e.dkim,
                e.dmarc,
                ts.label
            FROM test_set ts
            JOIN emails e ON e.id = ts.email_id
        """)
        df = pd.read_sql(query, engine)
        return df

    if split == "train":
        if not version:
            raise ValueError("version is required for train split")
        query = text("""
            SELECT
                e.id,
                e.timestamp,
                e.sender_email,
                e.subject,
                e.clean_body,
                e.spf,
                e.dkim,
                e.dmarc,
                ts.label
            FROM train_set ts
            JOIN emails e ON e.id = ts.email_id
            WHERE ts.version = :version
        """)
        df = pd.read_sql(query, engine, params={"version": version})
        return df

    raise ValueError("split must be 'train' or 'test'")


def load_dataset(engine: Engine, version: str) -> dict[str, pd.DataFrame]:
    """Load train and test splits. Train comes from the specified version, test is always the fixed test set."""
    return {
        "train": load_split(engine, version=version, split="train"),
        "test": load_split(engine, split="test"),
    }
