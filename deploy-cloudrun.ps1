# Deploy Bounty Radar to Google Cloud Run (Windows PowerShell)
# Do not run without explicit manual authorization.
param (
    [string]$ProjectId = $env:GCP_PROJECT_ID,
    [string]$Region = "us-central1",
    [string]$RepoName = "bounty-radar",
    [string]$ServiceName = "bounty-radar",
    [string]$GcsBucket = "",
    [string]$ImageTag = "latest"
)

if (-not $ProjectId) {
    $ProjectId = gcloud config get-value project 2>$null
}

if (-not $ProjectId) {
    Write-Error "GCP Project ID is required. Set `$env:GCP_PROJECT_ID or pass -ProjectId <id>"
    exit 1
}

if (-not $GcsBucket) {
    $GcsBucket = "${ProjectId}-bounty-radar-data"
}

Write-Host "=== Bounty Radar Cloud Run Deployment ===" -ForegroundColor Cyan
Write-Host "Project ID:       $ProjectId"
Write-Host "Region:           $Region"
Write-Host "Service Name:     $ServiceName"
Write-Host "Persistence GCS:  $GcsBucket"
Write-Host "========================================="

# 1. Enable required APIs
Write-Host "1. Enabling required Google Cloud APIs..." -ForegroundColor Yellow
gcloud services enable `
    run.googleapis.com `
    artifactregistry.googleapis.com `
    secretmanager.googleapis.com `
    cloudbuild.googleapis.com `
    --project=$ProjectId

# 2. Check / create Artifact Registry repository
Write-Host "2. Checking Artifact Registry repository..." -ForegroundColor Yellow
$repoExists = gcloud artifacts repositories describe $RepoName --location=$Region --project=$ProjectId 2>$null
if (-not $repoExists) {
    Write-Host "Creating Artifact Registry repository '$RepoName'..."
    gcloud artifacts repositories create $RepoName `
        --repository-format=docker `
        --location=$Region `
        --description="Bounty Radar container images" `
        --project=$ProjectId
}

# 3. Check / create GCS Bucket
Write-Host "3. Checking persistent GCS data bucket..." -ForegroundColor Yellow
$bucketExists = gcloud storage buckets describe "gs://${GcsBucket}" --project=$ProjectId 2>$null
if (-not $bucketExists) {
    Write-Host "Creating Cloud Storage bucket 'gs://${GcsBucket}'..."
    gcloud storage buckets create "gs://${GcsBucket}" `
        --location=$Region `
        --project=$ProjectId `
        --uniform-bucket-level-access
}

# 4. Build and deploy via Cloud Build
Write-Host "4. Submitting build to Google Cloud Build..." -ForegroundColor Yellow
gcloud builds submit `
    --project=$ProjectId `
    --config=cloudbuild.yaml `
    --substitutions="_REGION=${Region},_REPO_NAME=${RepoName},_SERVICE_NAME=${ServiceName},_GCS_DATA_BUCKET=${GcsBucket}"

# 5. Fetch live URL
Write-Host "5. Fetching service URL..." -ForegroundColor Yellow
$serviceUrl = gcloud run services describe $ServiceName --region=$Region --project=$ProjectId --format='value(status.url)'

Write-Host "`n=== Bounty Radar is live! ===" -ForegroundColor Green
Write-Host "Health check:   ${serviceUrl}/health"
Write-Host "Agent Card:     ${serviceUrl}/.well-known/agent-card.json"
Write-Host "A2A Endpoint:   ${serviceUrl}/a2a"
