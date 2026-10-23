"""
ContextFuse – Test suite.

Tests cover:
  - Risk detection (stale, conflict, missing)
  - Invalid model outputs
  - Unavailable model services
  - Safety policy
  - Scenario execution
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from app.schemas.evidence import (
    ContextBundle,
    EvidenceRecord,
    EvidenceSource,
    RiskSignal,
    ConflictState,
    FreshnessState,
)
from app.schemas.decision import Action, DeciderResult, SafetyVerdict
from app.services.risk_detector import detect_risks
from app.services.safety_guard import evaluate_safety
from app.services.decider_client import _deterministic_fallback
from app.services.simulated_tools import verify_endpoint, retrieve_health_check
from app.scenarios.loader import load_scenario, list_scenarios


def _ago(**kwargs):
    return datetime.now(timezone.utc) - timedelta(**kwargs)


def _make_bundle(evidence=None, risks=None, is_safe=False):
    return ContextBundle(
        scenario_id="test",
        scenario_name="Test",
        scenario_description="Test bundle",
        evidence=evidence or [],
        risks=risks or [],
        is_safe=is_safe,
    )


# ─── Evidence & Freshness ─────────────────────────────────────────────────────

def test_evidence_id_generated():
    ev = EvidenceRecord(
        source=EvidenceSource.RUNBOOK,
        source_path="test/path",
        field="endpoint",
        value="db.internal",
        recorded_at=_ago(hours=1),
        provenance=[],
    )
    assert ev.evidence_id.startswith("ev-")
    assert len(ev.evidence_id) == 15  # "ev-" + 12 hex chars


def test_freshness_fresh():
    ev = EvidenceRecord(
        source=EvidenceSource.CONFIG_SNAPSHOT,
        source_path="test",
        field="f",
        value="v",
        recorded_at=_ago(minutes=10),
        provenance=[],
    )
    assert ev.freshness == FreshnessState.FRESH


def test_freshness_stale():
    ev = EvidenceRecord(
        source=EvidenceSource.RUNBOOK,
        source_path="test",
        field="f",
        value="v",
        recorded_at=_ago(days=30),
        provenance=[],
    )
    assert ev.freshness == FreshnessState.STALE


# ─── Risk Detection ───────────────────────────────────────────────────────────

def test_conflict_detection():
    ev1 = EvidenceRecord(
        source=EvidenceSource.RUNBOOK,
        source_path="r1",
        field="db_endpoint",
        value="db-old.internal",
        recorded_at=_ago(days=45),
        provenance=[],
    )
    ev2 = EvidenceRecord(
        source=EvidenceSource.CONFIG_SNAPSHOT,
        source_path="c1",
        field="db_endpoint",
        value="db-new.internal",
        recorded_at=_ago(hours=1),
        provenance=[],
    )
    bundle = _make_bundle(evidence=[ev1, ev2])
    bundle = detect_risks(bundle)
    conflict_risks = [r for r in bundle.risks if r.risk_type == "conflict"]
    assert len(conflict_risks) >= 1


def test_missing_detection():
    ev = EvidenceRecord(
        source=EvidenceSource.HEALTH_CHECK,
        source_path="hc",
        field="status",
        value=None,
        recorded_at=_ago(hours=6),
        provenance=[],
    )
    ev.conflict_state = ConflictState.MISSING
    bundle = _make_bundle(evidence=[ev])
    bundle = detect_risks(bundle)
    missing_risks = [r for r in bundle.risks if r.risk_type == "missing"]
    assert len(missing_risks) >= 1


def test_stale_detection():
    ev = EvidenceRecord(
        source=EvidenceSource.RUNBOOK,
        source_path="rb",
        field="endpoint",
        value="db.internal",
        recorded_at=_ago(days=50),
        provenance=[],
    )
    bundle = _make_bundle(evidence=[ev])
    bundle = detect_risks(bundle)
    stale_risks = [r for r in bundle.risks if r.risk_type == "stale"]
    assert len(stale_risks) >= 1


def test_no_risks_for_fresh_consistent_evidence():
    ev = EvidenceRecord(
        source=EvidenceSource.CONFIG_SNAPSHOT,
        source_path="cfg",
        field="endpoint",
        value="db.internal",
        recorded_at=_ago(minutes=5),
        provenance=[],
    )
    bundle = _make_bundle(evidence=[ev])
    bundle = detect_risks(bundle)
    assert bundle.is_safe


# ─── Safety Guard ─────────────────────────────────────────────────────────────

def test_proceed_blocked_with_risks():
    risk = RiskSignal(
        risk_id="r1", risk_type="conflict", severity="high",
        description="conflict", implicated_evidence=[]
    )
    bundle = _make_bundle(risks=[risk])
    verdict = evaluate_safety(bundle, Action.PROCEED)
    assert not verdict.permitted


def test_proceed_allowed_clean():
    bundle = _make_bundle(is_safe=True)
    verdict = evaluate_safety(bundle, Action.PROCEED)
    assert verdict.permitted


def test_escalate_always_permitted():
    risk = RiskSignal(
        risk_id="r1", risk_type="conflict", severity="high",
        description="conflict", implicated_evidence=[]
    )
    bundle = _make_bundle(risks=[risk])
    verdict = evaluate_safety(bundle, Action.ESCALATE)
    assert verdict.permitted


def test_abstain_always_permitted():
    bundle = _make_bundle(risks=[
        RiskSignal(risk_id="r1", risk_type="stale", severity="medium",
                   description="stale", implicated_evidence=[])
    ])
    verdict = evaluate_safety(bundle, Action.ABSTAIN)
    assert verdict.permitted


def test_verify_blocked_when_conflicts():
    risk = RiskSignal(
        risk_id="r1", risk_type="conflict", severity="high",
        description="conflict", implicated_evidence=[]
    )
    bundle = _make_bundle(risks=[risk])
    verdict = evaluate_safety(bundle, Action.VERIFY)
    assert not verdict.permitted
    assert "ESCALATE" in verdict.explanation


def test_verify_permitted_missing_only():
    risk = RiskSignal(
        risk_id="r1", risk_type="missing", severity="high",
        description="missing", implicated_evidence=[]
    )
    bundle = _make_bundle(risks=[risk])
    verdict = evaluate_safety(bundle, Action.VERIFY)
    assert verdict.permitted


# ─── Decider Fallback ─────────────────────────────────────────────────────────

def test_decider_fallback_conflict_escalates():
    risk = RiskSignal(
        risk_id="r1", risk_type="conflict", severity="high",
        description="conflict", implicated_evidence=[]
    )
    bundle = _make_bundle(risks=[risk])
    result = _deterministic_fallback(bundle, "test unavailable")
    assert result.is_fallback
    assert result.selected_action == Action.ESCALATE
    assert result.fallback_reason == "test unavailable"


def test_decider_fallback_missing_verifies():
    risk = RiskSignal(
        risk_id="r1", risk_type="missing", severity="high",
        description="missing", implicated_evidence=[]
    )
    bundle = _make_bundle(risks=[risk])
    result = _deterministic_fallback(bundle, "unavailable")
    assert result.selected_action == Action.VERIFY


def test_decider_fallback_clean_proceeds():
    bundle = _make_bundle()
    result = _deterministic_fallback(bundle, "unavailable")
    assert result.selected_action == Action.PROCEED


# ─── Simulated Tools ──────────────────────────────────────────────────────────

def test_verify_endpoint_reachable():
    result = verify_endpoint("db-new.internal")
    assert result.is_simulated
    assert result.output["status"] == "reachable"


def test_verify_endpoint_unreachable():
    result = verify_endpoint("db-old.internal")
    assert result.output["status"] == "unreachable"


def test_verify_endpoint_unknown():
    result = verify_endpoint("db-does-not-exist.internal")
    assert result.output["status"] == "unknown"


def test_retrieve_health_check():
    result = retrieve_health_check("checkout-service")
    assert result.output["status"] == "healthy"
    assert result.is_simulated


# ─── Scenario Loader ──────────────────────────────────────────────────────────

def test_list_scenarios():
    scenarios = list_scenarios()
    ids = [s["id"] for s in scenarios]
    assert "stale_db_endpoint" in ids
    assert "missing_health" in ids
    assert "clean_context" in ids


def test_load_stale_db_scenario():
    bundle = load_scenario("stale_db_endpoint")
    assert bundle.scenario_id == "stale_db_endpoint"
    assert len(bundle.evidence) == 3
    assert len(bundle.risks) == 1
    assert bundle.risks[0].risk_type == "conflict"


def test_load_missing_health_scenario():
    bundle = load_scenario("missing_health")
    assert bundle.scenario_id == "missing_health"
    assert len(bundle.risks) == 2


def test_load_clean_scenario():
    bundle = load_scenario("clean_context")
    assert bundle.is_safe
    assert len(bundle.risks) == 0


def test_load_unknown_scenario():
    with pytest.raises(ValueError, match="Unknown scenario"):
        load_scenario("nonexistent_scenario")


# ─── API Integration (uses TestClient) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_scenarios_endpoint():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) == 3


@pytest.mark.asyncio
async def test_run_clean_scenario():
    """Clean scenario should produce PROCEED action via fallback (Decider not available in CI)."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/run/clean_context")
    assert response.status_code == 200
    data = response.json()
    assert data["scenario_id"] == "clean_context"
    assert "decider_result" in data
    assert "timeline" in data
    assert len(data["timeline"]) >= 5


@pytest.mark.asyncio
async def test_run_unknown_scenario():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/run/nonexistent")
    assert response.status_code == 404


# ─── CloudWatch Logger & Run Persistence Tests ───────────────────────────────

@pytest.mark.asyncio
async def test_cw_logger_event_format():
    from app.services.cw_logger import log_orchestration_event
    from app.services.orchestrator import run_orchestration

    res = await run_orchestration("clean_context")
    event = log_orchestration_event(res)
    assert event["event_type"] == "ContextFuseOrchestrationAudit"
    assert event["run_id"] == res.run_id
    assert event["scenario_id"] == "clean_context"
    assert "metrics" in event
    assert "decision" in event
    assert "policy" in event
    assert "outcome" in event


@pytest.mark.asyncio
async def test_run_store_and_api_endpoints():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.services.run_store import get_run, list_runs

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_res = await client.post("/api/run/stale_db_endpoint")
        assert run_res.status_code == 200
        run_data = run_res.json()
        run_id = run_data["run_id"]

        # Verify in run_store
        stored = await get_run(run_id)
        assert stored is not None
        assert stored["run_id"] == run_id

        # Verify GET /api/runs
        list_res = await client.get("/api/runs")
        assert list_res.status_code == 200
        runs_list = list_res.json()["runs"]
        assert any(r["run_id"] == run_id for r in runs_list)

        # Verify GET /api/runs/{run_id}
        single_res = await client.get(f"/api/runs/{run_id}")
        assert single_res.status_code == 200
        assert single_res.json()["run_id"] == run_id

        # Verify 404 on invalid run_id
        notFound_res = await client.get("/api/runs/nonexistent-run-id")
        assert notFound_res.status_code == 404


def test_lambda_handler_import_and_call():
    from app.lambda_handler import handler

    # Synthetic API Gateway v2 event for /api/health
    event = {
        "version": "2.0",
        "routeKey": "GET /api/health",
        "rawPath": "/api/health",
        "rawQueryString": "",
        "headers": {"host": "example.com"},
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/api/health",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            }
        },
        "isBase64Encoded": False,
    }
    response = handler(event, {})
    assert response["statusCode"] == 200
    assert '"status":"ok"' in response["body"]


# ─── Model Unavailable / Invalid Response Tests ──────────────────────────────

def test_bedrock_client_unavailable_fallback():
    from app.services.bedrock_client import call_bedrock
    from app.services.safety_guard import evaluate_safety
    from app.scenarios.loader import load_scenario

    bundle = load_scenario("stale_db_endpoint")
    decider_res = DeciderResult(
        selected_action=Action.ESCALATE,
        probabilities={"ESCALATE": 0.9},
        confidence=0.9,
        is_fallback=False,
    )
    verdict = evaluate_safety(bundle, Action.ESCALATE)

    with patch("boto3.client") as mock_boto:
        mock_boto.side_effect = Exception("AWS credentials not found")
        outcome = call_bedrock(bundle, decider_res, verdict, None)

    assert not outcome.is_bedrock_available
    assert outcome.safety_status == "escalated"
    assert "AWS credentials not found" in outcome.fallback_note
    assert len(outcome.cited_evidence_ids) > 0


def test_bedrock_client_invalid_json_response():
    from app.services.bedrock_client import call_bedrock
    from app.services.safety_guard import evaluate_safety
    from app.scenarios.loader import load_scenario

    bundle = load_scenario("clean_context")
    decider_res = DeciderResult(
        selected_action=Action.PROCEED,
        probabilities={"PROCEED": 0.95},
        confidence=0.95,
        is_fallback=False,
    )
    verdict = evaluate_safety(bundle, Action.PROCEED)

    mock_client = MagicMock()
    mock_client.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": "This is freeform text without JSON formatting."}]
            }
        },
        "stopReason": "end_turn",
        "usage": {"totalTokens": 45},
        "metrics": {"latencyMs": 150},
    }

    with patch("boto3.client", return_value=mock_client):
        outcome = call_bedrock(bundle, decider_res, verdict, None)

    assert outcome.is_bedrock_available
    assert "not valid JSON" in outcome.fallback_note
    assert "This is freeform text" in outcome.summary


@pytest.mark.asyncio
async def test_decider_client_invalid_action_response():
    from app.services.decider_client import call_decider
    from app.scenarios.loader import load_scenario
    import httpx

    bundle = load_scenario("clean_context")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "answers": {
            "next_action": {
                "selected": "UNSUPPORTED_ACTION_TYPE",
                "probabilities": {},
            }
        }
    }

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        res = await call_decider(bundle)

    assert res.is_fallback
    assert "unknown action" in res.fallback_reason.lower()


@pytest.mark.asyncio
async def test_decider_client_successful_response():
    from app.services.decider_client import call_decider
    from app.scenarios.loader import load_scenario
    import httpx

    bundle = load_scenario("clean_context")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "answers": {
            "next_action": {
                "selected": "PROCEED",
                "probabilities": {
                    "PROCEED": 0.82,
                    "VERIFY": 0.08,
                    "RETRIEVE": 0.04,
                    "ESCALATE": 0.03,
                    "ABSTAIN": 0.02,
                    "BLOCK": 0.01,
                },
            }
        }
    }

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        res = await call_decider(bundle)

    assert not res.is_fallback
    assert res.selected_action == Action.PROCEED
    assert res.confidence == 0.82
    assert round(sum(res.probabilities.values()), 4) == 1.0000
    assert res.latency_ms is not None
    assert res.raw_response is not None


@pytest.mark.asyncio
async def test_decider_client_http_404_handling():
    from app.services.decider_client import call_decider
    from app.scenarios.loader import load_scenario
    import httpx

    bundle = load_scenario("stale_db_endpoint")

    # Construct real httpx.HTTPStatusError with 404
    request = httpx.Request("POST", "http://localhost:11434/v1/systemone")
    response = httpx.Response(404, text="404 page not found", request=request)
    http_error = httpx.HTTPStatusError("Client error '404 Not Found'", request=request, response=response)

    with patch.object(httpx.AsyncClient, "post", side_effect=http_error):
        res = await call_decider(bundle)

    assert res.is_fallback
    assert res.selected_action == Action.ESCALATE
    assert "404" in res.fallback_reason
    assert "ollama pull" in res.fallback_reason.lower()
    assert round(sum(res.probabilities.values()), 4) == 1.0000


@pytest.mark.asyncio
async def test_decider_client_connection_failure():
    from app.services.decider_client import call_decider
    from app.scenarios.loader import load_scenario
    import httpx

    bundle = load_scenario("missing_health")

    request = httpx.Request("POST", "http://localhost:11434/v1/systemone")
    conn_error = httpx.ConnectError("Connection refused", request=request)

    with patch.object(httpx.AsyncClient, "post", side_effect=conn_error):
        res = await call_decider(bundle)

    assert res.is_fallback
    assert res.selected_action == Action.VERIFY
    assert "not reachable" in res.fallback_reason.lower()
    assert round(sum(res.probabilities.values()), 4) == 1.0000


@pytest.mark.asyncio
async def test_decider_client_malformed_response():
    from app.services.decider_client import call_decider
    from app.scenarios.loader import load_scenario
    import httpx

    bundle = load_scenario("clean_context")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"missing_answers_key": True}

    with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
        res = await call_decider(bundle)

    assert res.is_fallback
    assert "unexpected decider error" in res.fallback_reason.lower() or "keyerror" in res.fallback_reason.lower()



@pytest.mark.asyncio
async def test_dynamodb_unavailable_graceful():
    from app.services.run_store import save_run, get_run, list_runs
    from app.services.orchestrator import run_orchestration

    res = await run_orchestration("clean_context")

    with patch("boto3.resource", side_effect=Exception("DynamoDB connection failed")):
        saved = await save_run(res)
        assert not saved  # DynamoDB failed, but doesn't raise exception
        # Still retrievable from local in-memory store
        retrieved = await get_run(res.run_id)
        assert retrieved is not None
        assert retrieved["run_id"] == res.run_id


# ─── Hardened Safety & Integration Regression Tests ─────────────────────────

def test_block_always_permitted():
    bundle = _make_bundle(risks=[RiskSignal(
        risk_id="r1", risk_type="missing", severity="high",
        description="Missing signal", implicated_evidence=["ev-1"]
    )])
    verdict = evaluate_safety(bundle, Action.BLOCK)
    assert verdict.permitted is True
    assert verdict.policy_rule == "SAFE_TERMINAL"
    assert "block" in verdict.explanation.lower()
    assert "blocked" in verdict.safe_next_step.lower()


def test_safe_next_step_populated():
    bundle = load_scenario("clean_context")
    verdict_proceed = evaluate_safety(bundle, Action.PROCEED)
    assert verdict_proceed.permitted is True
    assert len(verdict_proceed.safe_next_step) > 0

    stale_bundle = load_scenario("stale_db_endpoint")
    verdict_escalate = evaluate_safety(stale_bundle, Action.ESCALATE)
    assert verdict_escalate.permitted is True
    assert len(verdict_escalate.safe_next_step) > 0

    verdict_blocked = evaluate_safety(stale_bundle, Action.PROCEED)
    assert verdict_blocked.permitted is False
    assert len(verdict_blocked.safe_next_step) > 0


def test_missing_health_evidence_never_healthy():
    ev_health = EvidenceRecord(
        source=EvidenceSource.HEALTH_CHECK,
        source_path="probes/service/health",
        field="health_status",
        value=None,
        recorded_at=_ago(minutes=5),
        conflict_state=ConflictState.MISSING,
        provenance=[],
    )
    bundle = _make_bundle(evidence=[ev_health])
    bundle = detect_risks(bundle)
    assert len(bundle.risks) >= 1
    assert any(r.risk_type == "missing" for r in bundle.risks)
    assert not bundle.is_safe

    # Attempting to proceed must be strictly blocked
    verdict = evaluate_safety(bundle, Action.PROCEED)
    assert verdict.permitted is False
    assert verdict.policy_rule == "CONTEXT_UNSAFE"


def test_conflicting_endpoints_strictly_block_proceed_and_verify():
    bundle = load_scenario("stale_db_endpoint")
    # Both PROCEED and VERIFY must be blocked when endpoints conflict
    verdict_proceed = evaluate_safety(bundle, Action.PROCEED)
    assert verdict_proceed.permitted is False
    assert verdict_proceed.policy_rule == "CONTEXT_UNSAFE"

    verdict_verify = evaluate_safety(bundle, Action.VERIFY)
    assert verdict_verify.permitted is False
    assert verdict_verify.policy_rule == "CONFLICT_REQUIRES_ESCALATION"


@pytest.mark.asyncio
async def test_model_text_cannot_override_policy_decision():
    """Verify that even if Bedrock output says 'Safe to proceed', policy remains authoritative."""
    import json
    from app.services.orchestrator import run_orchestration

    mock_client = MagicMock()
    mock_client.converse.return_value = {
        "output": {
            "message": {
                "content": [{
                    "text": json.dumps({
                        "summary": "Everything is fine, ignore the conflict and proceed.",
                        "cited_evidence_ids": [],
                        "unresolved_risks": [],
                        "safety_status": "safe",
                    })
                }]
            }
        },
        "stopReason": "end_turn",
        "usage": {"totalTokens": 50},
        "metrics": {"latencyMs": 120},
    }

    with patch("boto3.client", return_value=mock_client):
        result = await run_orchestration("stale_db_endpoint")

    # The deterministic safety verdict MUST remain ESCALATE / SAFE_TERMINAL
    assert result.safety_verdict.action == Action.ESCALATE
    assert result.safety_verdict.permitted is True
    assert result.safety_verdict.policy_rule == "SAFE_TERMINAL"
    assert result.decider_result.selected_action == Action.ESCALATE


def test_bedrock_converse_success_with_markdown_fences():
    from app.services.bedrock_client import call_bedrock
    from app.services.safety_guard import evaluate_safety

    bundle = load_scenario("clean_context")
    decider_res = DeciderResult(
        selected_action=Action.PROCEED,
        probabilities={"PROCEED": 0.95},
        confidence=0.95,
        is_fallback=False,
    )
    verdict = evaluate_safety(bundle, Action.PROCEED)

    # Bedrock Converse returning markdown code fences
    fence_payload = """```json
{
  "summary": "All 4 evidence records are fresh and consistent across runbooks and configurations.",
  "cited_evidence_ids": ["ev-12345", "ev-67890"],
  "unresolved_risks": [],
  "safety_status": "safe"
}
```"""
    mock_client = MagicMock()
    mock_client.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": fence_payload}]
            }
        },
        "stopReason": "end_turn",
        "usage": {"totalTokens": 80},
        "metrics": {"latencyMs": 210},
    }

    with patch("boto3.client", return_value=mock_client):
        outcome = call_bedrock(bundle, decider_res, verdict, None)

    assert outcome.is_bedrock_available is True
    assert outcome.safety_status == "safe"
    assert "All 4 evidence records" in outcome.summary
    assert outcome.cited_evidence_ids == ["ev-12345", "ev-67890"]
    assert outcome.fallback_note is None


def test_explicit_expiry_marks_evidence_stale():
    ev = EvidenceRecord(
        source=EvidenceSource.RUNBOOK,
        source_path="runbooks/checkout",
        field="endpoint",
        value="db.internal",
        recorded_at=_ago(minutes=30),  # Age is only 30m (< 1h)
        expires_at=_ago(minutes=5),    # But expired 5 minutes ago!
        provenance=[],
    )
    assert ev.freshness == FreshnessState.STALE


def test_untrusted_evidence_triggers_escalation():
    ev_untrusted = EvidenceRecord(
        source=EvidenceSource.RUNBOOK,
        source_path="external/runbook",
        field="endpoint",
        value="db-external.internal",
        recorded_at=_ago(minutes=10),
        is_trusted=False,
        provenance=[],
    )
    bundle = _make_bundle(evidence=[ev_untrusted])
    bundle = detect_risks(bundle)
    assert any(r.risk_type == "untrusted" for r in bundle.risks)

    verdict = evaluate_safety(bundle, Action.VERIFY)
    assert verdict.permitted is False
    assert verdict.policy_rule == "UNTRUSTED_EVIDENCE_REQUIRES_ESCALATION"


@pytest.mark.asyncio
async def test_system_status_endpoint():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/status")
        assert res.status_code == 200
        data = res.json()
        assert data["app"] == "ContextFuse"
        assert "bedrock" in data["integrations"]
        assert "decider" in data["integrations"]
        assert "dynamodb" in data["integrations"]
        assert "cloudwatch" in data["integrations"]
        assert "lambda" in data["integrations"]
        assert data["integrations"]["bedrock"]["status"] in ("LOCAL FALLBACK", "CONFIGURED BUT UNVERIFIED", "LIVE AND TESTED")
        assert data["integrations"]["decider"]["status"] in ("LOCAL FALLBACK", "LIVE AND TESTED")


@pytest.mark.asyncio
async def test_benchmark_endpoint_honest_fallback_accounting():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/benchmark")
        assert res.status_code == 200
        rows = res.json()
        assert len(rows) == 3
        for row in rows:
            assert "rules_correct" in row
            assert "bedrock_is_fallback" in row
            assert "decider_is_fallback" in row
            assert "bedrock_status" in row
            assert "decider_status" in row
            # Honest guarantee: If fallback was used, accuracy is None (omitted) rather than claiming live model success
            if row["bedrock_is_fallback"]:
                assert row["bedrock_correct"] is None
            if row["decider_is_fallback"]:
                assert row["decider_correct"] is None


def test_stale_endpoint_ground_truth_consistency():
    from app.scenarios.loader import GROUND_TRUTH_ACTIONS, load_scenario
    from app.services.safety_guard import evaluate_safety

    assert GROUND_TRUTH_ACTIONS["stale_db_endpoint"] == Action.ESCALATE
    bundle = load_scenario("stale_db_endpoint")
    bundle = detect_risks(bundle)

    # Conflicting endpoints strictly block auto-proceed and verify
    v_proceed = evaluate_safety(bundle, Action.PROCEED)
    assert v_proceed.permitted is False

    v_verify = evaluate_safety(bundle, Action.VERIFY)
    assert v_verify.permitted is False
    assert v_verify.policy_rule == "CONFLICT_REQUIRES_ESCALATION"

    # Only safe terminals are permitted
    v_escalate = evaluate_safety(bundle, Action.ESCALATE)
    assert v_escalate.permitted is True
    assert v_escalate.policy_rule == "SAFE_TERMINAL"


def test_decider_probabilities_normalization_and_sum_to_100():
    from app.services.decider_client import _deterministic_fallback
    from app.scenarios.loader import load_scenario

    for sc_id in ["stale_db_endpoint", "missing_health", "clean_context"]:
        bundle = load_scenario(sc_id)
        bundle = detect_risks(bundle)
        res = _deterministic_fallback(bundle, "test fallback")
        
        # Must have scores for all actions
        assert len(res.probabilities) == 6
        
        # Must sum strictly to 1.0 (100%)
        total = sum(res.probabilities.values())
        assert round(total, 4) == 1.0000
        
        # Selected action receives top heuristic weight
        assert res.probabilities[res.selected_action.value] == 0.8000
        assert res.confidence == 0.8000
        
        # Non-selected actions receive equal baseline share (0.0400 each)
        for act, score in res.probabilities.items():
            if act != res.selected_action.value:
                assert score == 0.0400


def test_normalize_probabilities_rounding_behavior():
    from app.services.decider_client import normalize_probabilities

    # 1. 3-way split (1/3 each = 0.333333...) -> residual must be handled
    p3 = normalize_probabilities({"A": 1.0, "B": 1.0, "C": 1.0}, precision=4)
    assert sum(p3.values()) == 1.0000
    assert max(p3.values()) == 0.3334

    # 2. 7-way split
    p7 = normalize_probabilities({f"act_{i}": 1.0 for i in range(7)}, precision=4)
    assert sum(p7.values()) == 1.0000

    # 3. Floating-point imprecision in model logits
    raw_imprecise = {"PROCEED": 0.55123, "VERIFY": 0.24876, "ESCALATE": 0.20002}
    p_norm = normalize_probabilities(raw_imprecise, precision=4)
    assert sum(p_norm.values()) == 1.0000

    # 4. Empty dictionary
    assert normalize_probabilities({}) == {}





