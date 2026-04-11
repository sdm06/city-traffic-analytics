"""
test_transforms.py — Unit tests for Apache Beam pipeline transforms.

Run with:
    pytest pipeline/tests/ -v

These tests use Apache Beam's TestPipeline — no GCP connection needed.
"""

import json
import unittest
from datetime import datetime, timezone

import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

# Add project root to path so we can import from pipeline/
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import EnrichTrafficEvent, ParseTrafficEvent


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_event(**overrides) -> dict:
    """Return a valid traffic event dict with optional field overrides."""
    base = {
        "event_id": "test-event-001",
        "timestamp": "2024-03-15T10:00:00+00:00",
        "intersection_id": "INT-001-TestStreet",
        "vehicle_type": "car",
        "speed_kmh": 60.0,
        "direction": "north",
        "lane": 1,
        "license_plate": "TEST-001",
        "is_emergency": False,
    }
    base.update(overrides)
    return base


def encode(event: dict) -> bytes:
    """Serialize a dict to JSON bytes (mimics Pub/Sub message format)."""
    return json.dumps(event).encode("utf-8")


# ── ParseTrafficEvent Tests ───────────────────────────────────────────────────

class TestParseTrafficEvent(unittest.TestCase):
    def test_valid_event_is_parsed(self):
        """A well-formed JSON message should be parsed into a dict."""
        raw = [encode(make_event())]

        with TestPipeline() as p:
            result = p | beam.Create(raw) | beam.ParDo(ParseTrafficEvent())
            assert_that(result, equal_to([make_event()]))

    def test_missing_required_field_is_dropped(self):
        """Events missing required fields should be silently dropped."""
        bad_event = make_event()
        del bad_event["speed_kmh"]  # Remove required field

        with TestPipeline() as p:
            result = p | beam.Create([encode(bad_event)]) | beam.ParDo(ParseTrafficEvent())
            assert_that(result, equal_to([]))  # Expect nothing output

    def test_invalid_json_is_dropped(self):
        """Malformed JSON bytes should be dropped without crashing."""
        bad_bytes = [b"this is not json {{{"]

        with TestPipeline() as p:
            result = p | beam.Create(bad_bytes) | beam.ParDo(ParseTrafficEvent())
            assert_that(result, equal_to([]))

    def test_multiple_valid_events(self):
        """Multiple valid events should all be parsed."""
        events = [
            make_event(event_id="e1", vehicle_type="car"),
            make_event(event_id="e2", vehicle_type="bus"),
            make_event(event_id="e3", vehicle_type="truck"),
        ]
        raw = [encode(e) for e in events]

        with TestPipeline() as p:
            result = p | beam.Create(raw) | beam.ParDo(ParseTrafficEvent())
            assert_that(result, equal_to(events))

    def test_all_required_fields_validated(self):
        """Each required field, when missing, should cause the event to be dropped."""
        required_fields = ["event_id", "timestamp", "intersection_id", "vehicle_type", "speed_kmh"]
        for field in required_fields:
            bad = make_event()
            del bad[field]
            with TestPipeline() as p:
                result = p | beam.Create([encode(bad)]) | beam.ParDo(ParseTrafficEvent())
                assert_that(result, equal_to([]), label=f"missing_{field}_should_drop")


# ── EnrichTrafficEvent Tests ──────────────────────────────────────────────────

class TestEnrichTrafficEvent(unittest.TestCase):
    def _enrich(self, event: dict) -> dict:
        """Helper: run EnrichTrafficEvent on a single event, return first result."""
        results = []
        for output in EnrichTrafficEvent().process(event):
            results.append(output)
        self.assertEqual(len(results), 1, "Expected exactly one output event")
        return results[0]

    # Speed category tests
    def test_speed_category_stationary(self):
        result = self._enrich(make_event(speed_kmh=0.0))
        self.assertEqual(result["speed_category"], "stationary")

    def test_speed_category_slow(self):
        result = self._enrich(make_event(speed_kmh=35.0))
        self.assertEqual(result["speed_category"], "slow")

    def test_speed_category_normal(self):
        result = self._enrich(make_event(speed_kmh=65.0))
        self.assertEqual(result["speed_category"], "normal")

    def test_speed_category_fast(self):
        result = self._enrich(make_event(speed_kmh=100.0))
        self.assertEqual(result["speed_category"], "fast")

    def test_speed_category_very_fast(self):
        result = self._enrich(make_event(speed_kmh=140.0))
        self.assertEqual(result["speed_category"], "very_fast")

    def test_speed_category_boundary_exactly_50(self):
        """50.0 km/h is the boundary between slow and normal → should be normal."""
        result = self._enrich(make_event(speed_kmh=50.0))
        self.assertEqual(result["speed_category"], "normal")

    def test_speed_category_boundary_exactly_90(self):
        """90.0 km/h is the boundary between normal and fast → should be fast."""
        result = self._enrich(make_event(speed_kmh=90.0))
        self.assertEqual(result["speed_category"], "fast")

    # Derived field tests
    def test_ingested_at_is_added(self):
        result = self._enrich(make_event())
        self.assertIn("ingested_at", result)
        self.assertIsNotNone(result["ingested_at"])

    def test_event_date_is_extracted(self):
        result = self._enrich(make_event(timestamp="2024-03-15T10:00:00+00:00"))
        self.assertEqual(result["event_date"], "2024-03-15")

    def test_event_date_different_day(self):
        result = self._enrich(make_event(timestamp="2024-12-31T23:59:59+00:00"))
        self.assertEqual(result["event_date"], "2024-12-31")

    def test_original_fields_preserved(self):
        """Enrichment should add fields, not modify existing ones."""
        original = make_event(speed_kmh=75.0, vehicle_type="truck")
        result = self._enrich(original)
        self.assertEqual(result["speed_kmh"], 75.0)
        self.assertEqual(result["vehicle_type"], "truck")
        self.assertEqual(result["event_id"], original["event_id"])

    # Pipeline integration test
    def test_parse_then_enrich_pipeline(self):
        """Full mini-pipeline: bytes → parse → enrich → check output fields."""
        event = make_event(speed_kmh=75.0)
        raw = [encode(event)]

        results = []

        def collect(element):
            results.append(element)

        with TestPipeline() as p:
            (
                p
                | beam.Create(raw)
                | beam.ParDo(ParseTrafficEvent())
                | beam.ParDo(EnrichTrafficEvent())
                | beam.Map(collect)
            )

        self.assertEqual(len(results), 1)
        enriched = results[0]
        self.assertIn("speed_category", enriched)
        self.assertIn("ingested_at", enriched)
        self.assertIn("event_date", enriched)
        self.assertEqual(enriched["speed_category"], "normal")


if __name__ == "__main__":
    unittest.main()
