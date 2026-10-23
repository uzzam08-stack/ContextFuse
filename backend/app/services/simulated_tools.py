"""
ContextFuse – Simulated read-only tools.

ALL tools are simulated — no production infrastructure is accessed.
This is enforced by design: functions never make real network calls.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from app.schemas.decision import Action, ToolCallResult


_SIMULATED_ENDPOINTS = {
    "db-new.internal": {
        "status": "reachable",
        "latency_ms": 12,
        "version": "PostgreSQL 15.4",
        "replica_lag_ms": 0,
    },
    "db-old.internal": {
        "status": "unreachable",
        "error": "Connection refused — endpoint decommissioned",
    },
    "db-primary.internal": {
        "status": "reachable",
        "latency_ms": 8,
        "version": "PostgreSQL 15.4",
        "replica_lag_ms": 0,
    },
}

_SIMULATED_HEALTH = {
    "checkout-service": {
        "status": "healthy",
        "uptime_s": 345600,
        "error_rate_pct": 0.01,
        "p99_latency_ms": 210,
    }
}


def verify_endpoint(endpoint: str) -> ToolCallResult:
    """
    Simulated DNS + connectivity check for a database endpoint.
    Returns the simulated reachability result.
    """
    result = _SIMULATED_ENDPOINTS.get(
        endpoint,
        {"status": "unknown", "error": f"No simulation data for endpoint '{endpoint}'"},
    )
    return ToolCallResult(
        tool_name="verify_endpoint",
        input_params={"endpoint": endpoint},
        output={
            "endpoint": endpoint,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            **result,
        },
        is_simulated=True,
    )


def retrieve_health_check(service_name: str) -> ToolCallResult:
    """
    Simulated retrieval of the latest health check result for a service.
    """
    result = _SIMULATED_HEALTH.get(
        service_name,
        {"status": "no_data", "error": f"No health data for service '{service_name}'"},
    )
    return ToolCallResult(
        tool_name="retrieve_health_check",
        input_params={"service": service_name},
        output={
            "service": service_name,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            **result,
        },
        is_simulated=True,
    )


def invoke_tool_for_action(
    action: Action,
    scenario_id: str,
) -> ToolCallResult | None:
    """
    Select and invoke the appropriate simulated tool based on the permitted action.
    Returns None if the action does not require a tool call.
    """
    tool_map: dict[str, dict[str, str]] = {
        "stale_db_endpoint": {"endpoint": "db-new.internal"},
        "missing_health": {"service": "checkout-service"},
        "missing_health_evidence": {"service": "checkout-service"},
        "clean_context": {"endpoint": "db-primary.internal"},
    }

    if action == Action.VERIFY:
        params = tool_map.get(scenario_id, {})
        if "endpoint" in params:
            return verify_endpoint(params["endpoint"])
        if "service" in params:
            return retrieve_health_check(params["service"])

    if action == Action.RETRIEVE:
        params = tool_map.get(scenario_id, {})
        if "service" in params:
            return retrieve_health_check(params["service"])

    return None
