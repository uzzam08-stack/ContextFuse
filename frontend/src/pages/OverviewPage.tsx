import { useState, useCallback, useEffect } from 'react';
import { Play, Loader2, Info, CheckCircle2, Database, BarChart3, Activity } from 'lucide-react';
import type { ScenarioInfo, OrchestrationResult, ContextBundle } from '../types';
import { api } from '../utils/api';
import KpiCards from '../components/cards/KpiCards';
import EvidenceLens from '../components/evidence/EvidenceLens';
import DecisionReplay from '../components/decision/DecisionReplay';
import Timeline from '../components/timeline/Timeline';
import OutcomePanel from '../components/timeline/OutcomePanel';
import PolicyGuard from '../components/policy/PolicyGuard';
import BenchmarkView from '../components/benchmark/BenchmarkView';
import EvidenceSourcesView from '../components/evidence/EvidenceSourcesView';
import DecisionPatternsView from '../components/decision/DecisionPatternsView';
import ReplayHistoryView from '../components/decision/ReplayHistoryView';

type Page = 'overview' | 'evidence' | 'replay' | 'policy' | 'sources' | 'patterns' | 'benchmark';

interface OverviewPageProps {
  scenarios: ScenarioInfo[];
  selectedScenario: string | null;
  bundle: ContextBundle | null;
  result: OrchestrationResult | null;
  isRunning: boolean;
  error: string | null;
  onSelectScenario: (id: string) => void;
  onRun: () => void;
  currentPage: Page;
}

function ScenarioSelector({
  scenarios,
  selected,
  onSelect,
  onRun,
  isRunning,
}: {
  scenarios: ScenarioInfo[];
  selected: string | null;
  onSelect: (id: string) => void;
  onRun: () => void;
  isRunning: boolean;
}) {
  const icons: Record<string, React.ReactNode> = {
    stale_db_endpoint: <Database size={14} />,
    missing_health:    <Activity size={14} />,
    clean_context:     <CheckCircle2 size={14} />,
  };

  const badges: Record<string, { label: string; color: string }> = {
    stale_db_endpoint: { label: 'CONFLICT DETECTED', color: 'var(--red)' },
    missing_health:    { label: 'MISSING TELEMETRY', color: 'var(--amber)' },
    clean_context:     { label: 'CONSISTENT SIGNALS', color: 'var(--green)' },
  };

  const selectedScenario = scenarios.find(s => s.id === selected);

  return (
    <div className="card" style={{ borderColor: selected ? 'var(--border-subtle)' : 'var(--cyan)' }}>
      <div className="card-header" style={{ paddingBottom: 10 }}>
        <div>
          <div className="card-title" style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Info size={14} style={{ color: 'var(--cyan)' }} />
            Operational Incident Context
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Step 1: Select an incident scenario &bull; Step 2: Run Context Safety Gate
          </div>
        </div>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.06em', fontWeight: 600 }}>
          READ-ONLY SIMULATION
        </span>
      </div>

      {/* Scenario buttons */}
      <div className="scenario-selector" style={{ marginBottom: 14 }}>
        {scenarios.map(s => {
          const isSelected = selected === s.id;
          const badge = badges[s.id];
          return (
            <button
              key={s.id}
              className={`scenario-btn${isSelected ? ' active' : ''}`}
              onClick={() => onSelect(s.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
                padding: '8px 12px',
                position: 'relative',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontWeight: isSelected ? 600 : 500 }}>
                {icons[s.id]}
                {s.name}
              </span>
              {badge && (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    padding: '1px 5px',
                    borderRadius: 3,
                    background: 'rgba(255,255,255,0.06)',
                    color: badge.color,
                  }}
                >
                  {badge.label}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Detail & Run Action Bar */}
      {selectedScenario ? (
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius)',
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }}>
            <div style={{ flex: 1, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {selectedScenario.description}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>Policy Expected:</div>
              <span className={`action-chip ${selectedScenario.ground_truth_action}`}>
                {selectedScenario.ground_truth_action}
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border-subtle)', paddingTop: 10 }}>
            <button
              className="btn btn-primary"
              onClick={onRun}
              disabled={isRunning}
              style={{
                padding: '10px 24px',
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                boxShadow: '0 0 12px rgba(6,182,212,0.25)',
              }}
            >
              {isRunning ? (
                <>
                  <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} />
                  Evaluating Safety Gate…
                </>
              ) : (
                <>
                  <Play size={15} />
                  Run Safety Evaluation &rarr;
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '12px', color: 'var(--text-muted)', fontSize: 12 }}>
          &larr; Choose an incident scenario above to begin evaluation
        </div>
      )}
    </div>
  );
}

export default function OverviewPage({
  scenarios,
  selectedScenario,
  bundle,
  result,
  isRunning,
  error,
  onSelectScenario,
  onRun,
  currentPage,
}: OverviewPageProps) {
  // Page routing
  if (currentPage === 'evidence') {
    return (
      <EvidenceLens
        evidence={bundle?.evidence ?? []}
        risks={bundle?.risks ?? []}
      />
    );
  }

  if (currentPage === 'replay') {
    return <ReplayHistoryView currentResult={result} />;
  }

  if (currentPage === 'policy') {
    return <PolicyGuard verdict={result?.safety_verdict ?? null} />;
  }

  if (currentPage === 'sources') {
    return <EvidenceSourcesView bundle={bundle} />;
  }

  if (currentPage === 'patterns') {
    return <DecisionPatternsView />;
  }

  if (currentPage === 'benchmark') {
    return <BenchmarkView />;
  }

  // Default: Overview
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Scenario selector with integrated run action */}
      <ScenarioSelector
        scenarios={scenarios}
        selected={selectedScenario}
        onSelect={onSelectScenario}
        onRun={onRun}
        isRunning={isRunning}
      />

      {/* Evaluating Feedback Banner */}
      {isRunning && (
        <div
          className="card"
          style={{
            borderColor: 'var(--cyan)',
            background: 'rgba(6, 182, 212, 0.06)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '12px 16px',
          }}
        >
          <Loader2 size={18} style={{ color: 'var(--cyan)', animation: 'spin 1s linear infinite', flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--cyan)' }}>
              ContextFuse Pipeline Evaluating: {scenarios.find(s => s.id === selectedScenario)?.name}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              Ingesting evidence corpus &bull; Checking freshness & contradictions &bull; Consulting pointer decider &bull; Enforcing deterministic safety policy
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card" style={{ borderColor: 'rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.05)' }}>
          <div style={{ color: 'var(--red)', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Orchestration Error
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{error}</div>
        </div>
      )}

      {/* KPIs */}
      <KpiCards result={result} isRunning={isRunning} />

      {result && (
        <>
          {/* Two-col: Evidence Lens + Decision Replay */}
          <div className="two-col">
            <EvidenceLens
              evidence={bundle?.evidence ?? []}
              risks={bundle?.risks ?? []}
            />
            <DecisionReplay deciderResult={result.decider_result} />
          </div>

          {/* Timeline */}
          <Timeline events={result.timeline} />

          {/* Two-col: Outcome + Policy */}
          <div className="two-col">
            <OutcomePanel outcome={result.outcome_brief} toolResult={result.tool_result} verdict={result.safety_verdict} />
            <PolicyGuard verdict={result.safety_verdict} />
          </div>
        </>
      )}

      {!result && !isRunning && (
        <div className="card">
          <div className="state-container">
            <div className="state-icon empty">
              <BarChart3 size={22} />
            </div>
            <span className="state-title">Select a Scenario and Run</span>
            <span className="state-desc">
              Choose one of the three simulated incidents above and click Run Scenario to
              start the ContextFuse orchestration pipeline.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
