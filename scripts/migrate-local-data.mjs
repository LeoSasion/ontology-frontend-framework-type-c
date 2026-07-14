import { copyFileSync, existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import {
  assertLocalServiceStopped,
  createSafetyBackup,
  localDataFiles,
  sha256,
} from "./local-data-snapshot.mjs";

const args = new Set(process.argv.slice(2));
const confirmed = args.has("--confirm");
const simulateFailure = args.has("--simulate-failure");
const simulateApplyFailure = args.has("--simulate-apply-failure");
const simulateValidationFailure = args.has("--simulate-validation-failure");
const python = process.env.PYTHON ?? "python";
const root = resolve(import.meta.dirname, "..");
const helper = resolve(root, "tools", "local_schema_migration.py");

function runHelper(command, files) {
  const byKind = new Map(files.map((item) => [item.kind, item.path]));
  const helperArgs = [helper, command];
  if (byKind.get("sqlite")) helperArgs.push("--sqlite", byKind.get("sqlite"));
  if (byKind.get("duckdb")) helperArgs.push("--duckdb", byKind.get("duckdb"));
  const result = spawnSync(python, helperArgs, { cwd: root, encoding: "utf8", env: process.env });
  let payload = null;
  try {
    payload = JSON.parse(result.stdout || "{}");
  } catch {
    payload = { ok: false, error: result.stderr || result.stdout || "Migration helper returned invalid JSON." };
  }
  if (result.status !== 0 || !payload.ok) {
    throw new Error(payload.error || result.stderr || `Migration helper failed with status ${result.status}.`);
  }
  return payload;
}

function fileReceipts(files) {
  return files.filter((item) => existsSync(item.path)).map((item) => ({
    kind: item.kind,
    path: item.path,
    bytes: readFileSync(item.path).byteLength,
    sha256: sha256(item.path),
  }));
}

function sameReceipts(before, after) {
  return before.length === after.length && before.every((item) => {
    const next = after.find((candidate) => candidate.kind === item.kind);
    return next && next.bytes === item.bytes && next.sha256 === item.sha256;
  });
}

await assertLocalServiceStopped();
const targets = localDataFiles();
const existingTargets = targets.filter((item) => existsSync(item.path));
if (!existingTargets.length) throw new Error("No local AIBI-C database files were found to migrate.");

const originalBefore = fileReceipts(existingTargets);
const compatibility = runHelper("inspect", existingTargets);
const incompatible = compatibility.databases.filter((item) => item.exists && !item.compatible);
if (incompatible.length) {
  throw new Error(`Local database is newer or invalid: ${incompatible.map((item) => `${item.kind}:v${item.version}`).join(", ")}`);
}

const previewRoot = mkdtempSync(join(tmpdir(), "aibi-c-schema-migration-"));
const previewFiles = existingTargets.map((item) => {
  const path = join(previewRoot, basename(item.path));
  copyFileSync(item.path, path);
  return { kind: item.kind, path };
});

let safetyBackup = null;
let applied = false;
let rolledBack = false;
try {
  const migration = runHelper("migrate", previewFiles);
  const previewReceipts = fileReceipts(previewFiles);
  const originalAfterPreview = fileReceipts(existingTargets);
  if (!sameReceipts(originalBefore, originalAfterPreview)) {
    throw new Error("Original database changed during isolated migration preview.");
  }
  if (simulateFailure) throw new Error("Simulated migration failure before apply.");

  if (!confirmed) {
    console.log(JSON.stringify({
      ok: true,
      schema: "aibi-local-migration-receipt/v1",
      confirmed: false,
      originalUnchanged: true,
      compatibility,
      migration,
      previewReceipts,
      next: "Run again with --confirm after reviewing schema versions and restore requirements.",
    }, null, 2));
    process.exitCode = 0;
  } else {
    safetyBackup = createSafetyBackup(existingTargets, `pre-migration-${new Date().toISOString().replace(/[:.]/g, "-")}`);
    let validation = null;
    try {
      for (let index = 0; index < existingTargets.length; index += 1) {
        const target = existingTargets[index];
        const source = previewFiles.find((item) => item.kind === target.kind);
        mkdirSync(dirname(target.path), { recursive: true });
        copyFileSync(source.path, target.path);
        if (simulateApplyFailure && index === 0) throw new Error("Simulated migration failure during apply.");
      }
      applied = true;
      validation = runHelper("inspect", existingTargets);
      if (simulateValidationFailure) throw new Error("Simulated migration failure during final validation.");
      const invalid = validation.databases.filter((item) => item.exists && (!item.compatible || item.version !== item.currentVersion));
      if (invalid.length) throw new Error(`Post-migration validation failed for: ${invalid.map((item) => item.kind).join(", ")}`);
    } catch (error) {
      for (const target of existingTargets) {
        const backupFile = join(safetyBackup, basename(target.path));
        if (existsSync(backupFile)) copyFileSync(backupFile, target.path);
      }
      rolledBack = true;
      throw error;
    }
    console.log(JSON.stringify({
      ok: true,
      schema: "aibi-local-migration-receipt/v1",
      confirmed: true,
      applied,
      rolledBack,
      safetyBackup,
      restoreCommand: `npm run restore:local -- --from \"${safetyBackup}\" --confirm`,
      compatibility,
      migration,
      validation,
      before: originalBefore,
      after: fileReceipts(existingTargets),
    }, null, 2));
  }
} catch (error) {
  const originalAfterFailure = fileReceipts(existingTargets);
  console.error(JSON.stringify({
    ok: false,
    schema: "aibi-local-migration-receipt/v1",
    confirmed,
    applied,
    rolledBack,
    originalUnchanged: sameReceipts(originalBefore, originalAfterFailure),
    safetyBackup,
    restoreCommand: safetyBackup ? `npm run restore:local -- --from \"${safetyBackup}\" --confirm` : null,
    error: error instanceof Error ? error.message : String(error),
  }, null, 2));
  process.exitCode = 1;
} finally {
  rmSync(previewRoot, { recursive: true, force: true });
}
