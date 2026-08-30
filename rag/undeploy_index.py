import os
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import aiplatform

# ============================================================
# NOTE: Vector Search endpoint management has no google-genai
# equivalent — still uses google-cloud-aiplatform. Auth is now
# via ADC instead of a service-account-key.json file.
#
# One-time setup:
#     gcloud auth application-default login
# ============================================================

repo_root = Path(__file__).resolve().parent.parent
dotenv_path = repo_root / ".env"
load_dotenv(dotenv_path)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-east1"

# PASTE your Index Endpoint resource name from Step 2.9
INDEX_ENDPOINT_RESOURCE_NAME = "projects/411440897339/locations/us-east1/indexEndpoints/1220875721249914880"
DEPLOYED_INDEX_ID = "epc_incidents_deployed"

aiplatform.init(project=PROJECT_ID, location=LOCATION)

index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
    index_endpoint_name=INDEX_ENDPOINT_RESOURCE_NAME
)

print("Undeploying index... this takes a few minutes.")
index_endpoint.undeploy_index(deployed_index_id=DEPLOYED_INDEX_ID)
print("Undeployed successfully. Billing for the deployed endpoint has stopped.")
