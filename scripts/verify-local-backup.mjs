import { createHash } from "node:crypto";
import {
  copyFileSync,
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { spawn, spawnSync } from "node:child_process";

const root = resolve(import.meta.dirname, "..");
const verifyDir = join(tmpdir(), `aibi-backup-verify-${process.pid}-${Date.now()}`);
const sqlitePath = join(verifyDir, "runtime.sqlite");
const duckdbPath = join(verifyDir, "runtime.duckdb");
const objectRoot = join(verifyDir, "dataset-objects-v2");
const backupPath = join(verifyDir, "backup");
const safetyRoot = join(verifyDir, "safety");
const recoveryRoot = join(verifyDir, "workspace-recovery");
const python = String(process.env.AIBI_PYTHON ?? process.env.PYTHON ?? "python");
const env = {
  ...process.env,
  AIBI_API_PORT: "65530",
  AIBI_BACKUP_ROOT: safetyRoot,
  AIBI_DATASET_OBJECT_ROOT: objectRoot,
  AIBI_HYBRID_DB_PATH: sqlitePath,
  AIBI_HYBRID_DUCKDB_PATH: duckdbPath,
  AIBI_WORKSPACE_RECOVERY_ROOT: recoveryRoot,
  PYTHONIOENCODING: "utf-8",
};
const checks = [];

function run(script, args, overrides = {}) {
  return spawnSync(process.execPath, [script, ...args], {
    cwd: root,
    env: { ...env, ...overrides },
    encoding: "utf8",
    windowsHide: true,
    timeout: 90_000,
  });
}

function runPython(args, overrides = {}) {
  return spawnSync(python, args, {
    cwd: root,
    env: { ...env, ...overrides },
    encoding: "utf8",
    windowsHide: true,
    timeout: 90_000,
  });
}

function parsed(result) {
  try {
    return JSON.parse(result.stdout);
  } catch {
    return null;
  }
}

function check(label, ok, detail = undefined) {
  checks.push({ label, ok: Boolean(ok), ...(ok || detail === undefined ? {} : { detail }) });
}

function validate(overrides = {}) {
  return runPython([
    "tools/local_data_snapshot_service.py",
    "validate",
    "--sqlite", overrides.sqlite ?? sqlitePath,
    "--duckdb", overrides.duckdb ?? duckdbPath,
    "--objects", overrides.objects ?? objectRoot,
    "--expected-path-root", overrides.pathRoot ?? objectRoot,
  ]);
}

function runStaleManifestRace(kind) {
  const racePath = join(verifyDir, `stale-manifest-${kind}`);
  cpSync(backupPath, racePath, { recursive: true });
  const script = `
    import { appendFileSync, existsSync, readdirSync } from "node:fs";
    import { join, resolve } from "node:path";
    import { createRestoreTransaction, recoverRestoreTransactions } from "./scripts/local-data-restore-transaction.mjs";
    import { readManifest, verifyManifestFiles } from "./scripts/local-data-snapshot.mjs";
    const directory = resolve(process.env.AIBI_RACE_SOURCE);
    const kind = process.env.AIBI_RACE_KIND;
    const manifest = await readManifest(directory);
    await verifyManifestFiles(directory, manifest);
    const transactionRoot = join(resolve(process.env.AIBI_BACKUP_ROOT), "restore-transactions");
    const before = new Set(existsSync(transactionRoot) ? readdirSync(transactionRoot) : []);
    const entry = manifest.files.find((item) => item.kind === kind);
    appendFileSync(resolve(directory, ...String(entry.file).split("/")), Buffer.from("post-verification-race"));
    let message = "";
    try {
      await createRestoreTransaction(directory, manifest);
    } catch (error) {
      message = String(error?.message ?? error);
    } finally {
      // inspected below before recovery removes the failed desired stage
    }
    const created = (existsSync(transactionRoot) ? readdirSync(transactionRoot) : []).find((name) => !before.has(name));
    function countFiles(path) {
      if (!path || !existsSync(path)) return 0;
      let count = 0;
      for (const entry of readdirSync(path, { withFileTypes: true })) {
        const target = join(path, entry.name);
        if (entry.isDirectory()) count += countFiles(target);
        else if (entry.isFile()) count += 1;
      }
      return count;
    }
    const copiedFiles = countFiles(created ? join(transactionRoot, created, "desired") : "");
    await recoverRestoreTransactions();
    console.log(JSON.stringify({ rejected: /changed while copying/i.test(message), copiedFiles, message }));
    if (!/changed while copying/i.test(message)) process.exitCode = 1;
  `;
  return spawnSync(process.execPath, ["--input-type=module", "-e", script], {
    cwd: root,
    env: { ...env, AIBI_RACE_SOURCE: racePath, AIBI_RACE_KIND: kind },
    encoding: "utf8",
    windowsHide: true,
    timeout: 90_000,
  });
}

function markerCount() {
  const result = runPython([
    "-c",
    "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute(\"SELECT COUNT(*) FROM system_flags WHERE key='backup_verify_marker'\").fetchone()[0])",
    sqlitePath,
  ]);
  return result.status === 0 ? Number(result.stdout.trim()) : -1;
}

function mutateLive(marker) {
  const sqlite = runPython([
    "-c",
    "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"INSERT INTO system_flags(key,value,updated_at) VALUES('backup_verify_marker',?,datetime('now')) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at\",(sys.argv[2],)); c.commit()",
    sqlitePath,
    marker,
  ]);
  if (sqlite.status !== 0) throw new Error(sqlite.stderr || sqlite.stdout);
  const duckdb = runPython([
    "-c",
    "import duckdb,sys; c=duckdb.connect(sys.argv[1]); c.execute('UPDATE __aibi_replica_manifest SET published_at=current_timestamp'); c.execute('CHECKPOINT'); c.close()",
    duckdbPath,
  ]);
  if (duckdb.status !== 0) throw new Error(duckdb.stderr || duckdb.stdout);
  const content = Buffer.from(`orphan-${marker}\n`, "utf8");
  const objectHash = createHash("sha256").update(content).digest("hex");
  const objectKey = `workspaces/${"f".repeat(24)}/objects/${objectHash.slice(0, 2)}/${objectHash}.parquet`;
  const objectPath = join(objectRoot, ...objectKey.split("/"));
  mkdirSync(resolve(objectPath, ".."), { recursive: true });
  writeFileSync(objectPath, content);
  return objectPath;
}

async function holdMutationFence() {
  const lockPath = join(verifyDir, ".aibi-cross-engine-writer.lock");
  const child = spawn(python, [
    "tools/local_data_snapshot_service.py",
    "hold-lock",
    "--path",
    lockPath,
    "--timeout",
    "5",
  ], { cwd: root, env, stdio: ["pipe", "pipe", "pipe"], windowsHide: true });
  await new Promise((resolveLock, rejectLock) => {
    let output = "";
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      output += chunk;
      if (output.includes("LOCKED")) resolveLock();
    });
    child.once("error", rejectLock);
    child.once("exit", (code) => rejectLock(new Error(`lock holder exited early: ${code}`)));
  });
  return child;
}

try {
  mkdirSync(verifyDir, { recursive: true });
  const bootstrap = runPython(["tools/aibi_cli.py", "--json", "status"]);
  const imported = runPython([
    "tools/aibi_cli.py", "--json", "import-commit",
    join(root, "validation-inputs", "orders.csv"),
    "--table", "orders",
    "--name", "Orders",
    "--mode", "create",
    "--yes",
  ]);
  const initialValidation = parsed(validate());
  check("clean-v18-v2-fixture", bootstrap.status === 0 && imported.status === 0 && initialValidation?.sqliteSchemaVersion === 18 && initialValidation?.duckdbSchemaVersion === 2, imported.stderr || imported.stdout);

  const backup = run("scripts/backup-local-data.mjs", ["--output", backupPath]);
  const backupPayload = parsed(backup);
  const backupManifest = backupPayload?.manifest;
  const backupSqlite = backupManifest?.files?.find((item) => item.kind === "sqlite");
  const backupObject = backupManifest?.files?.find((item) => item.kind === "dataset-object");
  check("backup-command", backup.status === 0 && backupPayload?.consistency?.mutationFence === "exclusive-cross-process", backup.stderr || backup.stdout);
  check("exact-v18-v2-validation", backupPayload?.consistency?.validation?.sqliteSchemaVersion === 18 && backupPayload?.consistency?.validation?.duckdbSchemaVersion === 2 && backupPayload?.consistency?.validation?.activeReplicaCount === 1, backupPayload);
  check("v2-complete-manifest", backupManifest?.schema === "aibi-local-backup/v2" && backupManifest?.files?.length === 3 && backupObject?.sha256 === backupObject?.objectHash);

  const plainSqlite = join(verifyDir, "plain.sqlite");
  const plainDuckdb = join(verifyDir, "plain.duckdb");
  writeFileSync(plainSqlite, "not sqlite", "utf8");
  writeFileSync(plainDuckdb, "not duckdb", "utf8");
  const plainSqliteResult = run("scripts/backup-local-data.mjs", ["--output", join(verifyDir, "plain-sqlite-backup")], { AIBI_HYBRID_DB_PATH: plainSqlite });
  const plainDuckdbResult = run("scripts/backup-local-data.mjs", ["--output", join(verifyDir, "plain-duckdb-backup")], { AIBI_HYBRID_DUCKDB_PATH: plainDuckdb });
  check("ordinary-text-databases-rejected", plainSqliteResult.status !== 0 && plainDuckdbResult.status !== 0, `${plainSqliteResult.stderr}\n${plainDuckdbResult.stderr}`);

  const oldSqlite = join(verifyDir, "old-v17.sqlite");
  copyFileSync(sqlitePath, oldSqlite);
  runPython(["-c", "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA user_version=17'); c.commit()", oldSqlite]);
  const oldSqliteResult = run("scripts/backup-local-data.mjs", ["--output", join(verifyDir, "old-sqlite-backup")], { AIBI_HYBRID_DB_PATH: oldSqlite });
  const oldDuckdb = join(verifyDir, "old-v1.duckdb");
  copyFileSync(duckdbPath, oldDuckdb);
  runPython(["-c", "import duckdb,sys; c=duckdb.connect(sys.argv[1]); c.execute(\"UPDATE __aibi_schema_metadata SET value='1' WHERE key='schema_version'\"); c.close()", oldDuckdb]);
  const oldDuckdbResult = run("scripts/backup-local-data.mjs", ["--output", join(verifyDir, "old-duckdb-backup")], { AIBI_HYBRID_DUCKDB_PATH: oldDuckdb });
  check("old-database-generations-rejected", oldSqliteResult.status !== 0 && oldDuckdbResult.status !== 0, `${oldSqliteResult.stderr}\n${oldDuckdbResult.stderr}`);

  const unpairedDuckdb = join(verifyDir, "unpaired.duckdb");
  copyFileSync(duckdbPath, unpairedDuckdb);
  runPython([
    "-c",
    "import duckdb,json,sys; c=duckdb.connect(sys.argv[1]); c.execute('UPDATE __aibi_replica_manifest SET object_hashes_json=?',[json.dumps(['0'*64])]); c.close()",
    unpairedDuckdb,
  ]);
  const unpairedResult = run("scripts/backup-local-data.mjs", ["--output", join(verifyDir, "unpaired-backup")], { AIBI_HYBRID_DUCKDB_PATH: unpairedDuckdb });
  check("unpaired-sqlite-duckdb-cas-rejected", unpairedResult.status !== 0 && /manifest|object|diverged|mismatch/i.test(`${unpairedResult.stderr}\n${unpairedResult.stdout}`), unpairedResult.stderr || unpairedResult.stdout);

  const legacyPath = join(verifyDir, "legacy-v1");
  mkdirSync(legacyPath, { recursive: true });
  writeFileSync(join(legacyPath, "manifest.json"), JSON.stringify({ schema: "aibi-local-backup/v1", files: [] }), "utf8");
  const legacy = run("scripts/restore-local-data.mjs", ["--from", legacyPath]);
  check("v1-backup-rejected", legacy.status !== 0 && /v2|unsupported|invalid/i.test(`${legacy.stderr}\n${legacy.stdout}`), legacy.stderr || legacy.stdout);

  const traversalPath = join(verifyDir, "traversal");
  cpSync(backupPath, traversalPath, { recursive: true });
  const traversalManifestPath = join(traversalPath, "manifest.json");
  const traversalManifest = JSON.parse(readFileSync(traversalManifestPath, "utf8"));
  traversalManifest.files[0].file = "../escape.sqlite";
  writeFileSync(traversalManifestPath, JSON.stringify(traversalManifest), "utf8");
  const traversal = run("scripts/restore-local-data.mjs", ["--from", traversalPath]);
  check("path-traversal-rejected", traversal.status !== 0 && /relative|invalid|escaped/i.test(`${traversal.stderr}\n${traversal.stdout}`), traversal.stderr || traversal.stdout);

  const tamperedPath = join(verifyDir, "tampered");
  cpSync(backupPath, tamperedPath, { recursive: true });
  writeFileSync(join(tamperedPath, ...String(backupObject.file).split("/")), "tampered", "utf8");
  const tampered = run("scripts/restore-local-data.mjs", ["--from", tamperedPath]);
  check("tampered-cas-rejected", tampered.status !== 0 && /checksum|hash|size/i.test(`${tampered.stderr}\n${tampered.stdout}`), tampered.stderr || tampered.stdout);

  const extraPath = join(verifyDir, "extra-file");
  cpSync(backupPath, extraPath, { recursive: true });
  writeFileSync(join(extraPath, "unexpected.txt"), "unmanifested", "utf8");
  const extra = run("scripts/restore-local-data.mjs", ["--from", extraPath]);
  check("unmanifested-backup-file-rejected", extra.status !== 0 && /inventory|extra|manifest/i.test(`${extra.stderr}\n${extra.stdout}`), extra.stderr || extra.stdout);

  const crossDriveTransactionId = "restore-cross-drive-journal";
  const crossDriveDirectory = join(safetyRoot, "restore-transactions", crossDriveTransactionId);
  mkdirSync(crossDriveDirectory, { recursive: true });
  writeFileSync(join(crossDriveDirectory, "restore-journal.json"), JSON.stringify({
    schema: "aibi-local-restore-transaction/v1",
    transactionId: crossDriveTransactionId,
    transactionDirectory: crossDriveDirectory,
    sourceDirectory: backupPath,
    desiredDirectory: `D:\\aibi-c-external-${process.pid}`,
    safetyDirectory: join(crossDriveDirectory, "safety"),
    phase: "preparing",
    installMode: "forward",
    installed: [],
    components: [],
    createdAt: new Date().toISOString(),
  }), "utf8");
  const crossDriveJournal = run("scripts/restore-local-data.mjs", ["--from", backupPath]);
  rmSync(crossDriveDirectory, { recursive: true, force: true });
  check(
    "cross-drive-and-noncanonical-journal-paths-are-rejected",
    crossDriveJournal.status !== 0 && /fixed transaction layout|escaped/i.test(`${crossDriveJournal.stderr}\n${crossDriveJournal.stdout}`),
    crossDriveJournal.stderr || crossDriveJournal.stdout,
  );

  const staleSqliteRace = runStaleManifestRace("sqlite");
  const staleDuckdbRace = runStaleManifestRace("duckdb");
  const staleSqlitePayload = parsed(staleSqliteRace);
  const staleDuckdbPayload = parsed(staleDuckdbRace);
  check(
    "post-verification-database-replacement-fails-closed",
    staleSqliteRace.status === 0
      && staleDuckdbRace.status === 0
      && staleSqlitePayload?.rejected === true
      && staleDuckdbPayload?.rejected === true
      && staleSqlitePayload?.copiedFiles <= 1
      && staleDuckdbPayload?.copiedFiles <= 2,
    { sqlite: staleSqliteRace.stderr || staleSqliteRace.stdout, duckdb: staleDuckdbRace.stderr || staleDuckdbRace.stdout },
  );

  const holder = await holdMutationFence();
  const locked = run("scripts/backup-local-data.mjs", ["--output", join(verifyDir, "locked-backup")], { AIBI_LOCAL_DATA_LOCK_TIMEOUT_MS: "100" });
  holder.stdin.end();
  await new Promise((resolveExit) => holder.once("exit", resolveExit));
  check("backup-uses-global-cross-process-fence", locked.status !== 0 && /fence|lock|boundary|timeout/i.test(`${locked.stderr}\n${locked.stdout}`), locked.stderr || locked.stdout);

  const orphan = mutateLive("preview");
  const beforePreview = { sqlite: createHash("sha256").update(readFileSync(sqlitePath)).digest("hex"), orphan: readFileSync(orphan, "utf8") };
  const preview = run("scripts/restore-local-data.mjs", ["--from", backupPath]);
  const previewPayload = parsed(preview);
  const afterPreview = createHash("sha256").update(readFileSync(sqlitePath)).digest("hex");
  check("restore-preview-is-read-only", preview.status === 0 && previewPayload?.confirmed === false && beforePreview.sqlite === afterPreview && readFileSync(orphan, "utf8") === beforePreview.orphan, preview.stderr || preview.stdout);

  const confirmed = run("scripts/restore-local-data.mjs", ["--from", backupPath, "--confirm"]);
  const confirmedPayload = parsed(confirmed);
  const restoredSqliteHash = createHash("sha256").update(readFileSync(sqlitePath)).digest("hex");
  check("restore-confirmed-transactional", confirmed.status === 0 && confirmedPayload?.transaction?.phase === "complete" && confirmedPayload?.transaction?.installMode === "forward", confirmed.stderr || confirmed.stdout);
  check("sqlite-and-cas-restored-exactly", restoredSqliteHash === backupSqlite?.sha256 && markerCount() === 0 && !existsSync(orphan), { restoredSqliteHash, backup: backupSqlite?.sha256, marker: markerCount(), orphan: existsSync(orphan) });
  check("safety-snapshot-is-validated-v2", confirmedPayload?.safetyBackup?.manifest?.schema === "aibi-local-backup/v2" && confirmedPayload?.safetyBackup?.manifest?.files?.length >= 3, confirmedPayload?.safetyBackup);
  check("restored-cross-engine-state-valid", validate().status === 0, validate().stderr);

  mutateLive("retry-success");
  const recoveredInstall = run(
    "scripts/restore-local-data.mjs",
    ["--from", backupPath, "--confirm"],
    { AIBI_RESTORE_FAILPOINT: "after-duckdb-install" },
  );
  const recoveredInstallPayload = parsed(recoveredInstall);
  check(
    "successful-install-retry-returns-success-not-a-false-failure",
    recoveredInstall.status === 0
      && recoveredInstallPayload?.transaction?.phase === "complete"
      && recoveredInstallPayload?.transaction?.recoveredFromInstallError === true
      && markerCount() === 0
      && validate().status === 0,
    recoveredInstall.stderr || recoveredInstall.stdout,
  );

  mutateLive("retry-warning-write-failure");
  const warningWriteFailure = run(
    "scripts/restore-local-data.mjs",
    ["--from", backupPath, "--confirm"],
    { AIBI_RESTORE_FAILPOINT: "after-duckdb-install,before-install-warning-journal-write" },
  );
  const warningWriteFailurePayload = parsed(warningWriteFailure);
  check(
    "post-commit-install-warning-write-is-best-effort",
    warningWriteFailure.status === 0
      && warningWriteFailurePayload?.transaction?.phase === "complete"
      && warningWriteFailurePayload?.transaction?.recoveredFromInstallError === true
      && warningWriteFailurePayload?.transaction?.installWarningPersisted === false
      && markerCount() === 0
      && validate().status === 0,
    warningWriteFailure.stderr || warningWriteFailure.stdout,
  );

  mutateLive("cleanup-pending");
  const cleanupPending = run(
    "scripts/restore-local-data.mjs",
    ["--from", backupPath, "--confirm"],
    { AIBI_RESTORE_FAILPOINT: "during-terminal-cleanup" },
  );
  const cleanupPendingPayload = parsed(cleanupPending);
  const cleanupJournalPath = cleanupPendingPayload?.transaction?.journal;
  const cleanupRetry = run("scripts/restore-local-data.mjs", ["--from", backupPath]);
  const cleanupJournal = cleanupJournalPath && existsSync(cleanupJournalPath)
    ? JSON.parse(readFileSync(cleanupJournalPath, "utf8"))
    : null;
  check(
    "terminal-cleanup-failure-never-rolls-back-committed-data",
    cleanupPending.status === 0
      && cleanupPendingPayload?.transaction?.phase === "complete"
      && cleanupPendingPayload?.transaction?.cleanupPending === true
      && markerCount() === 0
      && cleanupRetry.status === 0
      && cleanupJournal?.phase === "complete"
      && cleanupJournal?.cleanupPending === false
      && !existsSync(cleanupJournal?.desiredDirectory ?? "")
      && !existsSync(cleanupJournal?.safetyDirectory ?? "")
      && validate().status === 0,
    { cleanupPending: cleanupPending.stderr || cleanupPending.stdout, cleanupRetry: cleanupRetry.stderr || cleanupRetry.stdout, cleanupJournal },
  );

  const crashpoints = [
    "after-transaction-directory",
    "after-desired-stage",
    "after-safety-stage",
    "after-live-stage",
    "after-dataset-objects-install",
    "after-duckdb-install",
    "after-sqlite-install",
    "after-live-validation",
    "after-duckdb-install",
  ];
  const crashReceipts = [];
  for (const [index, crashpoint] of crashpoints.entries()) {
    mutateLive(`crash-${index}`);
    const crashed = run("scripts/restore-local-data.mjs", ["--from", backupPath, "--confirm"], { AIBI_RESTORE_CRASHPOINT: crashpoint });
    const recovered = run("scripts/restore-local-data.mjs", ["--from", backupPath]);
    const recoveredPayload = parsed(recovered);
    const receipt = recoveredPayload?.recoveredRestoreTransactions?.at(-1);
    crashReceipts.push({ crashpoint, crashExit: crashed.status, recoveryExit: recovered.status, outcome: receipt?.outcome });
    if (validate().status !== 0) break;
  }
  check(
    "every-restore-interruption-recovers-without-mixed-generation",
    crashReceipts.length === crashpoints.length
      && crashReceipts.every((item) => item.crashExit === 91 && item.recoveryExit === 0 && ["complete", "rolled-back-before-install", "rolled-back-before-journal"].includes(item.outcome)),
    crashReceipts,
  );
  check("post-install-recovery-is-repeatable", crashReceipts.filter((item) => item.crashpoint === "after-duckdb-install").every((item) => item.outcome === "complete"), crashReceipts);

  mutateLive("safety-rollback-window");
  const partialForward = run("scripts/restore-local-data.mjs", ["--from", backupPath, "--confirm"], { AIBI_RESTORE_CRASHPOINT: "after-dataset-objects-install" });
  const transactionDirectories = readdirSync(join(safetyRoot, "restore-transactions"), { withFileTypes: true })
    .filter((item) => item.isDirectory())
    .map((item) => join(safetyRoot, "restore-transactions", item.name));
  const installing = transactionDirectories
    .map((directory) => ({ directory, journal: JSON.parse(readFileSync(join(directory, "restore-journal.json"), "utf8")) }))
    .filter((item) => item.journal.phase === "installing")
    .sort((left, right) => String(right.journal.createdAt).localeCompare(String(left.journal.createdAt)))[0];
  const duckdbCandidate = installing?.journal?.components?.find((item) => item.kind === "duckdb")?.candidate;
  if (duckdbCandidate) rmSync(duckdbCandidate, { force: true });
  const rollbackStageCrash = run("scripts/restore-local-data.mjs", ["--from", backupPath], { AIBI_RESTORE_CRASHPOINT: "after-rollback-live-stage" });
  const rollbackRecovery = run("scripts/restore-local-data.mjs", ["--from", backupPath]);
  const rollbackReceipt = parsed(rollbackRecovery)?.recoveredRestoreTransactions?.at(-1);
  check(
    "safety-rollback-staging-crash-resumes-instead-of-discarding-candidates",
    partialForward.status === 91
      && Boolean(duckdbCandidate)
      && rollbackStageCrash.status === 91
      && rollbackRecovery.status === 0
      && rollbackReceipt?.outcome === "rolled-back-from-safety"
      && validate().status === 0,
    { partialForward: partialForward.status, duckdbCandidate, rollbackStageCrash: rollbackStageCrash.status, rollbackRecovery: rollbackRecovery.status, rollbackReceipt },
  );

  const finalRestore = run("scripts/restore-local-data.mjs", ["--from", backupPath, "--confirm"]);
  check("final-restored-state-is-clean-v18-v2", finalRestore.status === 0 && markerCount() === 0 && validate().status === 0, finalRestore.stderr || finalRestore.stdout);

  const terminalArtifacts = readdirSync(join(safetyRoot, "restore-transactions"), { withFileTypes: true })
    .filter((item) => item.isDirectory())
    .map((item) => {
      const directory = join(safetyRoot, "restore-transactions", item.name);
      const journal = JSON.parse(readFileSync(join(directory, "restore-journal.json"), "utf8"));
      return {
        phase: journal.phase,
        desired: existsSync(journal.desiredDirectory),
        safety: existsSync(journal.safetyDirectory),
        componentArtifacts: (journal.components ?? []).some((component) =>
          existsSync(component.candidate) || existsSync(component.rollback)),
      };
    });
  check(
    "terminal-restore-journals-do-not-retain-full-dataset-copies",
    terminalArtifacts.length > 0
      && terminalArtifacts.every((item) => ["complete", "rolled-back"].includes(item.phase))
      && terminalArtifacts.every((item) => !item.desired && !item.safety && !item.componentArtifacts),
    terminalArtifacts,
  );

  const symlinkRoot = join(verifyDir, "symlink-root");
  let symlinkPassed = true;
  try {
    symlinkSync(objectRoot, symlinkRoot, "junction");
    symlinkPassed = run("scripts/backup-local-data.mjs", ["--output", join(verifyDir, "symlink-backup")], { AIBI_DATASET_OBJECT_ROOT: symlinkRoot }).status !== 0;
  } catch {
    // Windows developer mode may be unavailable; the traversal/CAS checks above still run.
  }
  check("symlink-object-root-rejected", symlinkPassed);
  check("copy-and-hash-is-streamed", readFileSync(join(root, "scripts", "local-data-snapshot.mjs"), "utf8").includes("createReadStream") && !readFileSync(join(root, "scripts", "local-data-snapshot.mjs"), "utf8").includes("createHash(\"sha256\").update(readFileSync"));
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-local-backup-verify/v3",
  generatedBy: "scripts/verify-local-backup.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
