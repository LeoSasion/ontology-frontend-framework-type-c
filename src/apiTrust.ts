import { fetchJsonStrict } from "./apiClient";
import type { AnalysisRunsPayload, ConfirmedQueriesPayload, ContextPackPayload, QueryReceiptsPayload } from "./typesTrust";

export function getContextPack() {
  return fetchJsonStrict<ContextPackPayload>("/api/context");
}

export function saveContextTerm(options: Record<string, unknown>) {
  return fetchJsonStrict<Record<string, unknown>>("/api/context/terms", { method: "POST", body: JSON.stringify(options) });
}

export function saveContextRule(options: Record<string, unknown>) {
  return fetchJsonStrict<Record<string, unknown>>("/api/context/rules", { method: "POST", body: JSON.stringify(options) });
}

export function getConfirmedQueries(status = "") {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  return fetchJsonStrict<ConfirmedQueriesPayload>(`/api/confirmed-queries${suffix}`);
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
