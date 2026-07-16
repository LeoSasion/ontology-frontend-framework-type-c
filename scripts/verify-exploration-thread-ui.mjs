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

const api = source("src/apiExploration.ts");
const types = source("src/typesAgent.ts");
const routes = source("server/agentRoutes.ts");
const panel = source("src/components/ExplorationThreadPanel.tsx");
const styles = source("src/components/ExplorationThreadPanel.css");
const agentPanel = source("src/components/AgentPanel.tsx");
const trustPanel = source("src/components/AgentTrustAdvancedPanel.tsx");
const paths = [
  "/api/agent/exploration-threads",
  "/api/agent/exploration-threads/create",
  "/api/agent/exploration-threads/add-anchor",
  "/api/agent/exploration-threads/board",
];
const routeBlocks = paths.map((path) => routeBlock(routes, path));

const checks = [
  {
    label: "typed-client-covers-list-create-anchor-and-board",
    ok: api.includes("getExplorationThreads")
      && api.includes("createExplorationThread")
      && api.includes("addExplorationAnchor")
      && api.includes("setExplorationBoardItem")
      && types.includes("export interface ExplorationThread")
      && types.includes("export interface ExplorationAnchor")
      && types.includes("usableForContinuation")
      && types.includes("staleFallbackUsed: false"),
  },
  {
    label: "api-routes-are-server-active-workspace-bound",
    ok: routeBlocks.every((block) => block.length > 0)
      && routeBlocks.every((block) => !block.includes("workspaceId") && !block.includes("--workspace")),
  },
  {
    label: "mutations-use-preview-fingerprint-and-explicit-confirmation",
    ok: routeBlocks.slice(1).every((block) => block.includes("body.confirm === true") && block.includes("--expected-plan"))
      && panel.includes("expectedPlanFingerprint: payload.explorationPlan.planFingerprint")
      && panel.includes('data-testid="exploration-confirmation"')
      && panel.includes('data-testid="exploration-confirm"'),
  },
  {
    label: "workspace-switch-rejects-in-flight-cross-scope-results",
    ok: panel.includes("requestRef.current")
      && panel.includes("payload.workspaceId !== workspaceId")
      && panel.includes("requestRef.current += 1")
      && !panel.includes("localStorage")
      && !panel.includes("sessionStorage"),
  },
  {
    label: "result-board-shows-lineage-shape-and-live-status-without-rows",
    ok: panel.includes('data-testid="exploration-result-board"')
      && panel.includes("parentAnchor")
      && panel.includes("anchor.freshness.status")
      && panel.includes("anchor.summary.measureColumn")
      && panel.includes("anchor.summary.dimensionColumns")
      && panel.includes("anchor.summary.chartType")
      && !/anchor\.(?:rows|calculation)|summary\.rows\b/.test(panel),
  },
  {
    label: "board-removal-and-repin-preserve-anchor-history",
    ok: panel.includes('previewBoard(anchor.anchorKey, "removed")')
      && panel.includes('previewBoard(anchor.anchorKey, "pinned")')
      && panel.includes("hiddenAnchors")
      && panel.includes("锚点历史仍保留"),
  },
  {
    label: "executed-results-can-branch-and-trust-panel-uses-exploration-flow",
    ok: agentPanel.includes('result.analysisRun?.status === "executed"')
      && trustPanel.includes("<ExplorationThreadPanel")
      && !trustPanel.includes("submitBranch"),
  },
  {
    label: "responsive-board-has-no-overflow-prone-fixed-width",
    ok: styles.includes("repeat(auto-fit, minmax(min(100%, 220px), 1fr))")
      && styles.includes("@media (max-width: 640px)")
      && styles.includes("grid-template-columns: minmax(0, 1fr)")
      && !/\.exploration[^{}]*\{[^{}]*width:\s*\d{3,}px/s.test(styles),
  },
];

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-exploration-thread-ui-verify/v1",
  generatedBy: "scripts/verify-exploration-thread-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
