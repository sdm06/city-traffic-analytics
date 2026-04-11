# infrastructure/

Scripts and documentation for provisioning all Google Cloud Platform resources.

---

## ⚠️ One-Time Setup (Cloud Architect Only)

Run `setup_gcp.sh` **once** to create all GCP resources from scratch.
Every other team member just runs the application code — they don't need this.

---

## What `setup_gcp.sh` Creates

| Resource | Name | Purpose |
|---|---|---|
| Cloud Storage | `YOUR_PROJECT-dataflow` | Dataflow staging + temp files |
| Pub/Sub Topic | `traffic-events` | Receives vehicle events from simulator |
| Pub/Sub Topic | `traffic-events-deadletter` | Stores unprocessable messages |
| Pub/Sub Subscription | `traffic-events-sub` | Read by the Dataflow pipeline |
| BigQuery Dataset | `traffic_analytics` | Data warehouse (all 3 layers) |
| BigQuery Table | `raw_events` | Bronze layer, partitioned by event_date |
| Service Account | `dataflow-runner@...` | IAM identity for the pipeline |

---

## How to Run

```bash
# 1. Edit PROJECT_ID in the script
nano infrastructure/setup_gcp.sh

# 2. Make it executable
chmod +x infrastructure/setup_gcp.sh

# 3. Run (from repo root)
./infrastructure/setup_gcp.sh
```

The script is **idempotent** — safe to re-run. Resources that already exist are skipped.

---

## IAM Roles Granted to `dataflow-runner` Service Account

| Role | Why |
|---|---|
| `roles/dataflow.worker` | Run Dataflow jobs |
| `roles/bigquery.dataEditor` | Write to BigQuery tables |
| `roles/pubsub.subscriber` | Read from Pub/Sub subscriptions |
| `roles/storage.objectAdmin` | Read/write Dataflow staging files |

---

## Owner

**Cloud Architect** owns this folder.
Any changes to GCP resources must go through a PR reviewed by the full team,
since they affect everyone's development environment.
