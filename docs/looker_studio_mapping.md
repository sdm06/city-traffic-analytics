# Looker Studio Field Mapping Guide

Use this guide to configure your Data Source in Looker Studio using the `v_dashboard_unified` view.

## 1. Data Source Configuration
- **Project:** `city-traffic-analytics`
- **Dataset:** `traffic_analytics`
- **Table/View:** `v_dashboard_unified`

## 2. Field Types and Aggregations

| Field Name | Type | Aggregation | Description |
|---|---|---|---|
| `event_timestamp` | Date & Time | None | Primary time dimension for line charts |
| `event_date` | Date | None | For daily filtering |
| `intersection_id` | Text | None | Intersection dimension |
| `time_of_day` | Text | None | Categorical dimension (e.g. rush_morning) |
| `weather` | Text | None | Categorical dimension |
| `congestion_level` | Text | None | Categorical status |
| `total_vehicles` | Number | Sum | Total traffic volume |
| `avg_speed_kmh` | Number | Average | Mean speed |
| `congestion_score` | Number | Average | 0-100 score (higher = slower) |
| `emergency_count` | Number | Sum | Count of emergency vehicles |
| `incident_count` | Number | Sum | Count of active incidents |

## 3. Recommended Calculated Fields

### `Peak vs Off-Peak`
```sql
CASE 
  WHEN event_hour IN (7,8,9,16,17,18) THEN "Peak" 
  ELSE "Off-Peak" 
END
```

### `Safety Index`
```sql
(total_vehicles - (emergency_count + incident_count)) / total_vehicles
```

## 4. Chart Mapping

### Time Series (Traffic Flow)
- **Dimension:** `event_timestamp`
- **Metric:** `total_vehicles`
- **Breakdown Dimension:** `intersection_id`

### Map (Congestion Hotspots)
- **Location:** `intersection_id` (Note: You may need to join with a static CSV of GPS coordinates for actual map plotting)
- **Color Metric:** `congestion_score` (Average)

### Pie Chart (Vehicle Mix)
- **Dimension:** Create a "Vehicle Type" dimension by unpivoting or using the `vehicle_type_breakdown` table.
- **Metric:** `total_count`
