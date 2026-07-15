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

export function getAgentRuntimeProfiles(workspaceId: string) {
  return fetchJsonStrict<{ ok: boolean; selectedProfileId: string; runtimeProfiles: AgentRuntimeProfileStatus[]; providerCanWrite: false }>(`/api/agent/runtime-profiles?workspaceId=${encodeURIComponent(workspaceId)}`);
}

export function selectAgentRuntimeProfile(workspaceId: string, profileId: string, confirm = false) {
  return fetchJsonStrict<Record<string, unknown>>("/api/agent/runtime-profiles/select", {
    method: "POST",
    body: JSON.stringify({ workspaceId, profileId, confirm }),
  });
}

export function getAgentProviderEvaluations(workspaceId: string) {
  return fetchJsonStrict<{ ok: boolean; summary: { total: number; passed: number; fallbacks: number; validationFailures: number; providerWriteCount: number } }>(`/api/agent/provider/evaluations?workspaceId=${encodeURIComponent(workspaceId)}&limit=30`);
}
