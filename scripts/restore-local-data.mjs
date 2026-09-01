import { existsSync } from "node:fs";
import { resolve } from "node:path";
import {
  assertDisjointPath,
  assertLocalServiceStopped,
  backupRoot,
  datasetObjectRoot,
  localDataFiles,
  readManifest,
  snapshotPathsForManifest,
  validateLocalDataSnapshot,
  verifyManifestFiles,
  withMutationFence,
} from "./local-data-snapshot.mjs";
import {
  commitRestoreTransaction,
  createRestoreTransaction,
  recoverRestoreTransactions,
} from "./local-data-restore-transaction.mjs";

const values = process.argv.slice(2);
const args = new Set(values);
const fromIndex = values.indexOf("--from");
const sourceDirectory = fromIndex >= 0 && values[fromIndex + 1] ? resolve(values[fromIndex + 1]) : "";
if (!sourceDirectory) throw new Error("Use --from <backup-directory> to preview or restore a backup.");

const objectRoot = datasetObjectRoot();
assertDisjointPath(sourceDirectory, objectRoot, "Backup source and dataset object root");
assertDisjointPath(objectRoot, backupRoot(), "Dataset object root and persistent restore journal root");

let output;
await withMutationFence(async () => {
  await assertLocalServiceStopped();
  const recovered = await recoverRestoreTransactions();
  const manifest = await readManifest(sourceDirectory);
  const inventory = await verifyManifestFiles(sourceDirectory, manifest);
  const validation = validateLocalDataSnapshot(snapshotPathsForManifest(sourceDirectory, manifest));
  const objectEntries = manifest.files.filter((file) => file.kind === "dataset-object");
  const databases = new Map(localDataFiles().map((item) => [item.kind, resolve(item.path)]));
  const restorePlan = {
    sqlite: databases.get("sqlite"),
    duckdb: databases.get("duckdb"),
    datasetObjectRoot: objectRoot,
    datasetObjectCount: objectEntries.length,
    datasetObjectBytes: manifest.roots.datasetObjects.bytes,
  };

  if (!args.has("--confirm")) {
    output = {
      ok: true,
      confirmed: false,
      recoveredRestoreTransactions: recovered,
      manifest: {
        schema: manifest.schema,
        createdAt: manifest.createdAt,
        purpose: manifest.purpose,
        fileCount: manifest.files.length,
        datasetObjectCount: objectEntries.length,
        datasetObjectBytes: manifest.roots.datasetObjects.bytes,
      },
      inventory,
      validation,
      restorePlan,
      next: "Run again with --confirm after reviewing the target paths.",
    };
    return;
  }

  let transaction;
  try {
    transaction = await createRestoreTransaction(sourceDirectory, manifest);
    await commitRestoreTransaction(transaction.journal);
  } catch (error) {
    await recoverRestoreTransactions();
    throw error;
  }
  output = {
    ok: true,
    confirmed: true,
    recoveredRestoreTransactions: recovered,
    transaction: {
      transactionId: transaction.journal.transactionId,
      journal: resolve(transaction.journal.transactionDirectory, "restore-journal.json"),
      phase: transaction.journal.phase,
      installMode: transaction.journal.installMode,
      recoveredFromInstallError: transaction.journal.recoveredFromInstallError === true,
      installWarning: transaction.journal.installWarning ?? null,
      installWarningPersisted: transaction.journal.installWarningPersisted ?? null,
      cleanupPending: transaction.journal.cleanupPending === true,
      cleanupWarning: transaction.journal.cleanupWarning ?? null,
    },
    safetyBackup: {
      directory: transaction.journal.safetyDirectory,
      retained: existsSync(transaction.journal.safetyDirectory),
      manifest: transaction.safetyManifest,
    },
    restored: transaction.journal.components.map((item) => ({ kind: item.kind, target: item.target })),
    validation,
  };
}, { timeoutMs: Number(process.env.AIBI_LOCAL_DATA_LOCK_TIMEOUT_MS ?? 60_000) });

console.log(JSON.stringify(output, null, 2));
