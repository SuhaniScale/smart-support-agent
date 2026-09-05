# Run this file with 
# chmod +x deploy_epc_workflow.sh 
# ./deploy_epc_workflow.sh


#!/usr/bin/env bash
set -e

export GCP_PROJECT_ID="epc-platform-506918"
export FIRESTORE_DATABASE_ID="epcfirestoredb"

gcloud workflows deploy epc-pipeline-workflow \
  --source deployment/epc_pipeline_workflow.yaml \
  --location=us-east1 \
  --service-account epc-platform-agent@epc-platform-506918.iam.gserviceaccount.com \

if [ $? -ne 0 ]; then
  echo "Deployment failed."
  exit 1
fi

echo "Deployment command completed successfully."
