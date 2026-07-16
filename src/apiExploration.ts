import { fetchJsonStrict } from "./apiClient";
import type { ExplorationMutationPayload, ExplorationThreadsPayload } from "./types";

export function getExplorationThreads(threadKey = "") {
  const query = new URLSearchParams({ limit: "30" });
  if (threadKey) query.set("thread", threadKey);
  return fetchJsonStrict<ExplorationThreadsPayload>(`/api/agent/exploration-threads?${query}`);
}

export function createExplorationThread(options: {
  analysisRunKey: string;
  analysisUnitKey: string;
  sessionKey?: string;
  turnKey?: string;
  title?: string;
  label?: string;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
}) {
  return fetchJsonStrict<ExplorationMutationPayload>("/api/agent/exploration-threads/create", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function addExplorationAnchor(options: {
  threadKey: string;
  parentAnchorKey: string;
  analysisRunKey: string;
  analysisUnitKey: string;
  sessionKey?: string;
  turnKey?: string;
  label?: string;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
}) {
  return fetchJsonStrict<ExplorationMutationPayload>("/api/agent/exploration-threads/add-anchor", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function setExplorationBoardItem(options: {
  threadKey: string;
  anchorKey: string;
  state: "pinned" | "removed";
  position?: number;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
}) {
  return fetchJsonStrict<ExplorationMutationPayload>("/api/agent/exploration-threads/board", {
    method: "POST",
    body: JSON.stringify(options),
  });
}
