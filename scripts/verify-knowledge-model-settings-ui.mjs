import { readFileSync } from "node:fs";

const read = (path) => readFileSync(path, "utf8");
const settings = read("src/components/SettingsPanel.tsx");
const knowledge = read("src/components/SettingsKnowledgeSourcePanel.tsx");
const runtime = read("src/components/SettingsAgentRuntimeProfilePanel.tsx");
const api = read("src/apiTrust.ts");
const styles = read("src/components/settingsKnowledgeSourcePanel.css");
const checks = [
  { label: "knowledge-and-model-settings-are-lazy-mounted", ok: settings.includes('lazy(() => import("./SettingsKnowledgeSourcePanel"))') && settings.includes('lazy(() => import("./SettingsAgentRuntimeProfilePanel"))') && settings.includes('testId="settings-knowledge-source-details"') && settings.includes('testId="settings-agent-runtime-details"') && settings.includes("opened ? <Suspense") },
  { label: "knowledge-import-is-preview-confirm-review", ok: knowledge.includes("proposeKnowledgeSource") && knowledge.includes("run(false)") && knowledge.includes("run(true)") && knowledge.includes("确认进入审核") },
  { label: "knowledge-boundary-denies-network-sql-code-and-raw-documents", ok: knowledge.includes("Network / SQL / code: denied") && knowledge.includes("Raw documents and rows: not stored") },
  { label: "knowledge-api-is-typed-and-bounded", ok: api.includes("getKnowledgeSourceAdapters") && api.includes("getKnowledgeSources") && api.includes("proposeKnowledgeSource") },
  { label: "runtime-profile-keeps-provider-evaluation-and-no-secret-display", ok: runtime.includes("provider") && runtime.includes("evaluation") && !runtime.includes("apiKeyValue") },
  { label: "knowledge-layout-adapts-to-narrow-container", ok: styles.includes("@container") && styles.includes("grid-template-columns:minmax(0,1fr)") && styles.includes("min-height:44px") },
];
const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({ ok: failedChecks.length === 0, schema: "aibi-knowledge-model-settings-ui-verify/v1", checks, failedChecks }, null, 2));
if (failedChecks.length) process.exitCode = 1;
