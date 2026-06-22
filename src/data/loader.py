import pandas as pd
from typing import Literal
from sqlalchemy import text, Engine


def load_split(
    engine: Engine, version: str, split: Literal["train", "test"]
) -> pd.DataFrame:
    """Load a single split (train/test) for a given dataset version."""

    # check split type is valid
    if split not in ["train", "test"]:
        raise ValueError(f"Split should train or test, got `{split}`")

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
            ds.label
        FROM dataset_splits ds
        JOIN emails e ON e.id = ds.email_id
        WHERE ds.version = :version AND ds.split = :split
    """)
    df = pd.read_sql(query, engine, params={"version": version, "split": split})
    return df


def load_dataset(engine: Engine, version: str) -> dict[str, pd.DataFrame]:
    """Load all splits at once. Returns a dict {'train': df, 'test': df}."""
    return {split: load_split(engine, version, split) for split in ("train", "test")}
