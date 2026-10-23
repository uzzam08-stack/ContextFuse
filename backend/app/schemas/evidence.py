"""
ContextFuse – Evidence schemas and provenance models.

All evidence records carry: source, timestamp, field/value, provenance
chain, freshness metadata, conflict state, and a stable evidence ID.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class EvidenceSource(str, Enum):
    RUNBOOK = "runbook"
    CONFIG_SNAPSHOT = "config_snapshot"
    CHANGE_EVENT = "change_event"
    HEALTH_CHECK = "health_check"
    DEPLOYMENT_LOG = "deployment_log"
    MONITORING_ALERT = "monitoring_alert"


class FreshnessState(str, Enum):
    FRESH = "fresh"       # < 1 h
    RECENT = "recent"     # 1 h – 24 h
    STALE = "stale"       # > 24 h
    UNKNOWN = "unknown"


class ConflictState(str, Enum):
    NONE = "none"
    CONFLICT = "conflict"
    MISSING = "missing"
    SUPERSEDED = "superseded"
    UNTRUSTED = "untrusted"


class EvidenceRecord(BaseModel):
    """A single piece of context evidence with full provenance."""

    evidence_id: str = Field(description="Stable content-addressed ID (sha256 prefix)")
    source: EvidenceSource
    source_path: str = Field(description="Logical path or reference within the source")
    field: str = Field(description="The specific field this record pertains to")
    value: Any = Field(description="The asserted value for the field")
    recorded_at: datetime = Field(description="When this evidence was recorded")
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When ContextFuse ingested this evidence",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Explicit expiration timestamp after which evidence is considered expired/stale",
    )
    is_trusted: bool = Field(
        default=True,
        description="False if origin source is unverified, external, or tampered",
    )
    provenance: list[str] = Field(
        default_factory=list,
        description="Ordered chain of systems that produced/transmitted this evidence",
    )
    freshness: FreshnessState = FreshnessState.UNKNOWN
    conflict_state: ConflictState = ConflictState.NONE
    conflict_with: list[str] = Field(
        default_factory=list,
        description="Evidence IDs that conflict with this record",
    )
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def compute_evidence_id(cls, data: dict) -> dict:
        """Derive a stable content-addressed evidence_id if not supplied."""
        if not data.get("evidence_id"):
            fingerprint = json.dumps(
                {
                    "source": str(data.get("source", "")),
                    "source_path": data.get("source_path", ""),
                    "field": data.get("field", ""),
                    "value": str(data.get("value", "")),
                    "recorded_at": str(data.get("recorded_at", "")),
                },
                sort_keys=True,
            )
            data["evidence_id"] = "ev-" + hashlib.sha256(fingerprint.encode()).hexdigest()[:12]
        return data

    @model_validator(mode="after")
    def compute_freshness(self) -> EvidenceRecord:
        """Set freshness based on recorded_at age and explicit expires_at timestamp."""
        now = datetime.now(timezone.utc)
        if self.expires_at is not None:
            exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
            if now > exp:
                self.freshness = FreshnessState.STALE
                return self

        age_h = (now - self.recorded_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if age_h < 1:
            self.freshness = FreshnessState.FRESH
        elif age_h < 24:
            self.freshness = FreshnessState.RECENT
        else:
            self.freshness = FreshnessState.STALE
        return self


class RiskSignal(BaseModel):
    """A detected risk in the context corpus."""

    risk_id: str
    risk_type: str  # "stale", "conflict", "missing"
    severity: str   # "high", "medium", "low"
    description: str
    implicated_evidence: list[str] = Field(description="Evidence IDs involved")
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContextBundle(BaseModel):
    """The full set of evidence and derived risks for one scenario."""

    scenario_id: str
    scenario_name: str
    scenario_description: str
    evidence: list[EvidenceRecord]
    risks: list[RiskSignal] = Field(default_factory=list)
    is_safe: bool = False
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
