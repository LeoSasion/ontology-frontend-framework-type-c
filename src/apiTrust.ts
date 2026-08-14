import { fetchJsonStrict } from "./apiClient";
import type { AnalysisRunsPayload, ConfirmedPlansPayload, ConfirmedQueriesPayload, ContextPackPayload, KnowledgeSource, KnowledgeSourceAdapter, QueryReceiptsPayload, RecallReceiptsPayload, SemanticPatchCollectionPayload, SemanticReleasePlan, SemanticReleasesPayload } from "./typesTrust";

export function getContextPack() {
  return fetchJsonStrict<ContextPackPayload>("/api/context");
}

export function saveContextTerm(options: Record<string, unknown>) {
  return fetchJsonStrict<Record<string, unknown>>("/api/context/terms", { method: "POST", body: JSON.stringify(options) });
}

export function saveContextRule(options: Record<string, unknown>) {
  return fetchJsonStrict<Record<string, unknown>>("/api/context/rules", { method: "POST", body: JSON.stringify(options) });
}

export function getKnowledgeSourceAdapters() {
  return fetchJsonStrict<{ ok: boolean; adapters: KnowledgeSourceAdapter[]; count: number; guardrails: Record<string, false> }>("/api/knowledge-source-adapters");
}

export function getKnowledgeSources() {
  return fetchJsonStrict<{ ok: boolean; sources: KnowledgeSource[]; count: number; rawDocumentsIncluded: false }>("/api/knowledge-sources");
}

export function proposeKnowledgeSource(options: { input: string; adapter: string; sourceType: "data-dictionary" | "documentation"; sourceName: string; confirm?: boolean }) {
  return fetchJsonStrict<Record<string, unknown>>("/api/knowledge-sources/propose", { method: "POST", body: JSON.stringify(options) });
}

export function getSemanticPatches(status = "") {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  return fetchJsonStrict<SemanticPatchCollectionPayload>(`/api/semantic-patches${suffix}`);
}

export function proposeSemanticPatch(options: Record<string, unknown>) {
  return fetchJsonStrict<Record<string, unknown>>("/api/semantic-patches/propose", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function reviewSemanticPatch(proposalKey: string, decision: "accept" | "reject", confirm: boolean, note = "") {
  return fetchJsonStrict<Record<string, unknown>>("/api/semantic-patches/review", {
    method: "POST",
    body: JSON.stringify({ proposalKey, decision, confirm, note }),
  });
}

export function getSemanticReleases() {
  return fetchJsonStrict<SemanticReleasesPayload>("/api/semantic-releases");
}

export function previewSemanticRelease(options: { requestKey: string; label: string; proposalKeys: string[] }) {
  return fetchJsonStrict<{ ok: boolean; dryRun: true; releasePlan: SemanticReleasePlan }>("/api/semantic-releases/preview", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function publishSemanticRelease(options: { requestKey: string; label: string; proposalKeys: string[]; expectedPlanFingerprint: string }) {
  return fetchJsonStrict<Record<string, unknown>>("/api/semantic-releases/publish", {
    method: "POST",
    body: JSON.stringify({ ...options, confirm: true }),
  });
}

export function rollbackSemanticRelease(options: { releaseKey: string; requestKey: string; expectedPlanFingerprint?: string; confirm?: boolean }) {
  return fetchJsonStrict<Record<string, unknown>>("/api/semantic-releases/rollback", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function getConfirmedQueries(status = "") {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  return fetchJsonStrict<ConfirmedQueriesPayload>(`/api/confirmed-queries${suffix}`);
}

export function getConfirmedPlans(status = "") {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  return fetchJsonStrict<ConfirmedPlansPayload>(`/api/confirmed-plans${suffix}`);
}

export function getRecallReceipts(receipt = "") {
  const suffix = receipt ? `?receipt=${encodeURIComponent(receipt)}` : "";
  return fetchJsonStrict<RecallReceiptsPayload>(`/api/recall-receipts${suffix}`);
}

export function confirmQueryMemory(queryKey: string, confirm: boolean, status = "confirmed") {
  return fetchJsonStrict<Record<string, unknown>>("/api/confirmed-queries/confirm", {
    method: "POST",
    body: JSON.stringify({ queryKey, confirm, status }),
  });
}

export function exportEvidence(receipt: string) {
  return fetchJsonStrict<Record<string, unknown>>("/api/evidence/export", {
    method: "POST",
    body: JSON.stringify({ receipt }),
  });
}

export function getAnalysisRuns(run = "") {
  const suffix = run ? `?run=${encodeURIComponent(run)}` : "";
  return fetchJsonStrict<AnalysisRunsPayload>(`/api/analysis-runs${suffix}`);
}

export function getQueryReceipts(receipt = "") {
  const suffix = receipt ? `?receipt=${encodeURIComponent(receipt)}` : "";
  return fetchJsonStrict<QueryReceiptsPayload>(`/api/query-receipts${suffix}`);
}
