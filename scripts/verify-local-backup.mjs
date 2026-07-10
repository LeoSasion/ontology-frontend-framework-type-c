import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-backup-verify-"));
const sqlitePath = join(verifyDir, "runtime.sqlite");
const duckdbPath = join(verifyDir, "runtime.duckdb");
const backupPath = join(verifyDir, "backup");
const originalSqlite = "sqlite-production-backup-check";
const originalDuckdb = "duckdb-production-backup-check";
const env = { ...process.env, AIBI_API_PORT: "65530", AIBI_BACKUP_ROOT: join(verifyDir, "safety"), AIBI_HYBRID_DB_PATH: sqlitePath, AIBI_HYBRID_DUCKDB_PATH: duckdbPath };

function run(script, args) {
  return spawnSync(process.execPath, [script, ...args], { cwd: process.cwd(), env, encoding: "utf8", windowsHide: true });
}

try {
  writeFileSync(sqlitePath, originalSqlite);
  writeFileSync(duckdbPath, originalDuckdb);
  const backup = run("scripts/backup-local-data.mjs", ["--output", backupPath]);
  writeFileSync(sqlitePath, "changed");
  writeFileSync(duckdbPath, "changed");
  const preview = run("scripts/restore-local-data.mjs", ["--from", backupPath]);
  const confirmed = run("scripts/restore-local-data.mjs", ["--from", backupPath, "--confirm"]);
  const checks = [
    { label: "backup-command", ok: backup.status === 0, detail: backup.status === 0 ? "backup completed" : backup.stderr || backup.stdout },
    { label: "restore-preview", ok: preview.status === 0 && preview.stdout.includes('"confirmed": false'), detail: preview.status === 0 ? "restore preview completed" : preview.stderr || preview.stdout },
    { label: "restore-confirmed", ok: confirmed.status === 0 && confirmed.stdout.includes('"confirmed": true'), detail: confirmed.status === 0 ? "confirmed restore completed" : confirmed.stderr || confirmed.stdout },
    { label: "sqlite-restored", ok: readFileSync(sqlitePath, "utf8") === originalSqlite },
    { label: "duckdb-restored", ok: readFileSync(duckdbPath, "utf8") === originalDuckdb },
  ];
  const failedChecks = checks.filter((item) => !item.ok);
  console.log(JSON.stringify({ ok: failedChecks.length === 0, schema: "aibi-local-backup-verify/v1", generatedBy: "scripts/verify-local-backup.mjs", checks, failedChecks }, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
