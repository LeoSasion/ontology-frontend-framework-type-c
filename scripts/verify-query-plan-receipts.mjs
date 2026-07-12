import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-query-receipts-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args) {
  const result = spawnSync("python", ["tools/bi_cli.py", "--json", ...args], {
    cwd: process.cwd(), env, encoding: "utf8", windowsHide: true,
  });
  let parsed = null;
  try { parsed = JSON.parse(result.stdout.trim()); } catch { parsed = null; }
  return { label, ok: result.status === 0 && parsed?.ok === true, status: result.status, parsed, stderr: result.stderr, stdout: result.stdout };
}

try {
  const checks = [
    run("import", ["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]),
    run("dashboard", ["business-dashboard", "--op", "create", "--table", "orders", "--name", "Receipt verification", "--limit", "1", "--yes"]),
  ];
  const query = run("direct-query", ["query", "--table", "orders", "--group", "channel", "--measure", "net_sales", "--agg", "sum", "--request", "各渠道净销售额"]);
  checks.push(query);
  checks.push({
    label: "direct-query-has-executed-receipt",
    ok: query.parsed?.queryPlanReceipt?.schema === "aibi-query-plan-receipt/v1"
      && query.parsed?.queryPlanReceipt?.status === "executed"
      && query.parsed?.queryPlanReceipt?.selection?.measure === "net_sales"
      && query.parsed?.queryPlanReceipt?.selection?.group === "channel"
      && Boolean(query.parsed?.queryPlanReceipt?.runtime?.compiledSql)
      && query.parsed?.queryPlanReceipt?.validation?.whitelistOnly === true,
  });
  const ask = run("agent-query", ["ask", "请用net_sales按channel生成柱状图"]);
  checks.push(ask);
  checks.push({
    label: "agent-and-action-share-receipt",
    ok: ask.parsed?.queryPlanReceipt?.status === "executed"
      && ask.parsed?.queryPlanReceipt?.actionKey === ask.parsed?.actionDraft?.actionKey
      && ask.parsed?.answerCard?.queryPlanReceipt?.receiptKey === ask.parsed?.queryPlanReceipt?.receiptKey,
  });
  const drafts = run("action-drafts", ["action-drafts", "--all", "--limit", "10"]);
  checks.push(drafts);
  const linkedDraft = drafts.parsed?.actionDrafts?.find((item) => item?.action_key === ask.parsed?.actionDraft?.actionKey);
  checks.push({
    label: "draft-links-query-receipt",
    ok: linkedDraft?.payload?.queryReceiptKey === ask.parsed?.queryPlanReceipt?.receiptKey,
  });
  const blocked = run("blocked-query", ["ask", "请用不存在字段按channel生成柱状图"]);
  checks.push(blocked);
  checks.push({
    label: "blocked-request-has-receipt-with-unresolved",
    ok: blocked.parsed?.queryPlanReceipt?.status === "blocked"
      && blocked.parsed?.queryPlanReceipt?.validation?.blocked === true
      && blocked.parsed?.queryPlanReceipt?.unresolved?.length > 0,
  });
  const listed = run("list-receipts", ["query-receipts", "--limit", "10"]);
  checks.push(listed);
  checks.push({
    label: "receipts-are-workspace-scoped-and-listable",
    ok: listed.parsed?.count >= 3
      && listed.parsed?.queryReceipts?.every((item) => item?.source?.workspaceId === "default"),
  });

  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-query-plan-receipt-verify/v1",
    generatedBy: "scripts/verify-query-plan-receipts.mjs",
    checks: checks.map((check) => ({ label: check.label, ok: check.ok, status: check.status })),
    failedChecks: failedChecks.map((check) => ({ label: check.label, status: check.status, parsed: check.parsed, stderr: check.stderr, stdout: check.stdout?.slice(-1600) })),
  }, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
