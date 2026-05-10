# Deployment Guide — Smart City Traffic Analytics

How to deploy the Dataflow streaming pipeline to Google Cloud Platform.

---

## Prerequisites

- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- Project Owner or Editor role on the GCP project
- Python 3.10+ and `pip` installed

---

## Step 1 — Provision GCP Resources

Run the infrastructure setup script **once**. It creates the Cloud Storage bucket, Pub/Sub topics, BigQuery dataset and table, and the service account.

```bash
# Edit PROJECT_ID at the top of the script first
nano infrastructure/setup_gcp.sh

chmod +x infrastructure/setup_gcp.sh
./infrastructure/setup_gcp.sh
```

The script is idempotent — safe to re-run. See `infrastructure/README.md` for the full list of resources created.

---

## Step 2 — Download the Service Account Key

1. Open **GCP Console → IAM & Admin → Service Accounts**
2. Find `dataflow-runner@<project-id>.iam.gserviceaccount.com`
3. Click **Keys → Add Key → Create new key → JSON**
4. Save the downloaded file **outside the repository** (e.g. `~/.gcp/dataflow-runner-key.json`)

> Never commit this file. It grants full pipeline access to your GCP project.

---

## Step 3 — Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your real values:

```
GCP_PROJECT_ID=your-project-id
GCP_REGION=europe-west1
GCS_BUCKET=your-project-id-dataflow
PUBSUB_SUBSCRIPTION=traffic-events-sub
BQ_DATASET=traffic_analytics
GOOGLE_APPLICATION_CREDENTIALS=/home/you/.gcp/dataflow-runner-key.json
```

---

## Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 5 — Deploy the Pipeline

```bash
python pipeline/pipeline.py --runner DataflowRunner --project your-project-id
```

Beam packages the code, uploads it to `gs://<bucket>/staging/`, and submits the job to the Dataflow API. The job appears in **GCP Console → Dataflow → Jobs** within ~2 minutes.

The pipeline runs continuously (streaming) — it will keep pulling from Pub/Sub until you cancel it.

---

## Monitoring

**GCP Console** — go to Dataflow → Jobs → click the job to see the pipeline graph, element counts, and worker logs in real time.

**gcloud CLI:**

```bash
# List running jobs
gcloud dataflow jobs list --region europe-west1

# Show job details and status
gcloud dataflow jobs show <job-id> --region europe-west1
```

**BigQuery** — once the data generator is publishing events, rows appear in `traffic_analytics.raw_events`:

```sql
SELECT * FROM `<project-id>.traffic_analytics.raw_events`
ORDER BY ingested_at DESC
LIMIT 20;
```

---

## Stopping the Pipeline

```bash
gcloud dataflow jobs cancel <job-id> --region europe-west1
```

Or click **Stop → Cancel** in the GCP Console.

---

## Running Locally (no GCP needed)

Use `DirectRunner` to run the pipeline on your machine against a local Pub/Sub emulator:

```bash
python pipeline/pipeline.py --runner DirectRunner --project your-project-id
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `PERMISSION_DENIED` on launch | `GOOGLE_APPLICATION_CREDENTIALS` not set or wrong path | Check `.env` and re-run |
| Job fails immediately | Worker can't install dependencies | Confirm `requirements.txt` is present and `GCS_BUCKET` is accessible |
| No rows in BigQuery | Data generator not running | Start `data_generator/generator.py` to publish events |
| Workers not scaling | Pub/Sub backlog too small | Increase publish rate in the generator |
