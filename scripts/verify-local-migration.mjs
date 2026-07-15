import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";

const root = resolve(import.meta.dirname, "..");
const verifyRoot = mkdtempSync(join(tmpdir(), "aibi-c-migration-verify-"));
const sqlitePath = join(verifyRoot, "legacy-aibi-c.sqlite");
const duckdbPath = join(verifyRoot, "legacy-aibi-c.duckdb");
const env = {
  ...process.env,
  AIBI_API_PORT: "65529",
  AIBI_BACKUP_ROOT: join(verifyRoot, "backups"),
  AIBI_HYBRID_DB_PATH: sqlitePath,
  AIBI_HYBRID_DUCKDB_PATH: duckdbPath,
};
const checks = [];

function hash(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function run(command, args = [], options = {}) {
  return spawnSync(command, args, { cwd: root, env, encoding: "utf8", ...options });
}

function fixture(command) {
  return run(process.env.PYTHON ?? "python", [
    "scripts/legacy-aibi-c-migration-fixture.py",
    command,
    "--sqlite", sqlitePath,
    "--duckdb", duckdbPath,
  ]);
}

function migration(...args) {
  return run(process.execPath, ["scripts/migrate-local-data.mjs", ...args]);
}

function parseJson(text) {
  try {
    return JSON.parse(text || "{}");
  } catch {
    return {};
  }
}

function add(label, ok, detail = "") {
  checks.push({ label, ok: Boolean(ok), detail: ok ? "" : detail });
}

try {
  const created = fixture("legacy");
  add("legacy-aibi-c-fixture-created", created.status === 0, created.stderr || created.stdout);
  const beforePreview = { sqlite: hash(sqlitePath), duckdb: hash(duckdbPath) };

  const preview = migration();
  const previewPayload = parseJson(preview.stdout);
  add(
    "migration-preview-uses-isolated-copy",
    preview.status === 0 && previewPayload.confirmed === false && previewPayload.originalUnchanged === true,
    preview.stderr || preview.stdout,
  );
  add(
    "preview-does-not-change-original",
    hash(sqlitePath) === beforePreview.sqlite && hash(duckdbPath) === beforePreview.duckdb,
    { beforePreview },
  );

  const simulated = migration("--simulate-failure");
  const simulatedPayload = parseJson(simulated.stderr);
  add(
    "pre-apply-failure-keeps-original",
    simulated.status !== 0 && simulatedPayload.originalUnchanged === true && hash(sqlitePath) === beforePreview.sqlite && hash(duckdbPath) === beforePreview.duckdb,
    simulated.stderr || simulated.stdout,
  );

  const confirmed = migration("--confirm");
  const confirmedPayload = parseJson(confirmed.stdout);
  const inspected = fixture("inspect");
  const inspectedPayload = parseJson(inspected.stdout);
  add(
    "confirmed-migration-creates-restore-point",
    confirmed.status === 0 && confirmedPayload.confirmed === true && existsSync(confirmedPayload.safetyBackup) && confirmedPayload.restoreCommand?.includes("restore:local"),
    confirmed.stderr || confirmed.stdout,
  );
  add(
    "sqlite-and-duckdb-reach-current-version",
    inspected.status === 0 && inspectedPayload.sqliteVersion === 7 && inspectedPayload.duckdbVersion === 1,
    inspected.stderr || inspected.stdout,
  );
  add(
    "legacy-aibi-c-data-preserved",
    inspectedPayload.sqliteRow?.join(":") === "AIBI-C:preserve-me" && inspectedPayload.duckdbRow?.join(":") === "AIBI-C:preserve-me",
    inspectedPayload,
  );
  add(
    "v1-connectors-migrate-to-workspace-scoped-composite-key",
    inspectedPayload.connectorRow?.join(":") === "workspace-red:legacy-file:Legacy file connector"
      && inspectedPayload.connectorPrimaryKey?.join(":") === "workspace_id:connector_key",
    inspectedPayload,
  );

  rmSync(sqlitePath, { force: true });
  rmSync(duckdbPath, { force: true });
  fixture("legacy");
  const beforeApplyFailure = { sqlite: hash(sqlitePath), duckdb: hash(duckdbPath) };
  const applyFailure = migration("--confirm", "--simulate-apply-failure");
  const applyFailurePayload = parseJson(applyFailure.stderr);
  add(
    "apply-failure-rolls-back-both-databases",
    applyFailure.status !== 0 && applyFailurePayload.rolledBack === true && applyFailurePayload.originalUnchanged === true && hash(sqlitePath) === beforeApplyFailure.sqlite && hash(duckdbPath) === beforeApplyFailure.duckdb,
    applyFailure.stderr || applyFailure.stdout,
  );

  rmSync(sqlitePath, { force: true });
  rmSync(duckdbPath, { force: true });
  fixture("legacy");
  const beforeValidationFailure = { sqlite: hash(sqlitePath), duckdb: hash(duckdbPath) };
  const validationFailure = migration("--confirm", "--simulate-validation-failure");
  const validationFailurePayload = parseJson(validationFailure.stderr);
  add(
    "final-validation-failure-rolls-back-both-databases",
    validationFailure.status !== 0 && validationFailurePayload.rolledBack === true && validationFailurePayload.originalUnchanged === true && hash(sqlitePath) === beforeValidationFailure.sqlite && hash(duckdbPath) === beforeValidationFailure.duckdb,
    validationFailure.stderr || validationFailure.stdout,
  );

  rmSync(sqlitePath, { force: true });
  rmSync(duckdbPath, { force: true });
  fixture("future");
  const futureBefore = { sqlite: hash(sqlitePath), duckdb: hash(duckdbPath) };
  const future = migration();
  add(
    "future-schema-is-read-only-blocked",
    future.status !== 0 && hash(sqlitePath) === futureBefore.sqlite && hash(duckdbPath) === futureBefore.duckdb,
    future.stderr || future.stdout,
  );
  const futureCli = run(process.env.PYTHON ?? "python", ["tools/bi_cli.py", "--json", "workspace-list"]);
  add(
    "future-schema-blocks-runtime-startup-without-writing",
    futureCli.status !== 0 && hash(sqlitePath) === futureBefore.sqlite && hash(duckdbPath) === futureBefore.duckdb,
    futureCli.stderr || futureCli.stdout,
  );
} finally {
  rmSync(verifyRoot, { recursive: true, force: true });
}

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-local-migration-verify/v1",
  generatedBy: "scripts/verify-local-migration.mjs",
  checks,
  failedChecks,
}, null, 2));
process.exit(failedChecks.length ? 1 : 0);
