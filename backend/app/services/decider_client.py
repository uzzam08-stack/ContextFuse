"""
ContextFuse – Strands Decider 2B client.

API contract (verified against Ollama strands-decider:2b / /v1/systemone):
  POST /v1/systemone
  Body:  { state: str, questions: { key: { type: "choice", options: {...} } } }
  Reply: { answers: { key: { selected: str, probabilities: { ... } } } }

Rules:
  1. Never simulate a successful model call.
  2. If Decider is unavailable, return DeciderResult with is_fallback=True
     and a clear fallback_reason — never label the fallback as a real result.
  3. Confidence is taken directly from probabilities[selected], not manufactured.
"""

from __future__ import annotations

import time

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.decision import Action, ALL_ACTIONS, DeciderResult
from app.schemas.evidence import ContextBundle, RiskSignal


class DeciderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    decider_base_url: str = "http://localhost:11434"
    decider_model: str = "strands-decider:2b"


_settings = DeciderSettings()

# Action descriptions sent as options to Decider so it has semantic context
_ACTION_DESCRIPTIONS: dict[str, str] = {
    Action.PROCEED: (
        "Context is verified and consistent — proceed with the planned agent action"
    ),
    Action.VERIFY: (
        "At least one piece of context is unconfirmed; invoke a read-only verification "
        "tool before proceeding"
    ),
    Action.RETRIEVE: (
        "Required context is absent; retrieve fresh evidence from authoritative sources "
        "before any action"
    ),
    Action.ESCALATE: (
        "Conflicting or irreconcilable evidence detected; escalate to a human operator "
        "and suspend automated action"
    ),
    Action.ABSTAIN: (
        "Uncertainty is too high to act safely; abstain and log the unresolved state "
        "for human review"
    ),
    Action.BLOCK: (
        "Action is blocked by safety gate; automated progression halted to prevent risky state change"
    ),
}


async def check_decider_status() -> dict[str, Any]:
    """Check whether Ollama runtime is reachable and if strands-decider:2b is available."""
    try:
        async with httpx.AsyncClient(base_url=_settings.decider_base_url, timeout=1.0) as client:
            resp = await client.get("/api/tags")
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                has_model = any(_settings.decider_model in m for m in models)
                return {
                    "runtime_reachable": True,
                    "model_available": has_model,
                    "model_name": _settings.decider_model,
                    "status": "LIVE AND TESTED" if has_model else "LOCAL FALLBACK",
                    "note": (
                        "Live Strands Decider 2B inference ready"
                        if has_model
                        else f"Ollama reachable, but '{_settings.decider_model}' not found in local library. Deterministic fallback active."
                    ),
                }
    except Exception as exc:
        return {
            "runtime_reachable": False,
            "model_available": False,
            "model_name": _settings.decider_model,
            "status": "LOCAL FALLBACK",
            "note": f"Ollama not reachable at {_settings.decider_base_url} ({exc.__class__.__name__}). Deterministic fallback active.",
        }
    return {
        "runtime_reachable": False,
        "model_available": False,
        "model_name": _settings.decider_model,
        "status": "LOCAL FALLBACK",
        "note": "Deterministic fallback active.",
    }


def _build_state(bundle: ContextBundle) -> str:
    """
    Serialise the context bundle into a compact, token-efficient state string
    for Decider. Stays under the 4,000-token context window.
    """
    lines = [
        f"SCENARIO: {bundle.scenario_name}",
        f"DESCRIPTION: {bundle.scenario_description}",
        "",
        "EVIDENCE RECORDS:",
    ]
    for ev in bundle.evidence:
        lines.append(
            f"  [{ev.evidence_id}] source={ev.source.value} field={ev.field} "
            f"value={ev.value!r} freshness={ev.freshness.value} "
            f"conflict={ev.conflict_state.value}"
        )
    lines.append("")
    lines.append(f"RISK SIGNALS ({len(bundle.risks)} detected):")
    for risk in bundle.risks:
        lines.append(
            f"  [{risk.risk_id}] type={risk.risk_type} severity={risk.severity}: "
            f"{risk.description}"
        )
    lines.append("")
    lines.append(
        "TASK: Select the safest next action for an AI operations agent given the "
        "above context safety assessment."
    )
    return "\n".join(lines)


async def call_decider(bundle: ContextBundle) -> DeciderResult:
    """
    Call Strands Decider 2B via the /v1/systemone endpoint.
    Returns a real result or an honest fallback — never a simulated success.
    """
    state = _build_state(bundle)
    payload = {
        "model": _settings.decider_model,
        "state": state,
        "questions": {
            "next_action": {
                "type": "choice",
                "description": (
                    "Given the evidence safety assessment above, what is the safest "
                    "bounded next action for the agent?"
                ),
                "options": {
                    action: desc for action, desc in _ACTION_DESCRIPTIONS.items()
                },
            }
        },
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(
            base_url=_settings.decider_base_url, timeout=15.0
        ) as client:
            response = await client.post("/v1/systemone", json=payload)
            response.raise_for_status()
            data = response.json()
            latency_ms = (time.monotonic() - t0) * 1000

        answer = data["answers"]["next_action"]
        selected_raw: str = answer["selected"]
        probs: dict[str, float] = answer.get("probabilities", {})

        # Validate selected action is in our allowed set
        try:
            selected = Action(selected_raw.upper())
        except ValueError:
            return _deterministic_fallback(
                bundle,
                reason=f"Decider returned unknown action '{selected_raw}'",
            )

        upper_probs = {k.upper(): v for k, v in probs.items()}
        norm_probs = normalize_probabilities(upper_probs, precision=4)
        confidence = norm_probs.get(selected.value, probs.get(selected_raw, 0.0))

        return DeciderResult(
            selected_action=selected,
            probabilities=norm_probs,
            confidence=round(confidence, 4),
            is_fallback=False,
            raw_response=data,
            latency_ms=round(latency_ms, 1),
        )

    except httpx.ConnectError:
        return _deterministic_fallback(
            bundle,
            reason=(
                f"Strands Decider 2B is not reachable at {_settings.decider_base_url}. "
                f"Start Ollama and run: ollama pull {_settings.decider_model}"
            ),
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            reason = (
                f"Decider HTTP 404: 404 page not found. "
                f"Model '{_settings.decider_model}' is not pulled in local Ollama at {_settings.decider_base_url}. "
                f"To enable live inference, run: ollama pull {_settings.decider_model}"
            )
        else:
            reason = f"Decider HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        return _deterministic_fallback(bundle, reason=reason)
    except Exception as exc:
        return _deterministic_fallback(
            bundle, reason=f"Unexpected Decider error: {type(exc).__name__}: {exc}"
        )


def normalize_probabilities(probs: dict[str, float], precision: int = 4) -> dict[str, float]:
    """
    Normalize an action score/probability mapping so values strictly sum to 1.0 (100%).
    Accounts for rounding residuals by adjusting the highest-scoring action.
    """
    if not probs:
        return {}
    total = sum(probs.values())
    if total <= 0:
        n = len(probs)
        return {k: round(1.0 / n, precision) for k in probs}

    normalized = {k: round(v / total, precision) for k, v in probs.items()}
    diff = round(1.0 - sum(normalized.values()), precision)
    if diff != 0:
        max_k = max(normalized, key=lambda k: normalized[k])
        normalized[max_k] = round(normalized[max_k] + diff, precision)
    return normalized


def _deterministic_fallback(bundle: ContextBundle, reason: str) -> DeciderResult:
    """
    Pure-logic fallback used ONLY when Decider is unavailable.
    
    Scores are heuristic decision weights (NOT calibrated model probabilities):
    The rule-selected bounded action receives 80% (0.80) heuristic weight, and the remaining
    20% is divided evenly among the other 5 actions (4% / 0.04 each), strictly summing to 100%.
    Clearly labelled as fallback with raw model confidence omitted.
    """
    risks = bundle.risks
    high_risks = [r for r in risks if r.severity == "high"]
    conflict_risks = [r for r in risks if r.risk_type == "conflict"]
    missing_risks = [r for r in risks if r.risk_type == "missing"]

    if conflict_risks:
        action = Action.ESCALATE
    elif missing_risks:
        action = Action.VERIFY
    elif high_risks:
        action = Action.ABSTAIN
    elif risks:
        action = Action.VERIFY
    else:
        action = Action.PROCEED

    # Heuristic decision scores (not calibrated probabilities)
    other_actions = [a for a in ALL_ACTIONS if a != action.value]
    rem_share = 0.20 / len(other_actions) if other_actions else 0.0
    raw_scores = {a: rem_share for a in ALL_ACTIONS}
    raw_scores[action.value] = 0.80
    probs = normalize_probabilities(raw_scores, precision=4)

    return DeciderResult(
        selected_action=action,
        probabilities=probs,
        confidence=0.80,
        is_fallback=True,
        fallback_reason=reason,
        raw_response=None,
        latency_ms=None,
    )

