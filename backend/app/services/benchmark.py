"""
ContextFuse – Benchmark runner.

Compares three selection strategies on fixed scenarios:
  1. Rules-only       (deterministic risk detection → policy action)
  2. Bedrock-only     (Bedrock classifies the action without Decider)
  3. Decider-based    (Strands Decider 2B → safety policy)

Only measures results that actually ran — no synthetic accuracy scores.
"""

from __future__ import annotations

import time

import boto3
import json
from botocore.exceptions import BotoCoreError, ClientError

from app.scenarios.loader import load_scenario, GROUND_TRUTH_ACTIONS, SCENARIO_BUILDERS
from app.schemas.decision import Action, BenchmarkEntry
from app.schemas.evidence import ContextBundle
from app.services.risk_detector import detect_risks
from app.services.safety_guard import evaluate_safety


def _rules_only_action(bundle: ContextBundle) -> tuple[Action, float]:
    """Deterministic rule-based action selection."""
    t0 = time.monotonic()
    has_conflicts = any(r.risk_type == "conflict" for r in bundle.risks)
    has_missing = any(r.risk_type == "missing" for r in bundle.risks)
    has_risks = bool(bundle.risks)

    if has_conflicts:
        action = Action.ESCALATE
    elif has_missing:
        action = Action.VERIFY
    elif has_risks:
        action = Action.ABSTAIN
    else:
        action = Action.PROCEED

    latency_ms = (time.monotonic() - t0) * 1000
    return action, round(latency_ms, 3)


def _bedrock_only_action(bundle: ContextBundle) -> tuple[Action, float, bool, str]:
    """
    Use Bedrock Converse API to classify the action without Decider.
    Returns (action, latency_ms, is_fallback, status_string).
    Never reports a live success unless an authentic Bedrock call succeeds.
    """
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class _Cfg(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")
        aws_region: str = "us-east-1"
        bedrock_model_id: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

    cfg = _Cfg()
    evidence_block = "\n".join(
        f"  [{ev.evidence_id}] {ev.source.value}/{ev.field}={ev.value!r} "
        f"freshness={ev.freshness.value} conflict={ev.conflict_state.value}"
        for ev in bundle.evidence
    )
    risk_block = "\n".join(
        f"  [{r.risk_id}] {r.risk_type}/{r.severity}: {r.description}"
        for r in bundle.risks
    ) or "  None"

    prompt = (
        f"Given this AI agent context safety assessment:\n\n"
        f"Evidence:\n{evidence_block}\n\nRisks:\n{risk_block}\n\n"
        f"Select exactly one action from: PROCEED, VERIFY, ESCALATE, ABSTAIN, BLOCK.\n"
        f'Respond ONLY with a JSON object: {{"action": "<ACTION>"}}'
    )

    t0 = time.monotonic()
    try:
        session = boto3.Session(region_name=cfg.aws_region)
        if session.get_credentials() is None:
            raise RuntimeError("No AWS credentials configured in environment")

        client = session.client("bedrock-runtime", region_name=cfg.aws_region)
        response = client.converse(
            modelId=cfg.bedrock_model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 50, "temperature": 0.0},
        )
        latency_ms = (time.monotonic() - t0) * 1000
        raw = response["output"]["message"]["content"][0]["text"].strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        parsed = json.loads(raw)
        action = Action(parsed["action"].upper())
        return action, round(latency_ms, 1), False, "LIVE"
    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        # Bedrock unavailable — use rules baseline, clearly flagged as fallback
        action, _ = _rules_only_action(bundle)
        status_note = f"UNAVAILABLE ({type(exc).__name__})"
        return action, round(latency_ms, 1), True, status_note


async def run_benchmark() -> list[BenchmarkEntry]:
    """
    Run all scenarios through all three strategies and return comparison rows.
    
    POLICY RULE DOCUMENTATION FOR CONFLICTS:
    Conflicting evidence (such as decommissioned db-old.internal vs authoritative db-new.internal)
    strictly requires ESCALATE. Automated verification (VERIFY) cannot safely pick between conflicting
    records; human review is mandatory under safety policy CONFLICT_REQUIRES_ESCALATION.
    """
    from app.services.decider_client import call_decider

    results: list[BenchmarkEntry] = []

    for scenario_id in SCENARIO_BUILDERS:
        bundle = load_scenario(scenario_id)
        bundle = detect_risks(bundle)
        ground_truth = GROUND_TRUTH_ACTIONS[scenario_id]

        # Strategy 1: Rules only (deterministic safety policy)
        rules_action, rules_latency = _rules_only_action(bundle)

        # Strategy 2: Bedrock only
        bedrock_action, bedrock_latency, bedrock_is_fallback, bedrock_status = _bedrock_only_action(bundle)

        # Strategy 3: Decider (Strands Decider 2B + Safety Guard)
        t0 = time.monotonic()
        decider_result = await call_decider(bundle)
        decider_latency = (time.monotonic() - t0) * 1000
        safety = evaluate_safety(bundle, decider_result.selected_action)
        final_decider_action = decider_result.selected_action
        if not safety.permitted:
            has_conflicts = any(r.risk_type == "conflict" for r in bundle.risks)
            final_decider_action = Action.ESCALATE if has_conflicts else Action.ABSTAIN

        decider_is_fallback = decider_result.is_fallback
        decider_status = "LOCAL FALLBACK" if decider_is_fallback else "LIVE"

        results.append(
            BenchmarkEntry(
                scenario_id=scenario_id,
                scenario_name=bundle.scenario_name,
                rules_only_action=rules_action,
                bedrock_only_action=bedrock_action,
                decider_action=final_decider_action,
                ground_truth_action=ground_truth,
                rules_correct=rules_action == ground_truth,
                # Honest reporting: If fallback was used, do NOT report live model accuracy
                bedrock_correct=(bedrock_action == ground_truth) if not bedrock_is_fallback else None,
                decider_correct=(final_decider_action == ground_truth) if not decider_is_fallback else None,
                bedrock_is_fallback=bedrock_is_fallback,
                decider_is_fallback=decider_is_fallback,
                bedrock_status=bedrock_status,
                decider_status=decider_status,
                rules_latency_ms=round(rules_latency, 1),
                bedrock_latency_ms=round(bedrock_latency, 1),
                decider_latency_ms=round(decider_latency, 1),
            )
        )

    return results

