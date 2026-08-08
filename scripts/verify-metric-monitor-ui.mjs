import { readFileSync } from "node:fs";

const read = (path) => readFileSync(path, "utf8");
const snapshotPanel = read("src/components/AnalysisSnapshotPanel.tsx");
const panel = read("src/components/MetricMonitorPanel.tsx");
const api = read("src/apiMetricMonitors.ts");
const route = read("server/analysisUnitRoutes.ts");
const types = read("src/typesAgent.ts");
const css = read("src/components/MetricMonitorPanel.css");

const checks = [
  {
    label: "monitor-is-contained-in-the-on-demand-snapshot-surface",
    ok: snapshotPanel.includes('import { MetricMonitorPanel }')
      && snapshotPanel.includes("<MetricMonitorPanel snapshots={snapshots} />")
      && panel.includes('data-testid="metric-monitor-panel"'),
  },
  {
    label: "monitor-ui-protects-request-order-and-disables-duplicate-actions",
    ok: panel.includes("requestRef.current !== requestId")
      && panel.includes("requestRef.current += 1")
      && panel.includes("disabled={busy}")
      && panel.includes("useCallback")
      && panel.includes("useMemo")
      && panel.includes("monitor.semanticFingerprint"),
  },
  {
    label: "persistent-definitions-use-preview-and-exact-confirmation",
    ok: panel.includes('definition("create"')
      && panel.includes('definition("replace"')
      && panel.includes('operation: "delete"')
      && panel.includes("expectedPlanFingerprint: pending.plan.planFingerprint")
      && panel.includes('data-testid="metric-monitor-confirmation"'),
  },
  {
    label: "manual-run-exposes-local-evidence-status-without-automation",
    ok: panel.includes('operation: "run"')
      && panel.includes("不启用后台调度，也不发送通知")
      && panel.includes("未设置阈值时只报告变化")
      && types.includes("backgroundSchedulerEnabled: false")
      && types.includes("notificationsSent: 0")
      && types.includes("businessSystemWrites: 0"),
  },
  {
    label: "typed-api-covers-list-definition-lifecycle-and-run",
    ok: api.includes('"create" | "replace" | "delete" | "run"')
      && api.includes("/api/metric-monitors?")
      && api.includes("/api/metric-monitors/${input.operation}")
      && route.includes("metric-monitor-${operation}")
      && route.includes('operation) && body.confirm === true'),
  },
  {
    label: "monitor-layout-is-responsive-without-fixed-width",
    ok: css.includes("repeat(auto-fit")
      && css.includes("@container viewport-stage (max-width: 1100px)")
      && css.includes("@container viewport-stage (max-width: 680px)")
      && !/(?:^|[;{]\s*)width:\s*\d+px/m.test(css),
  },
];

const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-metric-monitor-ui-verify/v1",
  generatedBy: "scripts/verify-metric-monitor-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
