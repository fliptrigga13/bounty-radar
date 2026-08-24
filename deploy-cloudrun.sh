#!/usr/bin/env bash
# Deploy Bounty Radar to Google Cloud Run with Artifact Registry and Secret Manager.
# Do not run without explicit manual authorization.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${GCP_REGION:-us-central1}"
REPO_NAME="${GCP_REPO_NAME:-bounty-radar}"
SERVICE_NAME="${GCP_SERVICE_NAME:-bounty-radar}"
GCS_DATA_BUCKET="${GCP_GCS_BUCKET:-${PROJECT_ID}-bounty-radar-data}"
IMAGE_TAG="${1:-latest}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/bounty-radar:${IMAGE_TAG}"

if [ -z "$PROJECT_ID" ]; then
  echo "Error: GCP_PROJECT_ID is not set. Export GCP_PROJECT_ID or run: gcloud config set project <PROJECT_ID>" >&2
  exit 1
fi

echo "=== Bounty Radar Cloud Run Deployment ==="
echo "Project ID:       $PROJECT_ID"
echo "Region:           $REGION"
echo "Artifact Image:   $IMAGE_URI"
echo "Service Name:     $SERVICE_NAME"
echo "Persistence GCS:  $GCS_DATA_BUCKET"
echo "========================================="

# 1. Ensure GCP APIs are enabled
echo "1. Enabling required Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  --project="$PROJECT_ID"

# 2. Ensure Artifact Registry repository exists
echo "2. Checking Artifact Registry repository..."
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating Artifact Registry repository '$REPO_NAME'..."
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Bounty Radar container images" \
    --project="$PROJECT_ID"
fi

# 3. Ensure GCS bucket exists for persistent SQLite database
echo "3. Checking persistent GCS data bucket..."
if ! gcloud storage buckets describe "gs://${GCS_DATA_BUCKET}" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating Cloud Storage bucket 'gs://${GCS_DATA_BUCKET}'..."
  gcloud storage buckets create "gs://${GCS_DATA_BUCKET}" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --uniform-bucket-level-access
fi

# 4. Build and push image using Cloud Build
echo "4. Submitting build to Google Cloud Build..."
gcloud builds submit \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions="_REGION=${REGION},_REPO_NAME=${REPO_NAME},_SERVICE_NAME=${SERVICE_NAME},_GCS_DATA_BUCKET=${GCS_DATA_BUCKET}"

# 5. Retrieve public HTTPS URL
echo "5. Deployment completed. Fetching service URL..."
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')"

echo "=== Bounty Radar is live! ==="
echo "Health check:   ${SERVICE_URL}/health"
echo "Agent Card:     ${SERVICE_URL}/.well-known/agent-card.json"
echo "A2A Endpoint:   ${SERVICE_URL}/a2a"
