import { Shield, Zap, CheckCircle2, AlertTriangle, ArrowRight, Lock, Eye } from 'lucide-react';
import { ALL_ACTIONS } from '../../types';

export default function DecisionPatternsView() {
  const PATTERNS = [
    {
      action: 'PROCEED',
      title: 'Evidence-Agreement Gating',
      color: 'var(--green)',
      badgeClass: 'badge-fresh',
      condition: 'Zero conflicting or missing records. All evidence is fresh (<24h) and corroborated.',
      agentEffect: 'Agent is granted permission to execute planned read/write operation.',
    },
    {
      action: 'VERIFY',
      title: 'Automated Read-Only Probe',
      color: 'var(--cyan)',
      badgeClass: 'badge-recent',
      condition: 'Required context is unconfirmed or absent, but no contradictory evidence exists.',
      agentEffect: 'Triggers a safe simulated read-only probe before committing any action.',
    },
    {
      action: 'RETRIEVE',
      title: 'Authoritative Context Retrieval',
      color: 'var(--violet)',
      badgeClass: 'badge-superseded',
      condition: 'Context missing key attributes needed for high-confidence execution.',
      agentEffect: 'Queries authoritative systems of record to replenish missing evidence.',
    },
    {
      action: 'ESCALATE',
      title: 'Contradiction Safety Halt',
      color: 'var(--amber)',
      badgeClass: 'badge-stale',
      condition: 'Two or more evidence sources assert conflicting states (e.g. decommissioned vs new endpoint).',
      agentEffect: 'Automated action is immediately suspended; ticket dispatched to human on-call engineer.',
    },
    {
      action: 'ABSTAIN',
      title: 'Uncertainty Floor Protection',
      color: 'var(--red)',
      badgeClass: 'badge-conflict',
      condition: 'Unresolved risks or high entropy state where neither verification nor proceeding is safe.',
      agentEffect: 'Refuses operation safely. Never converts operational uncertainty into false certainty.',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Shield size={13} style={{ color: 'var(--violet)' }} />
            Core Pattern: Evidence-Gated Context Selection
          </div>
          <span className="badge badge-fresh">Bounded Action Space</span>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
          ContextFuse enforces bounded decision-making over freeform text generation. Instead of letting an LLM hallucinate
          or guess when faced with contradictory runbooks and configurations, Strands Decider 2B evaluates calibrated probabilities
          over a finite safety action space. The outcome is verified by deterministic safety policies before Bedrock interprets the incident.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {PATTERNS.map(p => (
            <div
              key={p.action}
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius)',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 16,
              }}
            >
              <div style={{ minWidth: 100 }}>
                <span className={`action-chip ${p.action}`}>{p.action}</span>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)', marginBottom: 4 }}>
                  {p.title}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                  <strong style={{ color: 'var(--text-secondary)' }}>Trigger Condition:</strong> {p.condition}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  <strong style={{ color: 'var(--text-secondary)' }}>Agent Effect:</strong> {p.agentEffect}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
