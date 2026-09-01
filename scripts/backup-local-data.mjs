import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, renameSync, rmSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import {
  assertBackupFilesComplete,
  assertDisjointPath,
  assertLocalServiceStopped,
  backupRoot,
  createBackupManifest,
  currentSnapshot,
  datasetObjectRoot,
  localDataFiles,
  materializeDatabaseSnapshot,
  snapshotPathsForManifest,
  timestamp,
  validateLocalDataSnapshot,
  verifyManifestFiles,
  withMutationFence,
} from "./local-data-snapshot.mjs";
import { recoverRestoreTransactions } from "./local-data-restore-transaction.mjs";

const args = process.argv.slice(2);
const outputIndex = args.indexOf("--output");
const outputDirectory = outputIndex >= 0 && args[outputIndex + 1]
  ? resolve(args[outputIndex + 1])
  : resolve(backupRoot(), `aibi-${timestamp()}`);
const objectRoot = datasetObjectRoot();

assertDisjointPath(outputDirectory, objectRoot, "Backup output and dataset object root");
assertDisjointPath(outputDirectory, resolve(backupRoot(), "restore-transactions"), "Backup output and restore transaction journal root");
if (existsSync(outputDirectory)) throw new Error(`Backup output directory already exists: ${outputDirectory}`);

const stagingDirectory = resolve(dirname(outputDirectory), `.${basename(outputDirectory)}.${randomUUID()}.snapshot.tmp`);
let manifest;
let validation;
let recoveredRestoreTransactions = [];
try {
  await withMutationFence(async () => {
    await assertLocalServiceStopped();
    recoveredRestoreTransactions = await recoverRestoreTransactions();
    const databases = localDataFiles();
    if (databases.some((item) => !existsSync(item.path))) {
      throw new Error("Both clean v2 local databases are required; refusing an incomplete backup.");
    }
    const sqlite = databases.find((item) => item.kind === "sqlite");
    const duckdb = databases.find((item) => item.kind === "duckdb");
    if (!sqlite || !duckdb) throw new Error("Clean v2 database paths are incomplete.");
    validateLocalDataSnapshot({
      sqlitePath: sqlite.path,
      duckdbPath: duckdb.path,
      objectRoot,
      expectedPathRoot: objectRoot,
    });

    mkdirSync(stagingDirectory, { recursive: true });
    const databaseScratch = join(stagingDirectory, ".database-snapshot");
    mkdirSync(databaseScratch, { recursive: true });
    const sqliteSnapshot = join(databaseScratch, basename(sqlite.path));
    const duckdbSnapshot = join(databaseScratch, basename(duckdb.path));
    materializeDatabaseSnapshot({
      sqlitePath: sqlite.path,
      duckdbPath: duckdb.path,
      sqliteTarget: sqliteSnapshot,
      duckdbTarget: duckdbSnapshot,
    });
    const entries = currentSnapshot().map((entry) => {
      if (entry.kind === "sqlite") return { ...entry, sourcePath: sqliteSnapshot };
      if (entry.kind === "duckdb") return { ...entry, sourcePath: duckdbSnapshot };
      return entry;
    });
    assertBackupFilesComplete(entries);
    manifest = await createBackupManifest(stagingDirectory, entries, "local-data-backup");
    rmSync(databaseScratch, { recursive: true, force: true });
    await verifyManifestFiles(stagingDirectory, manifest);
    const snapshot = snapshotPathsForManifest(stagingDirectory, manifest);
    validation = validateLocalDataSnapshot({ ...snapshot, expectedPathRoot: objectRoot });
    renameSync(stagingDirectory, outputDirectory);
  }, { timeoutMs: Number(process.env.AIBI_LOCAL_DATA_LOCK_TIMEOUT_MS ?? 60_000) });
} catch (error) {
  rmSync(stagingDirectory, { recursive: true, force: true });
  throw error;
}

console.log(JSON.stringify({
  ok: true,
  outputDirectory,
  consistency: {
    mutationFence: "exclusive-cross-process",
    sqliteSnapshot: "sqlite-backup-api",
    duckdbSnapshot: "closed-writer-copy",
    validation,
    recoveredRestoreTransactions,
  },
  manifest,
}, null, 2));
