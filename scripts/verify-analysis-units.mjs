import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-analysis-units-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args, expectedStatus = 0) {
  const result = spawnSync("python", ["tools/bi_cli.py", "--json", ...args], {
    cwd: process.cwd(), env, encoding: "utf8", windowsHide: true,
  });
  let parsed = null;
  try { parsed = JSON.parse(result.stdout.trim()); } catch { parsed = null; }
  return {
    label,
    ok: result.status === expectedStatus && (expectedStatus !== 0 || parsed?.ok === true),
    status: result.status,
    parsed,
    stderr: result.stderr,
    stdout: result.stdout,
  };
}

try {
  const checks = [
    run("import", ["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]),
  ];

  const comparison = run("comparison-query", ["query", "--table", "orders", "--group", "channel", "--measure", "net_sales", "--agg", "sum", "--request", "各渠道净销售额柱状图"]);
  checks.push(comparison);
  const comparisonUnit = comparison.parsed?.analysisUnit;
  checks.push({
    label: "query-creates-receipt-bound-comparison-unit",
    ok: comparisonUnit?.schema === "aibi-analysis-unit/v1"
      && comparisonUnit?.queryReceiptKey === comparison.parsed?.queryPlanReceipt?.receiptKey
      && comparisonUnit?.resultFingerprint === comparison.parsed?.queryPlanReceipt?.resultBinding?.resultFingerprint
      && comparisonUnit?.kind === "comparison"
      && comparisonUnit?.status === "ready"
      && comparisonUnit?.grain?.dimensions?.[0]?.field === "channel"
      && comparisonUnit?.grain?.dimensions?.[0]?.resultColumn === "label"
      && comparisonUnit?.grain?.measures?.[0]?.field === "net_sales"
      && comparisonUnit?.grain?.measures?.[0]?.resultColumn === "value"
      && comparisonUnit?.shape?.columns?.join(",") === "label,value"
      && comparisonUnit?.rows?.every((row) => !("raw" in row)),
  });
  checks.push({
    label: "comparison-chart-is-deterministic-bar",
    ok: comparison.parsed?.chartAdapter?.schema === "aibi-chart-adapter/v1"
      && comparison.parsed?.chartAdapter?.status === "ready"
      && comparison.parsed?.chartAdapter?.chartType === "bar"
      && comparison.parsed?.chartAdapter?.allowedChartTypes?.join(",") === "bar,table",
  });

  const list = run("list-units", ["analysis-units", "--receipt", comparisonUnit?.queryReceiptKey ?? "missing"]);
  checks.push(list, {
    label: "unit-is-workspace-scoped-and-listable",
    ok: list.parsed?.count === 1 && list.parsed?.analysisUnits?.[0]?.unitKey === comparisonUnit?.unitKey,
  });
  const verify = run("recalculate-unit", ["analysis-unit-verify", "--unit", comparisonUnit?.unitKey ?? "missing"]);
  checks.push(verify, {
    label: "frozen-snapshot-recalculates-exactly",
    ok: verify.parsed?.rowsFingerprintMatches === true && verify.parsed?.calculationMatches === true,
  });

  const composition = run("composition-unit", [
    "analysis-unit-build", "--receipt", comparisonUnit?.queryReceiptKey ?? "missing", "--kind", "composition",
    "--rows-json", JSON.stringify(comparison.parsed?.rows ?? []), "--preferred-chart", "pie",
  ]);
  checks.push(composition, {
    label: "composition-computes-shares-and-selects-pie",
    ok: composition.parsed?.analysisUnit?.kind === "composition"
      && composition.parsed?.analysisUnit?.calculation?.shares?.length === 3
      && composition.parsed?.chartAdapter?.chartType === "pie",
  });

  const ranking = run("ranking-unit", [
    "analysis-unit-build", "--receipt", comparisonUnit?.queryReceiptKey ?? "missing", "--kind", "ranking",
    "--rows-json", JSON.stringify(comparison.parsed?.rows ?? []),
  ]);
  checks.push(ranking, {
    label: "ranking-is-stably-ordered-and-horizontal",
    ok: ranking.parsed?.analysisUnit?.calculation?.ranks?.[0]?.rank === 1
      && ranking.parsed?.chartAdapter?.chartType === "bar"
      && ranking.parsed?.chartAdapter?.config?.barOrientation === "horizontal",
  });

  const trend = run("trend-query", ["query", "--table", "orders", "--group", "order_date", "--measure", "net_sales", "--agg", "sum", "--request", "净销售额按日期趋势折线图"]);
  checks.push(trend, {
    label: "temporal-shape-selects-trend-line",
    ok: trend.parsed?.analysisUnit?.kind === "trend"
      && trend.parsed?.analysisUnit?.shape?.temporalDimension === true
      && trend.parsed?.chartAdapter?.chartType === "line"
      && typeof trend.parsed?.analysisUnit?.calculation?.absoluteChange === "number",
  });

  const anomaly = run("anomaly-unit", [
    "analysis-unit-build", "--receipt", trend.parsed?.analysisUnit?.queryReceiptKey ?? "missing", "--kind", "anomaly",
    "--rows-json", JSON.stringify(trend.parsed?.rows ?? []),
  ]);
  checks.push(anomaly, {
    label: "anomaly-unit-requires-five-and-calculates-z-scores",
    ok: anomaly.parsed?.analysisUnit?.status === "ready"
      && anomaly.parsed?.analysisUnit?.calculation?.scoredPoints?.length >= 5
      && anomaly.parsed?.chartAdapter?.chartType === "line",
  });

  const metric = run("metric-query", ["query", "--table", "orders", "--measure", "net_sales", "--agg", "sum", "--request", "净销售额指标卡"]);
  checks.push(metric, {
    label: "single-value-shape-selects-metric",
    ok: metric.parsed?.analysisUnit?.kind === "metric"
      && metric.parsed?.analysisUnit?.shape?.rowCount === 1
      && metric.parsed?.chartAdapter?.chartType === "metric",
  });

  const incompatible = run("incompatible-chart-blocked", ["chart-adapt", "--unit", comparisonUnit?.unitKey ?? "missing", "--preferred-chart", "line"], 1);
  checks.push(incompatible, {
    label: "incompatible-preference-never-silently-renders",
    ok: incompatible.parsed?.ok === false
      && incompatible.parsed?.chartAdapter?.status === "blocked"
      && incompatible.parsed?.chartAdapter?.blockers?.includes("preferred-chart-incompatible"),
  });

  const tamperedRows = structuredClone(comparison.parsed?.rows ?? []);
  if (tamperedRows[0]) tamperedRows[0].value = Number(tamperedRows[0].value ?? 0) + 1;
  const tampered = run("tampered-result-blocked", [
    "analysis-unit-build", "--receipt", comparisonUnit?.queryReceiptKey ?? "missing", "--kind", "comparison",
    "--rows-json", JSON.stringify(tamperedRows),
  ], 1);
  checks.push(tampered, {
    label: "receipt-fingerprint-rejects-substituted-rows",
    ok: tampered.parsed?.ok === false && /fingerprint/i.test(String(tampered.parsed?.error ?? "")),
  });

  const agent = run("agent-query", ["ask", "请用net_sales按channel生成柱状图"]);
  checks.push(agent, {
    label: "agent-reuses-unit-and-chart-contract",
    ok: agent.parsed?.analysisUnit?.status === "ready"
      && agent.parsed?.answerCard?.analysisUnitRef?.unitKey === agent.parsed?.analysisUnit?.unitKey
      && agent.parsed?.answerCard?.chartAdapter?.inputFingerprint === agent.parsed?.chartAdapter?.inputFingerprint,
  });
  const blocked = run("blocked-agent-query", ["ask", "请用不存在字段按channel生成柱状图"]);
  checks.push(blocked, {
    label: "blocked-query-creates-blocked-unit-without-chart",
    ok: blocked.parsed?.analysisUnit?.status === "blocked"
      && blocked.parsed?.chartAdapter?.status === "blocked"
      && blocked.parsed?.chartAdapter?.chartType == null,
  });

  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-analysis-unit-verify/v1",
    generatedBy: "scripts/verify-analysis-units.mjs",
    checks: checks.map((check) => ({ label: check.label, ok: check.ok, status: check.status })),
    failedChecks: failedChecks.map((check) => ({
      label: check.label,
      status: check.status,
      parsed: check.parsed,
      stderr: check.stderr,
      stdout: check.stdout?.slice(-1800),
    })),
  }, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
