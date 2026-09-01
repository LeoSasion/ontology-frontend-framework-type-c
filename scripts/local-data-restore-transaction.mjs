import { randomUUID } from "node:crypto";
import {
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
} from "node:fs";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import {
  BACKUP_SCHEMA,
  backupRoot,
  copyWithReceipt,
  createBackupManifest,
  currentSnapshot,
  datasetObjectRoot,
  localDataFiles,
  materializeDatabaseSnapshot,
  readJsonFile,
  readManifest,
  rebaseDuckdbSnapshot,
  sha256,
  snapshotPathsForManifest,
  timestamp,
  validateLocalDataSnapshot,
  verifyManifestFiles,
  writeAtomicJson,
} from "./local-data-snapshot.mjs";

const JOURNAL_SCHEMA = "aibi-local-restore-transaction/v1";
const TERMINAL_PHASES = new Set(["complete", "rolled-back"]);

function pathWithin(base, candidate) {
  const suffix = relative(resolve(base), resolve(candidate));
  return suffix === "" || (suffix !== ".." && !suffix.startsWith(`..${sep}`) && !isAbsolute(suffix));
}

function assertRegularPath(path, type, label) {
  const stats = lstatSync(path);
  if (stats.isSymbolicLink() || (type === "file" ? !stats.isFile() : !stats.isDirectory())) {
    throw new Error(`${label} must be a non-symlink ${type}: ${path}`);
  }
}

function transactionRoot() {
  return resolve(backupRoot(), "restore-transactions");
}

function journalPath(transactionDirectory) {
  return resolve(transactionDirectory, "restore-journal.json");
}

function writeJournal(journal) {
  journal.updatedAt = new Date().toISOString();
  writeAtomicJson(journalPath(journal.transactionDirectory), journal);
}

function validateJournal(journal, transactionDirectory) {
  if (
    journal?.schema !== JOURNAL_SCHEMA
    || journal.transactionId !== basename(transactionDirectory)
    || resolve(journal.transactionDirectory) !== resolve(transactionDirectory)
    || !pathWithin(transactionRoot(), transactionDirectory)
    || !["preparing", "prepared", "live-staged", "installing", "installed", "complete", "rolled-back"].includes(journal.phase)
  ) {
    throw new Error(`Restore journal is invalid: ${transactionDirectory}`);
  }
  const expectedDirectories = {
    desiredDirectory: resolve(transactionDirectory, "desired"),
    safetyDirectory: resolve(transactionDirectory, "safety"),
  };
  for (const [key, expected] of Object.entries(expectedDirectories)) {
    if (!pathWithin(transactionDirectory, journal[key]) || resolve(journal[key]) !== expected) {
      throw new Error(`Restore journal ${key} does not match its fixed transaction layout.`);
    }
  }
  const expectedComponents = new Map(componentPaths(journal.transactionId).map((item) => [item.kind, item]));
  if (Array.isArray(journal.components) && journal.components.length) {
    if (journal.components.length !== expectedComponents.size) throw new Error("Restore journal component set is incomplete.");
    for (const item of journal.components) {
      const expected = expectedComponents.get(item.kind);
      if (
        !expected
        || item.type !== expected.type
        || resolve(item.target) !== expected.target
        || resolve(item.candidate) !== expected.candidate
        || resolve(item.rollback) !== expected.rollback
      ) {
        throw new Error(`Restore journal component paths are invalid: ${item.kind}`);
      }
    }
  }
  return journal;
}

function interruptAt(label) {
  const crashpoints = new Set(String(process.env.AIBI_RESTORE_CRASHPOINT ?? "").split(",").map((item) => item.trim()).filter(Boolean));
  const failpoints = new Set(String(process.env.AIBI_RESTORE_FAILPOINT ?? "").split(",").map((item) => item.trim()).filter(Boolean));
  if (crashpoints.has(label)) process.exit(91);
  if (failpoints.has(label)) throw new Error(`Injected restore failure: ${label}`);
}

function manifestEntries(sourceDirectory, manifest) {
  return manifest.files.map((file) => ({
    kind: file.kind,
    file: file.file,
    objectKey: file.objectKey,
    objectHash: file.objectHash,
    sourcePath: resolve(sourceDirectory, ...String(file.file).split("/")),
  }));
}

function manifestEntryKey(file) {
  return JSON.stringify([file.kind, file.file, file.objectKey ?? null]);
}

function assertManifestMatchesExpected(actualManifest, expectedManifest, label) {
  const actual = new Map(actualManifest.files.map((file) => [manifestEntryKey(file), file]));
  if (actual.size !== expectedManifest.files.length || actualManifest.files.length !== expectedManifest.files.length) {
    throw new Error(`${label} changed its file inventory while copying.`);
  }
  for (const expected of expectedManifest.files) {
    const copied = actual.get(manifestEntryKey(expected));
    if (
      !copied
      || copied.bytes !== expected.bytes
      || copied.sha256 !== expected.sha256
      || (expected.kind === "dataset-object" && copied.objectHash !== expected.objectHash)
    ) {
      throw new Error(`${label} changed while copying: ${expected.file}`);
    }
  }
}

function assertReceiptMatchesExpected(receipt, expected, label) {
  if (receipt.bytes !== expected.bytes || receipt.sha256 !== expected.sha256) {
    throw new Error(`${label} changed while copying: ${expected.file}`);
  }
}

async function copySnapshot(sourceDirectory, sourceManifest, targetDirectory, purpose) {
  mkdirSync(targetDirectory, { recursive: true });
  const manifest = await createBackupManifest(
    targetDirectory,
    manifestEntries(sourceDirectory, sourceManifest),
    purpose,
    { expectedFiles: sourceManifest.files },
  );
  assertManifestMatchesExpected(manifest, sourceManifest, "Restore source snapshot");
  await verifyManifestFiles(targetDirectory, manifest);
  validateLocalDataSnapshot(snapshotPathsForManifest(targetDirectory, manifest));
  return manifest;
}

async function createSafetySnapshot(directory) {
  const databases = localDataFiles();
  const sqlite = databases.find((item) => item.kind === "sqlite");
  const duckdb = databases.find((item) => item.kind === "duckdb");
  if (!sqlite || !duckdb) throw new Error("Clean v2 local database paths are incomplete.");
  validateLocalDataSnapshot({
    sqlitePath: sqlite.path,
    duckdbPath: duckdb.path,
    objectRoot: datasetObjectRoot(),
    expectedPathRoot: datasetObjectRoot(),
  });
  mkdirSync(directory, { recursive: true });
  const scratch = join(directory, ".database-snapshot");
  mkdirSync(scratch, { recursive: true });
  const sqliteSnapshot = join(scratch, basename(sqlite.path));
  const duckdbSnapshot = join(scratch, basename(duckdb.path));
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
  const manifest = await createBackupManifest(directory, entries, "pre-restore-safety-copy");
  rmSync(scratch, { recursive: true, force: true });
  await verifyManifestFiles(directory, manifest);
  validateLocalDataSnapshot({
    ...snapshotPathsForManifest(directory, manifest),
    expectedPathRoot: datasetObjectRoot(),
  });
  return manifest;
}

function componentPaths(transactionId) {
  const databases = localDataFiles();
  const sqlite = databases.find((item) => item.kind === "sqlite");
  const duckdb = databases.find((item) => item.kind === "duckdb");
  if (!sqlite || !duckdb) throw new Error("Clean v2 local database paths are incomplete.");
  const objects = datasetObjectRoot();
  const component = (kind, target, type) => ({
    kind,
    type,
    target: resolve(target),
    candidate: resolve(dirname(target), `.${basename(target)}.${transactionId}.restore-stage`),
    rollback: resolve(dirname(target), `.${basename(target)}.${transactionId}.restore-rollback`),
  });
  return [
    component("dataset-objects", objects, "directory"),
    component("duckdb", duckdb.path, "file"),
    component("sqlite", sqlite.path, "file"),
  ];
}

async function stageCandidates(journal, snapshotDirectory, snapshotManifest, mode) {
  const components = componentPaths(journal.transactionId);
  for (const item of components) {
    rmSync(item.candidate, { recursive: true, force: true });
    rmSync(item.rollback, { recursive: true, force: true });
  }
  const objectComponent = components.find((item) => item.kind === "dataset-objects");
  const sqliteComponent = components.find((item) => item.kind === "sqlite");
  const duckdbComponent = components.find((item) => item.kind === "duckdb");
  mkdirSync(objectComponent.candidate, { recursive: true });
  for (const file of snapshotManifest.files.filter((item) => item.kind === "dataset-object")) {
    const source = resolve(snapshotDirectory, ...String(file.file).split("/"));
    const target = resolve(objectComponent.candidate, ...String(file.objectKey).split("/"));
    const receipt = await copyWithReceipt(source, target, "dataset-object", {
      file: file.objectKey,
      objectKey: file.objectKey,
      objectHash: file.objectHash,
    });
    if (receipt.bytes !== file.bytes || receipt.sha256 !== file.sha256) {
      throw new Error(`Restore CAS stage changed while copying: ${file.objectKey}`);
    }
  }
  const sqliteSource = snapshotManifest.files.find((item) => item.kind === "sqlite");
  const duckdbSource = snapshotManifest.files.find((item) => item.kind === "duckdb");
  const sqliteReceipt = await copyWithReceipt(
    resolve(snapshotDirectory, ...String(sqliteSource.file).split("/")),
    sqliteComponent.candidate,
    "sqlite",
  );
  assertReceiptMatchesExpected(sqliteReceipt, sqliteSource, "Restore SQLite source");
  const duckdbReceipt = await copyWithReceipt(
    resolve(snapshotDirectory, ...String(duckdbSource.file).split("/")),
    duckdbComponent.candidate,
    "duckdb",
  );
  assertReceiptMatchesExpected(duckdbReceipt, duckdbSource, "Restore DuckDB source");
  rebaseDuckdbSnapshot({
    duckdbPath: duckdbComponent.candidate,
    objectRoot: objectComponent.candidate,
    targetObjectRoot: objectComponent.target,
  });
  validateLocalDataSnapshot({
    sqlitePath: sqliteComponent.candidate,
    duckdbPath: duckdbComponent.candidate,
    objectRoot: objectComponent.candidate,
    expectedPathRoot: objectComponent.target,
  });
  sqliteComponent.expected = { bytes: statSync(sqliteComponent.candidate).size, sha256: await sha256(sqliteComponent.candidate) };
  duckdbComponent.expected = { bytes: statSync(duckdbComponent.candidate).size, sha256: await sha256(duckdbComponent.candidate) };
  objectComponent.expected = {
    objectCount: snapshotManifest.roots.datasetObjects.objectCount,
    bytes: snapshotManifest.roots.datasetObjects.bytes,
    objects: snapshotManifest.files.filter((item) => item.kind === "dataset-object").map((item) => ({
      objectKey: item.objectKey,
      bytes: item.bytes,
      sha256: item.sha256,
    })),
  };
  journal.components = components;
  journal.installMode = mode;
  journal.installed = [];
  journal.phase = "live-staged";
  writeJournal(journal);
  return components;
}

async function componentMatches(item) {
  if (!existsSync(item.target)) return false;
  assertRegularPath(item.target, item.type === "file" ? "file" : "directory", "Restore target");
  if (item.type === "file") {
    return statSync(item.target).size === item.expected.bytes && await sha256(item.target) === item.expected.sha256;
  }
  const expected = new Map(item.expected.objects.map((entry) => [entry.objectKey, entry]));
  let count = 0;
  let inventoryMismatch = false;
  function walk(path) {
    for (const entry of readdirSync(path, { withFileTypes: true })) {
      const entryPath = join(path, entry.name);
      if (entry.isSymbolicLink()) throw new Error(`Restore target CAS cannot contain symlinks: ${entryPath}`);
      if (entry.isDirectory()) walk(entryPath);
      else if (entry.isFile()) {
        const key = relative(item.target, entryPath).replaceAll("\\", "/");
        if (key === ".aibi-dataset-object.lock") return;
        if (!expected.has(key)) {
          inventoryMismatch = true;
          return;
        }
        count += 1;
      } else throw new Error(`Restore target CAS has an unsupported entry: ${entryPath}`);
    }
  }
  walk(item.target);
  if (inventoryMismatch || count !== expected.size) return false;
  for (const [key, entry] of expected) {
    const path = resolve(item.target, ...key.split("/"));
    if (!existsSync(path) || statSync(path).size !== entry.bytes || await sha256(path) !== entry.sha256) return false;
  }
  return true;
}

async function installComponents(journal, { allowInterrupts }) {
  journal.phase = "installing";
  writeJournal(journal);
  for (const item of journal.components) {
    if (!(await componentMatches(item))) {
      if (!existsSync(item.candidate)) throw new Error(`Restore candidate is unavailable: ${item.kind}`);
      if (existsSync(item.target) && !existsSync(item.rollback)) renameSync(item.target, item.rollback);
      if (existsSync(item.target)) rmSync(item.target, { recursive: true, force: true });
      renameSync(item.candidate, item.target);
      if (!(await componentMatches(item))) throw new Error(`Installed restore component failed verification: ${item.kind}`);
    } else {
      rmSync(item.candidate, { recursive: true, force: true });
    }
    if (!journal.installed.includes(item.kind)) journal.installed.push(item.kind);
    writeJournal(journal);
    if (allowInterrupts) interruptAt(`after-${item.kind}-install`);
  }
  journal.phase = "installed";
  writeJournal(journal);
  const objectComponent = journal.components.find((item) => item.kind === "dataset-objects");
  validateLocalDataSnapshot({
    sqlitePath: journal.components.find((item) => item.kind === "sqlite").target,
    duckdbPath: journal.components.find((item) => item.kind === "duckdb").target,
    objectRoot: objectComponent.target,
    expectedPathRoot: objectComponent.target,
  });
  if (allowInterrupts) interruptAt("after-live-validation");
  for (const item of journal.components) rmSync(item.rollback, { recursive: true, force: true });
  journal.phase = journal.installMode === "rollback" ? "rolled-back" : "complete";
  journal.finishedAt = new Date().toISOString();
  writeJournal(journal);
  cleanupTerminalArtifacts(journal);
}

function cleanupTerminalArtifacts(journal) {
  if (!TERMINAL_PHASES.has(journal.phase)) return;
  try {
    interruptAt("during-terminal-cleanup");
    for (const item of journal.components || []) {
      rmSync(item.candidate, { recursive: true, force: true });
      rmSync(item.rollback, { recursive: true, force: true });
    }
    rmSync(journal.desiredDirectory, { recursive: true, force: true });
    rmSync(journal.safetyDirectory, { recursive: true, force: true });
    journal.artifactsCleanedAt = new Date().toISOString();
    journal.cleanupPending = false;
    delete journal.cleanupWarning;
    writeJournal(journal);
  } catch {
    // The terminal journal is already durable and live data is committed (or
    // rolled back). Cleanup is maintenance only and must never reverse that
    // business outcome. Startup recovery retries it idempotently.
    journal.cleanupPending = true;
    journal.cleanupWarning = "Terminal restore artifacts could not be removed and will be retried.";
    try {
      writeJournal(journal);
    } catch {
      // Even the warning is best-effort; the durable terminal phase remains
      // sufficient for the next recovery scan to retry cleanup safely.
    }
  }
}

async function rollbackFromSafety(journal) {
  const safetyManifest = await readManifest(journal.safetyDirectory);
  await verifyManifestFiles(journal.safetyDirectory, safetyManifest);
  validateLocalDataSnapshot({
    ...snapshotPathsForManifest(journal.safetyDirectory, safetyManifest),
    expectedPathRoot: datasetObjectRoot(),
  });
  await stageCandidates(journal, journal.safetyDirectory, safetyManifest, "rollback");
  interruptAt("after-rollback-live-stage");
  await installComponents(journal, { allowInterrupts: false });
}

export async function recoverRestoreTransactions() {
  const root = transactionRoot();
  if (!existsSync(root)) return [];
  assertRegularPath(root, "directory", "Restore transaction root");
  const recovered = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.isSymbolicLink()) throw new Error(`Restore transaction root contains an unsupported entry: ${entry.name}`);
    const directory = resolve(root, entry.name);
    const journalFile = journalPath(directory);
    if (!existsSync(journalFile)) {
      const remnants = readdirSync(directory, { withFileTypes: true });
      const safePreJournalCrash = remnants.every((item) => item.isFile() && !item.isSymbolicLink() && /^\.restore-journal\.json\.[a-f0-9-]+\.tmp$/i.test(item.name));
      if (!safePreJournalCrash) throw new Error(`Restore transaction is missing its durable journal: ${directory}`);
      rmSync(directory, { recursive: true, force: true });
      recovered.push({ transactionId: entry.name, outcome: "rolled-back-before-journal" });
      continue;
    }
    const journal = validateJournal(readJsonFile(journalFile, "Restore journal"), directory);
    if (TERMINAL_PHASES.has(journal.phase)) {
      cleanupTerminalArtifacts(journal);
      continue;
    }
    if (journal.phase === "live-staged" && journal.installMode === "rollback") {
      await installComponents(journal, { allowInterrupts: false });
      recovered.push({ transactionId: journal.transactionId, outcome: "rolled-back-from-safety" });
      continue;
    }
    if (["preparing", "prepared", "live-staged"].includes(journal.phase)) {
      for (const item of journal.components || componentPaths(journal.transactionId)) {
        rmSync(item.candidate, { recursive: true, force: true });
        rmSync(item.rollback, { recursive: true, force: true });
      }
      journal.phase = "rolled-back";
      journal.finishedAt = new Date().toISOString();
      writeJournal(journal);
      cleanupTerminalArtifacts(journal);
      recovered.push({ transactionId: journal.transactionId, outcome: "rolled-back-before-install" });
      continue;
    }
    try {
      await installComponents(journal, { allowInterrupts: false });
      recovered.push({ transactionId: journal.transactionId, outcome: journal.phase });
    } catch (error) {
      await rollbackFromSafety(journal);
      recovered.push({ transactionId: journal.transactionId, outcome: "rolled-back-from-safety", cause: String(error.message || error) });
    }
  }
  return recovered;
}

export async function createRestoreTransaction(sourceDirectory, sourceManifest) {
  const transactionId = `restore-${timestamp()}-${randomUUID()}`;
  const transactionDirectory = resolve(transactionRoot(), transactionId);
  const desiredDirectory = resolve(transactionDirectory, "desired");
  const safetyDirectory = resolve(transactionDirectory, "safety");
  mkdirSync(transactionDirectory, { recursive: true });
  interruptAt("after-transaction-directory");
  const journal = {
    schema: JOURNAL_SCHEMA,
    transactionId,
    transactionDirectory,
    sourceDirectory: resolve(sourceDirectory),
    desiredDirectory,
    safetyDirectory,
    backupSchema: BACKUP_SCHEMA,
    phase: "preparing",
    installMode: "forward",
    installed: [],
    components: [],
    createdAt: new Date().toISOString(),
  };
  writeJournal(journal);
  const desiredManifest = await copySnapshot(sourceDirectory, sourceManifest, desiredDirectory, "restore-staged-source");
  interruptAt("after-desired-stage");
  const safetyManifest = await createSafetySnapshot(safetyDirectory);
  journal.desiredManifest = { schema: desiredManifest.schema, files: desiredManifest.files.length };
  journal.safetyManifest = { schema: safetyManifest.schema, files: safetyManifest.files.length };
  journal.phase = "prepared";
  writeJournal(journal);
  interruptAt("after-safety-stage");
  await stageCandidates(journal, desiredDirectory, desiredManifest, "forward");
  interruptAt("after-live-stage");
  return { journal, desiredManifest, safetyManifest };
}

export async function commitRestoreTransaction(journal) {
  try {
    await installComponents(journal, { allowInterrupts: true });
  } catch (error) {
    try {
      if (["installing", "installed"].includes(journal.phase)) await installComponents(journal, { allowInterrupts: false });
      else await recoverRestoreTransactions();
    } catch (recoveryError) {
      try {
        await rollbackFromSafety(journal);
      } catch (rollbackError) {
        throw new AggregateError(
          [error, recoveryError, rollbackError],
          "Restore install and safety rollback both failed.",
        );
      }
      throw error;
    }
    if (journal.phase === "complete") {
      journal.recoveredFromInstallError = true;
      journal.installWarning = "The first install attempt failed; deterministic retry completed successfully.";
      try {
        interruptAt("before-install-warning-journal-write");
        writeJournal(journal);
        journal.installWarningPersisted = true;
      } catch {
        // Live data and the terminal journal are already committed. Recording
        // retry diagnostics is metadata-only and cannot reverse that outcome.
        journal.installWarningPersisted = false;
      }
      cleanupTerminalArtifacts(journal);
      return journal;
    }
    throw error;
  }
  return journal;
}
