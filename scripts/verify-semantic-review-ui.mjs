import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const panel = read("src/components/TrustContextSettingsPanel.tsx");
const api = read("src/apiTrust.ts");
const routes = read("server/settingsRoutes.ts");
const styles = read("src/styles/trustContext.css");
const types = read("src/typesTrust.ts");

const checks = [];
const check = (label, ok) => checks.push({ label, ok: Boolean(ok) });

check("review-inbox-renders-source-diff-freshness-and-status", panel.includes('data-testid="semantic-review-inbox"') && panel.includes("proposal.source?.name") && panel.includes("compactJson(proposal.before)") && panel.includes("compactJson(proposal.after)") && panel.includes("proposal.freshness.mismatches") && panel.includes("proposal.status"));
check("review-actions-use-preview-then-explicit-confirmation", panel.includes('previewReview(proposal, "accept")') && panel.includes('previewReview(proposal, "reject")') && panel.includes("confirmReview(proposal)") && panel.includes("确认接受并应用") && panel.includes("确认拒绝"));
check("stale-proposals-cannot-be-accepted-but-can-be-rejected", panel.includes("disabled={!isReviewable") && panel.includes('previewReview(proposal, "reject")'));
check("correction-forms-propose-instead-of-direct-context-writes", panel.includes("proposeSemanticPatch") && !panel.includes("saveContextTerm") && !panel.includes("saveContextRule") && panel.includes("预览提案") && panel.includes("确认提交审核"));
check("api-exposes-propose-list-and-review", api.includes("getSemanticPatches") && api.includes("proposeSemanticPatch") && api.includes("reviewSemanticPatch") && routes.includes('"/api/semantic-patches"') && routes.includes('"/api/semantic-patches/propose"') && routes.includes('"/api/semantic-patches/review"'));
check("server-only-active-workspace-boundary", !routes.match(/semantic-patches[\s\S]{0,250}workspaceId/) && routes.includes('"--adapter", "user-correction-v1"'));
check("typed-proposal-contract-includes-freshness-and-review", types.includes("export type SemanticPatchProposal") && types.includes("usableForReview") && types.includes("storedStatus") && types.includes("review:"));
check("responsive-review-layout-is-present", styles.includes(".semanticReviewInbox") && styles.includes(".semanticDiff") && styles.includes("@container viewport-stage (max-width: 760px)"));

const failed = checks.filter((item) => !item.ok);
console.log(JSON.stringify({ ok: failed.length === 0, schema: "aibi-semantic-review-ui-verify/v1", checks, failedChecks: failed }, null, 2));
if (failed.length) process.exitCode = 1;
