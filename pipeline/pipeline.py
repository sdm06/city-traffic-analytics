import argparse
import json
import logging
import os
from datetime import datetime, timezone

import apache_beam as beam
from apache_beam.options.pipeline_options import (
    GoogleCloudOptions,
    PipelineOptions,
    SetupOptions,
    StandardOptions,
    WorkerOptions,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

REQUIRED_FIELDS = {"event_id", "timestamp", "intersection_id", "vehicle_type", "speed_kmh"}


def _speed_category(speed_kmh: float) -> str:
    if speed_kmh == 0:
        return "stationary"
    if speed_kmh < 50:
        return "slow"
    if speed_kmh < 90:
        return "normal"
    if speed_kmh < 120:
        return "fast"
    return "very_fast"


class ParseTrafficEvent(beam.DoFn):
    def process(self, element: bytes):
        try:
            event = json.loads(element.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logging.warning("Dropped unparseable message")
            return

        if not REQUIRED_FIELDS.issubset(event.keys()):
            logging.warning("Dropped event missing fields: %s", REQUIRED_FIELDS - event.keys())
            return

        yield event


class EnrichTrafficEvent(beam.DoFn):
    def process(self, event: dict):
        enriched = dict(event)
        enriched["speed_category"] = _speed_category(event["speed_kmh"])
        enriched["event_date"] = event["timestamp"][:10]
        enriched["ingested_at"] = datetime.now(timezone.utc).isoformat()
        yield enriched


def run(argv=None):
    parser = argparse.ArgumentParser(description="Smart City Traffic Analytics pipeline")
    parser.add_argument("--project", default=os.getenv("GCP_PROJECT_ID"))
    parser.add_argument(
        "--subscription",
        default=None,
        help="Full Pub/Sub subscription path. Defaults to env vars.",
    )
    parser.add_argument(
        "--bq_table",
        default=None,
        help="BigQuery target: <project>:<dataset>.<table>. Defaults to env vars.",
    )
    parser.add_argument(
        "--runner",
        default="DirectRunner",
        choices=["DirectRunner", "DataflowRunner"],
    )
    parser.add_argument("--region", default=os.getenv("GCP_REGION", "europe-west1"))
    parser.add_argument("--temp_location", default=None)
    parser.add_argument("--staging_location", default=None)

    known_args, pipeline_args = parser.parse_known_args(argv)

    project = known_args.project
    if not project:
        raise ValueError("--project is required (or set GCP_PROJECT_ID in .env)")

    sub_name = os.getenv("PUBSUB_SUBSCRIPTION", "traffic-events-sub")
    subscription = known_args.subscription or f"projects/{project}/subscriptions/{sub_name}"

    bq_dataset = os.getenv("BQ_DATASET", "traffic_analytics")
    bq_table = known_args.bq_table or f"{project}:{bq_dataset}.raw_events"

    bucket = os.getenv("GCS_BUCKET", f"{project}-dataflow")
    temp_location = known_args.temp_location or f"gs://{bucket}/temp"
    staging_location = known_args.staging_location or f"gs://{bucket}/staging"

    options = PipelineOptions(
        pipeline_args,
        runner=known_args.runner,
        project=project,
        region=known_args.region,
        temp_location=temp_location,
        staging_location=staging_location,
        job_name="smart-city-traffic-pipeline",
        service_account_email=f"dataflow-runner@{project}.iam.gserviceaccount.com",
        streaming=True,
    )
    options.view_as(StandardOptions).streaming = True

    if known_args.runner == "DataflowRunner":
        worker_opts = options.view_as(WorkerOptions)
        worker_opts.num_workers = 1
        worker_opts.max_num_workers = 5
        worker_opts.machine_type = "n1-standard-2"

        setup_opts = options.view_as(SetupOptions)
        setup_opts.requirements_file = "requirements.txt"
        setup_opts.save_main_session = True

    gcp_opts = options.view_as(GoogleCloudOptions)
    gcp_opts.labels = {"env": "dev", "team": "smart-city", "component": "dataflow"}

    logging.info(
        "Starting pipeline | runner=%s | subscription=%s | bq_table=%s",
        known_args.runner,
        subscription,
        bq_table,
    )

    with beam.Pipeline(options=options) as p:
        (
            p
            | "ReadFromPubSub" >> beam.io.ReadFromPubSub(subscription=subscription)
            | "Parse" >> beam.ParDo(ParseTrafficEvent())
            | "Enrich" >> beam.ParDo(EnrichTrafficEvent())
            | "WriteToBigQuery"
            >> beam.io.WriteToBigQuery(
                table=bq_table,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
            )
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
