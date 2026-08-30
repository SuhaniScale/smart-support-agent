# Run this file with chmod +x deploy_epc_admin_panel.sh 
# ./deploy_epc_admin_panel.sh


#!/usr/bin/env bash
set -e

export GCP_PROJECT_ID="epc-platform-507008"
export FIRESTORE_DATABASE_ID="epcfirestoredb"

gcloud run deploy epc-admin-panel \
  --source . \
  --region us-east1 \
  --service-account epc-platform-agent@epc-platform-507008.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID="$GCP_PROJECT_ID",FIRESTORE_DATABASE_ID="$FIRESTORE_DATABASE_ID"

if [ $? -ne 0 ]; then
  echo "Deployment failed."
  exit 1
fi

echo "Deployment command completed successfully."
