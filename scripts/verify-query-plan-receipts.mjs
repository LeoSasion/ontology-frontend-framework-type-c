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
  const unsafeRatio = run("unverified-ratio", ["ask", "请计算退款率"]);
  checks.push(unsafeRatio);
  checks.push({
    label: "unverified-ratio-never-falls-through-to-count",
    ok: unsafeRatio.parsed?.queryPlanReceipt?.status === "blocked"
      && unsafeRatio.parsed?.businessUnderstanding?.status === "needs-clarification"
      && unsafeRatio.parsed?.answerCard?.clarification?.kind === "compound-analysis-definition"
      && unsafeRatio.parsed?.queryPlanReceipt?.validation?.executed === false
      && !unsafeRatio.parsed?.queryPlanReceipt?.runtime?.compiledSql,
  });
  for (const [label, prompt] of [
    ["standalone-share", "占比是多少"],
    ["standalone-ratio", "请按渠道统计，比例是多少"],
    ["standalone-percentage", "请给出，百分比"],
    ["percent-symbol", "退款订单占总订单多少%"],
    ["fullwidth-percent-symbol", "退款订单占总订单多少％"],
    ["percent-phrase", "退货订单占全部订单的百分之几"],
  ]) {
    const result = run(label, ["ask", prompt]);
    checks.push(result);
    checks.push({
      label: `${label}-requires-verified-ratio-definition`,
      ok: result.parsed?.queryPlanReceipt?.status === "blocked"
        && result.parsed?.queryPlanReceipt?.validation?.executed === false
        && !result.parsed?.queryPlanReceipt?.runtime?.compiledSql
        && result.parsed?.businessUnderstanding?.status === "needs-clarification"
        && result.parsed?.answerCard?.clarification?.kind === "compound-analysis-definition",
    });
  }
  const unsafeYearOverYear = run("unverified-year-over-year", ["ask", "按 order_date 看 net_sales 同比"]);
  checks.push(unsafeYearOverYear);
  checks.push({
    label: "year-over-year-without-comparison-period-never-runs-plain-grouping",
    ok: unsafeYearOverYear.parsed?.businessUnderstanding?.status === "needs-clarification"
      && unsafeYearOverYear.parsed?.queryPlanReceipt?.status === "blocked"
      && unsafeYearOverYear.parsed?.queryPlanReceipt?.validation?.executed === false
      && !unsafeYearOverYear.parsed?.queryPlanReceipt?.runtime?.compiledSql
      && unsafeYearOverYear.parsed?.actionDraft?.status === "read-only",
  });
  const enabledPack = run("enable-pack", ["domain-pack-set", "--pack", "platform-commerce", "--state", "enabled", "--yes"]);
  checks.push(enabledPack);
  const query = run("direct-query", ["query", "--table", "orders", "--group", "channel", "--measure", "net_sales", "--agg", "sum", "--request", "各渠道净销售额"]);
  checks.push(query);
  checks.push({
    label: "direct-query-has-executed-receipt",
    ok: query.parsed?.queryPlanReceipt?.schema === "aibi-query-plan-receipt/v1"
      && query.parsed?.queryPlanReceipt?.status === "executed"
      && query.parsed?.queryPlanReceipt?.selection?.measure === "net_sales"
      && query.parsed?.queryPlanReceipt?.selection?.group === "channel"
      && Boolean(query.parsed?.queryPlanReceipt?.runtime?.compiledSql)
      && query.parsed?.queryPlanReceipt?.validation?.whitelistOnly === true
      && query.parsed?.queryPlanReceipt?.domainPacks?.[0]?.packId === "platform-commerce"
      && query.parsed?.queryPlanReceipt?.domainPackFingerprint !== "",
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
