"""Download one NYC TLC HVFHV period and its zone lookup into immutable S3 keys."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import boto3
from awsglue.utils import getResolvedOptions
from botocore.exceptions import ClientError

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

TRIP_URL = (
    "https://d37ci6vzurychx.cloudfront.net/trip-data/"
    "fhvhv_tripdata_{year}-{month}.parquet"
)
ZONE_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
BUFFER_SIZE = 8 * 1024 * 1024
S3 = boto3.client("s3")


def _object_exists(bucket: str, key: str) -> bool:
    """Return whether an S3 object already exists."""
    try:
        S3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _download(url: str, destination: Path) -> tuple[int, str]:
    """Stream a public source object to disk and return bytes and SHA-256."""
    digest = hashlib.sha256()
    byte_count = 0
    request = Request(url, headers={"User-Agent": "nyc-mobility-reliability/1.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while chunk := response.read(BUFFER_SIZE):
            output.write(chunk)
            digest.update(chunk)
            byte_count += len(chunk)
    return byte_count, digest.hexdigest()


def _ingest_object(
    bucket: str,
    key: str,
    source_url: str,
    force: bool,
) -> dict[str, Any]:
    """Download and upload one object unless the deterministic key exists."""
    if _object_exists(bucket, key) and not force:
        head = S3.head_object(Bucket=bucket, Key=key)
        return {
            "status": "SKIPPED_EXISTING",
            "source_url": source_url,
            "s3_key": key,
            "bytes": head["ContentLength"],
            "etag": head.get("ETag", "").strip('"'),
            "sha256": head.get("Metadata", {}).get("sha256"),
        }

    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = Path(temp_dir) / Path(key).name
        byte_count, sha256 = _download(source_url, local_path)
        S3.upload_file(
            str(local_path),
            bucket,
            key,
            ExtraArgs={
                "Metadata": {
                    "sha256": sha256,
                    "source-url": source_url,
                }
            },
        )
    head = S3.head_object(Bucket=bucket, Key=key)
    return {
        "status": "UPLOADED",
        "source_url": source_url,
        "s3_key": key,
        "bytes": byte_count,
        "etag": head.get("ETag", "").strip('"'),
        "sha256": sha256,
    }


def main() -> None:
    """Run bounded ingestion for the requested source period."""
    args = getResolvedOptions(
        sys.argv,
        ["DATA_BUCKET", "YEAR", "MONTH", "RUN_ID", "FORCE"],
    )
    year = int(args["YEAR"])
    month = int(args["MONTH"])
    if year < 2019 or month < 1 or month > 12:
        raise ValueError("Invalid TLC source period")

    month_text = f"{month:02d}"
    force = args["FORCE"].lower() == "true"
    bucket = args["DATA_BUCKET"]
    run_id = args["RUN_ID"]
    trip_key = (
        f"raw/hvfhv/year={year:04d}/month={month_text}/"
        f"fhvhv_tripdata_{year:04d}-{month_text}.parquet"
    )
    zone_key = "raw/reference/taxi_zone_lookup.csv"

    started_at = datetime.now(timezone.utc)
    trip_result = _ingest_object(
        bucket,
        trip_key,
        TRIP_URL.format(year=year, month=month_text),
        force,
    )
    zone_result = _ingest_object(bucket, zone_key, ZONE_URL, False)
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "project": "nyc-mobility-reliability",
        "run_id": run_id,
        "source_period": f"{year:04d}-{month_text}",
        "force": force,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "objects": [trip_result, zone_result],
    }
    manifest_key = (
        f"manifests/source_period={year:04d}-{month_text}/"
        f"run_id={run_id}/ingestion.json"
    )
    S3.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    LOGGER.info(json.dumps({"event": "ingestion_complete", **manifest}))


if __name__ == "__main__":
    main()
