import { mkdtempSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";

const WARMUP_COUNT = 2;
const INITIAL_SAMPLE_COUNT = 9;
const CONFIRMED_SAMPLE_COUNT = 20;

export function nearestRankPercentile(samples, percentile) {
  if (!Array.isArray(samples) || samples.length === 0) throw new Error("Performance samples must not be empty.");
  if (!(percentile > 0 && percentile <= 1)) throw new Error("Percentile must be greater than 0 and at most 1.");
  if (!samples.every((sample) => Number.isFinite(sample) && sample >= 0)) throw new Error("Performance samples must be finite non-negative numbers.");
  const sorted = [...samples].sort((left, right) => left - right);
  return sorted[Math.max(0, Math.ceil(sorted.length * percentile) - 1)];
}

export function evaluateReleaseBaselineSamples(samples, { p50BudgetMs, p95BudgetMs }) {
  if (!(Number.isFinite(p50BudgetMs) && p50BudgetMs > 0)) throw new Error("P50 budget must be a positive number.");
  if (!(Number.isFinite(p95BudgetMs) && p95BudgetMs > 0)) throw new Error("P95 budget must be a positive number.");
  const p50Ms = nearestRankPercentile(samples, 0.5);
  const p95Ms = nearestRankPercentile(samples, 0.95);
  const steadyStatePassed = p50Ms <= p50BudgetMs;
  const tailPassed = p95Ms <= p95BudgetMs;
  return {
    ok: steadyStatePassed && tailPassed,
    p50Ms,
    p95Ms,
    maxMs: Math.max(...samples),
    steadyStatePassed,
    tailPassed,
    tailOverBudgetCount: samples.filter((sample) => sample > p95BudgetMs).length,
  };
}

export function needsTailConfirmation(evaluation, sampleCount) {
  return sampleCount < CONFIRMED_SAMPLE_COUNT && evaluation.steadyStatePassed && !evaluation.tailPassed;
}

function positiveBudget(name, fallback) {
  const value = Number(process.env[name] ?? fallback);
  if (!(Number.isFinite(value) && value > 0)) throw new Error(`${name} must be a positive number.`);
  return value;
}

function runReleaseBaseline() {
  const root = resolve(import.meta.dirname, "..");
  const samples = [];
  let verifyRoot = "";
  let env = null;

  function runCli(args) {
    const startedAt = performance.now();
    const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], {
      cwd: root,
      env,
      encoding: "utf8",
      windowsHide: true,
      maxBuffer: 16 * 1024 * 1024,
    });
    const durationMs = Number((performance.now() - startedAt).toFixed(1));
    let parsed = null;
    try {
      parsed = JSON.parse(result.stdout.trim());
    } catch {
      parsed = null;
    }
    return { ok: result.status === 0 && parsed?.ok === true, durationMs, parsed, stderr: result.stderr };
  }

  function collectSamples(queryArgs, targetCount) {
    while (samples.length < targetCount) {
      const sample = runCli(queryArgs);
      if (!sample.ok) throw new Error(sample.parsed?.error || sample.stderr || `Release baseline sample ${samples.length + 1} failed.`);
      samples.push(sample.durationMs);
    }
  }

  try {
    const budgets = {
      p50BudgetMs: positiveBudget("AIBI_QUERY_P50_BUDGET_MS", 1500),
      p95BudgetMs: positiveBudget("AIBI_QUERY_P95_BUDGET_MS", 3500),
    };
    verifyRoot = mkdtempSync(join(tmpdir(), "aibi-c-release-baseline-"));
    env = {
      ...process.env,
      AIBI_HYBRID_DB_PATH: join(verifyRoot, "runtime.sqlite"),
      AIBI_HYBRID_DUCKDB_PATH: join(verifyRoot, "runtime.duckdb"),
      AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyRoot, "evidence"),
      PYTHONIOENCODING: "utf-8",
    };
    const imported = runCli([
      "import-commit", resolve(root, "validation-inputs", "orders.csv"),
      "--table", "release_orders", "--name", "发布性能基线", "--mode", "create", "--yes",
    ]);
    if (!imported.ok) throw new Error(imported.parsed?.error || imported.stderr || "Release baseline import failed.");
    const queryArgs = [
      "query-table", "--workspace", "default", "--table", "release_orders", "--mode", "aggregate",
      "--group", "channel", "--measure", "net_sales", "--agg", "sum", "--limit", "20",
    ];
    for (let index = 0; index < WARMUP_COUNT; index += 1) {
      const warmup = runCli(queryArgs);
      if (!warmup.ok) throw new Error(warmup.parsed?.error || warmup.stderr || `Release baseline warmup ${index + 1} failed.`);
    }

    collectSamples(queryArgs, INITIAL_SAMPLE_COUNT);
    const initialEvaluation = evaluateReleaseBaselineSamples(samples, budgets);
    const confirmationTriggered = needsTailConfirmation(initialEvaluation, samples.length);
    if (confirmationTriggered) collectSamples(queryArgs, CONFIRMED_SAMPLE_COUNT);
    const finalEvaluation = evaluateReleaseBaselineSamples(samples, budgets);
    const receipt = {
      ok: finalEvaluation.ok,
      schema: "aibi-release-baseline/v1",
      generatedBy: "scripts/verify-release-baseline.mjs",
      runtime: "python-cli/sqlite-metadata/duckdb-query",
      query: "release_orders: sum(net_sales) by channel",
      warmupCount: WARMUP_COUNT,
      sampleCount: samples.length,
      samplesMs: samples,
      p50Ms: finalEvaluation.p50Ms,
      p95Ms: finalEvaluation.p95Ms,
      maxMs: finalEvaluation.maxMs,
      budgetP50Ms: budgets.p50BudgetMs,
      budgetP95Ms: budgets.p95BudgetMs,
      steadyStatePassed: finalEvaluation.steadyStatePassed,
      tailPassed: finalEvaluation.tailPassed,
      tailOverBudgetCount: finalEvaluation.tailOverBudgetCount,
      confirmationTriggered,
      initialEvaluation,
      budgetPolicy: "2 warmups; 9 steady-state samples; expand to 20 only when p50 passes and initial tail exceeds budget; nearest-rank p95 then permits one isolated outlier but fails two",
    };
    console.log(JSON.stringify(receipt, null, 2));
    if (!receipt.ok) process.exitCode = 1;
  } catch (error) {
    console.error(JSON.stringify({
      ok: false,
      schema: "aibi-release-baseline/v1",
      generatedBy: "scripts/verify-release-baseline.mjs",
      error: error instanceof Error ? error.message : String(error),
      samplesMs: samples,
    }, null, 2));
    process.exitCode = 1;
  } finally {
    if (verifyRoot) rmSync(verifyRoot, { recursive: true, force: true });
  }
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) runReleaseBaseline();
