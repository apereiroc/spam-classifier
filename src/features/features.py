import pandas as pd
from math import log
from collections import Counter


def _check_columns(df: pd.DataFrame, *columns: str):
    """
    Helper to check if the necessary columns are available
    """
    for col in columns:
        if col not in df.columns:
            raise RuntimeError(
                f"Column `{col}` is needed but was not found in DataFrame"
            )


def timestamp_to_datetime(df: pd.DataFrame) -> pd.DataFrame:
    _check_columns(df, "timestamp")
    df["received_at"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df.drop(columns=["timestamp"])


def break_down_datetime(df: pd.DataFrame) -> pd.DataFrame:
    _check_columns(df, "received_at")
    df["received_at_year"] = df["received_at"].dt.year
    df["received_at_month"] = df["received_at"].dt.month
    df["received_at_day"] = df["received_at"].dt.day
    df["received_at_hour"] = df["received_at"].dt.hour
    df["received_at_minute"] = df["received_at"].dt.minute
    df["received_at_second"] = df["received_at"].dt.second
    return df.drop(columns=["received_at"])


def break_down_sender_email(df: pd.DataFrame) -> pd.DataFrame:
    _check_columns(df, "sender_email")
    df[["sender_local", "domain_full"]] = df["sender_email"].str.split("@", expand=True)
    df[["sender_domain_name", "sender_tld"]] = df["domain_full"].str.rsplit(
        ".", n=1, expand=True
    )
    return df.drop(columns=["sender_email", "domain_full"])


def transform_security_protocols(df: pd.DataFrame) -> pd.DataFrame:
    _check_columns(df, "spf", "dkim", "dmarc")
    df["spf_pass"] = df["spf"] == "pass"
    df["dkim_pass"] = df["dkim"] == "pass"
    df["dmarc_pass"] = df["dmarc"] == "pass"
    return df.drop(columns=["spf", "dkim", "dmarc"])


def transform_text_column_to_statistics(df: pd.DataFrame, column: str) -> pd.DataFrame:
    _check_columns(df, column)
    df[f"{column}_len"] = df[column].str.len()

    # use lambda function to avoid unicode problems
    df["n_upper"] = df[column].apply(lambda s: sum(c.isupper() for c in str(s)))
    df["n_lower"] = df[column].apply(lambda s: sum(c.islower() for c in str(s)))
    df["n_digits"] = df[column].apply(lambda s: sum(c.isdigit() for c in str(s)))
    df["n_whitespaces"] = df[column].apply(lambda s: sum(c.isspace() for c in str(s)))

    # calculate proportions
    df[f"{column}_prop_upper"] = df["n_upper"] / df[f"{column}_len"]
    df[f"{column}_prop_lower"] = df["n_lower"] / df[f"{column}_len"]
    df[f"{column}_prop_digits"] = df["n_digits"] / df[f"{column}_len"]
    df[f"{column}_prop_whitespaces"] = df["n_whitespaces"] / df[f"{column}_len"]

    # aditional useful features in NLP
    df[f"{column}_upper_lower_ratio"] = df["n_upper"] / (df["n_lower"] + 1)
    df[f"{column}_n_words"] = df[column].str.split().str.len()
    df[f"{column}_shannon_entropy"] = df[column].apply(
        lambda i: -sum(
            f * log(f, 2) for f in ((j / len(i)) for j in Counter(i).values())
        )
    )
    return df.drop(columns=[column, "n_upper", "n_lower", "n_digits", "n_whitespaces"])
