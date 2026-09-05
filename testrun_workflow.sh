#!/bin/bash
# chmod +x testrun_workflow.sh
# ./testrun_workflow.sh

set -e

DATA='{
  "ticket_id": "T021",
  "raw_text": "My Android app crashes every time I try to upload a picture",
  "source": "manual_test",
  "timestamp": "2026-01-10T09:00:00Z"
}'

gcloud workflows execute epc-pipeline-workflow \
  --location=us-east1 \
  --data="$DATA"
