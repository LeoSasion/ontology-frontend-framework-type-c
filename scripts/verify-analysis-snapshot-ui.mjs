import { readFileSync } from "node:fs";

const read = (path) => readFileSync(path, "utf8");
const answerCard = read("src/components/AgentAnswerCard.tsx");
const panel = read("src/components/AnalysisSnapshotPanel.tsx");
const api = read("src/apiAnalysisSnapshots.ts");
const route = read("server/analysisUnitRoutes.ts");
const types = read("src/typesAgent.ts");
const css = read("src/components/AnalysisSnapshotPanel.css");

const checks = [
  {
    label: "snapshot-panel-is-conditionally-lazy-loaded",
    ok: answerCard.includes('lazy(() => import("./AnalysisSnapshotPanel")')
      && answerCard.includes("snapshotOpen ?")
      && answerCard.includes('data-testid="analysis-snapshot-open"'),
  },
  {
    label: "snapshot-panel-protects-workspace-unit-request-order",
    ok: panel.includes("requestRef.current !== requestId")
      && panel.includes("requestRef.current += 1")
      && panel.includes("disabled={busy}")
      && panel.includes("useCallback")
      && panel.includes("[unitKey]"),
  },
  {
    label: "all-persistent-mutations-preview-before-exact-confirmation",
    ok: ["create", "refresh", "replace", "delete"].every((operation) => panel.includes(`preview(\"${operation}\"`))
      && panel.includes("expectedPlanFingerprint: pending.plan.planFingerprint")
      && panel.includes('data-testid="analysis-snapshot-confirmation"'),
  },
  {
    label: "typed-api-covers-list-and-four-mutations",
    ok: api.includes('"create" | "refresh" | "replace" | "delete"')
      && api.includes("/api/analysis-snapshots?")
      && api.includes("/api/analysis-snapshots/${input.operation}")
      && route.includes("analysis-snapshot-${operation}")
      && route.includes('"--expected-plan"'),
  },
  {
    label: "public-ui-is-row-free-and-stale-fallback-free",
    ok: panel.includes("不会重查来源或回退到旧快照")
      && panel.includes("不返回冻结的业务结果行")
      && panel.includes("Provider 未参与")
      && !/\bsnapshot\.(?:content|rows)\b/.test(panel)
      && types.includes("rowsIncluded: false")
      && types.includes("staleFallbackUsed: false"),
  },
  {
    label: "snapshot-layout-is-responsive-without-fixed-width",
    ok: css.includes("repeat(auto-fit")
      && css.includes("@container viewport-stage (max-width: 860px)")
      && css.includes("@container viewport-stage (max-width: 620px)")
      && !/(?:^|[;{]\s*)width:\s*\d+px/m.test(css),
  },
];

const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-analysis-snapshot-ui-verify/v1",
  generatedBy: "scripts/verify-analysis-snapshot-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
