import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const verifyDir = mkdtempSync(join(tmpdir(), "aibi-relationship-workspace-"));
const databaseFile = join(verifyDir, "verify.sqlite");
const ordersFile = join(verifyDir, "orders.csv");
const refundsFile = join(verifyDir, "refunds.csv");
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: databaseFile,
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "verify.duckdb"),
  PYTHONIOENCODING: "utf-8",
};
const checks = [];

writeFileSync(ordersFile, "order_id,channel\nO1,web\nO2,store\n", "utf8");
writeFileSync(refundsFile, "order_id,refund_amount\nO1,10\nO2,5\n", "utf8");

function run(args) {
  const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], {
    cwd: root,
    encoding: "utf8",
    env,
    windowsHide: true,
  });
  let payload = null;
  try {
    payload = JSON.parse(result.stdout.trim());
  } catch {
    payload = null;
  }
  return { status: result.status, payload, stdout: result.stdout, stderr: result.stderr };
}

function check(label, ok, detail) {
  checks.push({ label, ok: Boolean(ok), detail: ok ? undefined : detail });
}

try {
  check("database-initializes", run(["status"]).status === 0);
  check("orders-import", run(["import-commit", ordersFile, "--table", "orders", "--mode", "create", "--yes"]).status === 0);
  check("refunds-import", run(["import-commit", refundsFile, "--table", "refunds", "--mode", "create", "--yes"]).status === 0);

  const otherWorkspace = run(["workspace-create", "--name", "Relationship Isolation", "--yes"]);
  check(
    "different-workspace-is-active",
    otherWorkspace.status === 0 && otherWorkspace.payload?.created?.id && otherWorkspace.payload.created.id !== "default",
    otherWorkspace,
  );

  const preview = run([
    "relationship-preview", "--workspace", "default",
    "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id",
  ]);
  check(
    "preview-stays-bound-to-request-workspace",
    preview.status === 0 && preview.payload?.workspaceId === "default" && preview.payload?.relationshipPreview?.metrics?.overlapKeys === 2,
    preview,
  );

  const saved = run([
    "relationship-save", "--workspace", "default",
    "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id", "--yes",
  ]);
  check(
    "save-stays-bound-to-request-workspace",
    saved.status === 0 && saved.payload?.workspaceId === "default" && saved.payload?.saved?.workspace_id === "default",
    saved,
  );

  const activeOtherRelationships = run(["list-relationships"]);
  check(
    "active-workspace-receives-no-cross-workspace-write",
    activeOtherRelationships.status === 0 && activeOtherRelationships.payload?.relationships?.length === 0,
    activeOtherRelationships,
  );

  run(["workspace-select", "default", "--yes"]);
  const defaultRelationships = run(["list-relationships"]);
  check(
    "requested-workspace-contains-saved-relationship",
    defaultRelationships.status === 0 && defaultRelationships.payload?.relationships?.some((item) => item.relation_key === "orders_refunds_order_id_order_id"),
    defaultRelationships,
  );
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-relationship-workspace-binding-verify/v1",
  generatedBy: "scripts/verify-relationship-workspace-binding.mjs",
  checks,
  failedChecks,
}, null, 2));
process.exit(failedChecks.length ? 1 : 0);
