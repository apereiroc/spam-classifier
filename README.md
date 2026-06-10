# spam-classifier

A machine learning project to classify your Gmail messages as spam or not spam.

## What it does so far

The basic data engineering is working correctly, with emails tagged in the inbox and the spam folder in Gmail (already categorised by Google) being inserted into a local SQLite database

- Connects to Gmail with read-only API access
- Fetches messages from inbox and spam using Gmail queries
- Extracts relevant features such as subject, body text, SPF, DKIM, DMARC, etc.
- Stores normalized email data in a local SQLite database

Custom splits into train/test can be locked with a version tag, containing the desired proportions for each class.


## Database schema

- Table `emails`: contains the raw emails fetched from Gmail. Only the body is passed through a text cleaner before storage.
- Table `label_history`: append-only label history to version labels over time (for example, when a message previously considered ham is later re-labeled as spam, or vice versa).
- Table `dataset_versions` and `dataset_splits`: used to freeze dataset snapshots and train/test splits for training reproducibility.

Split policy across versions: keep the same test set between versions in order to measure real model improvement. New examples are added only to the training split.

## Run


### Create the database and ingest your mail box

I am using `uv` for this project. Eventually the real time system will operate in Docker containers

1. Sync dependencies with uv. This will create a virtual environment and install local CLI entry points from `[project.scripts]`:
   - ```bash
     uv sync
     ```
2. Copy the dotenv sample and fill it in:
   - ```bash
     cp env.sample .env
     ```
   - Set `DATABASE_URL` in `.env` (for example: `sqlite:///emails.db`)
3. Add Google API OAuth credentials file as `credentials.json`
4. Extract your emails to the database, this can take several minutes.
   - ```bash
     uv run ingest-emails
     ```

On first run, a browser window will open for Gmail OAuth. The script then saves the data into the `emails` table.

### Create a snapshot

Run this to display the help message

```bash
uv run create-dataset-version --help
```

Example of usage:

```bash
uv run create-dataset-version --version v0.1-sandbox --n-spam 50 --n-ham 100 --test-ratio 0.15 --seed 42 --notes "first test, let's see how it goes"
```

You can verify the versions created at your database

```bash
uv run get-dataset-versions
```

And also remove a specific version

```bash
uv run remove-dataset-version --version <VERSION>
```

These scripts do not alter the `emails` main table. The database contains specific tables for managing the dynamic assignment of spam/ham labels and the assignment of email IDs to a dataset version that you have created
