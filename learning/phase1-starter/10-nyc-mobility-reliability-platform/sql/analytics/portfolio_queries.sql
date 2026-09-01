-- 1. Highest-demand pickup zones for a measured source period.
SELECT
    pickup_borough,
    pickup_zone,
    SUM(trip_count) AS trips,
    ROUND(AVG(average_trip_minutes), 2) AS average_trip_minutes,
    ROUND(SUM(total_passenger_charge), 2) AS total_passenger_charge
FROM nyc_mobility_reliability_dev.daily_zone_demand
WHERE source_year = 2025
  AND source_month = 1
GROUP BY pickup_borough, pickup_zone
ORDER BY trips DESC
LIMIT 20;

-- 2. Hourly demand profile. Partition filters keep Athena scans bounded.
SELECT
    pickup_hour,
    SUM(trip_count) AS trips,
    ROUND(AVG(average_base_fare), 2) AS average_base_fare,
    ROUND(AVG(average_trip_minutes), 2) AS average_trip_minutes
FROM nyc_mobility_reliability_dev.hourly_demand
WHERE source_year = 2025
  AND source_month = 1
GROUP BY pickup_hour
ORDER BY pickup_hour;

-- 3. Provider-level service mix without claiming business causality.
SELECT
    hvfhs_license_num,
    SUM(trip_count) AS trips,
    SUM(shared_trip_count) AS shared_trips,
    SUM(wav_trip_count) AS wav_trips,
    ROUND(SUM(total_passenger_charge), 2) AS total_passenger_charge,
    ROUND(SUM(total_driver_pay), 2) AS total_driver_pay
FROM nyc_mobility_reliability_dev.daily_provider_service
WHERE source_year = 2025
  AND source_month = 1
GROUP BY hvfhs_license_num
ORDER BY trips DESC;
