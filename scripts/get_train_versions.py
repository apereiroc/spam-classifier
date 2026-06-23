import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Engine


def fetch_versions(engine: Engine):
    query = text("""
    SELECT
        version,
        n_spam,
        n_ham,
        seed,
        notes
    FROM
        train_versions
    """)
    with engine.begin() as conn:
        rows = conn.execute(query).fetchall()

    if not rows:
        print("No training versions found.")
        return

    info = "\n\n".join(
        f"version: `{r.version}` -- notes: {r.notes}\n"
        f"  size: {r.n_ham + r.n_spam}\n  n_ham: {r.n_ham}\n  n_spam: {r.n_spam}\n  seed: {r.seed}"
        for r in rows
    )
    print(info)


def main():

    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("❌ DATABASE_URL is not set. Check your .env file.")

    engine = create_engine(db_url)
    try:
        fetch_versions(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
