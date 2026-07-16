import { fetchJson } from "./apiClient";
import type { MetricMonitorsPayload } from "./types";

export type MetricMonitorMutation = {
  operation: "create" | "replace" | "delete" | "run";
  monitorKey?: string;
  snapshotKey?: string;
  label?: string;
  metric?: string;
  cadence?: "manual" | "daily" | "weekly" | "monthly";
  comparisonStrategy?: "absolute-change" | "percent-change";
  direction?: "increase" | "decrease" | "absolute";
  threshold?: number;
  warningRatio?: number;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
};

const unavailable = { ok: false, error: "Local Metric Monitor service is unavailable" } satisfies MetricMonitorsPayload;

export function getMetricMonitors(monitorKey = "") {
  const query = new URLSearchParams({ limit: "30" });
  if (monitorKey) query.set("monitor", monitorKey);
  return fetchJson<MetricMonitorsPayload>(`/api/metric-monitors?${query}`, unavailable);
}

export function mutateMetricMonitor(input: MetricMonitorMutation) {
  return fetchJson<MetricMonitorsPayload>(`/api/metric-monitors/${input.operation}`, unavailable, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      monitorKey: input.monitorKey,
      snapshotKey: input.snapshotKey,
      label: input.label,
      metric: input.metric,
      cadence: input.cadence,
      comparisonStrategy: input.comparisonStrategy,
      direction: input.direction,
      threshold: input.threshold,
      warningRatio: input.warningRatio,
      confirm: input.confirm === true,
      expectedPlanFingerprint: input.expectedPlanFingerprint,
    }),
  });
}
