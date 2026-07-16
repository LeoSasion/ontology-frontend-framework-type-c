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
    inspected.status === 0 && inspectedPayload.sqliteVersion === 12 && inspectedPayload.duckdbVersion === 1,
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
  add(
    "v8-semantic-review-tables-and-indexes-are-created",
    inspectedPayload.semanticReviewTables?.join(":") === "knowledge_sources:semantic_patch_proposals"
      && inspectedPayload.semanticReviewIndexes?.join(":") === "idx_semantic_patch_workspace_source:idx_semantic_patch_workspace_status",
    inspectedPayload,
  );
  add(
    "v9-plan-memory-tables-and-indexes-are-created",
    inspectedPayload.planMemoryTables?.join(":") === "confirmed_plan_memories:recall_receipts"
      && inspectedPayload.planMemoryIndexes?.join(":") === "idx_confirmed_plan_workspace_query:idx_confirmed_plan_workspace_status:idx_recall_receipts_workspace_created",
    inspectedPayload,
  );
  add(
    "v10-plan-quality-table-and-index-are-created",
    inspectedPayload.planQualityTables?.join(":") === "plan_quality_scorecards"
      && inspectedPayload.planQualityIndexes?.join(":") === "idx_plan_quality_scorecards_workspace_created",
    inspectedPayload,
  );
  add(
    "v11-exploration-thread-tables-and-indexes-are-created",
    inspectedPayload.explorationTables?.join(":") === "exploration_anchors:exploration_board_items:exploration_threads"
      && inspectedPayload.explorationIndexes?.join(":") === "idx_exploration_anchors_thread_created:idx_exploration_board_thread_position:idx_exploration_threads_workspace_updated",
    inspectedPayload,
  );
  add(
    "v12-limited-research-tables-and-indexes-are-created",
    inspectedPayload.researchTables?.join(":") === "research_observations:research_plan_revisions:research_run_events:research_runs"
      && inspectedPayload.researchIndexes?.join(":") === "idx_research_events_run_sequence:idx_research_observations_run_created:idx_research_revisions_run_number:idx_research_runs_workspace_updated",
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
