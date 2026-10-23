import { useState, useEffect } from 'react';
import { Play, History, RefreshCw, Cpu, Shield, Clock, AlertTriangle, CheckCircle2, Wrench } from 'lucide-react';
import type { OrchestrationResult } from '../../types';
import { api } from '../../utils/api';
import DecisionReplay from './DecisionReplay';
import PolicyGuard from '../policy/PolicyGuard';
import Timeline from '../timeline/Timeline';
import OutcomePanel from '../timeline/OutcomePanel';

interface ReplayHistoryViewProps {
  currentResult: OrchestrationResult | null;
}

export default function ReplayHistoryView({ currentResult }: ReplayHistoryViewProps) {
  const [runs, setRuns] = useState<OrchestrationResult[]>([]);
  const [selectedRun, setSelectedRun] = useState<OrchestrationResult | null>(currentResult);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.runs();
      setRuns(data);
      if (!selectedRun && data.length > 0) {
        setSelectedRun(data[0]);
      } else if (currentResult) {
        setSelectedRun(currentResult);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  useEffect(() => {
    if (currentResult) {
      setSelectedRun(currentResult);
    }
  }, [currentResult]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <History size={16} style={{ color: 'var(--cyan)' }} />
            Decision History & Replay
          </h2>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            Audit log and decision state replay across past operational evaluations.
          </p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={fetchRuns}
          disabled={loading}
          style={{ fontSize: 12, padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <RefreshCw size={12} className={loading ? 'spin' : ''} />
          Refresh Runs
        </button>
      </div>

      {error && (
        <div className="fallback-banner">
          <AlertTriangle size={14} />
          <span>Failed to load run history: {error}</span>
        </div>
      )}

      {/* Main Layout: Left = Run List, Right = Selected Run Detail */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16, alignItems: 'start' }}>
        {/* Run List */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="card-header" style={{ padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div className="card-title" style={{ fontSize: 12 }}>
              <Clock size={12} />
              Recent Runs ({runs.length})
            </div>
          </div>
          <div style={{ maxHeight: '680px', overflowY: 'auto' }}>
            {runs.length === 0 ? (
              <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                No runs recorded in memory or DynamoDB. Execute a scenario to record an audit trail.
              </div>
            ) : (
              runs.map((run) => {
                const isSelected = selectedRun?.run_id === run.run_id;
                const action = run.decider_result.selected_action;
                const status = run.outcome_brief.safety_status;
                return (
                  <div
                    key={run.run_id}
                    onClick={() => setSelectedRun(run)}
                    style={{
                      padding: '10px 14px',
                      borderBottom: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      background: isSelected ? 'var(--bg-elevated)' : 'transparent',
                      borderLeft: isSelected ? '3px solid var(--cyan)' : '3px solid transparent',
                      transition: 'background 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <code style={{ fontSize: 11, color: 'var(--cyan)', fontWeight: 600 }}>{run.run_id}</code>
                      <span className={`badge badge-${status === 'safe' ? 'fresh' : status === 'escalated' ? 'conflict' : 'missing'}`}>
                        {status}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, marginBottom: 4 }}>
                      {run.scenario_id}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--text-secondary)' }}>
                      <span className={`action-chip ${action}`} style={{ fontSize: 9, padding: '2px 6px' }}>
                        {action}
                      </span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                        {run.completed_at ? new Date(run.completed_at).toLocaleTimeString() : 'Recent'}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected Run Inspection */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {selectedRun ? (
            <>
              {/* Meta Banner */}
              <div className="card" style={{ padding: '12px 16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                      Replaying Run: <code style={{ color: 'var(--cyan)' }}>{selectedRun.run_id}</code>
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      Scenario: <strong style={{ color: 'var(--text-secondary)' }}>{selectedRun.scenario_id}</strong>
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        padding: '2px 7px',
                        borderRadius: 3,
                        background: selectedRun.decider_result.is_fallback ? 'rgba(239,68,68,0.12)' : 'rgba(34,197,94,0.12)',
                        color: selectedRun.decider_result.is_fallback ? 'var(--amber)' : 'var(--green)',
                        border: `1px solid ${selectedRun.decider_result.is_fallback ? 'rgba(239,68,68,0.25)' : 'rgba(34,197,94,0.25)'}`,
                      }}
                    >
                      Decider: {selectedRun.decider_result.is_fallback ? 'Local Fallback' : 'Live Strands 2B'}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        padding: '2px 7px',
                        borderRadius: 3,
                        background: selectedRun.outcome_brief.is_bedrock_available ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                        color: selectedRun.outcome_brief.is_bedrock_available ? 'var(--green)' : 'var(--amber)',
                        border: `1px solid ${selectedRun.outcome_brief.is_bedrock_available ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
                      }}
                    >
                      Bedrock: {selectedRun.outcome_brief.is_bedrock_available ? 'Live Claude 3.5' : 'Local Fallback'}
                    </span>
                    <code style={{ fontSize: 10, color: 'var(--cyan)', background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 3 }}>
                      {selectedRun.safety_verdict.policy_rule}
                    </code>
                    <span className={`badge badge-${selectedRun.outcome_brief.safety_status === 'safe' ? 'fresh' : selectedRun.outcome_brief.safety_status === 'escalated' ? 'conflict' : 'missing'}`}>
                      {selectedRun.outcome_brief.safety_status.toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>

              {/* Decider & Policy Guard Replay */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <DecisionReplay deciderResult={selectedRun.decider_result} />
                <PolicyGuard verdict={selectedRun.safety_verdict} />
              </div>

              {/* Tool Execution if available */}
              {selectedRun.tool_result && (
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">
                      <Wrench size={13} style={{ color: 'var(--cyan)' }} />
                      Simulated Tool Call: <code>{selectedRun.tool_result.tool_name}</code>
                    </div>
                    <span className="badge badge-fresh">Simulated Read-Only</span>
                  </div>
                  <div style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', padding: 10, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                    <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>// Input Parameters</div>
                    <pre style={{ color: 'var(--cyan)', margin: '0 0 8px 0' }}>{JSON.stringify(selectedRun.tool_result.input_params, null, 2)}</pre>
                    <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>// Tool Output</div>
                    <pre style={{ color: 'var(--green)', margin: 0 }}>{JSON.stringify(selectedRun.tool_result.output, null, 2)}</pre>
                  </div>
                </div>
              )}

              {/* Outcome Brief */}
              <OutcomePanel outcome={selectedRun.outcome_brief} toolResult={selectedRun.tool_result ?? null} verdict={selectedRun.safety_verdict} />

              {/* Timeline */}
              <Timeline events={selectedRun.timeline} />
            </>
          ) : (
            <div className="card" style={{ padding: 40, textAlign: 'center' }}>
              <Play size={24} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
              <h3 style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Select a run from the history</h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                Review past Decider choices, policy checks, tool invocations, and full decision timelines.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
