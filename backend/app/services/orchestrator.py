"""
ContextFuse – Main orchestration state machine.

Flow:
  1. Load scenario → ContextBundle
  2. Detect risks (deterministic)
  3. Call Strands Decider 2B → DeciderResult
  4. Evaluate safety policy → SafetyVerdict
  5. If permitted: invoke simulated read-only tool
  6. Call Amazon Bedrock → OutcomeBrief
  7. Assemble timeline + OrchestrationResult
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.scenarios.loader import load_scenario
from app.schemas.decision import (
    Action,
    OrchestrationResult,
    TimelineEvent,
)
from app.schemas.evidence import ContextBundle
from app.services.bedrock_client import call_bedrock
from app.services.cw_logger import log_orchestration_event
from app.services.decider_client import call_decider
from app.services.risk_detector import detect_risks
from app.services.run_store import save_run
from app.services.safety_guard import evaluate_safety
from app.services.simulated_tools import invoke_tool_for_action


async def run_orchestration(scenario_id: str) -> OrchestrationResult:
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    timeline: list[TimelineEvent] = []
    step = 0

    def _event(stage: str, label: str, detail: str, status: str, ev_ids: list[str] = None) -> TimelineEvent:
        nonlocal step
        step += 1
        return TimelineEvent(
            step=step,
            stage=stage,
            label=label,
            detail=detail,
            status=status,
            evidence_ids=ev_ids or [],
        )

    # ── Step 1: Load context ─────────────────────────────────────────────────
    try:
        bundle: ContextBundle = load_scenario(scenario_id)
    except ValueError as exc:
        raise ValueError(str(exc))

    timeline.append(_event(
        "context_load", "Context Loaded",
        f"Loaded {len(bundle.evidence)} evidence records for scenario '{bundle.scenario_name}'",
        "complete",
        [ev.evidence_id for ev in bundle.evidence],
    ))

    # ── Step 2: Risk detection ───────────────────────────────────────────────
    bundle = detect_risks(bundle)
    risk_status = "warning" if bundle.risks else "complete"
    timeline.append(_event(
        "risk_detection", "Risks Detected",
        f"{len(bundle.risks)} risk signal(s) detected: "
        + (", ".join(f"{r.risk_type}/{r.severity}" for r in bundle.risks) or "none"),
        risk_status,
        [eid for r in bundle.risks for eid in r.implicated_evidence],
    ))

    # ── Step 3: Strands Decider 2B ───────────────────────────────────────────
    decider_result = await call_decider(bundle)
    decider_status = "complete" if not decider_result.is_fallback else "warning"
    decider_label = (
        f"Decider → {decider_result.selected_action.value}"
        + (" [FALLBACK]" if decider_result.is_fallback else "")
    )
    timeline.append(_event(
        "decider", "Decider Decision",
        decider_label + (
            f" (confidence={decider_result.confidence:.0%})" if not decider_result.is_fallback
            else f" — {decider_result.fallback_reason}"
        ),
        decider_status,
    ))

    # ── Step 4: Safety policy ────────────────────────────────────────────────
    safety_verdict = evaluate_safety(bundle, decider_result.selected_action)
    
    # If policy blocks the action, escalate or block depending on risk nature
    if not safety_verdict.permitted:
        has_conflicts = any(r.risk_type == "conflict" for r in bundle.risks)
        has_untrusted = any(r.risk_type == "untrusted" for r in bundle.risks)
        override_action = Action.ESCALATE if (has_conflicts or has_untrusted) else Action.BLOCK
        safety_verdict = evaluate_safety(bundle, override_action)
        # Re-run Decider result to reflect override
        decider_result.selected_action = override_action
        decider_result.confidence = 0.0  # action was overridden

    policy_status = "complete" if safety_verdict.permitted else "error"
    timeline.append(_event(
        "safety_guard", "Policy Guard",
        f"Rule: {safety_verdict.policy_rule} → "
        f"{'Permitted' if safety_verdict.permitted else 'Blocked'}: {safety_verdict.explanation}",
        policy_status,
    ))

    # ── Step 5: Simulated tool ───────────────────────────────────────────────
    tool_result = None
    if safety_verdict.action in (Action.VERIFY, Action.RETRIEVE) and safety_verdict.permitted:
        tool_result = invoke_tool_for_action(safety_verdict.action, scenario_id)
        if tool_result:
            timeline.append(_event(
                "tool_call", f"Tool: {tool_result.tool_name}",
                f"[SIMULATED] {tool_result.tool_name}({tool_result.input_params}) "
                f"→ {tool_result.output}",
                "complete",
            ))

    # ── Step 6: Bedrock explanation ──────────────────────────────────────────
    outcome = call_bedrock(bundle, decider_result, safety_verdict, tool_result)
    bedrock_status = "complete" if outcome.is_bedrock_available else "warning"
    timeline.append(_event(
        "bedrock", "Bedrock Outcome Brief",
        f"{'Bedrock' if outcome.is_bedrock_available else '[FALLBACK]'}: "
        f"status={outcome.safety_status}, "
        f"cited {len(outcome.cited_evidence_ids)} evidence IDs",
        bedrock_status,
    ))

    # ── Step 7: Final outcome ────────────────────────────────────────────────
    timeline.append(_event(
        "outcome", "Final Outcome",
        f"Safety status: {outcome.safety_status.upper()} | "
        f"Action: {safety_verdict.action.value} | "
        f"Unresolved risks: {len(outcome.unresolved_risks)}",
        "complete" if outcome.safety_status in ("safe", "escalated", "abstained", "blocked") else "warning",
    ))

    result = OrchestrationResult(
        run_id=run_id,
        scenario_id=scenario_id,
        evidence_count=len(bundle.evidence),
        risk_count=len(bundle.risks),
        decider_result=decider_result,
        safety_verdict=safety_verdict,
        tool_result=tool_result,
        outcome_brief=outcome,
        timeline=timeline,
    )

    # ── Audit & Persistence ──────────────────────────────────────────────────
    log_orchestration_event(result)
    await save_run(result)

    return result
