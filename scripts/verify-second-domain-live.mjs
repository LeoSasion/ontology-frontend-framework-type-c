import { mkdtempSync, rmSync } from "node:fs";
import { basename, join } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";

function option(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? String(process.argv[index + 1] ?? "").trim() : "";
}

const input = option("--file");
const measure = option("--measure");
const dimension = option("--dimension");
const chartType = option("--chart") || "bar";

if (!input || !measure || !dimension) {
  console.error("Usage: node scripts/verify-second-domain-live.mjs --file <csv/xlsx> --measure <field> --dimension <field> [--chart bar|line]");
  process.exit(2);
}

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-second-domain-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence-bundles"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args) {
  const result = spawnSync("python", ["tools/bi_cli.py", "--json", ...args], {
    cwd: process.cwd(),
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
    stderr: result.stderr,
    stdout: result.stdout,
  };
}

function firstValue(...values) {
  return values.find((value) => typeof value === "string" && value) ?? "";
}

try {
  const checks = [];
  const preview = run("preview-import", ["preview-import", input]);
  checks.push(preview);
  const tableKey = firstValue(
    preview.parsed?.preview?.tableKey,
    preview.parsed?.tableKey,
    preview.parsed?.importPlan?.tableKey,
    preview.parsed?.suggestedTableKey,
  );
  if (!tableKey) {
    checks.push({ label: "preview-resolves-table", ok: false, parsed: preview.parsed });
  }

  const commit = run("commit-import", [
    "import-commit", input,
    "--table", tableKey || "second_domain",
    "--name", basename(input),
    "--mode", "create",
    "--yes",
  ]);
  checks.push(commit);

  const profile = run("source-intelligence", [
    "source-intelligence", input,
    "--output-dir", join(verifyDir, "source-intelligence"),
    "--label", "second independent domain acceptance",
  ]);
  checks.push(profile);

  const dashboard = run("create-minimal-dashboard", [
    "business-dashboard", "--op", "create",
    "--table", tableKey || "second_domain",
    "--name", "Second domain acceptance",
    "--limit", "1",
    "--yes",
  ]);
  checks.push(dashboard);

  const chartWord = chartType === "line" ? "折线图" : "柱状图";
  const prompt = `请用 ${measure} 按 ${dimension} 生成一个${chartWord}`;
  const ask = run("ask-explicit-single-chart", ["ask", prompt]);
  checks.push(ask);
  const actionKey = firstValue(ask.parsed?.actionDraft?.actionKey);
  const query = ask.parsed?.answerCard?.query;
  checks.push({
    label: "explicit-fields-resolved-without-domain-fallback",
    ok: query?.measure === measure && query?.group === dimension && ask.parsed?.requiresConfirmation === true,
    parsed: { query, actionDraft: ask.parsed?.actionDraft },
  });
  checks.push({
    label: "answer-carries-source-and-query-evidence",
    ok: Array.isArray(ask.parsed?.answerCard?.evidenceRefs)
      && ask.parsed.answerCard.evidenceRefs.some((item) => item?.type === "sourceRun")
      && ask.parsed.answerCard.evidenceRefs.some((item) => item?.type === "queryRuntime"),
  });

  const confirm = actionKey
    ? run("confirm-single-chart", ["confirm-action", actionKey, "--yes"])
    : { label: "confirm-single-chart", ok: false, parsed: { error: "No action draft was created" } };
  checks.push(confirm);
  checks.push({
    label: "confirmed-one-widget",
    ok: Boolean(confirm.parsed?.confirmed && confirm.parsed?.addedWidget),
    parsed: confirm.parsed,
  });

  const failedChecks = checks.filter((check) => !check.ok);
  const receipt = {
    ok: failedChecks.length === 0,
    schema: "aibi-second-domain-live-acceptance/v1",
    generatedBy: "scripts/verify-second-domain-live.mjs",
    input: basename(input),
    tableKey,
    requested: { measure, dimension, chartType },
    checks: checks.map((check) => ({ label: check.label, ok: check.ok, status: check.status })),
    failedChecks: failedChecks.map((check) => ({
      label: check.label,
      status: check.status,
      parsed: check.parsed,
      stderr: check.stderr,
      stdout: check.stdout?.slice(-2000),
    })),
  };
  console.log(JSON.stringify(receipt, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
