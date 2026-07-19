import { readFileSync } from "node:fs";

const packPath = new URL("../knowledge/platform-commerce.v1.json", import.meta.url);
const loaderPath = new URL("../tools/platform_analytics_knowledge.py", import.meta.url);
const agentInteractionPath = new URL("../tools/aibi_runtime/use_cases/agent_interaction.py", import.meta.url);
const pack = JSON.parse(readFileSync(packPath, "utf8"));
const loader = readFileSync(loaderPath, "utf8");
const agentInteraction = readFileSync(agentInteractionPath, "utf8");
const intents = Array.isArray(pack.intents) ? pack.intents : [];
const ids = intents.map((intent) => intent.id);
const checks = [
  { label: "knowledge-pack-schema", ok: pack.schema === "aibi-agent-knowledge/v1" && pack.id === "cn-platform-commerce-v1" },
  { label: "knowledge-pack-has-curated-principles", ok: Array.isArray(pack.principles) && pack.principles.length >= 6 },
  { label: "knowledge-pack-covers-platform-cases", ok: intents.length >= 13 && new Set(ids).size === ids.length },
  {
    label: "knowledge-sql-is-read-only-and-role-bound",
    ok: intents.every((intent) => {
      const sql = String(intent.sql || "").trim();
      const roles = new Set((intent.tables || []).map((table) => table.role));
      const placeholders = [...sql.matchAll(/\{\{([^}]+)\}\}/g)].map((match) => match[1]);
      return /^(SELECT|WITH)\b/i.test(sql) && !sql.includes(";") && placeholders.length > 0 && placeholders.every((role) => roles.has(role));
    }),
  },
  { label: "knowledge-loader-validates-structure-before-query", ok: loader.includes("required.issubset(table[\"fields\"])") && loader.includes("Unsafe platform knowledge query") },
  { label: "knowledge-loader-has-complex-analysis-guard", ok: loader.includes("requires_verified_analysis_plan") && loader.includes("build_verified_analysis_gap") },
  { label: "knowledge-loader-normalizes-percent-threshold", ok: loader.includes("float(percent_match.group(1)) / 100") && ids.includes("jushuitan-multi-package-threshold") },
  {
    label: "agent-injects-model-independent-knowledge",
    ok: agentInteraction.includes("match_platform_knowledge(connection, workspace_id, business_prompt)")
      && agentInteraction.includes("platform_knowledge_context(platform_match)")
      && agentInteraction.includes('"modelIndependent": True'),
  },
  { label: "query-receipt-carries-knowledge-rule", ok: agentInteraction.includes("knowledge_rule=answer_card.get(\"knowledgeRule\")") },
];
const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-platform-knowledge-contract-verify/v1",
  generatedBy: "scripts/verify-platform-knowledge-contract.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
