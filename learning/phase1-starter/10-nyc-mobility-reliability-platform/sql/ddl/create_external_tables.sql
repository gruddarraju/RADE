-- Replace template tokens through scripts/setup_athena.ps1 before execution.
CREATE DATABASE IF NOT EXISTS {{DATABASE_NAME}};

CREATE EXTERNAL TABLE IF NOT EXISTS {{DATABASE_NAME}}.curated_hvfhv (
    hvfhs_license_num STRING,
    dispatching_base_num STRING,
    originating_base_num STRING,
    request_datetime TIMESTAMP,
    on_scene_datetime TIMESTAMP,
    pickup_datetime TIMESTAMP,
    dropoff_datetime TIMESTAMP,
    pickup_location_id INT,
    dropoff_location_id INT,
    trip_miles DOUBLE,
    trip_time_seconds BIGINT,
    base_passenger_fare DOUBLE,
    tolls DOUBLE,
    black_car_fund DOUBLE,
    sales_tax DOUBLE,
    congestion_surcharge DOUBLE,
    airport_fee DOUBLE,
    tips DOUBLE,
    driver_pay DOUBLE,
    cbd_congestion_fee DOUBLE,
    total_passenger_charge DOUBLE,
    shared_request BOOLEAN,
    shared_match BOOLEAN,
    access_a_ride BOOLEAN,
    wav_request BOOLEAN,
    wav_match BOOLEAN,
    trip_date DATE,
    pickup_hour INT,
    pickup_day_of_week STRING,
    is_weekend BOOLEAN,
    trip_duration_minutes DOUBLE,
    run_id STRING,
    processed_at TIMESTAMP
)
PARTITIONED BY (source_year INT, source_month INT, pickup_day INT)
STORED AS PARQUET
LOCATION 's3://{{DATA_BUCKET}}/curated/hvfhv/';

CREATE EXTERNAL TABLE IF NOT EXISTS {{DATABASE_NAME}}.daily_zone_demand (
    trip_date DATE,
    pickup_location_id INT,
    pickup_borough STRING,
    pickup_zone STRING,
    trip_count BIGINT,
    average_trip_miles DOUBLE,
    average_trip_minutes DOUBLE,
    total_passenger_charge DOUBLE,
    total_driver_pay DOUBLE
)
PARTITIONED BY (source_year INT, source_month INT, pickup_day INT)
STORED AS PARQUET
LOCATION 's3://{{DATA_BUCKET}}/aggregated/daily_zone_demand/';

CREATE EXTERNAL TABLE IF NOT EXISTS {{DATABASE_NAME}}.hourly_demand (
    trip_date DATE,
    pickup_hour INT,
    pickup_location_id INT,
    pickup_borough STRING,
    pickup_zone STRING,
    trip_count BIGINT,
    average_base_fare DOUBLE,
    average_trip_minutes DOUBLE
)
PARTITIONED BY (source_year INT, source_month INT, pickup_day INT)
STORED AS PARQUET
LOCATION 's3://{{DATA_BUCKET}}/aggregated/hourly_demand/';

CREATE EXTERNAL TABLE IF NOT EXISTS {{DATABASE_NAME}}.daily_provider_service (
    trip_date DATE,
    hvfhs_license_num STRING,
    trip_count BIGINT,
    shared_trip_count BIGINT,
    wav_trip_count BIGINT,
    total_passenger_charge DOUBLE,
    total_driver_pay DOUBLE
)
PARTITIONED BY (source_year INT, source_month INT, pickup_day INT)
STORED AS PARQUET
LOCATION 's3://{{DATA_BUCKET}}/aggregated/daily_provider_service/';

MSCK REPAIR TABLE {{DATABASE_NAME}}.curated_hvfhv;
MSCK REPAIR TABLE {{DATABASE_NAME}}.daily_zone_demand;
MSCK REPAIR TABLE {{DATABASE_NAME}}.hourly_demand;
MSCK REPAIR TABLE {{DATABASE_NAME}}.daily_provider_service;
