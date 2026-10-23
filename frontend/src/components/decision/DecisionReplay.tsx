import { Play, AlertTriangle, CheckCircle2, Cpu } from 'lucide-react';
import type { DeciderResult } from '../../types';
import { ALL_ACTIONS } from '../../types';

interface DecisionReplayProps {
  deciderResult: DeciderResult | null;
}

const ACTION_COLORS: Record<string, string> = {
  PROCEED:  'proceed',
  VERIFY:   'verify',
  RETRIEVE: 'retrieve',
  ESCALATE: 'escalate',
  ABSTAIN:  'abstain',
  BLOCK:    'abstain',
};

export default function DecisionReplay({ deciderResult }: DecisionReplayProps) {
  if (!deciderResult) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title"><Play size={13} /> Decision Replay</div>
        </div>
        <div className="state-container">
          <div className="state-icon empty"><Play size={18} /></div>
          <span className="state-title">No Decision Yet</span>
          <span className="state-desc">Run a scenario to see the Decider decision replay.</span>
        </div>
      </div>
    );
  }

  const { selected_action, probabilities, confidence, is_fallback, fallback_reason, latency_ms } = deciderResult;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Cpu size={13} style={{ color: 'var(--violet)' }} />
          Decision Replay
          <span style={{ color: 'var(--violet)' }}>· Strands Decider 2B</span>
        </div>
        {is_fallback ? (
          <span className="badge badge-missing">Fallback</span>
        ) : (
          <span className="badge badge-fresh">Live Result</span>
        )}
      </div>

      {is_fallback && (
        <div className="fallback-banner" style={{ marginBottom: 14 }}>
          <AlertTriangle size={13} />
          <span>
            <strong>Strands Decider 2B unavailable — deterministic fallback applied.</strong>
            {' '}{fallback_reason}
          </span>
        </div>
      )}

      {/* Action Scores Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: is_fallback ? 'var(--amber)' : 'var(--text-secondary)' }}>
          {is_fallback ? 'Decision scores (not calibrated probabilities)' : 'Calibrated Action Probabilities'}
        </span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          {is_fallback ? 'Heuristic rule weights · Sums to 100%' : 'Model softmax output'}
        </span>
      </div>

      {/* Action grid */}
      <div className="action-grid">
        {ALL_ACTIONS.map(action => {
          const prob = probabilities[action] ?? 0;
          const isSelected = action === selected_action;
          const cls = isSelected ? `action-tile selected-${ACTION_COLORS[action]}` : 'action-tile';
          return (
            <div key={action} className={cls}>
              <div className="action-name">{action}</div>
              <div className="action-prob">
                {(prob * 100).toFixed(0)}%
              </div>
              {isSelected && (
                <CheckCircle2 size={10} style={{ color: 'currentColor', margin: '4px auto 0', display: 'block' }} />
              )}
            </div>
          );
        })}
      </div>

      {is_fallback && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, marginBottom: 14, lineHeight: 1.4 }}>
          * <strong>Meaning:</strong> When Strands Decider 2B is unavailable, ContextFuse assigns deterministic heuristic decision weights to reflect the rule engine's choice (80% for <code>{selected_action}</code>, 4% baseline for other actions, strictly normalized to 100%). These are illustrative decision scores, not calibrated model probabilities.
        </div>
      )}

      {/* Meta */}
      <div className="decider-meta">
        <div className="decider-row">
          <span className="decider-row-label">Selected action</span>
          <span className={`action-chip ${selected_action}`}>{selected_action}</span>
        </div>
        {!is_fallback ? (
          <>
            <div className="decider-row">
              <span className="decider-row-label">Calibrated confidence</span>
              <span className="decider-row-val" style={{ color: 'var(--green)' }}>
                {(confidence * 100).toFixed(1)}%
              </span>
            </div>
            {latency_ms != null && (
              <div className="decider-row">
                <span className="decider-row-label">Latency</span>
                <span className="decider-row-val">{latency_ms.toFixed(0)} ms</span>
              </div>
            )}
          </>
        ) : (
          <div className="decider-row">
            <span className="decider-row-label">Decision score</span>
            <span className="decider-row-val" style={{ color: 'var(--amber)' }}>
              {(confidence * 100).toFixed(1)}% (heuristic weight, not model confidence)
            </span>
          </div>
        )}
        <div className="decider-row">
          <span className="decider-row-label">Model</span>
          <span className="decider-row-val">
            {is_fallback ? 'Deterministic fallback (rule engine)' : 'strands-decider:2b / /v1/systemone'}
          </span>
        </div>
        <div className="decider-row">
          <span className="decider-row-label">Decision type</span>
          <span className="decider-row-val">choice (pointer-head, not text generation)</span>
        </div>
      </div>
    </div>
  );
}

