// ContextFuse – API client

import type {
  OrchestrationResult,
  ScenarioInfo,
  ContextBundle,
  BenchmarkEntry,
  SystemStatus,
} from '../types';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || '/api';

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => apiFetch<{ status: string; service: string }>('/health'),
  status: () => apiFetch<SystemStatus>('/status'),
  scenarios: () =>
    apiFetch<{ scenarios: ScenarioInfo[] }>('/scenarios').then((r) => r.scenarios),
  scenario: (id: string) => apiFetch<ContextBundle>(`/scenarios/${id}`),
  run: (id: string) =>
    apiFetch<OrchestrationResult>(`/run/${id}`, { method: 'POST' }),
  benchmark: () => apiFetch<BenchmarkEntry[]>('/benchmark'),
  runs: () =>
    apiFetch<{ runs: OrchestrationResult[] }>('/runs').then((r) => r.runs),
  runById: (id: string) => apiFetch<OrchestrationResult>(`/runs/${id}`),
};
