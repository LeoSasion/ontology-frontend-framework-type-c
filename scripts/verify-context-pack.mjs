import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-context-pack-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args) {
  const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], {
    cwd: process.cwd(),
    env,
    encoding: "utf8",
    windowsHide: true,
  });
  let parsed = null;
  try {
    parsed = JSON.parse(result.stdout.trim());
  } catch {
    parsed = null;
  }
  return { label, ok: result.status === 0 && parsed?.ok === true, status: result.status, parsed, stderr: result.stderr, stdout: result.stdout };
}

try {
  const checks = [
    run("import", ["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]),
    run("dashboard", ["business-dashboard", "--op", "create", "--table", "orders", "--name", "Context verification", "--limit", "1", "--yes"]),
    run("term-preview", ["context-term", "--name", "成交额", "--definition", "订单净销售金额", "--alias", "销售额", "--scope-type", "field", "--scope-ref", "orders.net_sales", "--status", "confirmed", "--evidence", "field:orders.net_sales"]),
    run("term-confirm", ["context-term", "--name", "成交额", "--definition", "订单净销售金额", "--alias", "销售额", "--scope-type", "field", "--scope-ref", "orders.net_sales", "--status", "confirmed", "--evidence", "field:orders.net_sales", "--yes"]),
    run("rule-confirm", ["context-rule", "--title", "成交额单位", "--statement", "成交额按元解释", "--type", "unit", "--applies-to", "orders", "--status", "confirmed", "--evidence", "field:orders.net_sales", "--yes"]),
  ];
  const conflict = run("conflict-blocked", ["context-term", "--name", "销售额", "--definition", "全部订单金额", "--scope-type", "field", "--scope-ref", "orders.net_sales", "--status", "confirmed", "--evidence", "field:orders.net_sales", "--yes"]);
  checks.push({ label: conflict.label, ok: conflict.status === 1 && conflict.parsed?.ok === false && Array.isArray(conflict.parsed?.proposal?.conflicts), parsed: conflict.parsed });
  const ask = run("alias-resolves-field", ["ask", "请用成交额按channel生成一个柱状图"]);
  checks.push(ask);
  checks.push({
    label: "alias-is-grounded-in-field-scope",
    ok: ask.parsed?.answerCard?.query?.measure === "net_sales" && ask.parsed?.answerCard?.query?.group === "channel",
    parsed: { query: ask.parsed?.answerCard?.query, widget: ask.parsed?.matched?.widget, clarification: ask.parsed?.answerCard?.clarification },
  });
  checks.push({
    label: "answer-references-context-assets",
    ok: ask.parsed?.context?.matchedTermCount === 1
      && ask.parsed?.context?.matchedRuleCount === 1
      && ask.parsed?.answerCard?.evidenceRefs?.some((item) => item?.type === "contextTerm")
      && ask.parsed?.answerCard?.evidenceRefs?.some((item) => item?.type === "contextRule"),
  });
  const pack = run("context-pack", ["context-pack"]);
  checks.push(pack);
  checks.push({
    label: "pack-is-versioned-and-scoped",
    ok: pack.parsed?.contextPack?.schema === "aibi-context-pack/v1"
      && pack.parsed?.contextPack?.counts?.confirmedTerms === 1
      && pack.parsed?.contextPack?.counts?.confirmedRules === 1
      && /^[a-f0-9]{64}$/.test(String(pack.parsed?.contextPack?.schemaFingerprint ?? "")),
  });

  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-context-pack-verify/v1",
    generatedBy: "scripts/verify-context-pack.mjs",
    checks: checks.map((check) => ({ label: check.label, ok: check.ok, status: check.status })),
    failedChecks: failedChecks.map((check) => ({ label: check.label, status: check.status, parsed: check.parsed, stderr: check.stderr, stdout: check.stdout?.slice(-1600) })),
  }, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
