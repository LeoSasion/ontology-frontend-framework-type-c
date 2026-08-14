import { readFileSync } from "node:fs";

const answer = readFileSync("src/components/AgentAnswerCard.tsx", "utf8");
const panel = readFileSync("src/components/AgentPanel.tsx", "utf8");
const route = readFileSync("server/exportRoutes.ts", "utf8");
const css = readFileSync("src/components/agentAnalysisExport.css", "utf8");
const checks = [
  { label: "verified-unit-offers-four-clear-presets", ok: ["bundle", "docx", "pptx", "complete"].every((item) => answer.includes(`value=\"${item}\"`)) },
  { label: "one-export-action-forwards-explicit-formats", ok: answer.includes("onExportAnalysis?.(") && panel.includes("formats })") && panel.includes("Generating verified export") },
  { label: "server-allowlists-formats", ok: route.includes('["xlsx", "docx", "pptx", "md"]') && route.includes("ANALYSIS_EXPORT_FORMAT_INVALID") },
  { label: "format-control-adapts-below-760", ok: css.includes(".agentAnalysisExportFormat") && css.includes("grid-template-columns: 1fr") && css.includes("min-height: 44px") },
];
const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({ ok: failedChecks.length === 0, schema: "aibi-analysis-export-ui-verify/v1", checks, failedChecks }, null, 2));
if (failedChecks.length) process.exitCode = 1;
