"""Enrich curated trips with taxi zones and publish three daily aggregates."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

import boto3
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")
S3 = boto3.client("s3")
ZONE_SCHEMA = StructType(
    [
        StructField("LocationID", IntegerType(), False),
        StructField("Borough", StringType(), True),
        StructField("Zone", StringType(), True),
        StructField("service_zone", StringType(), True),
    ]
)


def _write_dataset(df: DataFrame, bucket: str, dataset: str) -> int:
    """Write one aggregate dataset with dynamic period replacement."""
    row_count = df.count()
    (
        df.repartition("source_year", "source_month", "pickup_day")
        .write.mode("overwrite")
        .option("compression", "snappy")
        .partitionBy("source_year", "source_month", "pickup_day")
        .parquet(f"s3://{bucket}/aggregated/{dataset}/")
    )
    return row_count


def _write_manifest(bucket: str, key: str, manifest: dict[str, Any]) -> None:
    """Write a JSON run manifest to S3."""
    S3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def main() -> None:
    """Execute one bounded curated-to-aggregate Glue Spark run."""
    args = getResolvedOptions(
        sys.argv,
        ["JOB_NAME", "DATA_BUCKET", "YEAR", "MONTH", "RUN_ID"],
    )
    year = int(args["YEAR"])
    month = int(args["MONTH"])
    run_id = args["RUN_ID"]
    bucket = args["DATA_BUCKET"]

    spark_context = SparkContext.getOrCreate()
    spark = SparkSession.builder.getOrCreate()
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    job = Job(spark_context)
    job.init(args["JOB_NAME"], args)

    curated_base = f"s3://{bucket}/curated/hvfhv/"
    curated_period = (
        f"{curated_base}source_year={year}/source_month={month}/"
    )
    curated_df = (
        spark.read.option("basePath", curated_base)
        .parquet(curated_period)
    )
    zones_df = (
        spark.read.option("header", True)
        .schema(ZONE_SCHEMA)
        .csv(f"s3://{bucket}/raw/reference/taxi_zone_lookup.csv")
    )

    pickup_zones = zones_df.select(
        F.col("LocationID").alias("pickup_location_id"),
        F.col("Borough").alias("pickup_borough"),
        F.col("Zone").alias("pickup_zone"),
        F.col("service_zone").alias("pickup_service_zone"),
    )
    dropoff_zones = zones_df.select(
        F.col("LocationID").alias("dropoff_location_id"),
        F.col("Borough").alias("dropoff_borough"),
        F.col("Zone").alias("dropoff_zone"),
        F.col("service_zone").alias("dropoff_service_zone"),
    )
    enriched_df = (
        curated_df.join(pickup_zones, "pickup_location_id", "left")
        .join(dropoff_zones, "dropoff_location_id", "left")
        .cache()
    )
    unmatched_zone_count = enriched_df.filter(
        F.col("pickup_zone").isNull() | F.col("dropoff_zone").isNull()
    ).count()

    daily_zone_demand = enriched_df.groupBy(
        "trip_date",
        "pickup_day",
        "pickup_location_id",
        "pickup_borough",
        "pickup_zone",
        "source_year",
        "source_month",
    ).agg(
        F.count(F.lit(1)).alias("trip_count"),
        F.round(F.avg("trip_miles"), 2).alias("average_trip_miles"),
        F.round(F.avg("trip_duration_minutes"), 2).alias("average_trip_minutes"),
        F.round(F.sum("total_passenger_charge"), 2).alias("total_passenger_charge"),
        F.round(F.sum("driver_pay"), 2).alias("total_driver_pay"),
    )

    hourly_demand = enriched_df.groupBy(
        "trip_date",
        "pickup_day",
        "pickup_hour",
        "pickup_location_id",
        "pickup_borough",
        "pickup_zone",
        "source_year",
        "source_month",
    ).agg(
        F.count(F.lit(1)).alias("trip_count"),
        F.round(F.avg("base_passenger_fare"), 2).alias("average_base_fare"),
        F.round(F.avg("trip_duration_minutes"), 2).alias("average_trip_minutes"),
    )

    daily_provider_service = enriched_df.groupBy(
        "trip_date",
        "pickup_day",
        "hvfhs_license_num",
        "source_year",
        "source_month",
    ).agg(
        F.count(F.lit(1)).alias("trip_count"),
        F.sum(F.col("shared_match").cast("long")).alias("shared_trip_count"),
        F.sum(F.col("wav_match").cast("long")).alias("wav_trip_count"),
        F.round(F.sum("total_passenger_charge"), 2).alias("total_passenger_charge"),
        F.round(F.sum("driver_pay"), 2).alias("total_driver_pay"),
    )

    counts = {
        "daily_zone_demand": _write_dataset(
            daily_zone_demand, bucket, "daily_zone_demand"
        ),
        "hourly_demand": _write_dataset(
            hourly_demand, bucket, "hourly_demand"
        ),
        "daily_provider_service": _write_dataset(
            daily_provider_service, bucket, "daily_provider_service"
        ),
    }
    manifest = {
        "project": "nyc-mobility-reliability",
        "stage": "curated_to_aggregate",
        "run_id": run_id,
        "source_period": f"{year:04d}-{month:02d}",
        "curated_count": enriched_df.count(),
        "unmatched_zone_count": unmatched_zone_count,
        "aggregate_row_counts": counts,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_key = (
        f"manifests/source_period={year:04d}-{month:02d}/"
        f"run_id={run_id}/curated_to_aggregate.json"
    )
    _write_manifest(bucket, manifest_key, manifest)
    LOGGER.info(json.dumps({"event": "aggregation_complete", **manifest}))
    enriched_df.unpersist()
    job.commit()


if __name__ == "__main__":
    main()
