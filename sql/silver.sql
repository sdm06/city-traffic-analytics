-- Silver Layer Transformations
-- These queries transform Bronze (raw_events) into cleaned and intermediate Silver tables.

-- 1. cleaned_events: Deduplicated and filtered traffic events.
CREATE OR REPLACE TABLE `traffic_analytics.cleaned_events`
PARTITION BY event_date
CLUSTER BY intersection_id, vehicle_type
AS
SELECT
    * EXCEPT(row_num)
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER(PARTITION BY event_id ORDER BY ingested_at DESC) as row_num
    FROM
        `traffic_analytics.raw_events`
)
WHERE
    row_num = 1;

-- 2. intersection_metrics: Detailed metrics per intersection, hour, and weather.
CREATE OR REPLACE TABLE `traffic_analytics.intersection_metrics`
PARTITION BY event_date
AS
SELECT
    event_date,
    EXTRACT(HOUR FROM timestamp) as event_hour,
    intersection_id,
    time_of_day,
    weather,
    COUNT(event_id) as total_vehicles,
    AVG(speed_kmh) as avg_speed_kmh,
    MIN(speed_kmh) as min_speed_kmh,
    MAX(speed_kmh) as max_speed_kmh,
    STDDEV(speed_kmh) as stddev_speed_kmh,
    -- Speed category counts
    COUNTIF(speed_category = 'stationary') as stationary_count,
    COUNTIF(speed_category = 'slow') as slow_count,
    COUNTIF(speed_category = 'normal') as normal_count,
    COUNTIF(speed_category = 'fast') as fast_count,
    COUNTIF(speed_category = 'very_fast') as very_fast_count,
    -- Identity and Safety
    COUNTIF(is_emergency = true) as emergency_count,
    COUNTIF(incident_nearby = true) as incident_count,
    -- Vehicle type breakdown
    COUNTIF(vehicle_type = 'car') as car_count,
    COUNTIF(vehicle_type = 'truck') as truck_count,
    COUNTIF(vehicle_type = 'bus') as bus_count,
    COUNTIF(vehicle_type = 'motorcycle') as motorcycle_count,
    COUNTIF(vehicle_type = 'bicycle') as bicycle_count
FROM
    `traffic_analytics.cleaned_events`
GROUP BY
    1, 2, 3, 4, 5;
