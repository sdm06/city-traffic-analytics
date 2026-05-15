# Architecture — Smart City Traffic Analytics

## System Overview

A real-time streaming pipeline on GCP that ingests simulated vehicle sensor events, processes them with Apache Beam on Dataflow, and stores the results in a three-layer BigQuery data warehouse for analysis and dashboarding.

## Data Flow

```
[data_generator/]
  generator.py
      │  JSON events over HTTP
      ▼
[Pub/Sub]
  traffic-events          ← main topic (7-day retention)
  traffic-events-deadletter ← malformed messages (14-day retention)
      │
      │  traffic-events-sub (ack deadline: 60s)
      ▼
[Dataflow — Apache Beam]
  ParseTrafficEvent       ← deserialise + validate required fields
  EnrichTrafficEvent      ← add speed_category, ingested_at, event_date
      │
      ├──▶ [Cloud Storage]  gs://<project>-dataflow/
      │      staging/        Dataflow worker JARs
      │      temp/           Shuffle storage
      │
      └──▶ [BigQuery]  traffic_analytics dataset
                Bronze → raw_events (partitioned by event_date)
                Silver → cleaned_events  (Phase 3)
                Gold   → hourly_summary, congestion_index  (Phase 3)
                             │
                             ▼
                       [Looker Studio]  (Phase 4)
```

## Medallion Layers

All three layers live in the `traffic_analytics` BigQuery dataset.

| Layer | Table(s) | Populated by | Status |
|---|---|---|---|
| Bronze | `raw_events` | Dataflow writer | Schema done; pipeline pending |
| Silver | `cleaned_events`, `intersection_metrics` | `sql/silver.sql` | Implemented (Phase 3) |
| Gold | `hourly_traffic_summary`, `congestion_index`, `vehicle_type_breakdown` | `sql/gold.sql` | Implemented (Phase 3) |

`raw_events` is partitioned by `event_date` (DATE) for query cost control.

## GCP Resources

| Resource | Name | Provisioned by |
|---|---|---|
| Cloud Storage bucket | `<project>-dataflow` | `infrastructure/setup_gcp.sh` |
| Pub/Sub topic | `traffic-events` | `infrastructure/setup_gcp.sh` |
| Pub/Sub topic | `traffic-events-deadletter` | `infrastructure/setup_gcp.sh` |
| Pub/Sub subscription | `traffic-events-sub` | `infrastructure/setup_gcp.sh` |
| BigQuery dataset | `traffic_analytics` | `infrastructure/setup_gcp.sh` |
| BigQuery table | `raw_events` | `infrastructure/setup_gcp.sh` |
| Service account | `dataflow-runner@<project>.iam.gserviceaccount.com` | `infrastructure/setup_gcp.sh` |

All resources are in `europe-west1`. The setup script is idempotent.

## Service Account IAM Roles

`dataflow-runner` is the only non-human identity the pipeline uses:

| Role | Why |
|---|---|
| `roles/dataflow.worker` | Execute Dataflow jobs |
| `roles/bigquery.dataEditor` | Write enriched events to BigQuery |
| `roles/pubsub.subscriber` | Read from `traffic-events-sub` |
| `roles/storage.objectAdmin` | Read/write Dataflow staging and temp files |

## Pipeline Transform Contract

The two Beam transforms in `pipeline/pipeline.py` must satisfy the contracts defined in `pipeline/tests/test_transforms.py`:

**`ParseTrafficEvent`** — `bytes → dict | (dropped)`
- Input: raw Pub/Sub message bytes (JSON-encoded)
- Required fields: `event_id`, `timestamp`, `intersection_id`, `vehicle_type`, `speed_kmh`
- Invalid JSON or any missing required field → silently drop the message (no exception)

**`EnrichTrafficEvent`** — `dict → dict`
- Adds `speed_category` based on `speed_kmh`:
  - `stationary`: 0
  - `slow`: > 0 and < 50
  - `normal`: ≥ 50 and < 90
  - `fast`: ≥ 90 and < 120
  - `very_fast`: ≥ 120
- Adds `event_date`: date portion of `timestamp` (e.g. `"2024-03-15"`)
- Adds `ingested_at`: current UTC timestamp (processing time)
- Must not modify any original fields

## Runner Modes

| Mode | Runner | When to use |
|---|---|---|
| Local dev | `DirectRunner` | Unit tests, local smoke tests — no GCP needed |
| Cloud | `DataflowRunner` | Integration testing and production — requires `.env` configured |

Config in `config/dataflow_config.yaml`. Workers start at 1, scale to 5 (`THROUGHPUT_BASED`), `n1-standard-2`.
