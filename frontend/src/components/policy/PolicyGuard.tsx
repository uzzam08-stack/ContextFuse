import { Lock, ShieldOff, CheckCircle2, XCircle, ShieldCheck } from 'lucide-react';
import type { SafetyVerdict } from '../../types';

interface PolicyGuardProps {
  verdict: SafetyVerdict | null;
}

export default function PolicyGuard({ verdict }: PolicyGuardProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Simulation notice — always visible */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <ShieldCheck size={13} style={{ color: 'var(--cyan)' }} />
            Simulation & Safety Notice
          </div>
        </div>
        <div className="sim-notice">
          <ShieldOff size={13} />
          <div>
            <strong>All tools are simulated.</strong> No production infrastructure is accessed.
            No write operations are possible. ContextFuse only performs deterministic read-only
            simulations. No real database connections, config changes, or external API calls
            are made in this MVP.
          </div>
        </div>
      </div>

      {/* Policy verdict */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Lock size={13} style={{ color: 'var(--violet)' }} />
            Deterministic Safety Policy
          </div>
        </div>

        {!verdict ? (
          <div className="state-container">
            <div className="state-icon empty"><Lock size={18} /></div>
            <span className="state-title">No Policy Evaluation Yet</span>
            <span className="state-desc">
              Go to the <strong>Overview</strong> page and execute an incident scenario. The deterministic safety guard will evaluate the proposed action against all rules (such as blocking unverified operations and preventing auto-proceed on conflicting signals) and display the enforcement result here.
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {verdict.permitted
                ? <CheckCircle2 size={18} color="var(--green)" />
                : <XCircle size={18} color="var(--red)" />}
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: verdict.permitted ? 'var(--green)' : 'var(--red)' }}>
                  Action {verdict.action}: {verdict.permitted ? 'PERMITTED' : 'BLOCKED'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  by deterministic policy rule
                </div>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 6 }}>
                Policy Rule
              </div>
              <span className="policy-rule-chip">{verdict.policy_rule}</span>
            </div>

            <div>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 6 }}>
                Explanation
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', padding: '10px 12px', border: '1px solid var(--border-subtle)' }}>
                {verdict.explanation}
              </div>
            </div>

            {/* Policy rules reference */}
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 8 }}>
                Policy Rules (Priority Order)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  ['SAFE_TERMINAL',           'ESCALATE / ABSTAIN always permitted'],
                  ['CONTEXT_VERIFIED',        'PROCEED only when zero risks detected'],
                  ['MISSING_EVIDENCE_VERIFIABLE', 'VERIFY allowed when evidence is missing (no conflicts)'],
                  ['RETRIEVAL_SAFE',          'RETRIEVE allowed when evidence is missing (no conflicts)'],
                  ['CONFLICT_REQUIRES_ESCALATION', 'Conflicts block VERIFY/RETRIEVE — force ESCALATE'],
                ].map(([rule, desc]) => (
                  <div key={rule} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <code className="policy-rule-chip" style={{ fontSize: 9, flexShrink: 0 }}>{rule}</code>
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)', paddingTop: 2 }}>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
