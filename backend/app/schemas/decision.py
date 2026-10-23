"""
ContextFuse – Decision and orchestration schemas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Action(str, Enum):
    PROCEED = "PROCEED"
    VERIFY = "VERIFY"
    RETRIEVE = "RETRIEVE"
    ESCALATE = "ESCALATE"
    ABSTAIN = "ABSTAIN"
    BLOCK = "BLOCK"


ALL_ACTIONS = [a.value for a in Action]


class DeciderResult(BaseModel):
    """Output from Strands Decider 2B – real or clearly-labelled fallback."""

    selected_action: Action
    probabilities: dict[str, float]
    confidence: float
    is_fallback: bool = Field(
        default=False,
        description="True when Decider was unavailable and deterministic fallback was used",
    )
    fallback_reason: str | None = None
    raw_response: dict | None = None
    latency_ms: float | None = None


class SafetyVerdict(BaseModel):
    """Deterministic safety policy evaluation result."""

    action: Action
    permitted: bool
    policy_rule: str
    explanation: str
    safe_next_step: str = Field(
        default="",
        description="Explicit guidance for operator or agent safe next action",
    )


class TimelineEvent(BaseModel):
    """A single step in the decision timeline."""

    step: int
    stage: str
    label: str
    detail: str
    status: str  # "complete", "active", "pending", "error", "warning"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_ids: list[str] = Field(default_factory=list)


class ToolCallResult(BaseModel):
    """Result of a simulated read-only tool invocation."""

    tool_name: str
    input_params: dict[str, Any]
    output: Any
    is_simulated: bool = True
    safety_note: str = "Simulated read-only tool — no production writes performed"


class OutcomeBrief(BaseModel):
    """Final evidence-grounded explanation from Bedrock."""

    summary: str
    cited_evidence_ids: list[str]
    unresolved_risks: list[str]
    safety_status: str  # "safe", "unsafe", "escalated", "abstained"
    bedrock_model_id: str | None = None
    bedrock_latency_ms: float | None = None
    is_bedrock_available: bool = True
    fallback_note: str | None = None
    raw_bedrock_response: dict | None = None


class OrchestrationResult(BaseModel):
    """Complete result of one full ContextFuse orchestration run."""

    run_id: str
    scenario_id: str
    evidence_count: int
    risk_count: int
    decider_result: DeciderResult
    safety_verdict: SafetyVerdict
    tool_result: ToolCallResult | None = None
    outcome_brief: OutcomeBrief
    timeline: list[TimelineEvent]
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BenchmarkEntry(BaseModel):
    """One row of benchmark comparison data with honest integration accounting."""

    scenario_id: str
    scenario_name: str
    rules_only_action: Action
    bedrock_only_action: Action
    decider_action: Action
    ground_truth_action: Action
    rules_correct: bool
    bedrock_correct: bool | None = None
    decider_correct: bool | None = None
    bedrock_is_fallback: bool = False
    decider_is_fallback: bool = False
    bedrock_status: str = "LIVE"
    decider_status: str = "LIVE"
    rules_latency_ms: float
    bedrock_latency_ms: float
    decider_latency_ms: float

