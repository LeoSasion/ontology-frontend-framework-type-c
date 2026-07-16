import { readFileSync } from "node:fs";

function source(relativePath) {
  return readFileSync(new URL(`../${relativePath}`, import.meta.url), "utf8");
}

function routeBlock(routeSource, pathname) {
  const marker = `if (url.pathname === "${pathname}"`;
  const start = routeSource.indexOf(marker);
  if (start < 0) return "";
  const next = routeSource.indexOf("\n  if (url.pathname === ", start + marker.length);
  return routeSource.slice(start, next < 0 ? routeSource.length : next);
}

const api = source("src/apiAgentRuntimeProfiles.ts");
const panel = source("src/components/SettingsAgentRuntimeProfilePanel.tsx");
const css = `${source("src/components/settingsPanel.css")}\n${source("src/components/planQualityPanel.css")}`;
const routes = source("server/agentRoutes.ts");
const caseRoute = routeBlock(routes, "/api/agent/plan-quality/cases");
const evaluateRoute = routeBlock(routes, "/api/agent/plan-quality/evaluate");
const scorecardRoute = routeBlock(routes, "/api/agent/plan-quality/scorecards");

const checks = [
  {
    label: "plan-quality-client-contract-is-typed",
    ok: api.includes("export interface PlanQualityScorecard")
      && api.includes("export interface PlanQualityCaseResult")
      && api.includes("export function getBusinessExpressionCases")
      && api.includes("export function getPlanQualityScorecards")
      && api.includes("export function runPlanQualityEvaluation"),
  },
  {
    label: "plan-quality-api-is-bound-to-active-workspace",
    ok: [caseRoute, evaluateRoute, scorecardRoute].every((block) => block.length > 0)
      && [caseRoute, evaluateRoute, scorecardRoute].every((block) => !block.includes("workspaceId") && !block.includes("--workspace")),
  },
  {
    label: "settings-separates-local-plan-quality-from-provider-summary",
    ok: panel.includes('data-testid="settings-plan-quality"')
      && panel.includes('zh="业务理解质量"')
      && panel.includes("不读取业务行，也不调用 Provider")
      && panel.indexOf('data-testid="settings-plan-quality"') < panel.indexOf('className="runtimeProfileGrid"'),
  },
  {
    label: "benchmark-action-has-loading-empty-success-and-failure-states",
    ok: panel.includes('data-testid="run-plan-quality"')
      && panel.includes("qualityBusy ?")
      && panel.includes("planQualityEmpty")
      && panel.includes("failedQualityCases")
      && panel.includes("releaseReady"),
  },
  {
    label: "quality-panel-exposes-thresholds-and-zero-tolerance-separately",
    ok: ["coreSlotAccuracy", "fieldBindingPrecision", "safeClarificationRate", "evidenceCoverage", "replayConsistency", "silentDisambiguationCount", "permissionEscalationCount", "crossWorkspaceLeakCount", "domainPackLeakCount"].every((token) => panel.includes(token)),
  },
  {
    label: "workspace-switch-aborts-and-rejects-cross-scope-quality-results",
    ok: panel.includes("requestRef.current?.controller.abort()")
      && panel.includes("requestRef.current?.id !== requestId")
      && panel.includes("scorecardsResult.value.workspaceId === expectedWorkspace")
      && panel.includes("qualityRunRef.current !== runId")
      && panel.includes("workspaceRef.current !== expectedWorkspace")
      && panel.includes("result.workspaceId !== expectedWorkspace"),
  },
  {
    label: "case-details-are-progressive-and-not-a-default-wall",
    ok: panel.includes('<details className="planQualityDetails"')
      && panel.includes('data-testid="plan-quality-details"')
      && panel.includes("planQualityCaseList"),
  },
  {
    label: "plan-quality-layout-is-responsive-without-overflow-prone-fixed-widths",
    ok: css.includes(".planQualityMetrics")
      && css.includes(".planQualityCaseList > div")
      && css.includes("@container settings-panel (max-width: 680px)")
      && css.includes("grid-template-columns: minmax(0, 1fr);")
      && !/\.planQuality[^{}]*\{[^{}]*width:\s*\d{3,}px/s.test(css),
  },
  {
    label: "quality-ui-does-not-render-raw-business-rows-or-provider-context",
    ok: !/\b(?:rawRows|sampleRows|businessRows|providerContext|promptText)\b/.test(panel),
  },
];

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-plan-quality-ui-verify/v1",
  generatedBy: "scripts/verify-plan-quality-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
