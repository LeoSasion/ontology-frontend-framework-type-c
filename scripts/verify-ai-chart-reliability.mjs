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
  const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], {
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
  const firstExplicitBarDraft = run("first-explicit-bar", ["ask", "基于 records，按 channel 汇总 net_sales，生成柱状图"]);
  results.push(firstExplicitBarDraft);
  const firstExplicitBarKey = firstExplicitBarDraft.parsed?.actionDraft?.actionKey ?? "missing-first-explicit-bar";
  results.push(run("first-explicit-bar-actions", ["action-drafts", "--limit", "10"]));
  results.push(run("first-explicit-bar-reject", ["confirm-action", firstExplicitBarKey, "--reject", "--yes"]));
  const firstChartDraft = run("first-chart-draft", ["ask", "基于 records，先问我最多一个必要问题，然后起草一个仅包含一个图表的看板。优先在折线图、柱状图、指标卡或表格中选择，说明字段、口径和证据，不直接写入。"]);
  results.push(firstChartDraft);
  const firstChartKey = firstChartDraft.parsed?.actionDraft?.actionKey ?? "missing-first-chart-draft";
  results.push(run("first-chart-actions", ["action-drafts", "--limit", "10"]));
  results.push(run("first-chart-confirm", ["confirm-action", firstChartKey, "--yes"]));
  results.push(run("dashboards-after-first-chart", ["dashboards"]));
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
      label: "first-explicit-bar-preserves-resolved-widget",
      ok: byLabel["first-explicit-bar"].parsed?.requiresConfirmation === true &&
        byLabel["first-explicit-bar"].parsed?.actionDraft?.kind === "dashboard.create" &&
        byLabel["first-explicit-bar"].parsed?.matched?.widget?.widgetType === "bar" &&
        byLabel["first-explicit-bar"].parsed?.matched?.widget?.measure === "net_sales" &&
        byLabel["first-explicit-bar"].parsed?.matched?.widget?.dimension === "channel" &&
        byLabel["first-explicit-bar"].parsed?.matched?.widget?.aggregation === "sum" &&
        byLabel["first-explicit-bar-actions"].parsed?.actionDrafts?.some((draft) =>
          draft.action_key === firstExplicitBarKey &&
          draft.payload?.originalPrompt === "基于 records，按 channel 汇总 net_sales，生成柱状图" &&
          draft.payload?.dashboardDraft?.source === "single-chart" &&
          draft.payload?.dashboardDraft?.widgets?.length === 1 &&
          draft.payload.dashboardDraft.widgets[0]?.type === "bar" &&
          draft.payload.dashboardDraft.widgets[0]?.measure === "net_sales" &&
          draft.payload.dashboardDraft.widgets[0]?.dimension === "channel" &&
          draft.payload.dashboardDraft.widgets[0]?.aggregation === "sum"
        ) &&
        byLabel["first-explicit-bar-reject"].parsed?.confirmed === true &&
        byLabel["first-explicit-bar-reject"].parsed?.decision === "reject",
    },
    {
      label: "first-chart-from-import-creates-one-widget-draft",
      ok: byLabel.import.status === 0 && byLabel.import.parsed?.ok === true &&
        byLabel["first-chart-draft"].parsed?.requiresConfirmation === true &&
        byLabel["first-chart-draft"].parsed?.actionDraft?.kind === "dashboard.create" &&
        byLabel["first-chart-actions"].parsed?.actionDrafts?.some((draft) =>
          draft.action_key === firstChartKey &&
          draft.label === "生成单图表草案" &&
          draft.payload?.dashboardDraft?.source === "single-chart" &&
          draft.payload?.dashboardDraft?.widgetCount === 1 &&
          draft.payload?.dashboardDraft?.widgets?.length === 1 &&
          ["metric", "line", "bar", "pie", "table"].includes(draft.payload.dashboardDraft.widgets[0]?.type)
        ) &&
        byLabel["first-chart-confirm"].parsed?.confirmed === true &&
        byLabel["dashboards-after-first-chart"].parsed?.dashboards?.some((dashboard) =>
          dashboard.dashboard_key === byLabel["first-chart-confirm"].parsed?.createdDashboardKey &&
          dashboard.widgets?.length === 1
        ),
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
