"""
ContextFuse – CloudWatch Structured Logging Service.

Emits structured JSON logs compatible with CloudWatch Insights, OpenSearch,
and Lambda CloudWatch log streams.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.schemas.decision import OrchestrationResult

logger = logging.getLogger("contextfuse.audit")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_orchestration_event(result: OrchestrationResult) -> dict[str, Any]:
    """
    Produce and emit a structured audit log entry for the orchestration run.
    """
    event = {
        "event_type": "ContextFuseOrchestrationAudit",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": result.run_id,
        "scenario_id": result.scenario_id,
        "metrics": {
            "evidence_count": result.evidence_count,
            "risk_count": result.risk_count,
            "decider_latency_ms": result.decider_result.latency_ms,
            "bedrock_latency_ms": result.outcome_brief.bedrock_latency_ms,
        },
        "decision": {
            "selected_action": result.decider_result.selected_action.value,
            "confidence": result.decider_result.confidence,
            "is_fallback": result.decider_result.is_fallback,
            "fallback_reason": result.decider_result.fallback_reason,
        },
        "policy": {
            "permitted": result.safety_verdict.permitted,
            "policy_rule": result.safety_verdict.policy_rule,
            "verdict_action": result.safety_verdict.action.value,
        },
        "outcome": {
            "safety_status": result.outcome_brief.safety_status,
            "cited_evidence_count": len(result.outcome_brief.cited_evidence_ids),
            "unresolved_risk_count": len(result.outcome_brief.unresolved_risks),
            "is_bedrock_available": result.outcome_brief.is_bedrock_available,
        },
    }

    logger.info(json.dumps(event))
    return event
