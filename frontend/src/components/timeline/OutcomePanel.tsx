import { FileSearch, CheckCircle2, XCircle, AlertTriangle, ShieldCheck } from 'lucide-react';
import type { OutcomeBrief, ToolCallResult, SafetyVerdict } from '../../types';

interface OutcomePanelProps {
  outcome: OutcomeBrief | null;
  toolResult: ToolCallResult | null;
  verdict?: SafetyVerdict | null;
}

function SafetyStatusIcon({ status }: { status: string }) {
  if (status === 'safe')      return <CheckCircle2 size={16} />;
  if (status === 'escalated') return <AlertTriangle size={16} />;
  if (status === 'abstained') return <ShieldCheck size={16} />;
  if (status === 'blocked')   return <XCircle size={16} />;
  return <XCircle size={16} />;
}

export default function OutcomePanel({ outcome, toolResult, verdict }: OutcomePanelProps) {
  if (!outcome) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title"><FileSearch size={13} /> Outcome Brief</div>
        </div>
        <div className="state-container">
          <div className="state-icon empty"><FileSearch size={18} /></div>
          <span className="state-title">No Outcome Yet</span>
          <span className="state-desc">Run a scenario to see the Bedrock-generated outcome brief.</span>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <FileSearch size={13} />
            Outcome Brief
            <span style={{ color: 'var(--text-muted)' }}>
              {outcome.is_bedrock_available
                ? `· Bedrock ${outcome.bedrock_model_id?.split(':')[0]?.split('.').slice(-1)[0] ?? ''}`
                : '· Deterministic Fallback'}
            </span>
          </div>
          {!outcome.is_bedrock_available && (
            <span className="badge badge-missing">Bedrock Offline</span>
          )}
        </div>

        {/* Safety status banner */}
        <div className={`safety-status-banner ${outcome.safety_status}`} style={{ marginBottom: 12 }}>
          <SafetyStatusIcon status={outcome.safety_status} />
          <span>
            Safety Status: <strong>{outcome.safety_status.toUpperCase()}</strong>
          </span>
          {outcome.bedrock_latency_ms != null && (
            <span style={{ marginLeft: 'auto', fontSize: 11, opacity: 0.7 }}>
              {outcome.bedrock_latency_ms.toFixed(0)}ms
            </span>
          )}
        </div>

        {/* Safe next step */}
        {verdict?.safe_next_step && (
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius)',
              padding: '10px 14px',
              marginBottom: 12,
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <ShieldCheck size={14} style={{ color: 'var(--cyan)', flexShrink: 0 }} />
            <div>
              <strong style={{ color: 'var(--cyan)' }}>Recommended Next Step: </strong>
              <span style={{ color: 'var(--text-primary)' }}>{verdict.safe_next_step}</span>
            </div>
          </div>
        )}

        {/* Bedrock fallback notice */}
        {outcome.fallback_note && (
          <div className="fallback-banner" style={{ marginBottom: 12 }}>
            <AlertTriangle size={13} />
            <span>{outcome.fallback_note}</span>
          </div>
        )}

        {/* Summary */}
        <div className="outcome-summary">{outcome.summary}</div>

        {/* Evidence IDs & Risk IDs */}
        <div className="outcome-meta-grid">
          <div className="outcome-meta-block">
            <div className="outcome-meta-label">Cited Evidence</div>
            <div className="evidence-id-list">
              {outcome.cited_evidence_ids.length > 0
                ? outcome.cited_evidence_ids.map(id => (
                    <span key={id} className="cited-ev-id">{id}</span>
                  ))
                : <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>none cited</span>}
            </div>
          </div>
          <div className="outcome-meta-block">
            <div className="outcome-meta-label">Unresolved Risks</div>
            <div className="risk-id-list">
              {outcome.unresolved_risks.length > 0
                ? outcome.unresolved_risks.map(id => (
                    <span key={id} className="unresolved-risk-id">{id}</span>
                  ))
                : <span style={{ color: 'var(--green)', fontSize: 11 }}>✓ none</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Tool result */}
      {toolResult && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <CheckCircle2 size={13} style={{ color: 'var(--green)' }} />
              Tool Invocation: {toolResult.tool_name}
            </div>
            <span className="badge badge-fresh">Simulated · Read-only</span>
          </div>
          <div className="sim-notice" style={{ marginBottom: 10 }}>
            <ShieldCheck size={13} />
            <span>{toolResult.safety_note}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
            Input: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {JSON.stringify(toolResult.input_params)}
            </code>
          </div>
          <div className="tool-output">
            {JSON.stringify(toolResult.output, null, 2)}
          </div>
        </div>
      )}
    </div>
  );
}
