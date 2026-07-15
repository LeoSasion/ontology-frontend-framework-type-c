import type { ContextBudgetReceipt } from "./contextBudget";

export type AgentProviderUsage = {
  promptTokens: number | null;
  completionTokens: number | null;
  totalTokens: number | null;
};

export type AgentProviderStatus = {
  profileId: string;
  profileFingerprint: string;
  provider: string;
  model: string;
  configured: boolean;
  enabled: boolean;
  mode: "provider" | "deterministic";
  baseUrl: string;
  wireApi: "none" | "openai-chat-completions";
  structuredOutput: "native-contract" | "json-object" | "prompt-contract";
  contextWindow: number;
  reasoningBudget: "none" | "low" | "medium";
  maxOutputTokens: number;
  retries: number;
  stages: string[];
  outboundPolicy: "deterministic-only" | "grounded-context-v1";
};

export type GroundedAgentContext = {
  schema: "aibi-agent-provider-context/v1";
  question: string;
  workspaceId: string;
  answer: {
    kind: string;
    confidence: string;
    title: string;
    summary: string;
    metrics: Array<{ label: string; value: string | number | null }>;
    blocked: boolean;
  };
  matched: {
    table: string | null;
    dashboard: string | null;
  };
  knowledgeRules: Array<{ id: string; title: string; grain: string }>;
  queryReceipt: {
    key: string | null;
    status: string;
    selection: Record<string, unknown>;
    evidenceTypes: string[];
    unresolved: unknown[];
  };
  analysisUnit: {
    key: string | null;
    kind: string | null;
    status: string | null;
    resultFingerprint: string | null;
    validationStatus: string | null;
    chartType: string | null;
    chartStatus: string | null;
    chartBlockers: string[];
  };
  actionBoundary: {
    requiresConfirmation: boolean;
    kind: string;
    status: string;
  };
  contextBudget?: ContextBudgetReceipt;
};

export type AgentProviderNarrative = {
  summary: string;
  rationale: string[];
  clarification: string | null;
  nextActions: string[];
  citedEvidence: string[];
  certainty: "grounded" | "needs_clarification";
};

export type AgentProviderRun = {
  ok: boolean;
  provider: string;
  model: string;
  runId: string;
  attempts: number;
  durationMs: number;
  requestHash: string;
  usage: AgentProviderUsage | null;
  estimatedCostUsd: number;
  profileId: string;
  profileFingerprint: string;
  validation: {
    status: "passed" | "failed" | "not-run";
    checks: Record<string, boolean>;
  };
  narrative: AgentProviderNarrative | null;
  errorCode: string | null;
};

export interface AgentProvider {
  status(): AgentProviderStatus;
  generate(context: GroundedAgentContext): Promise<AgentProviderRun>;
}
