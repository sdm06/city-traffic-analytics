#!/usr/bin/env bash
# ============================================================
# setup_gcp.sh — One-Time GCP Resource Provisioning
# Smart City Traffic Analytics
#
# Run ONCE by the Cloud Architect to create all GCP resources.
# Safe to re-run — most commands use --quiet and skip if exists.
#
# Usage:
#   chmod +x infrastructure/setup_gcp.sh
#   ./infrastructure/setup_gcp.sh
#
# Requirements:
#   - gcloud CLI installed and authenticated
#   - Your account has Project Owner or Editor role
# ============================================================

set -euo pipefail # Exit on error, treat unset vars as errors

# ── Configuration — Edit these before running ─────────────────────────────────
PROJECT_ID="YOUR_GCP_PROJECT_ID" # Your GCP project ID
REGION="europe-west1" # GCP region
ZONE="europe-west1-b" # GCP zone
BQ_DATASET="traffic_analytics" # BigQuery dataset name
BQ_LOCATION="EU" # BigQuery data location
GCS_BUCKET="${PROJECT_ID}-dataflow" # Cloud Storage bucket name
PUBSUB_TOPIC="traffic-events" # Pub/Sub topic name
PUBSUB_SUB="traffic-events-sub" # Pub/Sub subscription name
SA_NAME="dataflow-runner" # Service account name

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Colour

log() { echo -e "${GREEN}[✔]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✘]${NC} $1"; exit 1; }

# ── Validate project ───────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Smart City Traffic Analytics — GCP Setup"
echo "  Project: ${PROJECT_ID}"
echo "  Region:  ${REGION}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

[[ "$PROJECT_ID" == "YOUR_GCP_PROJECT_ID" ]] && \
  err "Edit PROJECT_ID in this script before running!"

gcloud config set project "$PROJECT_ID"

# ── Step 1: Enable APIs ────────────────────────────────────────────────────────
echo "▶ Enabling GCP APIs..."

gcloud services enable \
  pubsub.googleapis.com \
  dataflow.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  --project="$PROJECT_ID" \
  --quiet

log "APIs enabled"

# ── Step 2: Cloud Storage Bucket ───────────────────────────────────────────────
echo "▶ Creating Cloud Storage bucket: gs://${GCS_BUCKET}"

if gsutil ls "gs://${GCS_BUCKET}" &>/dev/null; then
  warn "Bucket gs://${GCS_BUCKET} already exists — skipping"
else
  gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${GCS_BUCKET}"
  gsutil lifecycle set infrastructure/bucket_lifecycle.json "gs://${GCS_BUCKET}" 2>/dev/null || true
  log "Bucket created: gs://${GCS_BUCKET}"
fi

# Create temp and staging folders (empty objects act as folder markers)
gsutil -q cp /dev/null "gs://${GCS_BUCKET}/temp/.keep"
gsutil -q cp /dev/null "gs://${GCS_BUCKET}/staging/.keep"
log "Staging and temp folders created"

# ── Step 3: Pub/Sub Topic & Subscription ──────────────────────────────────────
echo "▶ Creating Pub/Sub resources..."

# Main topic
if gcloud pubsub topics describe "$PUBSUB_TOPIC" --project="$PROJECT_ID" &>/dev/null; then
  warn "Topic '${PUBSUB_TOPIC}' already exists — skipping"
else
  gcloud pubsub topics create "$PUBSUB_TOPIC" \
    --project="$PROJECT_ID" \
    --message-retention-duration=7d \
    --labels=env=dev,team=smart-city
  log "Pub/Sub topic created: ${PUBSUB_TOPIC}"
fi

# Dead-letter topic
DL_TOPIC="${PUBSUB_TOPIC}-deadletter"
if gcloud pubsub topics describe "$DL_TOPIC" --project="$PROJECT_ID" &>/dev/null; then
  warn "Topic '${DL_TOPIC}' already exists — skipping"
else
  gcloud pubsub topics create "$DL_TOPIC" \
    --project="$PROJECT_ID" \
    --message-retention-duration=14d
  log "Dead-letter topic created: ${DL_TOPIC}"
fi

# Main subscription
if gcloud pubsub subscriptions describe "$PUBSUB_SUB" --project="$PROJECT_ID" &>/dev/null; then
  warn "Subscription '${PUBSUB_SUB}' already exists — skipping"
else
  gcloud pubsub subscriptions create "$PUBSUB_SUB" \
    --topic="$PUBSUB_TOPIC" \
    --project="$PROJECT_ID" \
    --ack-deadline=60 \
    --message-retention-duration=7d \
    --labels=env=dev,team=smart-city
  log "Pub/Sub subscription created: ${PUBSUB_SUB}"
fi

# ── Step 4: BigQuery Dataset ───────────────────────────────────────────────────
echo "▶ Creating BigQuery dataset: ${BQ_DATASET}"

if bq ls --project_id="$PROJECT_ID" "$BQ_DATASET" &>/dev/null; then
  warn "Dataset '${BQ_DATASET}' already exists — skipping"
else
  bq mk \
    --dataset \
    --location="$BQ_LOCATION" \
    --description="Smart City Traffic Analytics data warehouse" \
    --label=env:dev \
    --label=team:smart-city \
    "${PROJECT_ID}:${BQ_DATASET}"
  log "BigQuery dataset created: ${BQ_DATASET}"
fi

# Create the Bronze table from schema file
echo "▶ Creating BigQuery Bronze table..."
bq mk \
  --table \
  --project_id="$PROJECT_ID" \
  --description="Bronze layer: raw traffic events from Dataflow" \
  --time_partitioning_field=event_date \
  --time_partitioning_type=DAY \
  "${BQ_DATASET}.raw_events" \
  config/bigquery_schemas/raw_events.json 2>/dev/null && \
  log "BigQuery table created: ${BQ_DATASET}.raw_events" || \
  warn "Table raw_events already exists — skipping"

# ── Step 5: Service Account ────────────────────────────────────────────────────
echo "▶ Creating service account: ${SA_NAME}"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
  warn "Service account ${SA_EMAIL} already exists — skipping"
else
  gcloud iam service-accounts create "$SA_NAME" \
    --project="$PROJECT_ID" \
    --display-name="Dataflow Pipeline Runner" \
    --description="Service account for the Smart City Traffic Dataflow job"
  log "Service account created: ${SA_EMAIL}"
fi

# Grant required roles
declare -a ROLES=(
  "roles/dataflow.worker"
  "roles/bigquery.dataEditor"
  "roles/pubsub.subscriber"
  "roles/storage.objectAdmin"
)

echo "▶ Assigning IAM roles to ${SA_EMAIL}..."
for ROLE in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" \
    --quiet
  log "  Granted: ${ROLE}"
done

# ── Step 6: Summary ────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}  ✅  Setup complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Resources created:"
echo "  • Storage   : gs://${GCS_BUCKET}"
echo "  • Pub/Sub   : ${PUBSUB_TOPIC} + ${PUBSUB_SUB}"
echo "  • BigQuery  : ${PROJECT_ID}:${BQ_DATASET}.raw_events"
echo "  • SA        : ${SA_EMAIL}"
echo ""
echo "  Next steps:"
echo "  1. Copy .env.example → .env and fill in values"
echo "  2. Run: python data_generator/generator.py --project ${PROJECT_ID} --dry-run"
echo "  3. Run: python pipeline/pipeline.py --runner DirectRunner --project ${PROJECT_ID}"
echo ""
