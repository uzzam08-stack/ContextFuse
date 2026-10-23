import { useState, useCallback, useEffect } from 'react';
import type { ScenarioInfo, OrchestrationResult, ContextBundle, SystemStatus } from './types';
import { api } from './utils/api';
import Sidebar from './components/sidebar/Sidebar';
import TopBar from './components/topbar/TopBar';
import OverviewPage from './pages/OverviewPage';

type Page = 'overview' | 'evidence' | 'replay' | 'policy' | 'sources' | 'patterns' | 'benchmark';

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('overview');
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [bundle, setBundle] = useState<ContextBundle | null>(null);
  const [result, setResult] = useState<OrchestrationResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<'online' | 'offline' | 'checking'>('checking');
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);

  const fetchStatus = useCallback(() => {
    api.health()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'));

    api.status()
      .then(setSystemStatus)
      .catch(() => {});
  }, []);

  // Check backend health and status on mount
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Load scenarios
  useEffect(() => {
    api.scenarios()
      .then(setScenarios)
      .catch(() => {});
  }, []);

  const handleSelectScenario = useCallback(async (id: string) => {
    setSelectedScenario(id);
    setResult(null);
    setError(null);
    try {
      const b = await api.scenario(id);
      setBundle(b);
    } catch {
      setBundle(null);
    }
  }, []);

  const handleRun = useCallback(async () => {
    if (!selectedScenario) return;
    setIsRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.run(selectedScenario);
      setResult(res);
      // Refresh bundle with populated risks/evidence from run
      const b = await api.scenario(selectedScenario);
      setBundle(b);
      // Refresh status after run
      fetchStatus();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsRunning(false);
    }
  }, [selectedScenario, fetchStatus]);

  const handleRefresh = useCallback(() => {
    if (selectedScenario) {
      handleSelectScenario(selectedScenario);
    }
    fetchStatus();
  }, [selectedScenario, handleSelectScenario, fetchStatus]);

  const selectedName = scenarios.find(s => s.id === selectedScenario)?.name ?? null;

  return (
    <div className="app-shell">
      <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />
      <div className="main-area">
        <TopBar
          currentPage={currentPage}
          backendStatus={backendStatus}
          systemStatus={systemStatus}
          selectedScenario={selectedName}
          onRefresh={handleRefresh}
          isRunning={isRunning}
        />
        <main className="page-content">
          <OverviewPage
            scenarios={scenarios}
            selectedScenario={selectedScenario}
            bundle={bundle}
            result={result}
            isRunning={isRunning}
            error={error}
            onSelectScenario={handleSelectScenario}
            onRun={handleRun}
            currentPage={currentPage}
          />
        </main>
      </div>
    </div>
  );
}
