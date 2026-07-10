import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const verifyDir = mkdtempSync(join(tmpdir(), "aibi-ai-chart-reliability-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "verify.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "verify.duckdb"),
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
  return { label, status: result.status, parsed, stdout: result.stdout, stderr: result.stderr };
}

const results = [];
try {
  results.push(run("empty-chart", ["ask", "创建一个图表"]));
  results.push(run("import", ["import-commit", "validation-inputs/orders.csv", "--table", "records", "--name", "Records", "--mode", "create", "--yes"]));
  results.push(run("dashboard", ["business-dashboard", "--op", "create", "--table", "records", "--limit", "3", "--yes"]));
  results.push(run("generic-overview", ["ask", "--read-only", "概览当前数据"]));
  results.push(run("ambiguous-chart", ["ask", "创建一个图表"]));
  results.push(run("explicit-bar", ["ask", "用 records 的 net_sales 按 channel 创建柱状图"]));
  results.push(run("explicit-line", ["ask", "用 records 的 net_sales 按 order_date 创建折线图"]));
  results.push(run("unknown-field", ["ask", "用 records 的 imaginary_margin 按 channel 创建柱状图"]));
  results.push(run("missing-dimension", ["ask", "用 records 的 net_sales 创建柱状图"]));

  const byLabel = Object.fromEntries(results.map((result) => [result.label, result]));
  const checks = [
    {
      label: "empty-state-never-invents-chart",
      ok: byLabel["empty-chart"].parsed?.requiresConfirmation === false &&
        byLabel["empty-chart"].parsed?.answerCard?.kind === "gap" &&
        byLabel["empty-chart"].parsed?.actionDraft?.status === "read-only",
    },
    {
      label: "isolated-bootstrap-ready",
      ok: byLabel.import.status === 0 && byLabel.import.parsed?.ok === true &&
        byLabel.dashboard.status === 0 && byLabel.dashboard.parsed?.ok === true,
    },
    {
      label: "generic-overview-does-not-default-to-sales",
      ok: byLabel["generic-overview"].parsed?.answerCard?.kind === "data_overview" &&
        byLabel["generic-overview"].parsed?.answerCard?.query?.measure === "*" &&
        byLabel["generic-overview"].parsed?.answerCard?.query?.group == null &&
        byLabel["generic-overview"].parsed?.requiresConfirmation === false,
    },
    {
      label: "ambiguous-chart-asks-once-without-draft",
      ok: byLabel["ambiguous-chart"].parsed?.answerCard?.kind === "clarification" &&
        byLabel["ambiguous-chart"].parsed?.matched?.widget?.needsClarification === true &&
        byLabel["ambiguous-chart"].parsed?.requiresConfirmation === false,
    },
    {
      label: "explicit-bar-uses-requested-fields",
      ok: byLabel["explicit-bar"].parsed?.actionDraft?.kind === "dashboard.widget.add" &&
        byLabel["explicit-bar"].parsed?.requiresConfirmation === true &&
        byLabel["explicit-bar"].parsed?.answerCard?.kind === "chart_preview" &&
        byLabel["explicit-bar"].parsed?.answerCard?.query?.measure === "net_sales" &&
        byLabel["explicit-bar"].parsed?.answerCard?.query?.group === "channel",
    },
    {
      label: "explicit-line-uses-requested-time-field",
      ok: byLabel["explicit-line"].parsed?.requiresConfirmation === true &&
        byLabel["explicit-line"].parsed?.matched?.widget?.widgetType === "line" &&
        byLabel["explicit-line"].parsed?.answerCard?.query?.measure === "net_sales" &&
        byLabel["explicit-line"].parsed?.answerCard?.query?.group === "order_date",
    },
    {
      label: "unknown-field-never-falls-back-silently",
      ok: byLabel["unknown-field"].parsed?.answerCard?.kind === "clarification" &&
        byLabel["unknown-field"].parsed?.requiresConfirmation === false,
    },
    {
      label: "bar-without-dimension-never-picks-one-silently",
      ok: byLabel["missing-dimension"].parsed?.answerCard?.kind === "clarification" &&
        byLabel["missing-dimension"].parsed?.requiresConfirmation === false,
    },
  ];
  const failed = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failed.length === 0,
    generatedBy: "scripts/verify-ai-chart-reliability.mjs",
    checks,
    failures: failed.map((check) => check.label),
    commandErrors: results
      .filter((result) => result.status !== 0 || result.parsed?.ok !== true)
      .map((result) => ({ label: result.label, status: result.status, error: result.parsed?.error || result.stderr.trim() })),
  }, null, 2));
  process.exitCode = failed.length === 0 ? 0 : 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
