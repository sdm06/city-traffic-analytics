-- Unified Dashboard View for Looker Studio
-- Consolidates metrics from Silver and Gold layers for a one-stop-shop reporting source.

CREATE OR REPLACE VIEW `traffic_analytics.v_dashboard_unified` AS
SELECT
    m.event_date,
    m.event_hour,
    m.intersection_id,
    m.time_of_day,
    m.weather,
    -- Core metrics
    m.total_vehicles,
    m.avg_speed_kmh,
    m.min_speed_kmh,
    m.max_speed_kmh,
    m.stddev_speed_kmh,
    -- Congestion status (from congestion_index)
    c.congestion_score,
    c.congestion_level,
    -- Vehicle type breakdown
    m.car_count,
    m.truck_count,
    m.bus_count,
    m.motorcycle_count,
    m.bicycle_count,
    -- Safety and Incidents
    m.emergency_count,
    m.incident_count,
    -- Speed category counts
    m.stationary_count,
    m.slow_count,
    m.normal_count,
    m.fast_count,
    m.very_fast_count,
    -- Derived Time dimensions
    FORMAT_TIMESTAMP('%Y-%m-%d %H:00:00', TIMESTAMP(CAST(m.event_date AS STRING) || ' ' || CAST(m.event_hour AS STRING) || ':00:00')) as event_timestamp
FROM
    `traffic_analytics.intersection_metrics` m
LEFT JOIN
    `traffic_analytics.congestion_index` c
ON
    m.event_date = c.event_date
    AND m.event_hour = c.event_hour
    AND m.intersection_id = c.intersection_id
    AND m.time_of_day = c.time_of_day
    AND m.weather = c.weather;
