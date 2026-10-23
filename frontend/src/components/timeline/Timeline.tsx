import { CheckCircle2, XCircle, Clock, AlertTriangle, Zap, Shield } from 'lucide-react';
import type { TimelineEvent } from '../../types';

const STAGE_ICONS: Record<string, React.ReactNode> = {
  context_load: <CheckCircle2 size={10} />,
  risk_detection: <AlertTriangle size={10} />,
  decider: <Zap size={10} />,
  safety_guard: <Shield size={10} />,
  tool_call: <CheckCircle2 size={10} />,
  bedrock: <Zap size={10} />,
  outcome: <CheckCircle2 size={10} />,
};

interface TimelineProps {
  events: TimelineEvent[];
}

export default function Timeline({ events }: TimelineProps) {
  if (events.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title"><Clock size={13} /> Decision Timeline</div>
        </div>
        <div className="state-container">
          <div className="state-icon empty"><Clock size={18} /></div>
          <span className="state-title">No Timeline Yet</span>
          <span className="state-desc">Run a scenario to see the decision timeline.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><Clock size={13} /> Decision Timeline</div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{events.length} stages</span>
      </div>
      <div className="timeline">
        {events.map((ev, idx) => (
          <div key={ev.step} className="timeline-item">
            <div className="timeline-track">
              <div className={`timeline-dot ${ev.status}`}>
                {STAGE_ICONS[ev.stage] ?? ev.step}
              </div>
              {idx < events.length - 1 && <div className="timeline-connector" />}
            </div>
            <div className="timeline-body">
              <div className="timeline-label">
                {ev.label}
                <span className="timeline-stage">{ev.stage}</span>
              </div>
              <div className="timeline-detail">{ev.detail}</div>
              {ev.evidence_ids.length > 0 && (
                <div style={{ marginTop: 5, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {ev.evidence_ids.slice(0, 4).map(id => (
                    <code key={id} className="ev-id" style={{ fontSize: 9 }}>{id}</code>
                  ))}
                  {ev.evidence_ids.length > 4 && (
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                      +{ev.evidence_ids.length - 4} more
                    </span>
                  )}
                </div>
              )}
              <div className="timeline-ts">
                {new Date(ev.timestamp).toISOString().slice(11, 23)} UTC
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
