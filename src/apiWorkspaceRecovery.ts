import { fetchJsonStrict } from "./apiClient";
import type { WorkspaceRecoveryOperation, WorkspaceRecoveryPayload } from "./typesWorkspaceRecovery";

export type WorkspaceRecoveryMutation = {
  operation: WorkspaceRecoveryOperation;
  requestKey: string;
  recoveryPointKey?: string;
  reason?: string;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
};

export function getWorkspaceRecoveryPoints(options: { limit?: number; verify?: boolean; signal?: AbortSignal } = {}) {
  const query = new URLSearchParams({
    limit: String(Math.max(1, Math.min(options.limit ?? 5, 100))),
  });
  if (options.verify) query.set("verify", "true");
  return fetchJsonStrict<WorkspaceRecoveryPayload>(`/api/workspace-recovery?${query}`, { signal: options.signal });
}

export function inspectWorkspaceRecoveryPoint(recoveryPointKey: string, signal?: AbortSignal) {
  return fetchJsonStrict<WorkspaceRecoveryPayload>(
    `/api/workspace-recovery/${encodeURIComponent(recoveryPointKey)}`,
    { signal },
  );
}

export function mutateWorkspaceRecovery(input: WorkspaceRecoveryMutation, signal?: AbortSignal) {
  return fetchJsonStrict<WorkspaceRecoveryPayload>(`/api/workspace-recovery/${input.operation}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-idempotency-key": input.requestKey,
    },
    body: JSON.stringify({
      requestKey: input.requestKey,
      recoveryPointKey: input.recoveryPointKey,
      reason: input.reason,
      confirm: input.confirm === true,
      expectedPlanFingerprint: input.expectedPlanFingerprint,
    }),
    signal,
  });
}
