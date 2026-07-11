import { mkdtempSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { spawnSync } from "node:child_process";

const defaultIgnoredDirs = new Set([".git", "node_modules", "dist", "data", "tmp", "logs"]);

export function hasCssRule(source, selector, ...declarations) {
  const rulePattern = /([^{}]+)\{([^{}]*)\}/g;
  return Array.from(source.matchAll(rulePattern)).some((match) =>
    match[1]
      .split(",")
      .map((item) => item.trim())
      .includes(selector) &&
    declarations.every((declaration) => match[2].includes(declaration)),
  );
}

export function createVerifyRuntime({ prefix = "aibi-hybrid-verify-", ignoredDirs = defaultIgnoredDirs } = {}) {
  const root = process.cwd();
  const verifyDataDir = mkdtempVerifyDir(prefix);
  const verifyDbPath = join(verifyDataDir, "aibi_hybrid_verify.sqlite");
  const verifyDuckDbPath = join(verifyDataDir, "aibi_hybrid_verify.duckdb");
  const verifyReceiptPath = join(verifyDataDir, "verify-receipt.json");
  const fullOutput = process.argv.includes("--full") || process.env.AIBI_VERIFY_FULL === "1";

  function walk(dir) {
    const entries = [];
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      const rel = relative(root, path);
      const stats = statSync(path);
      if (stats.isDirectory()) {
        if (!ignoredDirs.has(name)) entries.push(...walk(path));
      } else {
        entries.push(rel);
      }
    }
    return entries;
  }

  function run(label, command, args) {
    const result = spawnSync(command, args, {
      cwd: root,
      encoding: "utf8",
      env: {
        ...process.env,
        AIBI_HYBRID_DB_PATH: verifyDbPath,
        AIBI_HYBRID_DUCKDB_PATH: verifyDuckDbPath,
        PYTHONIOENCODING: "utf-8",
      },
      windowsHide: true,
    });
    const stdout = result.stdout.trim();
    let parsed = null;
    try {
      parsed = stdout ? JSON.parse(stdout) : null;
    } catch {
      parsed = null;
    }
    return {
      label,
      ok: result.status === 0 && (!parsed || parsed.ok !== false),
      status: result.status,
      parsed,
      stdout,
      stderr: result.stderr.trim(),
    };
  }

  function runExpectedFailure(label, command, args) {
    const result = run(label, command, args);
    return {
      ...result,
      ok: result.status !== 0 && result.parsed?.ok === false,
    };
  }

  return {
    fullOutput,
    root,
    run,
    runExpectedFailure,
    verifyDataDir,
    verifyReceiptPath,
    walk,
  };
}

export function finishVerify({ checks, fullOutput, generatedBy, verifyReceiptPath }) {
  const failed = checks.filter((check) => !check.ok);
  const receipt = {
    ok: failed.length === 0,
    generatedBy,
    fullReceiptPath: verifyReceiptPath,
    checks,
    failedChecks: failed,
  };

  writeFileSync(verifyReceiptPath, JSON.stringify(receipt, null, 2), "utf8");
  console.log(JSON.stringify(fullOutput ? receipt : compactReceipt(receipt), null, 2));
  if (!receipt.ok) process.exit(1);
  return receipt;
}

function mkdtempVerifyDir(prefix) {
  return mkdtempSync(join(tmpdir(), prefix));
}

function tailText(value, limit = 2000) {
  const text = String(value ?? "");
  if (text.length <= limit) return text;
  return `...${text.slice(text.length - limit)}`;
}

function compactFailure(check) {
  const parsed = check.parsed && typeof check.parsed === "object" ? check.parsed : null;
  return {
    label: check.label,
    ok: check.ok,
    status: check.status,
    command: parsed?.command,
    error: parsed?.error ?? (check.stderr ? tailText(check.stderr, 1200) : undefined),
    parsed: parsed
      ? {
          ok: parsed.ok,
          command: parsed.command,
          error: parsed.error,
          failedChecks: parsed.failedChecks?.map((item) => ({
            label: item.label,
            ok: item.ok,
            status: item.status,
            error: item.parsed?.error ?? item.error,
          })),
        }
      : null,
    stdoutTail: !parsed && check.stdout ? tailText(check.stdout) : undefined,
    stderrTail: check.stderr ? tailText(check.stderr) : undefined,
  };
}

function compactReceipt(receipt) {
  const failedLabels = receipt.failedChecks.map((check) => check.label);
  return {
    ok: receipt.ok,
    generatedBy: receipt.generatedBy,
    fullReceiptPath: receipt.fullReceiptPath,
    totalChecks: receipt.checks.length,
    passedChecks: receipt.checks.length - receipt.failedChecks.length,
    failedChecks: receipt.failedChecks.map(compactFailure),
    failedCheckLabels: failedLabels,
  };
}
