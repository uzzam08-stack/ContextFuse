"""
ContextFuse – Deterministic risk detection service.

Operates independently of any ML model. Implements:
  - Stale evidence detection
  - Conflicting evidence detection
  - Missing evidence detection
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.schemas.evidence import (
    ContextBundle,
    ConflictState,
    EvidenceRecord,
    FreshnessState,
    RiskSignal,
)


def detect_risks(bundle: ContextBundle) -> ContextBundle:
    """
    Run all deterministic risk detectors on the bundle's evidence.
    Returns the bundle with risks populated.
    """
    risks: list[RiskSignal] = list(bundle.risks)  # preserve pre-loaded scenario risks

    already_seen = {r.risk_id for r in risks}

    # If the scenario already has risks (from loader), skip re-detection
    # but still annotate evidence freshness for display
    _annotate_freshness(bundle.evidence)

    if not risks:
        # Dynamic detection for arbitrary bundles
        risks.extend(_detect_conflicts(bundle.evidence, already_seen))
        risks.extend(_detect_missing(bundle.evidence, already_seen))
        risks.extend(_detect_stale(bundle.evidence, already_seen))
        risks.extend(_detect_untrusted(bundle.evidence, already_seen))

    bundle.risks = risks
    bundle.is_safe = len(risks) == 0
    return bundle


# ─── Internal detectors ──────────────────────────────────────────────────────

def _annotate_freshness(evidence: list[EvidenceRecord]) -> None:
    """Recompute freshness on all records respecting recorded_at and expires_at."""
    now = datetime.now(timezone.utc)
    for ev in evidence:
        if ev.expires_at is not None:
            exp = ev.expires_at if ev.expires_at.tzinfo else ev.expires_at.replace(tzinfo=timezone.utc)
            if now > exp:
                ev.freshness = FreshnessState.STALE
                continue
        age_h = (now - ev.recorded_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if age_h < 1:
            ev.freshness = FreshnessState.FRESH
        elif age_h < 24:
            ev.freshness = FreshnessState.RECENT
        else:
            ev.freshness = FreshnessState.STALE


def _detect_conflicts(
    evidence: list[EvidenceRecord], seen: set[str]
) -> list[RiskSignal]:
    """Find records that share a field but assert different values."""
    risks: list[RiskSignal] = []
    by_field: dict[str, list[EvidenceRecord]] = {}
    for ev in evidence:
        by_field.setdefault(ev.field, []).append(ev)

    for field, records in by_field.items():
        values = [str(r.value) for r in records]
        unique_values = set(v for v in values if v not in ("None", "null", ""))
        if len(unique_values) > 1:
            ids = [r.evidence_id for r in records]
            risk_id = f"risk-{uuid.uuid4().hex[:8]}"
            if risk_id not in seen:
                risks.append(
                    RiskSignal(
                        risk_id=risk_id,
                        risk_type="conflict",
                        severity="high",
                        description=(
                            f"Field '{field}' has conflicting values across evidence sources: "
                            + ", ".join(f"{r.source.value}={r.value!r}" for r in records)
                        ),
                        implicated_evidence=ids,
                    )
                )
    return risks


def _detect_missing(
    evidence: list[EvidenceRecord], seen: set[str]
) -> list[RiskSignal]:
    """Find records explicitly marked as missing or with null values."""
    risks: list[RiskSignal] = []
    for ev in evidence:
        if ev.conflict_state == ConflictState.MISSING or ev.value is None:
            risk_id = f"risk-{uuid.uuid4().hex[:8]}"
            if risk_id not in seen:
                risks.append(
                    RiskSignal(
                        risk_id=risk_id,
                        risk_type="missing",
                        severity="high",
                        description=(
                            f"Evidence record {ev.evidence_id!r} for field '{ev.field}' "
                            f"from source '{ev.source.value}' is missing or null."
                        ),
                        implicated_evidence=[ev.evidence_id],
                    )
                )
    return risks


def _detect_stale(
    evidence: list[EvidenceRecord], seen: set[str]
) -> list[RiskSignal]:
    """Flag stale evidence that is still being used (not superseded)."""
    risks: list[RiskSignal] = []
    for ev in evidence:
        if (
            ev.freshness == FreshnessState.STALE
            and ev.conflict_state not in (ConflictState.SUPERSEDED, ConflictState.MISSING)
        ):
            risk_id = f"risk-{uuid.uuid4().hex[:8]}"
            if risk_id not in seen:
                risks.append(
                    RiskSignal(
                        risk_id=risk_id,
                        risk_type="stale",
                        severity="medium",
                        description=(
                            f"Evidence record {ev.evidence_id!r} from '{ev.source.value}' "
                            f"for field '{ev.field}' is older than 24 h (recorded_at={ev.recorded_at.date()})."
                        ),
                        implicated_evidence=[ev.evidence_id],
                    )
                )
    return risks


def _detect_untrusted(
    evidence: list[EvidenceRecord], seen: set[str]
) -> list[RiskSignal]:
    """Find records from untrusted origins or marked untrusted."""
    risks: list[RiskSignal] = []
    for ev in evidence:
        if not ev.is_trusted or ev.conflict_state == ConflictState.UNTRUSTED:
            risk_id = f"risk-{uuid.uuid4().hex[:8]}"
            if risk_id not in seen:
                risks.append(
                    RiskSignal(
                        risk_id=risk_id,
                        risk_type="untrusted",
                        severity="high",
                        description=(
                            f"Evidence record {ev.evidence_id!r} from '{ev.source.value}' "
                            f"is untrusted or originates from an unverified origin."
                        ),
                        implicated_evidence=[ev.evidence_id],
                    )
                )
    return risks
