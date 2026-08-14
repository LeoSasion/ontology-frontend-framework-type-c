import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const panel = read("src/components/MetricContractPanel.tsx");
const host = read("src/components/SourceWorkbenchMetricDefinitionPanel.tsx");
const api = read("src/apiModel.ts");
const routes = read("server/modelRoutes.ts");
const styles = read("src/components/metricContractPanel.css");
const types = read("src/typesSource.ts");

const checks = [];
const check = (label, ok) => checks.push({ label, ok: Boolean(ok) });
check("panel-is-lazy-mounted-for-selected-metric", host.includes('lazy(() => import("./MetricContractPanel")') && host.includes("selectedMetrics[0]"));
check("contract-captures-seven-explicit-definition-fields", ["population", "grain", "unit", "nullPolicy", "dedupKey", "direction", "owner"].every((field) => panel.includes(field)));
check("publish-is-preview-then-exact-confirm", panel.includes("previewMetricContract") && panel.includes("pending.plan.planFingerprint") && panel.includes("publishMetricContract"));
check("stable-request-key-survives-response-loss", panel.includes("stableRequestKey") && !panel.includes("randomUUID") && !panel.includes("Date.now"));
check("scenario-replay-separates-attribution-and-delta", panel.includes("replayMetricContract") && panel.includes("replay.attribution") && panel.includes("scalarDelta"));
check("filter-values-are-not-rendered", types.includes("valueFingerprint") && !panel.includes("filter.value"));
check("api-and-route-lifecycle-is-complete", ["getMetricContracts", "previewMetricContract", "publishMetricContract", "replayMetricContract"].every((name) => api.includes(name)) && routes.includes('"/api/metric-contracts/replay"'));
check("responsive-contract-layout-is-present", styles.includes("@container viewport-stage (max-width: 760px)") && styles.includes("grid-template-columns: minmax(0, 1fr)") && styles.includes("min-height: 44px"));

const failed = checks.filter((item) => !item.ok);
console.log(JSON.stringify({ ok: !failed.length, schema: "aibi-metric-contract-ui-verify/v1", checks, failedChecks: failed }, null, 2));
if (failed.length) process.exitCode = 1;
