import { mkdtempSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { performance } from "node:perf_hooks";

const root = resolve(import.meta.dirname, "..");
const verifyRoot = mkdtempSync(join(tmpdir(), "aibi-c-release-baseline-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyRoot, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyRoot, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyRoot, "evidence"),
  PYTHONIOENCODING: "utf-8",
};
const queryBudgetMs = Number(process.env.AIBI_QUERY_P95_BUDGET_MS ?? 1500);
const samples = [];

function runCli(args) {
  const startedAt = performance.now();
  const result = spawnSync("python", ["tools/bi_cli.py", "--json", ...args], {
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

try {
  const imported = runCli([
    "import-commit", resolve(root, "validation-inputs", "orders.csv"),
    "--table", "release_orders", "--name", "发布性能基线", "--mode", "create", "--yes",
  ]);
  if (!imported.ok) throw new Error(imported.parsed?.error || imported.stderr || "Release baseline import failed.");
  const queryArgs = [
    "query-table", "--table", "release_orders", "--mode", "aggregate",
    "--group", "channel", "--measure", "net_sales", "--agg", "sum", "--limit", "20",
  ];
  const warmup = runCli(queryArgs);
  if (!warmup.ok) throw new Error(warmup.parsed?.error || warmup.stderr || "Release baseline warmup failed.");
  for (let index = 0; index < 7; index += 1) {
    const sample = runCli(queryArgs);
    if (!sample.ok) throw new Error(sample.parsed?.error || sample.stderr || `Release baseline sample ${index + 1} failed.`);
    samples.push(sample.durationMs);
  }
  const sorted = [...samples].sort((left, right) => left - right);
  const p50 = sorted[Math.floor((sorted.length - 1) * 0.5)];
  const p95 = sorted[Math.ceil(sorted.length * 0.95) - 1];
  const receipt = {
    ok: p95 <= queryBudgetMs,
    schema: "aibi-release-baseline/v1",
    generatedBy: "scripts/verify-release-baseline.mjs",
    runtime: "python-cli/sqlite-metadata/duckdb-query",
    query: "release_orders: sum(net_sales) by channel",
    sampleCount: samples.length,
    samplesMs: samples,
    p50Ms: p50,
    p95Ms: p95,
    budgetP95Ms: queryBudgetMs,
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
  rmSync(verifyRoot, { recursive: true, force: true });
}
