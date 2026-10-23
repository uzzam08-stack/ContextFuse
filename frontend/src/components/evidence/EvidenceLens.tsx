import { Eye, AlertOctagon, Clock, FileText, Server, Activity, Zap } from 'lucide-react';
import type { EvidenceRecord, RiskSignal } from '../../types';

// ─── Source icon ──────────────────────────────────────────────────────────────
function SourceIcon({ source }: { source: string }) {
  const icons: Record<string, React.ReactNode> = {
    runbook:        <FileText size={12} />,
    config_snapshot:<Server size={12} />,
    change_event:   <Zap size={12} />,
    health_check:   <Activity size={12} />,
    deployment_log: <Clock size={12} />,
    monitoring_alert:<AlertOctagon size={12} />,
  };
  return <>{icons[source] ?? <FileText size={12} />}</>;
}

// ─── Evidence Card ────────────────────────────────────────────────────────────
function EvidenceCard({ ev }: { ev: EvidenceRecord }) {
  const conflictClass =
    ev.conflict_state === 'conflict'    ? 'conflict'   :
    ev.conflict_state === 'missing'     ? 'missing'    :
    ev.conflict_state === 'superseded'  ? 'superseded' : '';

  const recordedDate = new Date(ev.recorded_at);
  const ageHours = (Date.now() - recordedDate.getTime()) / 3_600_000;
  const ageLabel =
    ageHours < 1    ? `${Math.round(ageHours * 60)}m ago` :
    ageHours < 24   ? `${Math.round(ageHours)}h ago` :
    `${Math.round(ageHours / 24)}d ago`;

  return (
    <div className={`evidence-card ${conflictClass}`}>
      <div className="ev-header">
        <code className="ev-id">{ev.evidence_id}</code>
        <div className="ev-badges">
          <span className={`badge badge-${ev.freshness}`}>{ev.freshness}</span>
          {ev.conflict_state !== 'none' && (
            <span className={`badge badge-${ev.conflict_state}`}>{ev.conflict_state}</span>
          )}
          <span className="badge badge-source">
            <SourceIcon source={ev.source} />
            {ev.source.replace('_', ' ')}
          </span>
        </div>
      </div>

      <div className="ev-field-row">
        <span className="ev-field">{ev.field}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>=</span>
        <span className="ev-value">
          {ev.value === null ? <em style={{ color: 'var(--amber)', fontSize: 11 }}>null — missing</em>
            : typeof ev.value === 'object'
            ? JSON.stringify(ev.value)
            : String(ev.value)}
        </span>
      </div>

      <div className="ev-meta">
        <span>recorded {ageLabel} · {recordedDate.toISOString().slice(0, 16).replace('T', ' ')} UTC</span>
        <div className="ev-provenance">
          <span style={{ marginRight: 3, color: 'var(--text-muted)' }}>via</span>
          {ev.provenance.map(p => (
            <span key={p} className="provenance-tag">{p}</span>
          ))}
        </div>
      </div>

      {ev.notes && <div className="ev-notes">{ev.notes}</div>}

      {ev.conflict_with.length > 0 && (
        <div style={{ fontSize: 10, color: 'var(--red)', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          <span>Conflicts with:</span>
          {ev.conflict_with.map(id => (
            <code key={id} style={{ fontSize: 10 }}>{id}</code>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Risk Card ────────────────────────────────────────────────────────────────
function RiskCard({ risk }: { risk: RiskSignal }) {
  return (
    <div className={`risk-card risk-${risk.severity}`}>
      <div className="risk-icon">
        <AlertOctagon
          size={14}
          color={
            risk.severity === 'high'   ? 'var(--red)'   :
            risk.severity === 'medium' ? 'var(--amber)' : 'var(--green)'
          }
        />
      </div>
      <div className="risk-content">
        <div className="risk-header">
          <span className={`badge badge-${risk.severity}`}>{risk.severity}</span>
          <span className="badge badge-source">{risk.risk_type}</span>
          <code className="risk-id">{risk.risk_id}</code>
        </div>
        <div className="risk-desc">{risk.description}</div>
        {risk.implicated_evidence.length > 0 && (
          <div className="risk-evidence-ids">
            {risk.implicated_evidence.map(id => (
              <code key={id} className="ev-id" style={{ fontSize: 10 }}>{id}</code>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Evidence Lens Panel ──────────────────────────────────────────────────────
interface EvidenceLensProps {
  evidence: EvidenceRecord[];
  risks: RiskSignal[];
}

export default function EvidenceLens({ evidence, risks }: EvidenceLensProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Evidence records */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Eye size={13} />
            Evidence Corpus
            <span
              style={{
                marginLeft: 4,
                background: 'var(--cyan-dim)',
                color: 'var(--cyan)',
                borderRadius: 99,
                padding: '1px 7px',
                fontSize: 10,
                fontWeight: 700,
              }}
            >
              {evidence.length}
            </span>
          </div>
        </div>
        {evidence.length === 0 ? (
          <div className="state-container">
            <div className="state-icon empty"><Eye size={18} /></div>
            <span className="state-title">No Evidence Loaded</span>
            <span className="state-desc">
              Go to the <strong>Overview</strong> page, select an incident scenario (such as <em>Stale Database Endpoint</em> or <em>Missing Health Evidence</em>), and click <strong>Run Safety Evaluation</strong> to ingest and analyze operational context.
            </span>
          </div>
        ) : (
          <div className="evidence-grid">
            {evidence.map(ev => (
              <EvidenceCard key={ev.evidence_id} ev={ev} />
            ))}
          </div>
        )}
      </div>

      {/* Risk signals */}
      {risks.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <AlertOctagon size={13} />
              Risk Signals
              <span
                style={{
                  marginLeft: 4,
                  background: 'var(--red-dim)',
                  color: 'var(--red)',
                  borderRadius: 99,
                  padding: '1px 7px',
                  fontSize: 10,
                  fontWeight: 700,
                }}
              >
                {risks.length}
              </span>
            </div>
          </div>
          <div className="risk-list">
            {risks.map(r => <RiskCard key={r.risk_id} risk={r} />)}
          </div>
        </div>
      )}
    </div>
  );
}
