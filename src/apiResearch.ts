import { fetchJsonStrict } from "./apiClient";
import type { ResearchMutationPayload, ResearchRunsPayload } from "./types";

export function getResearchRuns(researchKey = "") {
  const query = new URLSearchParams({ limit: "30" });
  if (researchKey) query.set("research", researchKey);
  return fetchJsonStrict<ResearchRunsPayload>(`/api/agent/research-runs?${query}`);
}

export function createResearchRun(options: {
  threadKey: string;
  anchorKey?: string;
  goal: string;
  skillRef?: string;
  hypotheses?: string[];
  counterexampleChecks?: string[];
  sensitivityChecks?: string[];
  maxObservations?: number;
  maxRevisions?: number;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
}) {
  return fetchJsonStrict<ResearchMutationPayload>("/api/agent/research-runs/create", { method: "POST", body: JSON.stringify(options) });
}

export function reviseResearchRun(options: {
  researchKey: string;
  reason: string;
  expectedRevisionFingerprint: string;
  goal?: string;
  skillRef?: string;
  hypotheses?: string[];
  counterexampleChecks?: string[];
  sensitivityChecks?: string[];
  confirm?: boolean;
  expectedPlanFingerprint?: string;
}) {
  return fetchJsonStrict<ResearchMutationPayload>("/api/agent/research-runs/revise", { method: "POST", body: JSON.stringify(options) });
}

export function observeResearchRun(options: {
  researchKey: string;
  anchorKey: string;
  kind: "evidence" | "counterexample" | "sensitivity";
  stepKey: string;
  verdict: "supports" | "challenges" | "inconclusive";
  note: string;
  expectedRevisionFingerprint: string;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
}) {
  return fetchJsonStrict<ResearchMutationPayload>("/api/agent/research-runs/observe", { method: "POST", body: JSON.stringify(options) });
}

export function finalizeResearchRun(options: {
  researchKey: string;
  expectedRevisionFingerprint: string;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
}) {
  return fetchJsonStrict<ResearchMutationPayload>("/api/agent/research-runs/finalize", { method: "POST", body: JSON.stringify(options) });
}
