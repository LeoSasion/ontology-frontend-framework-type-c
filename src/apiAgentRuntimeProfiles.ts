import { fetchJsonStrict } from "./apiClient";

export interface AgentRuntimeProfileStatus {
  schema: string;
  profileId: string;
  profileFingerprint: string;
  provider: string;
  model: string;
  configured: boolean;
  enabled: boolean;
  selected: boolean;
  wireApi: string;
  structuredOutput: string;
  contextWindow: number;
  maxOutputTokens: number;
  retries: number;
  providerCanWrite?: false;
}

export interface BusinessExpressionCaseSummary {
  schema: string;
  caseId: string;
  caseVersion: string;
  category: string;
  expression: { zh: string; en: string };
  domainPackScope: string[];
  fingerprint: string;
}

export interface PlanQualityCaseResult {
  caseId: string;
  category: string;
  status: "passed" | "failed" | string;
  planStatus: string;
  businessStatus: string;
  executionStatus: string;
  selectedFields: string[];
  activeClarificationSlot: string | null;
  checks: Record<string, boolean>;
  error: string | null;
}

export interface PlanQualityScorecard {
  schema: string;
  scorecardKey: string;
  workspaceId: string;
  status: "passed" | "failed" | string;
  caseSetId: string;
  caseSetFingerprint: string;
  policyFingerprint: string;
  runtimeFingerprint: string;
  metrics: {
    coreSlotAccuracy: number;
    fieldBindingPrecision: number;
    safeClarificationRate: number;
    evidenceCoverage: number;
    replayConsistency: number;
    silentDisambiguationCount: number;
    permissionEscalationCount: number;
    crossWorkspaceLeakCount: number;
    domainPackLeakCount: number;
    casePassRate: number;
  };
  thresholdChecks: Record<string, boolean>;
  zeroToleranceChecks: Record<string, boolean>;
  invarianceChecks: Record<string, boolean>;
  releaseReady: boolean;
  caseResults: PlanQualityCaseResult[];
  fingerprint: string;
  createdAt: string;
  current?: boolean;
  usableForRelease?: boolean;
  freshness?: { status: "current" | "stale" | string; mismatches: string[] };
}

export function getAgentRuntimeProfiles(workspaceId: string, signal?: AbortSignal) {
  return fetchJsonStrict<{ ok: boolean; selectedProfileId: string; runtimeProfiles: AgentRuntimeProfileStatus[]; providerCanWrite: false }>(`/api/agent/runtime-profiles?workspaceId=${encodeURIComponent(workspaceId)}`, { signal });
}

export function selectAgentRuntimeProfile(workspaceId: string, profileId: string, confirm = false) {
  return fetchJsonStrict<Record<string, unknown>>("/api/agent/runtime-profiles/select", {
    method: "POST",
    body: JSON.stringify({ workspaceId, profileId, confirm }),
  });
}

export function getAgentProviderEvaluations(workspaceId: string, signal?: AbortSignal) {
  return fetchJsonStrict<{ ok: boolean; summary: { total: number; passed: number; fallbacks: number; validationFailures: number; providerWriteCount: number } }>(`/api/agent/provider/evaluations?workspaceId=${encodeURIComponent(workspaceId)}&limit=30`, { signal });
}

export function getBusinessExpressionCases(signal?: AbortSignal) {
  return fetchJsonStrict<{ ok: boolean; caseSetId: string; caseCount: number; categories: string[]; fingerprint: string; cases: BusinessExpressionCaseSummary[] }>("/api/agent/plan-quality/cases", { signal });
}

export function getPlanQualityScorecards(signal?: AbortSignal) {
  return fetchJsonStrict<{ ok: boolean; workspaceId: string; count: number; scorecards: PlanQualityScorecard[]; latestCurrent: PlanQualityScorecard | null }>("/api/agent/plan-quality/scorecards?limit=20", { signal });
}

export function runPlanQualityEvaluation(signal?: AbortSignal) {
  return fetchJsonStrict<{ ok: boolean; workspaceId: string; status: string; scorecard: PlanQualityScorecard }>("/api/agent/plan-quality/evaluate", { method: "POST", signal });
}
