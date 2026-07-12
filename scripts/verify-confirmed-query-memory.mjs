import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-confirmed-query-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args) {
  const result = spawnSync("python", ["tools/bi_cli.py", "--json", ...args], { cwd: process.cwd(), env, encoding: "utf8", windowsHide: true });
  let parsed = null;
  try { parsed = JSON.parse(result.stdout.trim()); } catch { parsed = null; }
  return { label, ok: result.status === 0 && parsed?.ok === true, status: result.status, parsed, stderr: result.stderr, stdout: result.stdout };
}

try {
  const checks = [
    run("import", ["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]),
    run("dashboard", ["business-dashboard", "--op", "create", "--table", "orders", "--name", "Memory verification", "--limit", "1", "--yes"]),
  ];
  const unconfirmedAsk = run("unconfirmed-ask", ["ask", "请用quantity按category生成柱状图"]);
  checks.push(unconfirmedAsk);
  const beforeConfirm = run("no-candidate-before-action-confirm", ["confirmed-queries", "--limit", "10"]);
  checks.push(beforeConfirm);
  checks.push({ label: "draft-does-not-become-memory", ok: beforeConfirm.parsed?.count === 0 });

  const ask = run("ask", ["ask", "请用net_sales按channel生成柱状图"]);
  checks.push(ask);
  const actionKey = ask.parsed?.actionDraft?.actionKey;
  const actionConfirm = run("confirm-chart", ["confirm-action", actionKey, "--yes"]);
  checks.push(actionConfirm);
  const candidate = actionConfirm.parsed?.confirmedQueryCandidate;
  checks.push({
    label: "confirmed-chart-creates-candidate-only",
    ok: candidate?.status === "candidate"
      && candidate?.originating_action_key === actionKey
      && candidate?.query_receipt_key === ask.parsed?.queryPlanReceipt?.receiptKey,
  });
  const beforePromotionAsk = run("candidate-not-recalled", ["ask", "请用net_sales按channel生成柱状图"]);
  checks.push(beforePromotionAsk);
  checks.push({ label: "candidate-is-not-active-memory", ok: beforePromotionAsk.parsed?.context?.confirmedQueries?.length === 0 });

  const promotePreview = run("promote-preview", ["confirm-query", "--query", candidate?.query_key]);
  checks.push(promotePreview);
  checks.push({ label: "promotion-requires-confirmation", ok: promotePreview.parsed?.dryRun === true && promotePreview.parsed?.requiresConfirmation === true });
  const promoted = run("promote-confirm", ["confirm-query", "--query", candidate?.query_key, "--yes"]);
  checks.push(promoted);
  checks.push({ label: "query-promoted", ok: promoted.parsed?.savedQuery?.status === "confirmed" && Boolean(promoted.parsed?.savedQuery?.confirmed_at) });

  const recalled = run("confirmed-query-recalled", ["ask", "请用net_sales按channel生成柱状图"]);
  checks.push(recalled);
  checks.push({
    label: "confirmed-memory-is-auditable",
    ok: recalled.parsed?.context?.confirmedQueries?.some((item) => item?.queryKey === candidate?.query_key)
      && recalled.parsed?.answerCard?.evidenceRefs?.some((item) => item?.type === "confirmedQuery"),
  });

  const semanticChange = run("semantic-change", ["field-update", "--table", "orders", "--field", "net_sales", "--role", "dimension", "--usage", "groupable", "--confidence", "0.95", "--yes"]);
  checks.push(semanticChange);
  const staleList = run("stale-refresh", ["confirmed-queries", "--status", "stale", "--limit", "10"]);
  checks.push(staleList);
  checks.push({
    label: "schema-or-semantic-change-invalidates-memory",
    ok: staleList.parsed?.confirmedQueries?.some((item) => item?.query_key === candidate?.query_key && item?.stale_reason),
  });
  const afterStale = run("stale-query-not-recalled", ["ask", "请用net_sales按channel生成柱状图"]);
  checks.push(afterStale);
  checks.push({ label: "stale-memory-is-excluded", ok: afterStale.parsed?.context?.confirmedQueries?.length === 0 });

  const createFirstChartWorkspace = run("create-first-chart-workspace", ["workspace-create", "--name", "First chart memory", "--yes"]);
  checks.push(createFirstChartWorkspace);
  const firstChartWorkspaceId = createFirstChartWorkspace.parsed?.created?.id;
  checks.push(run("select-first-chart-workspace", ["workspace-select", firstChartWorkspaceId, "--yes"]));
  checks.push(run("import-first-chart-source", ["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]));
  const firstChartAsk = run("ask-first-chart", ["ask", "基于 orders，用 net_sales 按 channel 起草一个仅包含一个柱状图的看板，确认前不要写入"]);
  checks.push(firstChartAsk);
  const firstChartActionKey = firstChartAsk.parsed?.actionDraft?.actionKey;
  const firstChartConfirm = run("confirm-first-chart", ["confirm-action", firstChartActionKey, "--yes"]);
  checks.push(firstChartConfirm);
  checks.push({
    label: "first-dashboard-chart-also-creates-memory-candidate",
    ok: firstChartAsk.parsed?.actionDraft?.kind === "dashboard.create"
      && firstChartConfirm.parsed?.confirmedQueryCandidate?.status === "candidate"
      && firstChartConfirm.parsed?.confirmedQueryCandidate?.originating_action_key === firstChartActionKey,
  });

  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-confirmed-query-memory-verify/v1",
    generatedBy: "scripts/verify-confirmed-query-memory.mjs",
    checks: checks.map((check) => ({ label: check.label, ok: check.ok, status: check.status })),
    failedChecks: failedChecks.map((check) => ({ label: check.label, status: check.status, parsed: check.parsed, stderr: check.stderr, stdout: check.stdout?.slice(-1600) })),
  }, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
