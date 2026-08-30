import os
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import aiplatform

# ============================================================
# NOTE: Vector Search (Matching Engine) index management has no
# google-genai equivalent — it's infrastructure, not a model call —
# so it still uses google-cloud-aiplatform. Only the auth method
# changed below: no service-account-key.json, uses ADC instead.
#
# One-time setup:
#     gcloud auth application-default login
# ============================================================

repo_root = Path(__file__).resolve().parent.parent
dotenv_path = repo_root / ".env"
load_dotenv(dotenv_path)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-east1"

if not PROJECT_ID:
    raise EnvironmentError(
        "GCP_PROJECT_ID is not set. Add it to your .env file."
    )

BUCKET_NAME = "epc-platform-507008-embeddings"

aiplatform.init(
    project=PROJECT_ID,
    location=LOCATION,
)

print("Creating index. This typically takes 5-10 minutes...")

index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
    display_name="epc-historical-incidents-index",
    contents_delta_uri=f"gs://{BUCKET_NAME}/embeddings/",
    dimensions=768,
    approximate_neighbors_count=10,
    distance_measure_type="COSINE_DISTANCE",
    index_update_method="BATCH_UPDATE",
)

print("Index created successfully.")
print(f"Index resource name: {index.resource_name}")
