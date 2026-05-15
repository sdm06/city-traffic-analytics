#!/usr/bin/env bash
# ============================================================
# apply_transformations.sh — Apply Silver and Gold SQL Layers
# Smart City Traffic Analytics
#
# Run this script to create or update the Silver and Gold
# tables in BigQuery after the Bronze layer is populated.
#
# Usage:
#   chmod +x infrastructure/apply_transformations.sh
#   ./infrastructure/apply_transformations.sh
# ============================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID=$(gcloud config get-value project)
BQ_DATASET="traffic_analytics"

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[✔]${NC} $1"; }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Applying SQL Transformations"
echo "  Project: ${PROJECT_ID}"
echo "  Dataset: ${BQ_DATASET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Step 1: Apply Silver Layer ────────────────────────────────────────────────
echo "▶ Applying Silver Layer (sql/silver.sql)..."
bq query --use_legacy_sql=false < sql/silver.sql
log "Silver layer applied successfully."

# ── Step 2: Apply Gold Layer ──────────────────────────────────────────────────
echo "▶ Applying Gold Layer (sql/gold.sql)..."
bq query --use_legacy_sql=false < sql/gold.sql
log "Gold layer applied successfully."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}  ✅  Transformations applied!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
