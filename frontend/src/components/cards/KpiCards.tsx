import { Database, AlertTriangle, Zap, Cpu } from 'lucide-react';
import type { OrchestrationResult } from '../../types';

interface KpiCardsProps {
  result: OrchestrationResult | null;
  isRunning: boolean;
}

export default function KpiCards({ result, isRunning }: KpiCardsProps) {
  const placeholder = '—';

  const actionColors: Record<string, string> = {
    PROCEED: 'var(--green)',
    VERIFY: 'var(--cyan)',
    RETRIEVE: 'var(--violet)',
    ESCALATE: 'var(--amber)',
    ABSTAIN: 'var(--red)',
    BLOCK: 'var(--red)',
  };

  const action = result?.decider_result.selected_action;
  const actionColor = action ? actionColors[action] : 'var(--text-muted)';

  return (
    <div className="kpi-grid">
      <div className="kpi-card kpi-cyan">
        <div className="kpi-label">
          <Database size={11} />
          Evidence Records
        </div>
        <div className="kpi-value">
          {isRunning ? '…' : result ? result.evidence_count : placeholder}
        </div>
        <div className="kpi-sub">
          {result?.run_id ? (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>ID: {result.run_id}</span>
          ) : (
            'loaded from scenario'
          )}
        </div>
      </div>

      <div className="kpi-card kpi-amber">
        <div className="kpi-label">
          <AlertTriangle size={11} />
          Risk Signals
        </div>
        <div className="kpi-value">
          {isRunning ? '…' : result ? result.risk_count : placeholder}
        </div>
        <div className="kpi-sub">
          {result && result.risk_count > 0 ? 'context unsafe' : 'detected by rule engine'}
        </div>
      </div>

      <div className="kpi-card kpi-green">
        <div className="kpi-label">
          <Zap size={11} />
          Selected Action
        </div>
        <div
          className="kpi-value"
          style={{ fontSize: action ? '18px' : '26px', color: actionColor }}
        >
          {isRunning ? '…' : action ?? placeholder}
        </div>
        <div className="kpi-sub">
          {result?.decider_result.is_fallback ? '⚠ deterministic fallback' : 'Decider decision'}
        </div>
      </div>

      <div className="kpi-card kpi-violet">
        <div className="kpi-label">
          <Cpu size={11} />
          Model Status
        </div>
        <div className="kpi-value" style={{ fontSize: '15px', lineHeight: 1.3 }}>
          {isRunning
            ? '…'
            : result
            ? result.decider_result.is_fallback
              ? 'Fallback'
              : `${(result.decider_result.confidence * 100).toFixed(0)}%`
            : placeholder}
        </div>
        <div className="kpi-sub">
          {result?.decider_result.latency_ms != null
            ? `${result.decider_result.latency_ms.toFixed(0)}ms · Decider 2B`
            : result?.decider_result.is_fallback
            ? 'Decider unavailable'
            : 'confidence · latency'}
        </div>
      </div>
    </div>
  );
}
