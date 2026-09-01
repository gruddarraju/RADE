"""Transform one HVFHV source period into curated and quarantined Parquet."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

import boto3
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark import StorageLevel
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")
S3 = boto3.client("s3")

SOURCE_SCHEMA = StructType(
    [
        StructField("hvfhs_license_num", StringType(), True),
        StructField("dispatching_base_num", StringType(), True),
        StructField("originating_base_num", StringType(), True),
        StructField("request_datetime", TimestampType(), True),
        StructField("on_scene_datetime", TimestampType(), True),
        StructField("pickup_datetime", TimestampType(), True),
        StructField("dropoff_datetime", TimestampType(), True),
        StructField("PULocationID", IntegerType(), True),
        StructField("DOLocationID", IntegerType(), True),
        StructField("trip_miles", DoubleType(), True),
        StructField("trip_time", LongType(), True),
        StructField("base_passenger_fare", DoubleType(), True),
        StructField("tolls", DoubleType(), True),
        StructField("bcf", DoubleType(), True),
        StructField("sales_tax", DoubleType(), True),
        StructField("congestion_surcharge", DoubleType(), True),
        StructField("airport_fee", DoubleType(), True),
        StructField("tips", DoubleType(), True),
        StructField("driver_pay", DoubleType(), True),
        StructField("shared_request_flag", StringType(), True),
        StructField("shared_match_flag", StringType(), True),
        StructField("access_a_ride_flag", StringType(), True),
        StructField("wav_request_flag", StringType(), True),
        StructField("wav_match_flag", StringType(), True),
        StructField("cbd_congestion_fee", DoubleType(), True),
    ]
)
REQUIRED_SOURCE_COLUMNS = {
    "hvfhs_license_num",
    "pickup_datetime",
    "dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "trip_miles",
    "base_passenger_fare",
}


def _boolean_flag(column_name: str) -> Any:
    """Convert a source Y/N flag to a null-safe Boolean."""
    return F.coalesce(
        F.upper(F.trim(F.col(column_name))) == F.lit("Y"),
        F.lit(False),
    )


def _transform(raw_df: DataFrame, year: int, month: int, run_id: str) -> DataFrame:
    """Apply the versioned source-to-target mapping."""
    money_fields = [
        "base_passenger_fare",
        "tolls",
        "bcf",
        "sales_tax",
        "congestion_surcharge",
        "airport_fee",
        "tips",
        "cbd_congestion_fee",
    ]
    total_charge = sum(
        (F.coalesce(F.col(name), F.lit(0.0)) for name in money_fields),
        F.lit(0.0),
    )

    return raw_df.select(
        F.trim("hvfhs_license_num").alias("hvfhs_license_num"),
        F.trim("dispatching_base_num").alias("dispatching_base_num"),
        F.trim("originating_base_num").alias("originating_base_num"),
        "request_datetime",
        "on_scene_datetime",
        "pickup_datetime",
        "dropoff_datetime",
        F.col("PULocationID").alias("pickup_location_id"),
        F.col("DOLocationID").alias("dropoff_location_id"),
        "trip_miles",
        F.col("trip_time").alias("trip_time_seconds"),
        "base_passenger_fare",
        F.coalesce("tolls", F.lit(0.0)).alias("tolls"),
        F.coalesce("bcf", F.lit(0.0)).alias("black_car_fund"),
        F.coalesce("sales_tax", F.lit(0.0)).alias("sales_tax"),
        F.coalesce("congestion_surcharge", F.lit(0.0)).alias("congestion_surcharge"),
        F.coalesce("airport_fee", F.lit(0.0)).alias("airport_fee"),
        F.coalesce("tips", F.lit(0.0)).alias("tips"),
        F.coalesce("driver_pay", F.lit(0.0)).alias("driver_pay"),
        F.coalesce("cbd_congestion_fee", F.lit(0.0)).alias("cbd_congestion_fee"),
        total_charge.alias("total_passenger_charge"),
        _boolean_flag("shared_request_flag").alias("shared_request"),
        _boolean_flag("shared_match_flag").alias("shared_match"),
        _boolean_flag("access_a_ride_flag").alias("access_a_ride"),
        _boolean_flag("wav_request_flag").alias("wav_request"),
        _boolean_flag("wav_match_flag").alias("wav_match"),
        F.to_date("pickup_datetime").alias("trip_date"),
        F.hour("pickup_datetime").alias("pickup_hour"),
        F.date_format("pickup_datetime", "EEEE").alias("pickup_day_of_week"),
        F.dayofweek("pickup_datetime").isin(1, 7).alias("is_weekend"),
        (
            (F.col("dropoff_datetime").cast("long") - F.col("pickup_datetime").cast("long"))
            / F.lit(60.0)
        ).alias("trip_duration_minutes"),
        F.lit(year).alias("source_year"),
        F.lit(month).alias("source_month"),
        F.dayofmonth("pickup_datetime").alias("pickup_day"),
        F.lit(run_id).alias("run_id"),
        F.current_timestamp().alias("processed_at"),
    )


def _apply_quality_rules(curated_df: DataFrame) -> DataFrame:
    """Attach deterministic rejection reason codes to each row."""
    reasons = [
        F.when(F.col("pickup_datetime").isNull(), F.lit("DQ001")),
        F.when(F.col("dropoff_datetime").isNull(), F.lit("DQ002")),
        F.when(
            F.col("dropoff_datetime") <= F.col("pickup_datetime"),
            F.lit("DQ003"),
        ),
        F.when(
            F.col("trip_miles").isNull()
            | (F.col("trip_miles") < 0)
            | (F.col("trip_miles") > 500),
            F.lit("DQ004"),
        ),
        F.when(
            F.col("base_passenger_fare").isNull()
            | (F.col("base_passenger_fare") < 0)
            | (F.col("base_passenger_fare") >= 10000),
            F.lit("DQ005"),
        ),
        F.when(
            F.col("pickup_location_id").isNull()
            | F.col("dropoff_location_id").isNull()
            | (F.col("pickup_location_id") <= 0)
            | (F.col("dropoff_location_id") <= 0),
            F.lit("DQ006"),
        ),
        F.when(
            F.col("hvfhs_license_num").isNull()
            | (F.length(F.col("hvfhs_license_num")) == 0),
            F.lit("DQ007"),
        ),
    ]
    return curated_df.withColumn("quality_reasons", F.concat_ws("|", *reasons))


def _write_manifest(bucket: str, key: str, manifest: dict[str, Any]) -> None:
    """Write a JSON run manifest to S3."""
    S3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def main() -> None:
    """Execute one bounded raw-to-curated Glue Spark run."""
    args = getResolvedOptions(
        sys.argv,
        [
            "JOB_NAME",
            "DATA_BUCKET",
            "YEAR",
            "MONTH",
            "RUN_ID",
            "REJECT_RATE_THRESHOLD",
        ],
    )
    year = int(args["YEAR"])
    month = int(args["MONTH"])
    run_id = args["RUN_ID"]
    threshold = float(args["REJECT_RATE_THRESHOLD"])
    bucket = args["DATA_BUCKET"]

    spark_context = SparkContext.getOrCreate()
    spark = SparkSession.builder.getOrCreate()
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    job = Job(spark_context)
    job.init(args["JOB_NAME"], args)

    month_text = f"{month:02d}"
    input_path = (
        f"s3://{bucket}/raw/hvfhv/year={year:04d}/month={month_text}/"
    )
    observed_columns = set(spark.read.parquet(input_path).columns)
    missing_columns = sorted(REQUIRED_SOURCE_COLUMNS - observed_columns)
    if missing_columns:
        raise ValueError(f"Required source columns are missing: {missing_columns}")

    raw_df = spark.read.schema(SOURCE_SCHEMA).parquet(input_path)
    checked_df = _apply_quality_rules(
        _transform(raw_df, year, month, run_id)
    ).persist(StorageLevel.MEMORY_AND_DISK)
    valid_df = checked_df.filter(F.col("quality_reasons") == "")
    rejected_df = checked_df.filter(F.col("quality_reasons") != "")

    source_count = checked_df.count()
    valid_count = valid_df.count()
    rejected_count = rejected_df.count()
    if source_count != valid_count + rejected_count:
        raise RuntimeError("Source, valid, and rejected counts do not reconcile")
    reject_rate = rejected_count / source_count if source_count else 0.0

    quarantine_path = (
        f"s3://{bucket}/quarantine/hvfhv/source_period={year:04d}-{month_text}/"
        f"run_id={run_id}/"
    )
    if rejected_count:
        rejected_df.write.mode("overwrite").parquet(quarantine_path)

    manifest = {
        "project": "nyc-mobility-reliability",
        "stage": "raw_to_curated",
        "run_id": run_id,
        "source_period": f"{year:04d}-{month_text}",
        "source_count": source_count,
        "valid_count": valid_count,
        "rejected_count": rejected_count,
        "reject_rate": reject_rate,
        "reject_rate_threshold": threshold,
        "rule_version": "1.0.0",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_key = (
        f"manifests/source_period={year:04d}-{month_text}/"
        f"run_id={run_id}/raw_to_curated.json"
    )
    _write_manifest(bucket, manifest_key, manifest)
    LOGGER.info(json.dumps({"event": "quality_summary", **manifest}))

    if reject_rate > threshold:
        raise RuntimeError(
            f"Reject rate {reject_rate:.4%} exceeds threshold {threshold:.4%}"
        )

    (
        valid_df.drop("quality_reasons")
        .repartition("source_year", "source_month", "pickup_day")
        .write.mode("overwrite")
        .option("compression", "snappy")
        .partitionBy("source_year", "source_month", "pickup_day")
        .parquet(f"s3://{bucket}/curated/hvfhv/")
    )
    checked_df.unpersist()
    job.commit()


if __name__ == "__main__":
    main()
