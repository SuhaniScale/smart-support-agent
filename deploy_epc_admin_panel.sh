# Run this file with chmod +x deploy_epc_admin_panel.sh 
# ./deploy_epc_admin_panel.sh


#!/usr/bin/env bash
set -e

# Load environment variables from .env
if [ -f .env ]; then
  export $(cat .env | grep -v '^#' | xargs)
fi

export GCP_PROJECT_ID="${GCP_PROJECT_ID:-epc-platform-506918}"
export FIRESTORE_DATABASE_ID="${FIRESTORE_DATABASE_ID:-epcfirestoredb}"

# Ensure you're using the correct GCP project
gcloud config set project "$GCP_PROJECT_ID"

echo "Deploying to GCP Project: $GCP_PROJECT_ID"

gcloud run deploy epc-admin-panel \
  --source . \
  --region us-east1 \
  --project "$GCP_PROJECT_ID" \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID="$GCP_PROJECT_ID",FIRESTORE_DATABASE_ID="$FIRESTORE_DATABASE_ID"

if [ $? -ne 0 ]; then
  echo "Deployment failed."
  exit 1
fi

echo "Deployment command completed successfully."
