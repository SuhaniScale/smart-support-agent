
import os
import json
from dotenv import load_dotenv
from google.cloud import bigquery
from pathlib import Path

script_path = Path(__file__).resolve()
repo_root = None
for parent in [script_path, *script_path.parents]:
    if (parent / ".env").exists():
        repo_root = parent
        break

if repo_root is None:
    repo_root = script_path.parents[2]

dotenv_path = repo_root / ".env"
load_dotenv(dotenv_path)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET_ID = "epcdatasetid"
TABLE_ID = "historical_incidents"

INCIDENTS_FILE = "../data/historical_incidents.json"

client = bigquery.Client(project=PROJECT_ID)

table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

schema = [
    bigquery.SchemaField("incident_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("summary", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("outcome", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
]


def create_table_if_needed():
    try:
        client.get_table(table_ref)
        print(f"Table {table_ref} already exists. Skipping creation.")
    except Exception:
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        print(f"Created table {table_ref}")


def load_incidents():
    with open(INCIDENTS_FILE, "r") as f:
        incidents = json.load(f)

    errors = client.insert_rows_json(table_ref, incidents)

    if errors:
        print("Errors occurred while inserting rows:")
        print(errors)
    else:
        print(f"Successfully inserted {len(incidents)} rows into {table_ref}")


if __name__ == "__main__":
    create_table_if_needed()
    load_incidents()

