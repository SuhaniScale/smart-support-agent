import os
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import aiplatform

# ============================================================
# NOTE: Vector Search index deployment has no google-genai
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

if not PROJECT_ID:
    raise EnvironmentError("GCP_PROJECT_ID is not set. Add it to your .env file.")

# PASTE the full "Index resource name" you copied from Step 2.8
INDEX_RESOURCE_NAME = "projects/411440897339/locations/us-east1/indexes/1586828375345856512"

aiplatform.init(project=PROJECT_ID, location=LOCATION)

index = aiplatform.MatchingEngineIndex(index_name=INDEX_RESOURCE_NAME)

print("Creating index endpoint...")

index_endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
    display_name="epc-historical-incidents-endpoint",
    public_endpoint_enabled=True,
)

print(f"Endpoint created: {index_endpoint.resource_name}")
print("\nDeploying index to endpoint. This takes 20-40 minutes. Please wait...")

index_endpoint.deploy_index(
    index=index,
    deployed_index_id="epc_incidents_deployed",
)

print("\nDeployment complete!")
print(f"Index Endpoint resource name: {index_endpoint.resource_name}")
print("Deployed Index ID: epc_incidents_deployed")
print("\nIMPORTANT: copy both lines above. You will need them in the query script.")
