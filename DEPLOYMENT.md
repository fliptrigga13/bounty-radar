# Bounty Radar - Production HTTPS Deployment Guide (Google Cloud Run)

This guide documents the production deployment architecture for Bounty Radar on Google Cloud Run with Artifact Registry, Secret Manager, and durable persistent storage.

---

## 1. Architecture Overview

```
                          HTTPS Ingress
                                │
                                ▼
                   ┌─────────────────────────┐
                   │     Google Cloud Run    │
                   │   (A2A v0.3 / Poller)   │
                   └────────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│Google Secret │        │Cloud Storage │        │   Artifact   │
│   Manager    │        │  FUSE Volume │        │   Registry   │
│  (Webhooks/  │        │   (/data/    │        │  (Container  │
│ Bot Tokens)  │        │  radar.db)   │        │   Images)    │
└──────────────┘        └──────────────┘        └──────────────┘
```

---

## 2. Persistent Storage Strategy

Cloud Run container local filesystems are **ephemeral**: files written outside persistent mounts are discarded when instances restart or scale to zero.

### Option A: Cloud Storage FUSE Volume Mount (Recommended for SQLite)
Cloud Run supports second-generation volume mounts backed by Google Cloud Storage buckets.
- **Mount Path:** `/data`
- **Database Location:** `/data/radar.db`
- **Concurrency Setting:** Set `--min-instances=1` and `--max-instances=1` so a single instance owns SQLite locks cleanly without multi-writer contention.
- **Durability:** The SQLite database file, WAL files, and delivery states are persisted in the GCS bucket across container restarts, revisions, and scale events.

### Option B: Cloud SQL / Managed Relational Backend
For horizontal scaling across multiple active pollers or high-throughput A2A routing:
- Connect to Google Cloud SQL (PostgreSQL) using Cloud SQL Auth Proxy.
- Migrations run through standard database drivers.

### Option C: Single-Instance Demonstration Mode
- If running without Cloud Storage FUSE or Cloud SQL, deploy as a single instance (`--max-instances=1`).
- **Limitation:** Data in `/data/radar.db` is ephemeral and will reset upon instance recycling.

---

## 3. Prerequisites & GCP Services

Enable required APIs:
```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com
```

Create Artifact Registry repository:
```bash
gcloud artifacts repositories create bounty-radar \
  --repository-format=docker \
  --location=us-central1 \
  --description="Bounty Radar container repository"
```

Create persistent Cloud Storage bucket:
```bash
gcloud storage buckets create "gs://${PROJECT_ID}-bounty-radar-data" \
  --location=us-central1 \
  --uniform-bucket-level-access
```

---

## 4. Secret Manager Configuration

Store webhook credentials and tokens securely in Secret Manager:

```bash
# Discord incoming webhook URL
echo -n "https://discord.com/api/webhooks/..." | gcloud secrets create bounty-radar-discord-webhook \
  --data-file=- \
  --replication-policy="automatic"

# Telegram bot token (if using Telegram)
echo -n "123456789:ABC..." | gcloud secrets create bounty-radar-telegram-token \
  --data-file=- \
  --replication-policy="automatic"

# Telegram chat ID (if using Telegram)
echo -n "987654321" | gcloud secrets create bounty-radar-telegram-chat-id \
  --data-file=- \
  --replication-policy="automatic"
```

Grant Cloud Run runtime service account permission to access secrets:
```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding bounty-radar-discord-webhook \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 5. Deployment Options

### Method A: Automated Cloud Build (Recommended)
Submit the build and deployment pipeline using `cloudbuild.yaml`:

```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions="_REGION=us-central1,_REPO_NAME=bounty-radar,_SERVICE_NAME=bounty-radar,_GCS_DATA_BUCKET=${PROJECT_ID}-bounty-radar-data"
```

### Method B: Direct CLI Deployment Script

**Linux / macOS (Bash):**
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
./deploy-cloudrun.sh
```

**Windows (PowerShell):**
```powershell
$env:GCP_PROJECT_ID = "your-project-id"
.\deploy-cloudrun.ps1
```

---

## 6. Verification and Health Checks

After deployment, Cloud Run returns a public HTTPS URL (`https://bounty-radar-<hash>-uc.a.run.app`).

1. **Verify Health Endpoint:**
   ```bash
   curl -i https://<SERVICE_URL>/health
   # Expected: HTTP 200 OK, {"status":"ok"}
   ```

2. **Verify Agent Card:**
   ```bash
   curl -i https://<SERVICE_URL>/.well-known/agent-card.json
   # Expected: HTTP 200 OK, A2A v0.3 JSON with url matching the public HTTPS URL
   ```

3. **Verify A2A JSON-RPC Feed Subscription:**
   ```bash
   curl -X POST https://<SERVICE_URL>/a2a \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"show new opportunities from feed"}]}}}'
   ```
