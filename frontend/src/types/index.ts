// ContextFuse – TypeScript type definitions matching backend Pydantic schemas

export type FreshnessState = 'fresh' | 'recent' | 'stale' | 'unknown';
export type ConflictState = 'none' | 'conflict' | 'missing' | 'superseded' | 'untrusted';
export type EvidenceSource =
  | 'runbook'
  | 'config_snapshot'
  | 'change_event'
  | 'health_check'
  | 'deployment_log'
  | 'monitoring_alert';

export type Action = 'PROCEED' | 'VERIFY' | 'RETRIEVE' | 'ESCALATE' | 'ABSTAIN' | 'BLOCK';
export const ALL_ACTIONS: Action[] = ['PROCEED', 'VERIFY', 'RETRIEVE', 'ESCALATE', 'ABSTAIN', 'BLOCK'];

export interface EvidenceRecord {
  evidence_id: string;
  source: EvidenceSource;
  source_path: string;
  field: string;
  value: unknown;
  recorded_at: string;
  ingested_at: string;
  expires_at?: string | null;
  is_trusted?: boolean;
  provenance: string[];
  freshness: FreshnessState;
  conflict_state: ConflictState;
  conflict_with: string[];
  notes: string;
}

export interface RiskSignal {
  risk_id: string;
  risk_type: 'stale' | 'conflict' | 'missing' | 'untrusted';
  severity: 'high' | 'medium' | 'low';
  description: string;
  implicated_evidence: string[];
  detected_at: string;
}

export interface ContextBundle {
  scenario_id: string;
  scenario_name: string;
  scenario_description: string;
  evidence: EvidenceRecord[];
  risks: RiskSignal[];
  is_safe: boolean;
  loaded_at: string;
}

export interface DeciderResult {
  selected_action: Action;
  probabilities: Record<string, number>;
  confidence: number;
  is_fallback: boolean;
  fallback_reason: string | null;
  raw_response: unknown | null;
  latency_ms: number | null;
}

export interface SafetyVerdict {
  action: Action;
  permitted: boolean;
  policy_rule: string;
  explanation: string;
  safe_next_step?: string;
}

export interface IntegrationDetail {
  status: string;
  note?: string;
  model_name?: string;
  model_id?: string;
  region?: string;
  mode?: string;
  is_dynamodb_active?: boolean;
  table_name?: string;
  storage_note?: string;
}

export interface SystemStatus {
  app: string;
  version: string;
  integrations: {
    bedrock: IntegrationDetail;
    decider: IntegrationDetail;
    dynamodb: IntegrationDetail;
    cloudwatch: IntegrationDetail;
    lambda: IntegrationDetail;
  };
}

export interface TimelineEvent {
  step: number;
  stage: string;
  label: string;
  detail: string;
  status: 'complete' | 'active' | 'pending' | 'error' | 'warning';
  timestamp: string;
  evidence_ids: string[];
}

export interface ToolCallResult {
  tool_name: string;
  input_params: Record<string, unknown>;
  output: unknown;
  is_simulated: boolean;
  safety_note: string;
}

export interface OutcomeBrief {
  summary: string;
  cited_evidence_ids: string[];
  unresolved_risks: string[];
  safety_status: 'safe' | 'unsafe' | 'escalated' | 'abstained';
  bedrock_model_id: string | null;
  bedrock_latency_ms: number | null;
  is_bedrock_available: boolean;
  fallback_note: string | null;
  raw_bedrock_response: unknown | null;
}

export interface OrchestrationResult {
  run_id: string;
  scenario_id: string;
  evidence_count: number;
  risk_count: number;
  decider_result: DeciderResult;
  safety_verdict: SafetyVerdict;
  tool_result: ToolCallResult | null;
  outcome_brief: OutcomeBrief;
  timeline: TimelineEvent[];
  completed_at: string;
}

export interface ScenarioInfo {
  id: string;
  name: string;
  description: string;
  ground_truth_action: Action;
}

export interface BenchmarkEntry {
  scenario_id: string;
  scenario_name: string;
  rules_only_action: Action;
  bedrock_only_action: Action;
  decider_action: Action;
  ground_truth_action: Action;
  rules_correct: boolean;
  bedrock_correct: boolean | null;
  decider_correct: boolean | null;
  bedrock_is_fallback: boolean;
  decider_is_fallback: boolean;
  bedrock_status: string;
  decider_status: string;
  rules_latency_ms: number;
  bedrock_latency_ms: number;
  decider_latency_ms: number;
}

