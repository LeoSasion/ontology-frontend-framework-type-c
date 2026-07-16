import { fetchJson } from "./apiClient";
import type { AnalysisSnapshotsPayload } from "./types";

export type AnalysisSnapshotOperation = "create" | "refresh" | "replace" | "delete";

export type AnalysisSnapshotMutation = {
  operation: AnalysisSnapshotOperation;
  unitKey?: string;
  snapshotKey?: string;
  reason?: string;
  rowLimit?: number;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
};

const unavailable = { ok: false, error: "Local Analysis Snapshot service is unavailable" } satisfies AnalysisSnapshotsPayload;

export function getAnalysisSnapshots(unitKey: string) {
  const query = new URLSearchParams({ unit: unitKey, limit: "30" });
  return fetchJson<AnalysisSnapshotsPayload>(`/api/analysis-snapshots?${query}`, unavailable);
}

export function mutateAnalysisSnapshot(input: AnalysisSnapshotMutation) {
  return fetchJson<AnalysisSnapshotsPayload>(`/api/analysis-snapshots/${input.operation}`, unavailable, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      unitKey: input.unitKey,
      snapshotKey: input.snapshotKey,
      reason: input.reason,
      rowLimit: input.rowLimit,
      confirm: input.confirm === true,
      expectedPlanFingerprint: input.expectedPlanFingerprint,
    }),
  });
}
