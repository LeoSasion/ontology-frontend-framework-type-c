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

check("release-panel-is-production-mounted", panel.includes('data-testid="semantic-release-panel"') && panel.includes("getSemanticReleases"));
check("pending-proposals-are-grouped-into-one-preview", panel.includes('proposal.status === "pending"') && panel.includes("previewSemanticRelease") && panel.includes("proposal.proposalKey).sort()"));
check("publish-reuses-exact-preview-binding", panel.includes("releaseDraft.plan.planFingerprint") && panel.includes("publishSemanticRelease") && panel.includes("Confirm version publish"));
check("rollback-is-previewed-before-confirmation", panel.includes("previewRollback(release)") && panel.includes("confirmRollback()") && panel.includes("readyToRollback"));
check("history-distinguishes-current-drift-and-history", panel.includes("release.current") && panel.includes('release.status === "stale"') && panel.includes("Historical version"));
check("api-and-routes-cover-release-lifecycle", api.includes("getSemanticReleases") && api.includes("previewSemanticRelease") && api.includes("publishSemanticRelease") && api.includes("rollbackSemanticRelease") && routes.includes('"/api/semantic-releases/publish"') && routes.includes('"/api/semantic-releases/rollback"'));
check("typed-release-contract-includes-freshness", types.includes("export type SemanticRelease") && types.includes("publishedFingerprint") && types.includes("readyToPublish"));
check("responsive-release-layout-is-present", styles.includes(".semanticReleasePanel") && styles.includes(".semanticReleaseItem") && styles.includes("grid-template-columns: minmax(0, 1fr);"));

const failed = checks.filter((item) => !item.ok);
console.log(JSON.stringify({ ok: failed.length === 0, schema: "aibi-semantic-release-ui-verify/v1", checks, failedChecks: failed }, null, 2));
if (failed.length) process.exitCode = 1;
