-- Gold Layer Transformations
-- These queries transform Silver (cleaned_events) into business-ready Gold tables for dashboards.

-- 1. hourly_traffic_summary: Hourly traffic volume and speed averages.
CREATE OR REPLACE TABLE `traffic_analytics.hourly_traffic_summary`
PARTITION BY event_date
AS
WITH base_metrics AS (
    SELECT
        event_date,
        EXTRACT(HOUR FROM timestamp) as event_hour,
        intersection_id,
        time_of_day,
        weather,
        COUNT(event_id) as total_vehicles,
        ROUND(AVG(speed_kmh), 2) as avg_speed_kmh,
        MIN(speed_kmh) as min_speed_kmh,
        MAX(speed_kmh) as max_speed_kmh,
        COUNTIF(is_emergency = true) as emergency_vehicles,
        COUNTIF(incident_nearby = true) as incidents
    FROM
        `traffic_analytics.cleaned_events`
    GROUP BY
        1, 2, 3, 4, 5
)
SELECT
    *,
    CASE 
        WHEN event_hour BETWEEN 7 AND 9 OR event_hour BETWEEN 16 AND 18 THEN true
        ELSE false
    END as is_peak_hour
FROM
    base_metrics;

-- 2. congestion_index: Real-time congestion detection.
CREATE OR REPLACE TABLE `traffic_analytics.congestion_index`
PARTITION BY event_date
AS
SELECT
    event_date,
    EXTRACT(HOUR FROM timestamp) as event_hour,
    intersection_id,
    time_of_day,
    weather,
    COUNT(event_id) as total_vehicles,
    ROUND(AVG(speed_kmh), 2) as avg_speed_kmh,
    -- Simple congestion score (higher = more congested)
    ROUND(100 * (1 - (AVG(speed_kmh) / 80)), 2) as congestion_score,
    CASE
        WHEN AVG(speed_kmh) < 10 THEN 'standstill'
        WHEN AVG(speed_kmh) < 25 THEN 'heavy'
        WHEN AVG(speed_kmh) < 45 THEN 'moderate'
        WHEN AVG(speed_kmh) < 65 THEN 'light'
        ELSE 'free_flow'
    END as congestion_level,
    COUNTIF(incident_nearby = true) as incidents,
    COUNTIF(is_emergency = true) as emergency_vehicles
FROM
    `traffic_analytics.cleaned_events`
GROUP BY
    1, 2, 3, 4, 5;

-- 3. vehicle_type_breakdown: Daily breakdown of vehicle types.
CREATE OR REPLACE TABLE `traffic_analytics.vehicle_type_breakdown`
PARTITION BY event_date
AS
SELECT
    event_date,
    vehicle_type,
    COUNT(event_id) as total_count,
    ROUND(AVG(speed_kmh), 2) as avg_speed,
    COUNTIF(is_emergency = true) as emergency_count
FROM
    `traffic_analytics.cleaned_events`
GROUP BY
    1, 2;
