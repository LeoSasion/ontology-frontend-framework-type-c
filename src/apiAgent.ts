import { fetchJson, fetchJsonStrict } from "./apiClient";
import { emptyActionDrafts } from "./emptyWorkspaceData";
import type { ActionDraftPayload, AgentAskResult } from "./types";

export function askAgent(prompt: string, options: { parentRunKey?: string; branchLabel?: string; workspaceId?: string; sessionKey?: string } = {}) {
  return fetchJsonStrict<AgentAskResult>("/api/agent/ask", {
    method: "POST",
    body: JSON.stringify({ prompt, ...options }),
  });
}

export function askAgentReadOnly(prompt: string, workspaceId?: string, sessionKey?: string) {
  return fetchJsonStrict<AgentAskResult>("/api/agent/explain", {
    method: "POST",
    body: JSON.stringify({ prompt, workspaceId, sessionKey }),
  });
}

export function confirmAction(actionKey: string, confirm = false, reject = false, workspaceId?: string) {
  return fetchJson<Record<string, unknown>>("/api/actions/confirm", { ok: false, dryRun: true }, {
    method: "POST",
    body: JSON.stringify({ actionKey, confirm, reject, workspaceId }),
  });
}

export function getActionDrafts() {
  return fetchJson<ActionDraftPayload>("/api/actions?limit=12", emptyActionDrafts);
}
