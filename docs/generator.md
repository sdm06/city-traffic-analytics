# Traffic Generator Guide (Simulation Engineer)

This document defines how to use `data_generator/generator.py`, what event contract it emits, and how to coordinate handoff with other roles.

## Quick start

```bash
# From repository root
python data_generator/generator.py --dry-run --events 5
```

## Modes

```bash
# Synthetic simulation (default)
python data_generator/generator.py --simulate --dry-run --events 50

# Continuous stream
python data_generator/generator.py --simulate --dry-run --continuous --delay 0.2

# Force a traffic profile
python data_generator/generator.py --simulate --dry-run --time-of-day rush_morning --events 100

# Named scenario
python data_generator/generator.py --scenario rainy_rush --dry-run

# CSV replay
python data_generator/generator.py --replay --csv data/traffic.csv --dry-run

# Deterministic backend handoff test pack
python data_generator/generator.py --test-pack --seed 42 --dry-run
```

## Pub/Sub publish mode

```bash
python data_generator/generator.py \
  --simulate \
  --project YOUR_GCP_PROJECT_ID \
  --topic traffic-events \
  --events 100
```

`--project` is required when not using `--dry-run`.

## Event contract (v1)

The generator emits JSON objects with these fields:

| Field             | Type    | Notes                                          |
| ----------------- | ------- | ---------------------------------------------- |
| `event_id`        | string  | UUID v4                                        |
| `timestamp`       | string  | ISO-8601 UTC timestamp                         |
| `intersection_id` | string  | Example: `INT-006`                             |
| `vehicle_type`    | string  | `car`, `truck`, `bus`, `motorcycle`, `bicycle` |
| `speed_kmh`       | number  | Speed in km/h                                  |
| `direction`       | string  | `north`, `south`, `east`, `west`               |
| `lane`            | integer | Lane index from 1                              |
| `license_plate`   | string  | Simulated value                                |
| `is_emergency`    | boolean | Emergency vehicle marker                       |
| `time_of_day`     | string  | Context enrichment from simulator              |
| `weather`         | string  | `clear`, `rain`, `fog`, `snow`                 |
| `incident_nearby` | boolean | Synthetic nearby-incident signal               |

Core Bronze compatibility fields are: `event_id`, `timestamp`, `intersection_id`, `vehicle_type`, `speed_kmh`, `direction`, `lane`, `license_plate`, `is_emergency`.

## Backend engineer checklist

1. Run `--dry-run` locally and confirm payload shape.
2. Run `--test-pack --seed 42` and share sample output in team chat.
3. Publish to `traffic-events` and confirm Data Engineer can ingest it.
4. Lock schema changes before adding/removing fields.
