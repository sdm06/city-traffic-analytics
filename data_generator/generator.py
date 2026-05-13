"""
generator.py — Smart City Traffic Event Simulator
  - Night-time low traffic (23:00–05:00)
  - Weekday vs weekend differences
  - Weather impact on speed
  - Random incidents (accidents, road works)
  - Emergency vehicle bursts

Modes:
  --dry-run          Print events to console, no GCP needed
  --replay           Read a real CSV dataset and publish it
  --simulate         Generate synthetic events (default)
  --continuous       Run until Ctrl+C

Usage Examples:
  # Quick test, no GCP:
  python generator.py --dry-run --events 20

  # Simulate 1 hour of peak morning traffic:
  python generator.py --dry-run --simulate --time-of-day rush_morning --events 200

  # Replay a real Kaggle CSV:
  python generator.py --replay --csv data/traffic.csv --project YOUR_PROJECT

  # Full simulation publishing to Pub/Sub:
  python generator.py --simulate --project YOUR_PROJECT --topic traffic-events --continuous
"""

import argparse
import csv
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

try:
    from google.cloud import pubsub_v1
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False

try:
    from faker import Faker
    fake = Faker()
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False
    logger.warning("Faker not installed. Using placeholder license plates.")


@dataclass
class Intersection:
    id: str
    name: str
    type: str          # downtown | highway | residential | industrial
    lanes: int
    speed_limit: int   # km/h


CITY_MAP = [
    Intersection("INT-001", "Central Square",         "downtown",    4, 50),
    Intersection("INT-002", "North Highway Ramp",     "highway",     6, 100),
    Intersection("INT-003", "Tech Park Entrance",     "industrial",  3, 70),
    Intersection("INT-004", "University Boulevard",   "residential", 2, 50),
    Intersection("INT-005", "City Hall Avenue",       "downtown",    4, 50),
    Intersection("INT-006", "Airport Express",        "highway",     6, 120),
    Intersection("INT-007", "Shopping District",      "downtown",    3, 50),
    Intersection("INT-008", "Riverside Drive",        "residential", 2, 70),
]

INTERSECTION_MAP = {i.id: i for i in CITY_MAP}

VEHICLE_TYPES   = ["car", "truck", "bus", "motorcycle", "bicycle"]
VEHICLE_WEIGHTS = [65,    10,      8,     12,            5]
DIRECTIONS      = ["north", "south", "east", "west"]

class TimeOfDay(str, Enum):
    NIGHT         = "night"           # 23:00–05:00
    EARLY_MORNING = "early_morning"   # 05:00–07:00
    RUSH_MORNING  = "rush_morning"    # 07:00–09:30
    MIDDAY        = "midday"          # 09:30–16:00
    RUSH_EVENING  = "rush_evening"    # 16:00–19:00
    EVENING       = "evening"         # 19:00–23:00

class WeatherCondition(str, Enum):
    CLEAR  = "clear"
    RAIN   = "rain"
    FOG    = "fog"
    SNOW   = "snow"


TRAFFIC_VOLUME_MULTIPLIER = {
    TimeOfDay.NIGHT:         0.05,   # Almost nothing
    TimeOfDay.EARLY_MORNING: 0.20,
    TimeOfDay.RUSH_MORNING:  1.00,   # Peak baseline
    TimeOfDay.MIDDAY:        0.55,
    TimeOfDay.RUSH_EVENING:  0.95,
    TimeOfDay.EVENING:       0.40,
}

WEATHER_SPEED_FACTOR = {
    WeatherCondition.CLEAR: 1.00,
    WeatherCondition.RAIN:  0.80,
    WeatherCondition.FOG:   0.70,
    WeatherCondition.SNOW:  0.50,
}

VEHICLE_WEIGHTS_BY_TIME = {
    TimeOfDay.NIGHT:         [50, 30, 5,  10, 5],   # More trucks at night
    TimeOfDay.RUSH_MORNING:  [70,  5, 10,  10, 5],   # More cars in rush
    TimeOfDay.MIDDAY:        [60, 12, 10,  10, 8],
    TimeOfDay.RUSH_EVENING:  [72,  5, 10,   8, 5],
    TimeOfDay.EVENING:       [65,  8,  8,  12, 7],
    TimeOfDay.EARLY_MORNING: [55, 20,  8,  10, 7],
}



@dataclass
class TrafficEvent:
    event_id:        str
    timestamp:       str
    intersection_id: str
    vehicle_type:    str
    speed_kmh:       float
    direction:       str
    lane:            int
    license_plate:   str
    is_emergency:    bool
    time_of_day:     str
    weather:         str
    incident_nearby: bool

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def to_pubsub_bytes(self) -> bytes:
        return self.to_json().encode("utf-8")


def get_time_of_day(dt: Optional[datetime] = None) -> TimeOfDay:
    """Return the TimeOfDay enum for a given datetime (defaults to now)."""
    now = dt or datetime.now()
    minute_of_day = now.hour * 60 + now.minute
    if minute_of_day >= 23 * 60 or minute_of_day < 5 * 60:
        return TimeOfDay.NIGHT
    if 5 * 60 <= minute_of_day < 7 * 60:
        return TimeOfDay.EARLY_MORNING
    if 7 * 60 <= minute_of_day < 9 * 60 + 30:
        return TimeOfDay.RUSH_MORNING
    if 9 * 60 + 30 <= minute_of_day < 16 * 60:
        return TimeOfDay.MIDDAY
    if 16 * 60 <= minute_of_day < 19 * 60:
        return TimeOfDay.RUSH_EVENING
    return TimeOfDay.EVENING


def random_weather() -> WeatherCondition:
    """Return a random weather condition (clear is most likely)."""
    return random.choices(
        list(WeatherCondition),
        weights=[70, 15, 10, 5],
        k=1
    )[0]


def generate_speed(
    intersection: Intersection,
    vehicle_type: str,
    time_of_day: TimeOfDay,
    weather: WeatherCondition,
    incident_nearby: bool,
) -> float:
    """
    Generate a realistic speed based on:
    - The road type and speed limit
    - Vehicle type capabilities
    - Time-of-day congestion
    - Weather conditions
    - Nearby incidents
    """
    limit = intersection.speed_limit

    base_ranges = {
        "car":        (0.4, 1.05),
        "truck":      (0.3, 0.90),
        "bus":        (0.3, 0.85),
        "motorcycle": (0.4, 1.10),
        "bicycle":    (0.05, 0.30),
    }
    lo, hi = base_ranges.get(vehicle_type, (0.4, 1.0))

    rush_penalty = {
        TimeOfDay.RUSH_MORNING: 0.75,
        TimeOfDay.RUSH_EVENING: 0.75,
        TimeOfDay.MIDDAY:       0.90,
        TimeOfDay.NIGHT:        1.10,  # Night = can go faster
    }.get(time_of_day, 1.0)

    weather_factor = WEATHER_SPEED_FACTOR[weather]
    incident_factor = 0.4 if incident_nearby else 1.0

    effective_hi = hi * limit * rush_penalty * weather_factor * incident_factor
    effective_lo = lo * limit * weather_factor * incident_factor

    speed = random.uniform(
        max(0.0, effective_lo),
        max(effective_lo + 1.0, effective_hi),
    )
    return round(speed, 1)


def generate_event(
    time_of_day: Optional[TimeOfDay] = None,
    weather: Optional[WeatherCondition] = None,
    force_emergency: bool = False,
) -> TrafficEvent:
    """Generate a single realistic traffic event."""
    now = datetime.now(timezone.utc)
    tod = time_of_day or get_time_of_day(now)
    wth = weather or random_weather()

    intersection = random.choice(CITY_MAP)

    weights = VEHICLE_WEIGHTS_BY_TIME.get(tod, VEHICLE_WEIGHTS)
    vehicle_type = random.choices(VEHICLE_TYPES, weights=weights, k=1)[0]

    incident_nearby = random.random() < 0.03   # 3% chance of nearby incident

    speed = generate_speed(intersection, vehicle_type, tod, wth, incident_nearby)

    is_emergency = force_emergency or (random.random() < 0.008)  # 0.8% base rate

    if is_emergency:
        speed = random.uniform(60, min(150, intersection.speed_limit * 1.8))
        speed = round(speed, 1)

    plate = fake.license_plate() if FAKER_AVAILABLE else f"XX-{random.randint(1000,9999)}-X"

    return TrafficEvent(
        event_id        = str(uuid.uuid4()),
        timestamp       = now.isoformat(),
        intersection_id = intersection.id,
        vehicle_type    = vehicle_type,
        speed_kmh       = speed,
        direction       = random.choice(DIRECTIONS),
        lane            = random.randint(1, intersection.lanes),
        license_plate   = plate,
        is_emergency    = is_emergency,
        time_of_day     = tod.value,
        weather         = wth.value,
        incident_nearby = incident_nearby,
    )


def read_csv_dataset(filepath: str):
    """
    Read a traffic CSV dataset and yield normalised TrafficEvent dicts.

    Supports these CSV formats:
      Format A (Traffic Prediction - fedesoriano):
        DateTime, Junction, Vehicles, ID

      Format B (Smart City Traffic Patterns):
        timestamp, intersection_id, vehicle_count, avg_speed, ...

      Format C (Generic):
        Any CSV — maps columns best-effort
    """
    logger.info(f"Reading CSV: {filepath}")
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = [h.lower().strip() for h in reader.fieldnames or []]
        logger.info(f"CSV columns: {headers}")

        for i, row in enumerate(reader):
            row_lower = {k.lower().strip(): v for k, v in row.items()}

            if "junction" in row_lower and "vehicles" in row_lower:
                junction_num = row_lower.get("junction", "1")
                junction_id  = f"INT-00{junction_num}"
                vehicle_count = int(row_lower.get("vehicles", 1))
                timestamp_raw = row_lower.get("datetime", datetime.now(timezone.utc).isoformat())

                for _ in range(min(vehicle_count, 50)):  # cap at 50 per row
                    yield _csv_row_to_event(junction_id, timestamp_raw)
                continue

            intersection_id = (
                row_lower.get("intersection_id")
                or row_lower.get("junction")
                or row_lower.get("location")
                or f"INT-00{(i % 5) + 1}"
            )
            timestamp_raw = (
                row_lower.get("timestamp")
                or row_lower.get("datetime")
                or row_lower.get("date")
                or datetime.now(timezone.utc).isoformat()
            )
            speed = float(row_lower.get("avg_speed", 0) or row_lower.get("speed", 0) or 0)
            if speed == 0:
                speed = round(random.uniform(20, 90), 1)

            vehicle_type = row_lower.get("vehicle_type", random.choice(VEHICLE_TYPES))

            yield {
                "event_id":        str(uuid.uuid4()),
                "timestamp":       timestamp_raw,
                "intersection_id": str(intersection_id),
                "vehicle_type":    str(vehicle_type).lower(),
                "speed_kmh":       speed,
                "direction":       row_lower.get("direction", random.choice(DIRECTIONS)),
                "lane":            int(row_lower.get("lane", random.randint(1, 3))),
                "license_plate":   fake.license_plate() if FAKER_AVAILABLE else "CSV-DATA",
                "is_emergency":    False,
                "time_of_day":     "csv_replay",
                "weather":         row_lower.get("weather", "clear"),
                "incident_nearby": False,
            }


def _csv_row_to_event(intersection_id: str, timestamp_raw: str) -> dict:
    """Helper: create one synthetic event from a CSV row."""
    tod = TimeOfDay.MIDDAY
    try:
        dt = datetime.fromisoformat(timestamp_raw)
        tod = get_time_of_day(dt)
    except (ValueError, TypeError):
        pass

    weights = VEHICLE_WEIGHTS_BY_TIME.get(tod, VEHICLE_WEIGHTS)
    vehicle_type = random.choices(VEHICLE_TYPES, weights=weights, k=1)[0]

    intersection = INTERSECTION_MAP.get(
        intersection_id, random.choice(CITY_MAP)
    )
    speed = generate_speed(intersection, vehicle_type, tod, WeatherCondition.CLEAR, False)

    return {
        "event_id":        str(uuid.uuid4()),
        "timestamp":       timestamp_raw,
        "intersection_id": intersection_id,
        "vehicle_type":    vehicle_type,
        "speed_kmh":       speed,
        "direction":       random.choice(DIRECTIONS),
        "lane":            random.randint(1, intersection.lanes),
        "license_plate":   fake.license_plate() if FAKER_AVAILABLE else "CSV-DATA",
        "is_emergency":    False,
        "time_of_day":     tod.value,
        "weather":         "clear",
        "incident_nearby": False,
    }



class PubSubPublisher:
    def __init__(self, project_id: str, topic_id: str):
        if not PUBSUB_AVAILABLE:
            raise ImportError("Install google-cloud-pubsub: pip install google-cloud-pubsub")
        self.client = pubsub_v1.PublisherClient()
        self.topic_path = self.client.topic_path(project_id, topic_id)
        logger.info(f"Publisher ready → {self.topic_path}")

    def publish(self, event_dict: dict) -> str:
        data = json.dumps(event_dict).encode("utf-8")
        future = self.client.publish(self.topic_path, data=data)
        return future.result()  # Returns message ID



SCENARIOS = {
    "normal_day": {
        "description": "A typical weekday — mix of all time periods",
        "sequence": [
            (TimeOfDay.EARLY_MORNING, 20,  WeatherCondition.CLEAR),
            (TimeOfDay.RUSH_MORNING,  100, WeatherCondition.CLEAR),
            (TimeOfDay.MIDDAY,        60,  WeatherCondition.CLEAR),
            (TimeOfDay.RUSH_EVENING,  100, WeatherCondition.CLEAR),
            (TimeOfDay.EVENING,       40,  WeatherCondition.CLEAR),
            (TimeOfDay.NIGHT,         10,  WeatherCondition.CLEAR),
        ],
    },
    "rainy_rush": {
        "description": "Morning rush hour in heavy rain — slower speeds, more congestion",
        "sequence": [
            (TimeOfDay.RUSH_MORNING, 150, WeatherCondition.RAIN),
        ],
    },
    "night_trucks": {
        "description": "Late night — mostly trucks, low volume",
        "sequence": [
            (TimeOfDay.NIGHT, 30, WeatherCondition.CLEAR),
        ],
    },
    "incident_stress": {
        "description": "Stress test: high volume + incidents + emergency vehicles",
        "sequence": [
            (TimeOfDay.RUSH_MORNING, 200, WeatherCondition.RAIN),
        ],
        "force_emergencies": 5,
    },
}


def run_scenario(name: str, publisher=None, dry_run: bool = False, delay: float = 0.0):
    """Run a named scenario."""
    scenario = SCENARIOS.get(name)
    if not scenario:
        logger.error(f"Unknown scenario '{name}'. Available: {list(SCENARIOS.keys())}")
        return

    logger.info(f"Running scenario: {name} — {scenario['description']}")
    total = 0

    for tod, count, weather in scenario["sequence"]:
        logger.info(f"  → {tod.value}: {count} events, weather={weather.value}")
        for _ in range(count):
            event = generate_event(tod, weather)
            _output_event(event.to_dict(), publisher, dry_run, total)
            total += 1
            if delay: time.sleep(delay)

    for _ in range(scenario.get("force_emergencies", 0)):
        event = generate_event(force_emergency=True)
        _output_event(event.to_dict(), publisher, dry_run, total)
        total += 1

    logger.info(f"Scenario '{name}' complete — {total} events generated")



def _output_event(event: dict, publisher, dry_run: bool, count: int):
    if dry_run:
        print(json.dumps(event, indent=2))
    elif publisher:
        msg_id = publisher.publish(event)
        logger.debug(f"Published #{count}: {event['event_id']} → msg_id={msg_id}")


def generate_backend_test_pack(seed: int = 42) -> list[dict]:
    """
    Generate a deterministic test pack for cross-team integration checks.

    This pack can be shared with Data Engineer / Data Analyst so everyone runs
    the same edge cases.
    """
    random.seed(seed)

    pack = []

    normal = generate_event(TimeOfDay.MIDDAY, WeatherCondition.CLEAR).to_dict()
    pack.append(normal)

    rainy_incident = generate_event(TimeOfDay.RUSH_MORNING, WeatherCondition.RAIN).to_dict()
    rainy_incident["incident_nearby"] = True
    rainy_incident["speed_kmh"] = round(min(rainy_incident["speed_kmh"], 12.0), 1)
    pack.append(rainy_incident)

    stationary = generate_event(TimeOfDay.RUSH_EVENING, WeatherCondition.FOG).to_dict()
    stationary["speed_kmh"] = 0.0
    stationary["incident_nearby"] = True
    pack.append(stationary)

    emergency = generate_event(TimeOfDay.RUSH_MORNING, WeatherCondition.CLEAR, force_emergency=True).to_dict()
    pack.append(emergency)

    fast_highway = generate_event(TimeOfDay.NIGHT, WeatherCondition.CLEAR).to_dict()
    fast_highway["intersection_id"] = "INT-006"
    fast_highway["vehicle_type"] = "car"
    fast_highway["speed_kmh"] = 130.0
    pack.append(fast_highway)

    return pack



def main():
    parser = argparse.ArgumentParser(
        description="Smart City Traffic Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generator.py --dry-run --events 10
  python generator.py --dry-run --scenario rainy_rush
  python generator.py --dry-run --scenario normal_day --delay 0.1
  python generator.py --replay --csv data/traffic.csv --dry-run
  python generator.py --project my-project --topic traffic-events --continuous
""",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--simulate",   action="store_true", help="Generate synthetic events (default)")
    mode_group.add_argument("--replay",     action="store_true",                help="Replay events from a CSV file")
    mode_group.add_argument("--scenario",   type=str, choices=list(SCENARIOS.keys()), help="Run a named test scenario")
    mode_group.add_argument("--test-pack",  action="store_true", help="Emit deterministic edge-case events for team integration")

    parser.add_argument("--dry-run",    action="store_true", help="Print to console, don't publish")
    parser.add_argument("--project",    type=str,            help="GCP project ID (required unless --dry-run)")
    parser.add_argument("--topic",      type=str, default="traffic-events")

    parser.add_argument("--events",     type=int, default=50,  help="Number of events")
    parser.add_argument("--delay",      type=float, default=0.5, help="Seconds between events")
    parser.add_argument("--continuous", action="store_true",   help="Run until Ctrl+C")
    parser.add_argument("--time-of-day", type=str,
                        choices=[t.value for t in TimeOfDay],
                        help="Force a specific time-of-day profile")

    parser.add_argument("--csv",        type=str, help="Path to CSV file (required with --replay)")
    parser.add_argument("--seed",       type=int, default=42, help="Random seed (used by --test-pack)")

    args = parser.parse_args()

    if not args.dry_run and not args.project:
        parser.error("--project is required unless using --dry-run")
    if args.replay and not args.csv:
        parser.error("--csv is required when using --replay")

    publisher = None
    if not args.dry_run:
        publisher = PubSubPublisher(args.project, args.topic)

    if args.scenario:
        run_scenario(args.scenario, publisher, args.dry_run, args.delay)
        return

    if args.test_pack:
        test_events = generate_backend_test_pack(seed=args.seed)
        for index, event_dict in enumerate(test_events):
            _output_event(event_dict, publisher, args.dry_run, index)
            if args.delay:
                time.sleep(args.delay)
        logger.info(f"Test pack complete — {len(test_events)} events emitted")
        return

    if args.replay:
        count = 0
        try:
            for event_dict in read_csv_dataset(args.csv):
                _output_event(event_dict, publisher, args.dry_run, count)
                count += 1
                if args.delay:
                    time.sleep(args.delay)
        except KeyboardInterrupt:
            pass
        logger.info(f"CSV replay complete — {count} events published")
        return

    tod_override = TimeOfDay(args.time_of_day) if args.time_of_day else None
    count = 0

    logger.info(
        f"Starting simulation | dry_run={args.dry_run} | "
        f"time_of_day={tod_override or 'auto'} | "
        f"{'continuous' if args.continuous else f'{args.events} events'}"
    )

    try:
        while True:
            event = generate_event(time_of_day=tod_override)
            event_dict = event.to_dict()
            _output_event(event_dict, publisher, args.dry_run, count)
            count += 1

            if not args.continuous and count >= args.events:
                break

            sleep_seconds = args.delay
            if args.continuous:
                active_tod = TimeOfDay(event_dict["time_of_day"])
                volume_multiplier = TRAFFIC_VOLUME_MULTIPLIER.get(active_tod, 1.0)
                sleep_seconds = args.delay / max(volume_multiplier, 0.05)

            time.sleep(sleep_seconds)

    except KeyboardInterrupt:
        logger.info(f"Stopped by user after {count} events")

    logger.info(f"Done — {count} events generated")


if __name__ == "__main__":
    main()
