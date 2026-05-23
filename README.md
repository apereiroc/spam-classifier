# spam-classifier

A machine learning project to classify your Gmail messages as spam or not spam.

## What it does so far

The basic data engineering is working correctly, with emails tagged in the inbox and the spam folder in Gmail (already categorised by Google) being inserted into a local SQLite database

- Connects to Gmail with read-only API access
- Fetches messages from inbox and spam using Gmail queries
- Extracts relevant features such as subject, body text, SPF, DKIM, DMARC, etc.
- Stores normalized email data in a local SQLite database

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
