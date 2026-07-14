import { fetchJsonStrict } from "./apiClient";
import type { AnalysisJobsPayload } from "./typesJobs";

export function fetchAnalysisJobs(options: {
  jobKey?: string;
  statuses?: string[];
  includeEvents?: boolean;
  eventsAfter?: number;
  limit?: number;
} = {}) {
  const params = new URLSearchParams();
  if (options.jobKey) params.set("job", options.jobKey);
  for (const status of options.statuses ?? []) params.append("status", status);
  if (options.includeEvents) params.set("includeEvents", "true");
  if (options.eventsAfter !== undefined) params.set("eventsAfter", String(options.eventsAfter));
  params.set("limit", String(options.limit ?? 50));
  return fetchJsonStrict<AnalysisJobsPayload>(`/api/jobs?${params.toString()}`);
}

export function cancelAnalysisJob(jobKey: string, options: { reason?: string; confirm?: boolean } = {}) {
  return fetchJsonStrict<Record<string, unknown>>("/api/jobs/cancel", {
    method: "POST",
    body: JSON.stringify({ jobKey, reason: options.reason, confirm: options.confirm === true }),
  });
}
