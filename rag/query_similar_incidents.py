import os
import json
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.cloud import aiplatform

# ============================================================
# NOTE: Vector Search querying (find_neighbors) has no google-genai
# equivalent — still uses google-cloud-aiplatform for the index
# endpoint. Only the embedding call below was moved to google-genai.
# Auth is now via ADC instead of a service-account-key.json file.
#
# One-time setup:
#     gcloud auth application-default login
# ============================================================

repo_root = Path(__file__).resolve().parent.parent
load_dotenv(repo_root / ".env")

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-east1"

EMBEDDING_MODEL_NAME = "text-embedding-004"  # kept same as generate_embeddings.py
# so query vectors match the 768-dim vectors already stored in the index.

# PASTE your values from Step 2.9
INDEX_ENDPOINT_RESOURCE_NAME = "projects/411440897339/locations/us-east1/indexEndpoints/1220875721249914880"
DEPLOYED_INDEX_ID = "epc_incidents_deployed"

INCIDENTS_FILE = "../data/historical_incidents.json"

if not PROJECT_ID:
    raise EnvironmentError("GCP_PROJECT_ID is not set. Fix your .env file.")

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

aiplatform.init(project=PROJECT_ID, location=LOCATION)

index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
    index_endpoint_name=INDEX_ENDPOINT_RESOURCE_NAME
)

# Prefer a gRPC match client for find_neighbors (avoids REST $alt issue)
try:
    from google.api_core.client_options import ClientOptions
    from google.cloud.aiplatform_v1beta1.services.match_service import MatchServiceClient

    public_client = getattr(index_endpoint, "_public_match_client", None)
    if public_client is not None and getattr(public_client, "_transport", None):
        host = public_client._transport._host
        grpc_client = MatchServiceClient(transport="grpc", client_options=ClientOptions(api_endpoint=host))
        index_endpoint._public_match_client = grpc_client
except Exception:
    # non-fatal: fall back to whatever the SDK provided
    pass

with open(INCIDENTS_FILE, "r") as f:
    incidents_lookup = {i["incident_id"]: i for i in json.load(f)}


def find_similar_incidents(ticket_text: str, top_k: int = 5):
    embed_response = client.models.embed_content(
        model=EMBEDDING_MODEL_NAME,
        contents=ticket_text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    query_embedding = embed_response.embeddings[0].values

    response = index_endpoint.find_neighbors(
        deployed_index_id=DEPLOYED_INDEX_ID,
        queries=[query_embedding],
        num_neighbors=top_k,
    )

    neighbors = response[0]
    results = []
    for neighbor in neighbors:
        incident = incidents_lookup.get(neighbor.id, {})
        results.append({
            "incident_id": neighbor.id,
            "similarity_score": round(neighbor.distance, 4),
            "summary": incident.get("summary", "Unknown"),
            "outcome": incident.get("outcome", "Unknown"),
        })
    return results


if __name__ == "__main__":
    test_ticket = "App keeps crashing when I try to upload photos on Android"
    print(f"Query ticket: {test_ticket}\n")

    matches = find_similar_incidents(test_ticket)
    for m in matches:
        print(f"[{m['incident_id']}] score={m['similarity_score']} - {m['summary']}")
        print(f"    Outcome: {m['outcome']}\n")
