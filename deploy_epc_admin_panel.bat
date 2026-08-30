@echo off
setlocal

set "GCP_PROJECT_ID=epc-platform-507008"
set "FIRESTORE_DATABASE_ID=epcfirestoredb"

gcloud run deploy epc-admin-panel ^
  --source . ^
  --region us-east1 ^
  --service-account epc-platform-agent@epc-platform-507008.iam.gserviceaccount.com ^
  --allow-unauthenticated ^
  --set-env-vars GCP_PROJECT_ID=%GCP_PROJECT_ID%,FIRESTORE_DATABASE_ID=%FIRESTORE_DATABASE_ID%

if errorlevel 1 (
    echo Deployment failed.
    exit /b 1
)

echo Deployment command completed successfully.
exit /b 0
