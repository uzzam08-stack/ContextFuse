import { Database, FileText, Server, Zap, Activity, Clock, AlertOctagon, CheckCircle2, Shield } from 'lucide-react';
import type { ContextBundle } from '../../types';

interface EvidenceSourcesViewProps {
  bundle: ContextBundle | null;
}

const SOURCE_CATALOG = [
  {
    type: 'config_snapshot',
    name: 'Authoritative Config Store',
    provider: 'Terraform State / AWS AppConfig / SSM',
    icon: <Server size={16} />,
    color: 'var(--cyan)',
    freshnessSLA: '< 1 hour',
    role: 'Primary source of truth for runtime endpoints and credentials.',
  },
  {
    type: 'change_event',
    name: 'Change Event Feed',
    provider: 'Change Management API / EventBridge / CI/CD',
    icon: <Zap size={16} />,
    color: 'var(--amber)',
    freshnessSLA: '< 4 hours',
    role: 'Records planned operational migrations, releases, and rollbacks.',
  },
  {
    type: 'health_check',
    name: 'Synthetic Health Probes',
    provider: 'Route 53 / ALB Health Checks / Internal Cron',
    icon: <Activity size={16} />,
    color: 'var(--green)',
    freshnessSLA: '< 5 minutes',
    role: 'Real-time heartbeat verifying endpoint reachability and latency.',
  },
  {
    type: 'deployment_log',
    name: 'Deployment Pipelines',
    provider: 'ArgoCD / AWS CodeDeploy / GitHub Actions',
    icon: <Clock size={16} />,
    color: 'var(--violet)',
    freshnessSLA: '< 24 hours',
    role: 'Immutable record of binary releases, container tags, and commit hashes.',
  },
  {
    type: 'monitoring_alert',
    name: 'Alertmanager & Alarms',
    provider: 'Amazon CloudWatch Alarms / Prometheus',
    icon: <AlertOctagon size={16} />,
    color: 'var(--red)',
    freshnessSLA: 'Real-time (< 1 min)',
    role: 'Signals service degradation, latency spikes, or error rate breaches.',
  },
  {
    type: 'runbook',
    name: 'Operational Runbooks',
    provider: 'Confluence / Git repository docs',
    icon: <FileText size={16} />,
    color: 'var(--text-secondary)',
    freshnessSLA: '< 30 days (High Stale Risk)',
    role: 'Human-authored procedure guides. Frequently prone to drift.',
  },
];

export default function EvidenceSourcesView({ bundle }: EvidenceSourcesViewProps) {
  const activeSources = new Set(bundle?.evidence.map(e => e.source) ?? []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Database size={13} style={{ color: 'var(--cyan)' }} />
            Evidence Ingestion Sources & Provenance Architecture
          </div>
          <span className="badge badge-fresh">Content-Addressed (SHA-256)</span>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
          ContextFuse ingests operational signals across multiple systems of record. Every evidence record is assigned a
          deterministic content-addressed identifier (<code style={{ fontFamily: 'var(--font-mono)' }}>ev-[sha256:12]</code>),
          timestamped, and checked against staleness thresholds before being admitted into the agent context gate.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
          {SOURCE_CATALOG.map(source => {
            const isActive = activeSources.has(source.type as any);
            return (
              <div
                key={source.type}
                style={{
                  background: 'var(--bg-elevated)',
                  border: `1px solid ${isActive ? 'var(--cyan)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--radius)',
                  padding: 14,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: source.color }}>
                    {source.icon}
                    <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>
                      {source.name}
                    </span>
                  </div>
                  {isActive ? (
                    <span className="badge badge-fresh">In Context</span>
                  ) : (
                    <span className="badge badge-source">Registered</span>
                  )}
                </div>

                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  Provider: <span style={{ color: 'var(--text-secondary)' }}>{source.provider}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  Freshness SLA: <span style={{ color: 'var(--text-secondary)' }}>{source.freshnessSLA}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 4 }}>
                  {source.role}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
