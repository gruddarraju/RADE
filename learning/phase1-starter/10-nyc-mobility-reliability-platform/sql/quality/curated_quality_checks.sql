-- Set these values to the period being validated.
WITH curated_period AS (
    SELECT *
    FROM nyc_mobility_reliability_dev.curated_hvfhv
    WHERE source_year = 2025
      AND source_month = 1
),
quality_summary AS (
    SELECT
        COUNT(*) AS curated_rows,
        SUM(CASE WHEN pickup_datetime IS NULL THEN 1 ELSE 0 END) AS null_pickup_rows,
        SUM(CASE WHEN dropoff_datetime IS NULL THEN 1 ELSE 0 END) AS null_dropoff_rows,
        SUM(CASE WHEN dropoff_datetime <= pickup_datetime THEN 1 ELSE 0 END) AS invalid_time_order_rows,
        SUM(CASE WHEN trip_miles < 0 OR trip_miles > 500 THEN 1 ELSE 0 END) AS invalid_distance_rows,
        SUM(CASE WHEN base_passenger_fare < 0 OR base_passenger_fare >= 10000 THEN 1 ELSE 0 END) AS invalid_fare_rows,
        SUM(CASE WHEN pickup_location_id <= 0 OR dropoff_location_id <= 0 THEN 1 ELSE 0 END) AS invalid_location_rows
    FROM curated_period
),
aggregate_reconciliation AS (
    SELECT COALESCE(SUM(trip_count), 0) AS aggregate_trip_rows
    FROM nyc_mobility_reliability_dev.daily_zone_demand
    WHERE source_year = 2025
      AND source_month = 1
)
SELECT
    q.*,
    a.aggregate_trip_rows,
    q.curated_rows - a.aggregate_trip_rows AS reconciliation_difference
FROM quality_summary AS q
CROSS JOIN aggregate_reconciliation AS a;
