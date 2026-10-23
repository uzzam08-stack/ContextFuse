import { useState, useEffect } from 'react';
import { BarChart3, Loader2, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import type { BenchmarkEntry } from '../../types';
import { api } from '../../utils/api';

export default function BenchmarkView() {
  const [data, setData] = useState<BenchmarkEntry[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const entries = await api.benchmark();
      setData(entries);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <BarChart3 size={13} style={{ color: 'var(--violet)' }} />
          Strategy Benchmark
          <span style={{ color: 'var(--text-muted)' }}>· Rules vs Bedrock vs Decider</span>
        </div>
        <button className="btn btn-ghost" onClick={load} disabled={loading}>
          <RefreshCw size={11} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Run
        </button>
      </div>

      {loading && (
        <div className="state-container">
          <div className="state-icon loading"><Loader2 size={20} /></div>
          <span className="state-title">Running Benchmark…</span>
          <span className="state-desc">Evaluating all three strategies on all scenarios.</span>
        </div>
      )}

      {error && (
        <div className="state-container">
          <div className="state-icon error"><XCircle size={20} /></div>
          <span className="state-title">Benchmark Failed</span>
          <span className="state-desc">{error}</span>
        </div>
      )}

      {data && !loading && (
        <>
          {/* Summary row */}
          <div className="three-col" style={{ marginBottom: 16 }}>
            {/* Rules */}
            <div style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius)',
              padding: '12px 14px',
              textAlign: 'center',
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--cyan)', marginBottom: 8 }}>
                Rules Only (Deterministic)
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--cyan)', lineHeight: 1, marginBottom: 4 }}>
                {data.filter(d => d.rules_correct).length}/{data.length}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>100% Policy Adherence</div>
            </div>

            {/* Bedrock */}
            {(() => {
              const fallbacks = data.filter(d => d.bedrock_is_fallback).length;
              const liveCount = data.length - fallbacks;
              const correct = data.filter(d => d.bedrock_correct === true).length;
              return (
                <div style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius)',
                  padding: '12px 14px',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--amber)', marginBottom: 8 }}>
                    Bedrock Only (Claude 3.5)
                  </div>
                  <div style={{ fontSize: fallbacks === data.length ? 22 : 28, fontWeight: 800, color: 'var(--amber)', lineHeight: 1.2, marginBottom: 4 }}>
                    {fallbacks === data.length ? 'FALLBACK' : `${correct}/${liveCount}`}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {fallbacks === data.length ? 'Model Offline (Score Omitted)' : 'Live Model Accuracy'}
                  </div>
                </div>
              );
            })()}

            {/* Decider */}
            {(() => {
              const fallbacks = data.filter(d => d.decider_is_fallback).length;
              const liveCount = data.length - fallbacks;
              const correct = data.filter(d => d.decider_correct === true).length;
              return (
                <div style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius)',
                  padding: '12px 14px',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--violet)', marginBottom: 8 }}>
                    Decider-Based (Strands 2B)
                  </div>
                  <div style={{ fontSize: fallbacks === data.length ? 22 : 28, fontWeight: 800, color: 'var(--violet)', lineHeight: 1.2, marginBottom: 4 }}>
                    {fallbacks === data.length ? 'FALLBACK' : `${correct}/${liveCount}`}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {fallbacks === data.length ? 'Model Offline (Score Omitted)' : 'Live Model Accuracy'}
                  </div>
                </div>
              );
            })()}
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="benchmark-table">
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Ground Truth</th>
                  <th>Rules Only</th>
                  <th>Rules ms</th>
                  <th>Bedrock Only</th>
                  <th>Bedrock ms</th>
                  <th>Decider</th>
                  <th>Decider ms</th>
                </tr>
              </thead>
              <tbody>
                {data.map(row => (
                  <tr key={row.scenario_id}>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{row.scenario_name}</td>
                    <td><span className={`action-chip ${row.ground_truth_action}`}>{row.ground_truth_action}</span></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className={`action-chip ${row.rules_only_action}`}>{row.rules_only_action}</span>
                        {row.rules_correct
                          ? <CheckCircle2 size={12} className="correct-tick" />
                          : <XCircle size={12} className="incorrect-tick" />}
                      </div>
                    </td>
                    <td><span className="latency-val">{row.rules_latency_ms.toFixed(2)}</span></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className={`action-chip ${row.bedrock_only_action}`}>{row.bedrock_only_action}</span>
                        {row.bedrock_is_fallback ? (
                          <span className="badge badge-missing" style={{ fontSize: 9, padding: '1px 5px' }}>Fallback</span>
                        ) : row.bedrock_correct ? (
                          <CheckCircle2 size={12} className="correct-tick" />
                        ) : (
                          <XCircle size={12} className="incorrect-tick" />
                        )}
                      </div>
                    </td>
                    <td><span className="latency-val">{row.bedrock_latency_ms.toFixed(0)}</span></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className={`action-chip ${row.decider_action}`}>{row.decider_action}</span>
                        {row.decider_is_fallback ? (
                          <span className="badge badge-missing" style={{ fontSize: 9, padding: '1px 5px' }}>Fallback</span>
                        ) : row.decider_correct ? (
                          <CheckCircle2 size={12} className="correct-tick" />
                        ) : (
                          <XCircle size={12} className="incorrect-tick" />
                        )}
                      </div>
                    </td>
                    <td><span className="latency-val">{row.decider_latency_ms.toFixed(0)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
            * <strong>Benchmark Honesty Guarantee:</strong> Live model accuracy is only scored when authentic API calls succeed. When Bedrock or Decider run in local fallback mode, their score is omitted (N/A) to prevent attributing deterministic fallback decisions to unavailable models.
          </div>
        </>
      )}
    </div>
  );
}
