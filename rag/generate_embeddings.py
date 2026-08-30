import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.cloud import storage
from google.api_core import exceptions

# ============================================================
# AUTH NOTE:
# No service-account-key.json needed anymore. Auth comes from
# Application Default Credentials (ADC) — set up once by running:
#
#     gcloud auth application-default login
#
# Both the genai Client and google-cloud-storage automatically
# find and use those credentials. Nothing else to configure.
# ============================================================

repo_root = Path(__file__).resolve().parent.parent
dotenv_path = repo_root / ".env"
load_dotenv(dotenv_path)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-east1"
EMBEDDING_MODEL_NAME = "text-embedding-004"  

# kept same as before so vector
# dimensions (768) still match your existing Vector Search index.
# If you want to move to the newer "gemini-embedding-001" model later,
# you must set output_dimensionality=768 in EmbedContentConfig below,
# otherwise it defaults to 3072 dims and breaks the deployed index.

if not PROJECT_ID:
    raise EnvironmentError("GCP_PROJECT_ID is not set. Add it to .env or export it before running the script.")

# CHANGE THIS to the exact bucket name you created in Step 2.2
BUCKET_NAME = "epc-platform-507008-embeddings"

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
INPUT_FILE = str(PROJECT_ROOT / "data" / "historical_incidents.json")
OUTPUT_LOCAL_FILE = str(PROJECT_ROOT / "data" / "embeddings9_output.json")
GCS_DESTINATION_FOLDER = "embeddings"

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)


def get_embeddings_with_retry(texts, max_retries=3, initial_delay=2):
    attempt = 0
    while attempt < max_retries:
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL_NAME,
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            return response.embeddings
        except exceptions.ResourceExhausted as exc:
            attempt += 1
            delay = initial_delay * (2 ** (attempt - 1))
            if attempt >= max_retries:
                raise RuntimeError(
                    "Vertex AI quota exhausted. "
                    "Reduce batch size, slow down requests, or request a quota increase. "
                    f"Last error: {exc}"
                ) from exc
            print(f"Quota exhausted, retrying in {delay} seconds... (attempt {attempt}/{max_retries})")
            time.sleep(delay)
        except Exception as exc:
            raise RuntimeError("Embedding request failed.") from exc


def generate_and_save_embeddings():
    with open(INPUT_FILE, "r") as f:
        incidents = json.load(f)

    lines = []
    batch_size = 8
    batch = []
    batch_ids = []

    for incident in incidents:
        batch_ids.append(incident["incident_id"])
        batch.append(incident["summary"])

        if len(batch) >= batch_size:
            embeddings = get_embeddings_with_retry(batch)
            for incident_id, embedding in zip(batch_ids, embeddings):
                vector = embedding.values
                print(f"Embedded {incident_id}: vector length = {len(vector)}")
                lines.append(json.dumps({"id": incident_id, "embedding": vector}))
            batch = []
            batch_ids = []

    if batch:
        embeddings = get_embeddings_with_retry(batch)
        for incident_id, embedding in zip(batch_ids, embeddings):
            vector = embedding.values
            print(f"Embedded {incident_id}: vector length = {len(vector)}")
            lines.append(json.dumps({"id": incident_id, "embedding": vector}))

    with open(OUTPUT_LOCAL_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"\nSaved {len(lines)} embeddings locally to {OUTPUT_LOCAL_FILE}")

    upload_to_gcs()


def upload_to_gcs():
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob_path = f"{GCS_DESTINATION_FOLDER}/embeddings_output.json"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(OUTPUT_LOCAL_FILE)

    print(f"Uploaded to gs://{BUCKET_NAME}/{blob_path}")


if __name__ == "__main__":
    generate_and_save_embeddings()
