import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const panel = read("src/components/TrustContextSettingsPanel.tsx");
const api = read("src/apiTrust.ts");
const routes = read("server/settingsRoutes.ts");
const types = read("src/typesTrust.ts");
const styles = read("src/styles/trustContext.css");

const checks = [];
const check = (label, ok) => checks.push({ label, ok: Boolean(ok) });

check("ui-loads-plan-memories-and-recall-receipts", panel.includes("getConfirmedPlans") && panel.includes("getRecallReceipts") && panel.includes('data-testid="confirmed-plan-memory"') && panel.includes('data-testid="recall-receipt-summary"'));
check("ui-states-candidate-only-boundaries", panel.includes("历史计划只参与候选排序") && panel.includes("仅候选，不自动采用"));
check("api-clients-are-typed", api.includes("getConfirmedPlans") && api.includes("ConfirmedPlansPayload") && api.includes("getRecallReceipts") && api.includes("RecallReceiptsPayload"));
check("server-routes-are-read-only-and-active-workspace-bound", routes.includes('"/api/confirmed-plans"') && routes.includes('["confirmed-plans"') && routes.includes('"/api/recall-receipts"') && routes.includes('["recall-receipts"') && !routes.match(/confirmed-plans[\s\S]{0,220}workspaceId/));
check("types-expose-evidence-and-authority-boundaries", types.includes("export type ConfirmedPlanMemory") && types.includes("bindingFingerprint") && types.includes("export type RecallReceipt") && types.includes("canAuthorizeSelection: false") && types.includes("canBypassAmbiguity: false"));
check("responsive-recall-summary-is-present", styles.includes(".recallEvidencePanel") && styles.includes(".recallReceiptSummary") && styles.includes("grid-template-columns: 1fr"));

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({ ok: failedChecks.length === 0, schema: "aibi-confirmed-plan-recall-ui-verify/v1", checks, failedChecks }, null, 2));
if (failedChecks.length) process.exitCode = 1;
