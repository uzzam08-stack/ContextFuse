import { RefreshCw, Zap, Cpu, Database, Cloud } from 'lucide-react';
import type { SystemStatus } from '../../types';

type Page = 'overview' | 'evidence' | 'replay' | 'policy' | 'sources' | 'patterns' | 'benchmark';

const PAGE_LABELS: Record<Page, string> = {
  overview:  'Overview',
  evidence:  'Evidence Lens',
  replay:    'Decision Replay',
  policy:    'Policy Guard',
  sources:   'Evidence Sources',
  patterns:  'Decision Patterns',
  benchmark: 'Benchmark',
};

interface TopBarProps {
  currentPage: Page;
  backendStatus: 'online' | 'offline' | 'checking';
  systemStatus?: SystemStatus | null;
  selectedScenario: string | null;
  onRefresh: () => void;
  isRunning: boolean;
}

export default function TopBar({
  currentPage,
  backendStatus,
  systemStatus,
  selectedScenario,
  onRefresh,
  isRunning,
}: TopBarProps) {
  const statusLabel = {
    online: 'Backend Connected',
    offline: 'Backend Offline',
    checking: 'Connecting…',
  }[backendStatus];

  const bedrockStatus = systemStatus?.integrations?.bedrock?.status ?? 'LOCAL FALLBACK';
  const deciderStatus = systemStatus?.integrations?.decider?.status ?? 'LOCAL FALLBACK';
  const dynamoStatus = systemStatus?.integrations?.dynamodb?.mode === 'dynamodb' ? 'LIVE' : 'FALLBACK';

  return (
    <header className="topbar">
      <div className="topbar-breadcrumbs">
        <span className="crumb">ContextFuse</span>
        <span className="crumb-sep">/</span>
        <span className="crumb">{PAGE_LABELS[currentPage]}</span>
        {selectedScenario && (
          <>
            <span className="crumb-sep">/</span>
            <span className="crumb-active">{selectedScenario}</span>
          </>
        )}
      </div>

      <div className="topbar-actions">
        {/* Backend Connectivity */}
        <div className="status-chip" title="FastAPI Backend Status">
          <span className={`status-dot ${backendStatus}`} />
          <span>{statusLabel}</span>
        </div>

        {/* Amazon Bedrock Integration Status */}
        <div
          className="status-chip"
          title={systemStatus?.integrations?.bedrock?.note ?? 'Bedrock Inference'}
          style={{
            borderColor: bedrockStatus === 'LIVE AND TESTED' ? 'rgba(16,185,129,0.3)' : 'rgba(245,158,11,0.2)',
          }}
        >
          <Cloud size={10} style={{ color: bedrockStatus === 'LIVE AND TESTED' ? 'var(--green)' : 'var(--amber)' }} />
          <span style={{ color: bedrockStatus === 'LIVE AND TESTED' ? 'var(--green)' : 'var(--amber)' }}>
            Bedrock: {bedrockStatus === 'LIVE AND TESTED' ? 'Live' : 'Fallback'}
          </span>
        </div>

        {/* Strands Decider 2B Status */}
        <div
          className="status-chip"
          title={systemStatus?.integrations?.decider?.note ?? 'Strands Decider'}
          style={{
            borderColor: deciderStatus === 'LIVE AND TESTED' ? 'rgba(16,185,129,0.3)' : 'rgba(139,92,246,0.2)',
          }}
        >
          <Cpu size={10} style={{ color: deciderStatus === 'LIVE AND TESTED' ? 'var(--green)' : 'var(--violet)' }} />
          <span style={{ color: deciderStatus === 'LIVE AND TESTED' ? 'var(--green)' : 'var(--violet)' }}>
            Decider: {deciderStatus === 'LIVE AND TESTED' ? 'Live' : 'Fallback'}
          </span>
        </div>

        {/* Storage Persistence Status */}
        <div className="status-chip" title={systemStatus?.integrations?.dynamodb?.storage_note ?? 'Run Persistence'}>
          <Database size={10} style={{ color: dynamoStatus === 'LIVE' ? 'var(--green)' : 'var(--cyan)' }} />
          <span style={{ color: dynamoStatus === 'LIVE' ? 'var(--green)' : 'var(--cyan)' }}>
            {dynamoStatus === 'LIVE' ? 'DynamoDB' : 'In-Memory Store'}
          </span>
        </div>

        {/* Simulation Badge */}
        <div className="status-chip">
          <Zap size={10} style={{ color: 'var(--amber)' }} />
          <span style={{ color: 'var(--amber)' }}>Simulation</span>
        </div>

        <button
          className="btn btn-ghost"
          onClick={onRefresh}
          disabled={isRunning}
          title="Refresh"
        >
          <RefreshCw
            size={12}
            style={{ animation: isRunning ? 'spin 1s linear infinite' : 'none' }}
          />
          Refresh
        </button>
      </div>
    </header>
  );
}
