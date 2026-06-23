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

Split policy across versions: keep the same test set between versions in order to measure real model improvement. New examples are added only to newer training set versions.

- Table `emails`: contains the raw emails fetched from Gmail. Only the body is passed through a minimal text cleaner before storage.
- Table `label_history`: append-only label history to version labels over time (for example, when a message previously considered ham is later re-labeled as spam, or vice versa).
- Table `train_versions` and `train_set`: used to freeze training dataset snapshots and versions for reproducibility.
- Table `test_set`: a permanently fixed test set. Once created, this test set typically never changes, allowing you to compare models across different training data versions.

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
4. Extract your emails to the database with `uv run ingest-emails`, use `--help` to see the available options. Since it can take several minutes to complete with the default runtime parameters, a small batch can be ingested with
   - ```bash
     uv run ingest-emails --spam-max-results 50 --ham-max-results 50
     ```

On first run, a browser window will open for Gmail OAuth. The script then saves the data into the `emails` table.

### Create a fixed test set

To ensure that your model evaluation is consistent across multiple training iterations, you can create a permanently fixed test set. This test set will ideally never change, allowing you to measure real model improvements by always evaluating against the same emails.

Create a fixed test set with the desired number of spam and ham examples:

```bash
uv run create-test-set --n-spam 40 --n-ham 200 --seed 42
```

Once created, the fixed test set:
- Excludes those emails from all future training versions (created with `create-train-version`)
- Remains unchanged for model evaluation across training iterations
- Only changes if you explicitly use the `--force` flag to redefine it. This is useful if your initial test set is quite small, as in my case.

#### Redefining the test set

As you collect more data, you may want to redefine your test set with different proportions. Use the `--force` flag to overwrite the existing test set:

```bash
uv run create-test-set --n-spam 100 --n-ham 500 --seed 99 --force
```

When you redefine the test set:
- The previous test set is completely replaced
- All future training versions will exclude the new test set emails. You should **create a new training version** after this redefinition.
- Previous models trained with the old test set will have different evaluation baselines

### Create a training version

Once you have created a fixed test set, you can create training versions that will be used for model development. Each version creates a training set that excludes the fixed test set emails.

Run this to display the help message:

```bash
uv run create-train-version --help
```

Example of usage:

```bash
uv run create-train-version --version v1.0-train --n-spam 30 --n-ham 500 --seed 42 --notes "First training iteration"
```

Note that `create-train-version` automatically excludes emails in the fixed test set

You can verify the versions created in your database with

```bash
uv run get-train-versions
```

And also remove a specific version

```bash
uv run remove-train-version --version <VERSION>
```

### Load datasets in your code

To load datasets in your training pipeline, use the provided dataloader utilities:

```python
from src.data import load_dataset, load_split

# load a complete dataset (train + test)
dataset = load_dataset(engine=engine, version="v1.0-train")
train_df = dataset["train"]
test_df = dataset["test"]

# Or load splits individually
train_df = load_split(engine=engine, version="v1.0-train", split="train")
test_df = load_split(engine=engine, split="test")
```
