"""
ContextFuse – Three working scenarios.

1. stale_db_endpoint   – Old runbook vs new config conflict
2. missing_health       – Missing deployment health evidence
3. clean_context        – All evidence agrees, safe to proceed
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Callable

from app.schemas.evidence import (
    ContextBundle,
    EvidenceRecord,
    EvidenceSource,
    RiskSignal,
    ConflictState,
)
from app.schemas.decision import Action

# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _ago(**kwargs) -> datetime:
    return datetime.now(timezone.utc) - timedelta(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 – Stale database endpoint (conflict)
# ─────────────────────────────────────────────────────────────────────────────

def _build_stale_db_scenario() -> ContextBundle:
    ev_runbook = EvidenceRecord(
        source=EvidenceSource.RUNBOOK,
        source_path="runbooks/checkout-service/database.md",
        field="db_endpoint",
        value="db-old.internal",
        recorded_at=_ago(days=45),
        provenance=["confluence", "runbook-sync-v2"],
        notes="Original runbook entry, never updated after migration",
    )
    ev_config = EvidenceRecord(
        source=EvidenceSource.CONFIG_SNAPSHOT,
        source_path="configs/checkout-service/prod.yaml#database.host",
        field="db_endpoint",
        value="db-new.internal",
        recorded_at=_ago(hours=3),
        provenance=["terraform-apply", "config-store-v3"],
        notes="Current authoritative config from Terraform-managed config store",
    )
    ev_change = EvidenceRecord(
        source=EvidenceSource.CHANGE_EVENT,
        source_path="changefeed/events/chg-20240918-db-migration",
        field="db_endpoint",
        value={"from": "db-old.internal", "to": "db-new.internal"},
        recorded_at=_ago(hours=4),
        provenance=["change-management-api", "migration-pipeline"],
        notes="Recorded during planned database migration – approved change #CHG-0918",
    )

    # Mark the runbook evidence as conflicting
    ev_runbook.conflict_state = ConflictState.CONFLICT
    ev_runbook.conflict_with = [ev_config.evidence_id, ev_change.evidence_id]
    ev_config.conflict_state = ConflictState.SUPERSEDED  # supersedes runbook

    risk = RiskSignal(
        risk_id="risk-001",
        risk_type="conflict",
        severity="high",
        description=(
            "Runbook asserts db_endpoint=db-old.internal but current config and change "
            "event both record db-new.internal. Agent action based on runbook would "
            "target the decommissioned endpoint."
        ),
        implicated_evidence=[
            ev_runbook.evidence_id,
            ev_config.evidence_id,
            ev_change.evidence_id,
        ],
    )

    return ContextBundle(
        scenario_id="stale_db_endpoint",
        scenario_name="Stale Database Endpoint",
        scenario_description=(
            "The checkout-service runbook references a decommissioned database endpoint. "
            "A newer config snapshot and a change event both record the current endpoint. "
            "ContextFuse must detect the conflict and select a safe action before any "
            "agent proceeds."
        ),
        evidence=[ev_runbook, ev_config, ev_change],
        risks=[risk],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 – Missing deployment health evidence
# ─────────────────────────────────────────────────────────────────────────────

def _build_missing_health_scenario() -> ContextBundle:
    from app.schemas.evidence import FreshnessState

    ev_deploy_log = EvidenceRecord(
        source=EvidenceSource.DEPLOYMENT_LOG,
        source_path="deployments/checkout-service/deploy-20241022-v2.3.1",
        field="deploy_status",
        value="completed",
        recorded_at=_ago(minutes=12),
        provenance=["argocd", "deploy-pipeline"],
        notes="Deployment finished 12 minutes ago",
    )
    # Monitoring alert shows degraded state – no fresh health check to confirm
    ev_alert = EvidenceRecord(
        source=EvidenceSource.MONITORING_ALERT,
        source_path="alertmanager/alerts/alert-svc-latency-p99",
        field="service_latency_p99_ms",
        value=4200,
        recorded_at=_ago(minutes=8),
        provenance=["prometheus", "alertmanager"],
        notes="P99 latency spiked above 3000 ms SLA immediately after deploy",
    )
    # Health check evidence is stale / absent – explicitly modelled as missing
    ev_health_missing = EvidenceRecord(
        source=EvidenceSource.HEALTH_CHECK,
        source_path="healthcheck/checkout-service/latest",
        field="health_status",
        value=None,
        recorded_at=_ago(hours=6),
        provenance=["health-probe-cron"],
        notes="Last successful health check ran 6 hours ago — no post-deploy probe result yet",
    )
    ev_health_missing.conflict_state = ConflictState.MISSING

    risk_missing = RiskSignal(
        risk_id="risk-002a",
        risk_type="missing",
        severity="high",
        description=(
            "No post-deployment health check result exists. Cannot confirm the service "
            "is healthy following deploy v2.3.1."
        ),
        implicated_evidence=[ev_health_missing.evidence_id],
    )
    risk_latency = RiskSignal(
        risk_id="risk-002b",
        risk_type="missing",
        severity="high",
        description=(
            "Active alert: P99 latency at 4200 ms exceeds 3000 ms SLA. Post-deployment "
            "health check verification is missing to confirm runtime health."
        ),
        implicated_evidence=[ev_deploy_log.evidence_id, ev_alert.evidence_id],
    )

    return ContextBundle(
        scenario_id="missing_health",
        scenario_name="Missing Deployment Health Evidence",
        scenario_description=(
            "The checkout-service was recently deployed (v2.3.1). A monitoring alert "
            "reports elevated P99 latency. No post-deploy health check evidence exists. "
            "ContextFuse must detect the missing evidence and block unsafe progression."
        ),
        evidence=[ev_deploy_log, ev_alert, ev_health_missing],
        risks=[risk_missing, risk_latency],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 – Clean context (evidence agrees, safe to proceed)
# ─────────────────────────────────────────────────────────────────────────────

def _build_clean_context_scenario() -> ContextBundle:
    ev_config = EvidenceRecord(
        source=EvidenceSource.CONFIG_SNAPSHOT,
        source_path="configs/checkout-service/prod.yaml",
        field="db_endpoint",
        value="db-primary.internal",
        recorded_at=_ago(minutes=20),
        provenance=["terraform-apply", "config-store-v3"],
    )
    ev_runbook = EvidenceRecord(
        source=EvidenceSource.RUNBOOK,
        source_path="runbooks/checkout-service/database.md",
        field="db_endpoint",
        value="db-primary.internal",
        recorded_at=_ago(hours=2),
        provenance=["confluence", "runbook-sync-v2"],
        notes="Runbook updated after last migration",
    )
    ev_health = EvidenceRecord(
        source=EvidenceSource.HEALTH_CHECK,
        source_path="healthcheck/checkout-service/latest",
        field="health_status",
        value="healthy",
        recorded_at=_ago(minutes=5),
        provenance=["health-probe-cron"],
    )
    ev_deploy = EvidenceRecord(
        source=EvidenceSource.DEPLOYMENT_LOG,
        source_path="deployments/checkout-service/deploy-20241022-v2.2.9",
        field="deploy_status",
        value="completed",
        recorded_at=_ago(hours=3),
        provenance=["argocd"],
        notes="Stable deploy, no alerts since",
    )

    return ContextBundle(
        scenario_id="clean_context",
        scenario_name="Clean Context — Evidence Agrees",
        scenario_description=(
            "All evidence sources agree on the database endpoint and service health. "
            "No conflicts or missing records detected. ContextFuse confirms context "
            "safety and allows the agent to proceed."
        ),
        evidence=[ev_config, ev_runbook, ev_health, ev_deploy],
        risks=[],
        is_safe=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO_BUILDERS: dict[str, Callable[[], ContextBundle]] = {
    "stale_db_endpoint": _build_stale_db_scenario,
    "missing_health": _build_missing_health_scenario,
    "clean_context": _build_clean_context_scenario,
}

GROUND_TRUTH_ACTIONS: dict[str, Action] = {
    "stale_db_endpoint": Action.ESCALATE,
    "missing_health": Action.VERIFY,
    "clean_context": Action.PROCEED,
}


def load_scenario(scenario_id: str) -> ContextBundle:
    if scenario_id == "missing_health_evidence":
        scenario_id = "missing_health"
    builder = SCENARIO_BUILDERS.get(scenario_id)
    if builder is None:
        raise ValueError(f"Unknown scenario: {scenario_id!r}")
    return builder()


def list_scenarios() -> list[dict]:
    return [
        {
            "id": sid,
            "name": load_scenario(sid).scenario_name,
            "description": load_scenario(sid).scenario_description,
            "ground_truth_action": GROUND_TRUTH_ACTIONS[sid].value,
        }
        for sid in SCENARIO_BUILDERS
    ]
