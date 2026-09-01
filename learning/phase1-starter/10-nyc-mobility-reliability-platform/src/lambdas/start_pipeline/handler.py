"""Validate a pipeline request and start a deterministic Step Functions execution."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]
PROJECT_NAME = os.getenv("PROJECT_NAME", "nyc-mobility-reliability")
STEP_FUNCTIONS = boto3.client("stepfunctions")
VALID_MODES = {"monthly", "backfill", "reprocess"}


def _previous_month(now: datetime) -> tuple[int, int]:
    """Return the previous calendar month in UTC."""
    if now.month == 1:
        return now.year - 1, 12
    return now.year, now.month - 1


def _parse_period(event: dict[str, Any], now: datetime) -> tuple[int, int]:
    """Read and validate a requested period, defaulting to the prior month."""
    if "year" not in event and "month" not in event:
        return _previous_month(now)
    if "year" not in event or "month" not in event:
        raise ValueError("year and month must be supplied together")

    year = int(event["year"])
    month = int(event["month"])
    if year < 2019 or year > now.year:
        raise ValueError(f"year must be between 2019 and {now.year}")
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    if (year, month) > (now.year, now.month):
        raise ValueError("future source periods are not allowed")
    return year, month


def _execution_name(
    mode: str,
    year: int,
    month: int,
    requested_run_id: str | None,
    now: datetime,
) -> tuple[str, str]:
    """Build an execution name and run ID safe for Step Functions."""
    period = f"{year:04d}-{month:02d}"
    if mode == "reprocess":
        suffix = requested_run_id or now.strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{period}-reprocess-{suffix}"
    else:
        run_id = requested_run_id or f"{period}-{mode}"

    raw_name = f"{PROJECT_NAME}-{run_id}"
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "-", raw_name)[:80].rstrip("-")
    if not safe_name:
        raise ValueError("execution name was empty after validation")
    return safe_name, run_id


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Start one monthly, backfill, or explicit reprocessing execution."""
    now = datetime.now(timezone.utc)
    mode = str(event.get("mode", "monthly")).lower()
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")

    year, month = _parse_period(event, now)
    requested_run_id = event.get("run_id")
    execution_name, run_id = _execution_name(
        mode,
        year,
        month,
        str(requested_run_id) if requested_run_id else None,
        now,
    )
    payload = {
        "mode": mode,
        "year": f"{year:04d}",
        "month": f"{month:02d}",
        "run_id": run_id,
        "force": "true" if mode == "reprocess" else "false",
        "requested_at": now.isoformat(),
        "stages": {},
    }

    try:
        response = STEP_FUNCTIONS.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(payload, separators=(",", ":")),
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ExecutionAlreadyExists":
            LOGGER.info(
                json.dumps(
                    {
                        "event": "duplicate_execution_skipped",
                        "execution_name": execution_name,
                        "source_period": f"{year:04d}-{month:02d}",
                    }
                )
            )
            return {
                "status": "DUPLICATE_SKIPPED",
                "execution_name": execution_name,
                "run_id": run_id,
            }
        raise

    result = {
        "status": "STARTED",
        "execution_arn": response["executionArn"],
        "execution_name": execution_name,
        "run_id": run_id,
        "source_period": f"{year:04d}-{month:02d}",
    }
    LOGGER.info(json.dumps({"event": "pipeline_started", **result}))
    return result
