"""
ContextFuse – Deterministic Safety Guard.

Validates a proposed action against policy rules before execution.
This layer is 100% deterministic — no ML involved.
"""

from __future__ import annotations

from app.schemas.decision import Action, SafetyVerdict
from app.schemas.evidence import ContextBundle


def evaluate_safety(bundle: ContextBundle, proposed_action: Action) -> SafetyVerdict:
    """
    Run the safety policy against the proposed action and context bundle.
    
    Policy rules (in priority order):
    1. ESCALATE/ABSTAIN/BLOCK are always permitted — they are safe terminal states.
    2. PROCEED is only permitted when the context is confirmed safe (no risks).
    3. Untrusted evidence strictly blocks PROCEED and requires ESCALATE.
    4. VERIFY is permitted when only missing evidence exists (no conflicts or untrusted).
    5. RETRIEVE is permitted when evidence is missing but no conflicts exist.
    6. Any action other than ESCALATE/ABSTAIN/BLOCK is blocked when conflicts exist.
    """
    has_conflicts = any(r.risk_type == "conflict" for r in bundle.risks)
    has_untrusted = any(r.risk_type == "untrusted" for r in bundle.risks)
    has_missing = any(r.risk_type == "missing" for r in bundle.risks)
    has_high_risk = any(r.severity == "high" for r in bundle.risks)

    if proposed_action in (Action.ESCALATE, Action.ABSTAIN, Action.BLOCK):
        step_guidance = {
            Action.ESCALATE: "Human operator must review conflicting evidence and manually reconcile endpoints before continuing.",
            Action.ABSTAIN: "Execution suspended due to operational uncertainty; notify on-call engineer.",
            Action.BLOCK: "Action blocked by safety gate; automated progression halted to prevent risky state change.",
        }.get(proposed_action, "Suspend automated execution.")

        return SafetyVerdict(
            action=proposed_action,
            permitted=True,
            policy_rule="SAFE_TERMINAL",
            explanation=(
                f"{proposed_action.value} is a safe terminal action — always permitted "
                "as it defers to human judgement or suspends operation."
            ),
            safe_next_step=step_guidance,
        )

    if proposed_action == Action.PROCEED:
        if bundle.is_safe and not bundle.risks:
            return SafetyVerdict(
                action=proposed_action,
                permitted=True,
                policy_rule="CONTEXT_VERIFIED",
                explanation="All evidence is consistent and fresh — proceeding is safe.",
                safe_next_step="Proceed with planned agent operation; all context is verified and fresh.",
            )
        return SafetyVerdict(
            action=proposed_action,
            permitted=False,
            policy_rule="CONTEXT_UNSAFE",
            explanation=(
                f"PROCEED blocked: {len(bundle.risks)} unresolved risk(s) detected. "
                "Context must be verified or escalated before proceeding."
            ),
            safe_next_step="Resolve detected risks or switch to VERIFY/ESCALATE before proceeding.",
        )

    if proposed_action == Action.VERIFY:
        if has_untrusted:
            return SafetyVerdict(
                action=proposed_action,
                permitted=False,
                policy_rule="UNTRUSTED_EVIDENCE_REQUIRES_ESCALATION",
                explanation="VERIFY blocked: untrusted evidence detected — ESCALATE required.",
                safe_next_step="Escalate to security/operations team to verify origin provenance.",
            )
        if has_conflicts:
            return SafetyVerdict(
                action=proposed_action,
                permitted=False,
                policy_rule="CONFLICT_REQUIRES_ESCALATION",
                explanation=(
                    "VERIFY blocked: conflicting evidence cannot be resolved by a "
                    "read-only verification tool alone — ESCALATE required."
                ),
                safe_next_step="Escalate to human operator; verification probes cannot override contradictory authoritative sources.",
            )
        return SafetyVerdict(
            action=proposed_action,
            permitted=True,
            policy_rule="MISSING_EVIDENCE_VERIFIABLE",
            explanation=(
                "VERIFY permitted: evidence is missing or unconfirmed but no "
                "irreconcilable conflicts exist."
            ),
            safe_next_step="Execute read-only verification probe to confirm missing operational signals.",
        )

    if proposed_action == Action.RETRIEVE:
        if has_conflicts:
            return SafetyVerdict(
                action=proposed_action,
                permitted=False,
                policy_rule="CONFLICT_REQUIRES_ESCALATION",
                explanation=(
                    "RETRIEVE blocked: conflicting evidence detected. Retrieving more "
                    "data will not resolve a conflict — ESCALATE required."
                ),
                safe_next_step="Escalate to human operator; additional retrieval will not resolve conflicting records.",
            )
        return SafetyVerdict(
            action=proposed_action,
            permitted=True,
            policy_rule="RETRIEVAL_SAFE",
            explanation="RETRIEVE permitted: fetching fresh evidence is a safe read-only action.",
            safe_next_step="Query authoritative source for updated context snapshot.",
        )

    # Fallback — should not reach here with valid Action enum
    return SafetyVerdict(
        action=proposed_action,
        permitted=False,
        policy_rule="UNKNOWN_ACTION",
        explanation=f"Unknown action '{proposed_action}' — blocked by default.",
        safe_next_step="Halt execution and report unhandled action.",
    )
