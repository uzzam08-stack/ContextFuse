"""
ContextFuse – Run Persistence Service.

Persists OrchestrationResult records to Amazon DynamoDB table (contextfuse-runs)
with in-memory fallback for local development and offline environments.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.schemas.decision import OrchestrationResult

logger = logging.getLogger("contextfuse.run_store")

TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "contextfuse-runs")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# In-memory LRU-like ring buffer for local/demo runs
_IN_MEMORY_RUNS: dict[str, dict[str, Any]] = {}
_MAX_LOCAL_RUNS = 100


def _get_dynamodb_resource():
    try:
        return boto3.resource("dynamodb", region_name=AWS_REGION)
    except Exception as exc:
        logger.debug("Could not instantiate DynamoDB resource: %s", exc)
        return None


async def save_run(result: OrchestrationResult) -> bool:
    """
    Save orchestration result. Always saves in memory, attempts DynamoDB if reachable.
    """
    result_dict = result.model_dump(mode="json")
    _IN_MEMORY_RUNS[result.run_id] = result_dict
    if len(_IN_MEMORY_RUNS) > _MAX_LOCAL_RUNS:
        oldest_key = next(iter(_IN_MEMORY_RUNS))
        _IN_MEMORY_RUNS.pop(oldest_key, None)

    # Persist to DynamoDB if configured
    dynamo = _get_dynamodb_resource()
    if not dynamo:
        return False

    try:
        table = dynamo.Table(TABLE_NAME)
        # Store full payload as serialized JSON to preserve complex nested types safely
        item = {
            "run_id": result.run_id,
            "scenario_id": result.scenario_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "selected_action": result.decider_result.selected_action.value,
            "safety_status": result.outcome_brief.safety_status,
            "is_fallback": result.decider_result.is_fallback,
            "payload": json.dumps(result_dict),
        }
        table.put_item(Item=item)
        logger.info("Saved run %s to DynamoDB table %s", result.run_id, TABLE_NAME)
        return True
    except (BotoCoreError, ClientError) as exc:
        logger.info(
            "DynamoDB table '%s' not accessible (%s). Run saved to in-memory store.",
            TABLE_NAME,
            exc.__class__.__name__,
        )
        return False
    except Exception as exc:
        logger.warning("Unexpected error saving run to DynamoDB: %s", exc)
        return False


async def get_run(run_id: str) -> dict[str, Any] | None:
    """
    Retrieve a specific run by run_id from memory or DynamoDB.
    """
    if run_id in _IN_MEMORY_RUNS:
        return _IN_MEMORY_RUNS[run_id]

    dynamo = _get_dynamodb_resource()
    if not dynamo:
        return None

    try:
        table = dynamo.Table(TABLE_NAME)
        response = table.get_item(Key={"run_id": run_id})
        item = response.get("Item")
        if item and "payload" in item:
            return json.loads(item["payload"])
        return item
    except Exception as exc:
        logger.warning("Error fetching run %s from DynamoDB: %s", run_id, exc)
        return None


async def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    """
    List recent orchestration runs (most recent first).
    Checks in-memory store; if empty, attempts DynamoDB scan.
    """
    if _IN_MEMORY_RUNS:
        runs = list(_IN_MEMORY_RUNS.values())
        runs.reverse()
        return runs[:limit]

    dynamo = _get_dynamodb_resource()
    if dynamo:
        try:
            table = dynamo.Table(TABLE_NAME)
            response = table.scan(Limit=limit)
            items = response.get("Items", [])
            parsed_runs = []
            for item in items:
                if "payload" in item:
                    parsed_runs.append(json.loads(item["payload"]))
                else:
                    parsed_runs.append(item)
            return parsed_runs
        except Exception as exc:
            logger.debug("Could not scan DynamoDB for runs: %s", exc)

    return []


def get_storage_status() -> dict[str, Any]:
    """Return status of storage backend for observability and honest UI status."""
    dynamo = _get_dynamodb_resource()
    dynamo_active = False
    if dynamo:
        try:
            client = boto3.client("dynamodb", region_name=AWS_REGION)
            client.describe_table(TableName=TABLE_NAME)
            dynamo_active = True
        except Exception:
            dynamo_active = False

    return {
        "mode": "dynamodb" if dynamo_active else "in_memory_fallback",
        "is_dynamodb_active": dynamo_active,
        "table_name": TABLE_NAME,
        "region": AWS_REGION,
        "in_memory_run_count": len(_IN_MEMORY_RUNS),
        "storage_note": (
            "Amazon DynamoDB active"
            if dynamo_active
            else "Using volatile in-memory ring buffer (DynamoDB table not connected)"
        ),
    }
