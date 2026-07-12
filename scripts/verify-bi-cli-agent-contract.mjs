import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const verifyDir = mkdtempSync(join(tmpdir(), "aibi-bi-cli-agent-contract-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "aibi_hybrid_cli_contract.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "aibi_hybrid_cli_contract.duckdb"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args) {
  const result = spawnSync("python", ["tools/bi_cli.py", "--json", ...args], {
    cwd: root,
    encoding: "utf8",
    env,
    windowsHide: true,
  });
  let parsed = null;
  try {
    parsed = JSON.parse(result.stdout.trim());
  } catch {
    parsed = null;
  }
  return {
    label,
    ok: result.status === 0 && parsed?.ok === true,
    status: result.status,
    parsed,
    stdout: result.stdout,
    stderr: result.stderr,
  };
}

const markdownPath = join(verifyDir, "bi-cli-contract.md");
const checks = [
  run("status-envelope", ["status"]),
  run("contract-json", ["cli-contract"]),
  run("contract-markdown-output", ["cli-contract", "--format", "markdown", "--output", markdownPath]),
  run("dashboard-command-list", ["list-commands", "--domain", "dashboard", "--writes", "yes"]),
  run("verify-contract-bootstrap-import-orders", ["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]),
  run("verify-contract-bootstrap-import-refunds", ["import-commit", "validation-inputs/refunds.csv", "--table", "refunds", "--name", "Refunds", "--mode", "create", "--yes"]),
  run("verify-contract-bootstrap-dashboard", ["business-dashboard", "--op", "create", "--table", "orders", "--limit", "3", "--yes"]),
  run("preview-import-evidence-bundle", ["preview-import", "validation-inputs/orders.csv"]),
  run("business-dashboard-draft-evidence-bundle", ["business-dashboard", "--op", "draft", "--table", "orders", "--limit", "3"]),
];

const byLabel = Object.fromEntries(checks.map((check) => [check.label, check]));
const contract = byLabel["contract-json"].parsed?.contract;
const contractCommands = Array.isArray(contract?.commands) ? contract.commands : [];
const sourceIntelligenceContract = contractCommands.find((command) => command.name === "source-intelligence");
const businessDashboardContract = contractCommands.find((command) => command.name === "business-dashboard");
const trustCommandNames = ["context-pack", "query-receipts", "export-evidence", "confirmed-queries", "analysis-runs"];
const trustCommands = trustCommandNames.map((name) => contractCommands.find((command) => command.name === name));
const previewImport = byLabel["preview-import-evidence-bundle"].parsed;
const businessDraft = byLabel["business-dashboard-draft-evidence-bundle"].parsed;
const markdown = existsSync(markdownPath) ? readFileSync(markdownPath, "utf8") : "";

checks.push(
  {
    label: "contract-discovers-command-surface",
    ok: contract?.schema === "aibi-bi-cli-contract/v1" &&
      contract.commandCount >= 70 &&
      sourceIntelligenceContract?.writesEvidence === true &&
      businessDashboardContract?.requiresYes === true,
  },
  {
    label: "contract-discovers-trusted-analysis-surface",
    ok: trustCommands.every(Boolean) &&
      trustCommands.find((command) => command?.name === "export-evidence")?.writesEvidence === true,
  },
  {
    label: "status-has-compatible-envelope",
    ok: byLabel["status-envelope"].parsed?.envelope?.schema === "aibi-bi-cli-envelope/v1" &&
      byLabel["status-envelope"].parsed?.command === "status" &&
      Array.isArray(byLabel["status-envelope"].parsed?.artifacts) &&
      byLabel["status-envelope"].parsed?.requiresConfirmation === false,
  },
  {
    label: "preview-import-bundle-files-exist",
    ok: previewImport?.dryRun === true &&
      previewImport?.envelope?.writesEvidence === true &&
      existsSync(previewImport?.evidenceBundle?.manifestPath ?? "") &&
      existsSync(previewImport?.evidenceBundle?.summaryPath ?? ""),
  },
  {
    label: "business-dashboard-draft-bundle-and-confirmation-contract",
    ok: businessDraft?.dryRun === true &&
      businessDraft?.requiresConfirmation === false &&
      businessDraft?.envelope?.mutationMode === "dry-run-confirm" &&
      existsSync(businessDraft?.evidenceBundle?.manifestPath ?? "") &&
      existsSync(businessDraft?.evidenceBundle?.summaryPath ?? ""),
  },
  {
    label: "contract-markdown-generated",
    ok: markdown.includes("# BI CLI Contract") &&
      markdown.includes("`source-intelligence`") &&
      markdown.includes("`business-dashboard`"),
  },
);

const failedChecks = checks.filter((check) => !check.ok);
const receipt = {
  ok: failedChecks.length === 0,
  generatedBy: "scripts/verify-bi-cli-agent-contract.mjs",
  verifyDir,
  checks: checks.map((check) => ({ label: check.label, ok: check.ok, status: check.status })),
  failedChecks: failedChecks.map((check) => ({
    label: check.label,
    status: check.status,
    stderr: check.stderr,
    stdout: check.stdout?.slice(-2000),
    parsed: check.parsed,
  })),
};

console.log(JSON.stringify(receipt, null, 2));
process.exit(receipt.ok ? 0 : 1);
