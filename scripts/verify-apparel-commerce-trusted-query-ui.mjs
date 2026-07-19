import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const source = (path) => readFileSync(join(root, path), "utf8");
const answer = source("src/components/AgentAnswerCard.tsx");
const visualization = source("src/components/AgentAnswerVisualization.tsx");
const visualizationModel = source("src/components/agentAnswerVisualizationModel.ts");
const folder = source("src/components/SourceWorkbenchImportPanel.tsx");
const routes = source("server/sourceRoutes.ts");
const types = source("src/typesAgent.ts");
const checks = [];
const check = (label, ok, detail = "") => checks.push({ label, ok: Boolean(ok), detail: ok ? "" : detail });

for (const state of ["executed", "draft", "blocked", "simulation", "stale"]) {
  check(`result-state-${state}`, answer.includes(`${state}:`) && types.includes(`\"${state}\"`), state);
}
check("only-strictly-trusted-results-render-business-numbers", answer.includes("trustedReceiptGate.allowed") && visualizationModel.includes('validation?.canSupportBusinessConclusion === true') && visualizationModel.includes('currentSourceRunMatches === true'));
check("executed-visualization-is-lazy-and-unit-backed", answer.includes('lazy(() => import("./AgentAnswerVisualization"))') && answer.includes("analysisUnit={analysisUnit}") && visualization.includes("buildAgentVisualizationModel(analysisUnit, chartAdapter, evidenceRefs)"));
check("non-executed-states-never-mount-business-chart", answer.includes("canRenderVisualization && analysisUnit") && answer.includes("agent-visualization-guard") && visualizationModel.includes('resultState === "executed"'));
check("visualization-exposes-receipt-fingerprint-and-data-table", visualization.includes('data-receipt-key={queryPlanReceipt.receiptKey}') && visualization.includes('data-result-fingerprint={analysisUnit.resultFingerprint}') && visualization.includes('data-testid="agent-visualization-data-table"'));
check("receipt-source-run-and-coverage-are-visible", answer.includes("currentSourceRunId") && answer.includes("agent-trusted-result-state") && answer.includes("executionCoverage"));
check("folder-plan-blockers-disable-confirm", folder.includes("folderImportPlan.readyToCommit !== true") && folder.includes("group.blockers"));
check("folder-plan-fingerprint-reaches-cli", routes.includes('body.expectedPlan') && routes.includes('"--expected-plan"'));
check("folder-owner-key-reaches-preview-and-commit", (routes.match(/--unique-fields/g) ?? []).length >= 4);

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-apparel-commerce-trusted-query-ui-verify/v1",
  generatedBy: "scripts/verify-apparel-commerce-trusted-query-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
process.exitCode = failedChecks.length ? 1 : 0;
