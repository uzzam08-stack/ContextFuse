"""
ContextFuse – Amazon Bedrock Converse API client.

API contract (verified):
  bedrock-runtime.converse(
      modelId=str,
      messages=[{role, content: [{text}]}],
      system=[{text}],
      inferenceConfig={maxTokens, temperature}
  )
  → {output: {message: {role, content: [{text}]}}, stopReason, usage, metrics}

Rules:
  1. Never simulate a successful Bedrock call.
  2. If Bedrock is unavailable, return OutcomeBrief with is_bedrock_available=False
     and a clear fallback_note.
  3. Always cite actual evidence IDs in the prompt so Bedrock grounds its output.
"""

from __future__ import annotations

import json
import time
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.decision import Action, DeciderResult, OutcomeBrief, SafetyVerdict
from app.schemas.evidence import ContextBundle


class BedrockSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_region: str = "us-east-1"
    bedrock_model_id: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"


_settings = BedrockSettings()


def check_bedrock_status() -> dict[str, Any]:
    """Check AWS credentials and Bedrock configuration without printing secrets."""
    try:
        session = boto3.Session(region_name=_settings.aws_region)
        creds = session.get_credentials()
        has_creds = creds is not None
    except Exception:
        has_creds = False

    return {
        "credentials_configured": has_creds,
        "region": _settings.aws_region,
        "model_id": _settings.bedrock_model_id,
        "status": "CONFIGURED BUT UNVERIFIED" if has_creds else "LOCAL FALLBACK",
        "note": (
            "AWS credentials configured via standard credential chain."
            if has_creds
            else "No AWS credentials detected in environment. Deterministic grounded explanation fallback active."
        ),
    }


def _build_bedrock_prompt(
    bundle: ContextBundle,
    decider_result: DeciderResult,
    safety_verdict: SafetyVerdict,
    tool_output: Any | None,
) -> str:
    """
    Build a structured prompt that forces Bedrock to cite actual evidence IDs
    and produce a grounded, evidence-anchored explanation.
    """
    evidence_block = "\n".join(
        f"  - [{ev.evidence_id}] source={ev.source.value}, field={ev.field}, "
        f"value={ev.value!r}, freshness={ev.freshness.value}, "
        f"conflict={ev.conflict_state.value}"
        for ev in bundle.evidence
    )
    risk_block = "\n".join(
        f"  - [{r.risk_id}] {r.risk_type}/{r.severity}: {r.description}"
        for r in bundle.risks
    ) or "  None"

    decider_note = (
        f"⚠ FALLBACK (Decider unavailable — reason: {decider_result.fallback_reason})"
        if decider_result.is_fallback
        else f"Decider selected: {decider_result.selected_action.value} "
        f"(confidence={decider_result.confidence:.2%})"
    )

    tool_block = (
        f"  Tool '{tool_output.tool_name}' returned: {json.dumps(tool_output.output)}"
        if tool_output
        else "  No tool was invoked."
    )

    return f"""You are ContextFuse, an AI context-safety system for AI operations agents.

SCENARIO: {bundle.scenario_name}
{bundle.scenario_description}

EVIDENCE CORPUS (use these IDs when citing evidence):
{evidence_block}

DETECTED RISKS:
{risk_block}

DECISION MODEL OUTPUT:
  {decider_note}

SAFETY POLICY VERDICT:
  Action: {safety_verdict.action.value} | Permitted: {safety_verdict.permitted}
  Policy rule: {safety_verdict.policy_rule}

TOOL INVOCATION RESULT:
{tool_block}

TASK:
Write a concise Outcome Brief (3–5 sentences) that:
1. States the final safety status clearly.
2. Cites specific evidence by their IDs (e.g. [ev-abc123def456]) to justify the conclusion.
3. Lists any unresolved risks by their risk IDs.
4. Explains what a human operator should do next, if anything.

Do NOT invent evidence or risk IDs. Only cite IDs that appear above.
Respond ONLY with a JSON object matching exactly this schema:
{{
  "summary": "<3-5 sentence evidence-grounded explanation>",
  "cited_evidence_ids": ["<ev-id>", ...],
  "unresolved_risks": ["<risk-id>", ...],
  "safety_status": "<safe|unsafe|escalated|abstained>"
}}"""


def call_bedrock(
    bundle: ContextBundle,
    decider_result: DeciderResult,
    safety_verdict: SafetyVerdict,
    tool_output: Any | None = None,
) -> OutcomeBrief:
    """
    Call Amazon Bedrock Converse API to generate an evidence-grounded explanation.
    Returns OutcomeBrief — real result or honest fallback, never simulated success.
    """
    prompt = _build_bedrock_prompt(bundle, decider_result, safety_verdict, tool_output)

    try:
        client = boto3.client("bedrock-runtime", region_name=_settings.aws_region)
        t0 = time.monotonic()

        response = client.converse(
            modelId=_settings.bedrock_model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=[
                {
                    "text": (
                        "You are a precise AI safety analyst. Always respond with valid JSON only. "
                        "Never add markdown fences or commentary outside the JSON object."
                    )
                }
            ],
            inferenceConfig={"maxTokens": 512, "temperature": 0.1},
        )
        latency_ms = (time.monotonic() - t0) * 1000

        # Extract text from response
        content_blocks = response["output"]["message"]["content"]
        raw_text = next(
            (block["text"] for block in content_blocks if "text" in block), "{}"
        )

        # Strip markdown fences if present
        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()

        # Parse JSON response from Bedrock
        try:
            parsed = json.loads(clean_text)
        except json.JSONDecodeError:
            # Bedrock responded but JSON was malformed
            return OutcomeBrief(
                summary=raw_text[:500],
                cited_evidence_ids=[ev.evidence_id for ev in bundle.evidence],
                unresolved_risks=[r.risk_id for r in bundle.risks],
                safety_status="unsafe" if bundle.risks else "safe",
                bedrock_model_id=_settings.bedrock_model_id,
                bedrock_latency_ms=round(latency_ms, 1),
                is_bedrock_available=True,
                fallback_note="Bedrock responded but output was not valid JSON — raw text preserved.",
                raw_bedrock_response=response,
            )

        return OutcomeBrief(
            summary=parsed.get("summary", ""),
            cited_evidence_ids=parsed.get("cited_evidence_ids", []),
            unresolved_risks=parsed.get("unresolved_risks", []),
            safety_status=parsed.get("safety_status", "unsafe"),
            bedrock_model_id=_settings.bedrock_model_id,
            bedrock_latency_ms=round(latency_ms, 1),
            is_bedrock_available=True,
            raw_bedrock_response={
                "stop_reason": response.get("stopReason"),
                "usage": response.get("usage"),
                "metrics": response.get("metrics"),
            },
        )

    except (BotoCoreError, ClientError) as exc:
        return _bedrock_fallback(bundle, safety_verdict, reason=str(exc))
    except Exception as exc:
        return _bedrock_fallback(
            bundle, safety_verdict, reason=f"{type(exc).__name__}: {exc}"
        )


def _bedrock_fallback(
    bundle: ContextBundle,
    safety_verdict: SafetyVerdict,
    reason: str,
) -> OutcomeBrief:
    """
    Deterministic fallback used ONLY when Bedrock is unavailable.
    Always clearly marked — never presented as a Bedrock result.
    """
    status_map = {
        Action.PROCEED: "safe",
        Action.VERIFY: "unsafe",
        Action.RETRIEVE: "unsafe",
        Action.ESCALATE: "escalated",
        Action.ABSTAIN: "abstained",
        Action.BLOCK: "blocked",
    }
    safety_status = status_map.get(safety_verdict.action, "unsafe")
    risk_ids = [r.risk_id for r in bundle.risks]
    ev_ids = [ev.evidence_id for ev in bundle.evidence]

    summary = (
        f"[BEDROCK UNAVAILABLE — DETERMINISTIC FALLBACK] "
        f"Scenario '{bundle.scenario_name}' was evaluated with {len(bundle.evidence)} evidence records. "
        f"{len(bundle.risks)} risk(s) were detected by the rule engine. "
        f"Safety policy verdict: {safety_verdict.action.value} — {safety_verdict.explanation} "
        + (f"Recommended step: {safety_verdict.safe_next_step} " if safety_verdict.safe_next_step else "")
        + f"Bedrock could not be reached to provide an evidence-grounded explanation: {reason[:150]}."
    )

    return OutcomeBrief(
        summary=summary,
        cited_evidence_ids=ev_ids,
        unresolved_risks=risk_ids,
        safety_status=safety_status,
        bedrock_model_id=None,
        bedrock_latency_ms=None,
        is_bedrock_available=False,
        fallback_note=reason,
    )
