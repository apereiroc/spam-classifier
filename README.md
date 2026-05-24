# spam-classifier

A machine learning project to classify your Gmail messages as spam or not spam.

## What it does so far

The basic data engineering is working correctly, with emails tagged in the inbox and the spam folder in Gmail (already categorised by Google) being inserted into a local SQLite database

- Connects to Gmail with read-only API access
- Fetches messages from inbox and spam using Gmail queries
- Extracts relevant features such as subject, body text, SPF, DKIM, DMARC, etc.
- Stores normalized email data in a local SQLite database

## Database schema

- Table `emails`: contains the raw emails fetched from Gmail. Only the body is passed through a text cleaner before storage.
- Table `label_history`: append-only label history to version labels over time (for example, when a message previously considered ham is later re-labeled as spam, or vice versa).
- Table `dataset_versions` and `dataset_members`: used to freeze dataset snapshots and train/val/test splits for training reproducibility.

Split policy across versions: keep the same test set between versions in order to measure real model improvement. New examples are added only to the training split.

## Run

I am using `uv` for this project. Eventually the real time system will be run in Docker containers

1. Sync dependencies with uv. This will create a virtual environment:
   - `uv sync`
2. Copy the dotenv sample and fill it in:
   - `cp env.sample .env`
   - Set `DATABASE_URL` in `.env` (for example: `sqlite:///emails.db`)
3. Add Google API OAuth credentials file as `credentials.json`
4. Run:
   - `uv run extract.py`

On first run, a browser window will open for Gmail OAuth. The script then saves data into the `emails` table.
