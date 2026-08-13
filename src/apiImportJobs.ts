import { fetchJsonStrict } from "./apiClient";
import type { AnalysisJobsPayload } from "./typesJobs";

export type CreateImportJobOptions = {
  requestKey: string;
  expectedPlan: string;
  importKind: "single" | "folder";
  path: string;
  table?: string;
  name?: string;
  mode?: string;
  uniqueFields?: string[];
  conflictRule?: string;
  recursive?: boolean;
  limit?: number;
};

export function createImportJob(options: CreateImportJobOptions) {
  return fetchJsonStrict<AnalysisJobsPayload>("/api/import/jobs", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function fetchImportJob(jobKey: string, signal?: AbortSignal) {
  return fetchJsonStrict<AnalysisJobsPayload>(`/api/import/jobs/${encodeURIComponent(jobKey)}`, { signal });
}

export function listImportJobs(limit = 20, signal?: AbortSignal) {
  const boundedLimit = Math.max(1, Math.min(Number(limit) || 20, 100));
  return fetchJsonStrict<AnalysisJobsPayload>(`/api/import/jobs?limit=${boundedLimit}`, { signal });
}

export function cancelImportJob(jobKey: string, reason = "user-requested") {
  return fetchJsonStrict<AnalysisJobsPayload>(`/api/import/jobs/${encodeURIComponent(jobKey)}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function resumeImportJob(jobKey: string) {
  return fetchJsonStrict<AnalysisJobsPayload>(`/api/import/jobs/${encodeURIComponent(jobKey)}/resume`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
