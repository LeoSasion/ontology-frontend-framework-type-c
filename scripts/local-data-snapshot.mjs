import { createHash, randomUUID } from "node:crypto";
import {
  closeSync,
  createReadStream,
  createWriteStream,
  existsSync,
  fsyncSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { pipeline } from "node:stream/promises";
import { Transform } from "node:stream";

export const root = resolve(import.meta.dirname, "..");
export const BACKUP_SCHEMA = "aibi-local-backup/v2";
export const DATASET_OBJECT_KIND = "dataset-object";
const SHA256_RE = /^[a-f0-9]{64}$/;
const OBJECT_KEY_RE = /^workspaces\/[a-f0-9]{24}\/objects\/[a-f0-9]{2}\/[a-f0-9]{64}\.parquet$/;
const DATASET_LOCK_FILE = ".aibi-dataset-object.lock";
const SNAPSHOT_SERVICE = resolve(root, "tools", "local_data_snapshot_service.py");

function loadLocalEnv() {
  const envPath = resolve(root, ".env");
  if (!existsSync(envPath)) return;
  for (const rawLine of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const separator = line.indexOf("=");
    if (separator <= 0) continue;
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (key && process.env[key] === undefined) process.env[key] = value;
  }
}

loadLocalEnv();

export function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function configuredPath(name, fallback) {
  const value = String(process.env[name] ?? "").trim();
  return value ? (isAbsolute(value) ? resolve(value) : resolve(root, value)) : resolve(root, fallback);
}

function pythonExecutable() {
  return String(process.env.AIBI_PYTHON ?? process.env.PYTHON ?? "python").trim() || "python";
}

function helperResult(args) {
  const result = spawnSync(pythonExecutable(), [SNAPSHOT_SERVICE, ...args], {
    cwd: root,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    encoding: "utf8",
    windowsHide: true,
  });
  if (result.status !== 0) {
    const detail = String(result.stderr || result.stdout || `exit ${result.status}`).trim();
    throw new Error(`Local-data snapshot validation failed: ${detail}`);
  }
  try {
    return JSON.parse(String(result.stdout || "{}"));
  } catch (error) {
    throw new Error(`Local-data snapshot helper returned invalid JSON: ${error.message}`);
  }
}

export function localDataFiles() {
  return [
    { kind: "sqlite", path: configuredPath("AIBI_HYBRID_DB_PATH", join("data", "local", "aibi_control_v2.sqlite")) },
    { kind: "duckdb", path: configuredPath("AIBI_HYBRID_DUCKDB_PATH", join("data", "local", "aibi_catalog_v2.duckdb")) },
  ];
}

export function datasetObjectRoot() {
  return configuredPath("AIBI_DATASET_OBJECT_ROOT", join("data", "local", "dataset-objects-v2"));
}

export function backupRoot() {
  return configuredPath("AIBI_BACKUP_ROOT", "backups");
}

export function mutationFencePath() {
  const sqlite = localDataFiles().find((item) => item.kind === "sqlite");
  if (!sqlite) throw new Error("SQLite control database path is unavailable.");
  return resolve(dirname(sqlite.path), ".aibi-cross-engine-writer.lock");
}

export async function withMutationFence(operation, { timeoutMs = 60_000 } = {}) {
  const numericTimeout = Number(timeoutMs);
  const boundedTimeout = Number.isFinite(numericTimeout) && numericTimeout > 0 ? numericTimeout : 60_000;
  const lockPath = mutationFencePath();
  mkdirSync(dirname(lockPath), { recursive: true });
  const child = spawn(pythonExecutable(), [
    SNAPSHOT_SERVICE,
    "hold-lock",
    "--path",
    lockPath,
    "--timeout",
    String(Math.max(0.05, boundedTimeout / 1000)),
  ], {
    cwd: root,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    stdio: ["pipe", "pipe", "pipe"],
    windowsHide: true,
  });
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => {
    stderr = `${stderr}${chunk}`.slice(-16_384);
  });
  await new Promise((resolveLock, rejectLock) => {
    let stdout = "";
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill();
      rejectLock(new Error(`Timed out acquiring the cross-process mutation fence: ${lockPath}`));
    }, boundedTimeout + 2_000);
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      if (settled) return;
      stdout += chunk;
      if (stdout.includes("LOCKED\n") || stdout.includes("LOCKED\r\n")) {
        settled = true;
        clearTimeout(timer);
        resolveLock();
      }
    });
    child.once("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      rejectLock(error);
    });
    child.once("exit", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      rejectLock(new Error(`Cross-process mutation fence failed (${code}): ${stderr}`));
    });
  });
  try {
    return await operation({ lockPath });
  } finally {
    child.stdin.end();
    await new Promise((resolveExit) => {
      if (child.exitCode !== null || child.signalCode !== null) resolveExit();
      else child.once("exit", resolveExit);
    });
  }
}

export function validateLocalDataSnapshot({
  sqlitePath,
  duckdbPath,
  objectRoot,
  expectedPathRoot,
}) {
  const args = [
    "validate",
    "--sqlite", resolve(sqlitePath),
    "--duckdb", resolve(duckdbPath),
    "--objects", resolve(objectRoot),
  ];
  if (expectedPathRoot) args.push("--expected-path-root", resolve(expectedPathRoot));
  return helperResult(args);
}

export function rebaseDuckdbSnapshot({ duckdbPath, objectRoot, targetObjectRoot }) {
  return helperResult([
    "rebase",
    "--duckdb", resolve(duckdbPath),
    "--objects", resolve(objectRoot),
    "--target-object-root", resolve(targetObjectRoot),
  ]);
}

export function materializeDatabaseSnapshot({ sqlitePath, duckdbPath, sqliteTarget, duckdbTarget }) {
  return helperResult([
    "materialize",
    "--sqlite", resolve(sqlitePath),
    "--duckdb", resolve(duckdbPath),
    "--sqlite-out", resolve(sqliteTarget),
    "--duckdb-out", resolve(duckdbTarget),
  ]);
}

function normalizeRelativePath(value, label = "relative path") {
  const raw = String(value ?? "");
  const normalized = raw.replaceAll("\\", "/");
  if (
    !normalized ||
    normalized.includes("\0") ||
    normalized.startsWith("/") ||
    /^[A-Za-z]:\//.test(normalized) ||
    normalized.split("/").some((part) => !part || part === "." || part === "..")
  ) {
    throw new Error(`${label} must be a safe relative path.`);
  }
  return normalized;
}

function pathWithin(base, candidate) {
  const resolvedBase = resolve(base);
  const resolvedCandidate = resolve(candidate);
  const suffix = relative(resolvedBase, resolvedCandidate);
  return suffix === "" || (suffix !== ".." && !suffix.startsWith(`..${sep}`) && !isAbsolute(suffix));
}

function tryLstat(path) {
  try {
    return lstatSync(path);
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    throw error;
  }
}

function assertNoSymlink(path, label = "Path") {
  const stats = tryLstat(path);
  if (stats?.isSymbolicLink()) throw new Error(`${label} cannot be a symbolic link: ${path}`);
}

function assertNoSymlinkAncestors(path, label = "Path") {
  let cursor = resolve(path);
  while (true) {
    assertNoSymlink(cursor, label);
    const parent = dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }
}

function assertRegularFile(path, label = "File") {
  assertNoSymlinkAncestors(path, label);
  const stats = tryLstat(path);
  if (!stats) throw new Error(`${label} is missing: ${path}`);
  if (stats.isSymbolicLink() || !stats.isFile()) throw new Error(`${label} must be a regular file: ${path}`);
}

function assertDirectory(path, label = "Directory") {
  assertNoSymlinkAncestors(path, label);
  const stats = tryLstat(path);
  if (!stats) throw new Error(`${label} is missing: ${path}`);
  if (stats.isSymbolicLink() || !stats.isDirectory()) throw new Error(`${label} must be a directory: ${path}`);
}

function fsyncFile(path) {
  const descriptor = openSync(path, "r+");
  try {
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}

function makeHashTransform() {
  const digest = createHash("sha256");
  let bytes = 0;
  const transform = new Transform({
    transform(chunk, _encoding, callback) {
      digest.update(chunk);
      bytes += chunk.length;
      callback(null, chunk);
    },
  });
  return {
    transform,
    receipt() {
      return { bytes, sha256: digest.digest("hex") };
    },
  };
}

export async function sha256(path) {
  assertRegularFile(path, "Hash input");
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest("hex");
}

async function copyStreamWithHash(sourcePath, targetPath) {
  assertRegularFile(sourcePath, "Copy source");
  assertNoSymlinkAncestors(targetPath, "Copy target");
  if (existsSync(targetPath)) {
    assertRegularFile(targetPath, "Copy target");
    throw new Error(`Copy target already exists: ${targetPath}`);
  }
  mkdirSync(dirname(targetPath), { recursive: true });
  assertNoSymlinkAncestors(dirname(targetPath), "Copy target directory");
  const hashed = makeHashTransform();
  const output = createWriteStream(targetPath, { flags: "wx" });
  let created = false;
  output.once("open", () => {
    created = true;
  });
  try {
    await pipeline(createReadStream(sourcePath), hashed.transform, output);
    fsyncFile(targetPath);
    return hashed.receipt();
  } catch (error) {
    if (created) rmSync(targetPath, { force: true });
    throw error;
  }
}

export async function copyWithReceipt(sourcePath, targetPath, kind, options = {}) {
  const receipt = await copyStreamWithHash(resolve(sourcePath), resolve(targetPath));
  return {
    kind,
    file: options.file ?? basename(targetPath),
    bytes: receipt.bytes,
    sha256: receipt.sha256,
    ...(options.objectKey ? { objectKey: options.objectKey } : {}),
    ...(options.objectHash ? { objectHash: options.objectHash } : {}),
  };
}

export function writeManifest(directory, manifest) {
  assertNoSymlinkAncestors(directory, "Manifest directory");
  mkdirSync(directory, { recursive: true });
  assertDirectory(directory, "Manifest directory");
  const manifestPath = join(directory, "manifest.json");
  assertNoSymlink(manifestPath, "Manifest file");
  const temporary = join(directory, `.${basename(manifestPath)}.${randomUUID()}.tmp`);
  writeFileSync(temporary, `${JSON.stringify(manifest, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
  try {
    fsyncFile(temporary);
    renameSync(temporary, manifestPath);
  } finally {
    rmSync(temporary, { force: true });
  }
}

export function writeAtomicJson(path, value) {
  const target = resolve(path);
  assertNoSymlinkAncestors(target, "JSON target");
  mkdirSync(dirname(target), { recursive: true });
  const temporary = join(dirname(target), `.${basename(target)}.${randomUUID()}.tmp`);
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
  try {
    fsyncFile(temporary);
    renameSync(temporary, target);
    fsyncFile(target);
  } finally {
    rmSync(temporary, { force: true });
  }
}

export function readJsonFile(path, label = "JSON file") {
  const target = resolve(path);
  assertRegularFile(target, label);
  try {
    return JSON.parse(readFileSync(target, "utf8"));
  } catch (error) {
    throw new Error(`${label} is invalid JSON: ${error.message}`);
  }
}

function walkDatasetObjects(directory, rootDirectory, output) {
  assertDirectory(directory, "Dataset object directory");
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const entryPath = join(directory, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Dataset object tree cannot contain symbolic links: ${entryPath}`);
    if (entry.isDirectory()) {
      walkDatasetObjects(entryPath, rootDirectory, output);
      continue;
    }
    if (!entry.isFile()) throw new Error(`Dataset object tree contains an unsupported entry: ${entryPath}`);
    const relativeKey = normalizeRelativePath(relative(rootDirectory, entryPath), "Dataset object key");
    if (relativeKey === DATASET_LOCK_FILE && resolve(directory) === resolve(rootDirectory)) continue;
    if (!OBJECT_KEY_RE.test(relativeKey)) throw new Error(`Dataset object tree contains an unsupported file: ${entryPath}`);
    const objectHash = basename(relativeKey, ".parquet");
    if (!SHA256_RE.test(objectHash) || relativeKey.split("/")[3] !== objectHash.slice(0, 2)) {
      throw new Error(`Dataset object path does not match its content hash: ${relativeKey}`);
    }
    output.push({ kind: DATASET_OBJECT_KIND, objectKey: relativeKey, objectHash, sourcePath: resolve(entryPath) });
  }
}

export function datasetObjectFiles(objectRoot = datasetObjectRoot()) {
  const resolvedRoot = resolve(objectRoot);
  assertNoSymlinkAncestors(resolvedRoot, "Dataset object root");
  if (!tryLstat(resolvedRoot)) return [];
  assertDirectory(resolvedRoot, "Dataset object root");
  const output = [];
  walkDatasetObjects(resolvedRoot, resolvedRoot, output);
  output.sort((left, right) => left.objectKey.localeCompare(right.objectKey));
  return output;
}

export function currentSnapshot() {
  const databaseEntries = localDataFiles().map((item) => ({
    kind: item.kind,
    sourcePath: resolve(item.path),
    file: `databases/${basename(item.path)}`,
  }));
  const objects = datasetObjectFiles();
  return [...databaseEntries.filter((item) => tryLstat(item.sourcePath)), ...objects.map((item) => ({
    ...item,
    file: `objects/${item.objectKey}`,
  }))];
}

export function assertBackupFilesComplete(entries) {
  const kinds = new Set(entries.filter((item) => item.kind !== DATASET_OBJECT_KIND).map((item) => item.kind));
  for (const required of ["sqlite", "duckdb"]) {
    if (!kinds.has(required)) throw new Error(`Local ${required} database is missing; refusing incomplete backup.`);
  }
}

export async function createBackupManifest(
  directory,
  entries,
  purpose = "local-data-backup",
  { expectedFiles = null } = {},
) {
  const receipts = [];
  let objectBytes = 0;
  let objectCount = 0;
  const receiptKey = (item) => JSON.stringify([item.kind, item.file, item.objectKey ?? null]);
  const expectedByKey = expectedFiles
    ? new Map(expectedFiles.map((item) => [receiptKey(item), item]))
    : null;
  const matchedExpected = new Set();
  for (const entry of entries) {
    const relativeFile = normalizeRelativePath(entry.file, "Backup manifest file");
    const target = resolve(directory, ...relativeFile.split("/"));
    if (!pathWithin(directory, target)) throw new Error(`Backup target escaped the output directory: ${relativeFile}`);
    const receipt = await copyWithReceipt(entry.sourcePath, target, entry.kind, {
      file: relativeFile,
      objectKey: entry.objectKey,
      objectHash: entry.objectHash,
    });
    if (expectedByKey) {
      const key = receiptKey(receipt);
      const expected = expectedByKey.get(key);
      if (
        !expected
        || receipt.bytes !== expected.bytes
        || receipt.sha256 !== expected.sha256
        || (receipt.kind === DATASET_OBJECT_KIND && receipt.objectHash !== expected.objectHash)
      ) {
        throw new Error(`Backup source changed while copying: ${relativeFile}`);
      }
      matchedExpected.add(key);
    }
    if (entry.kind === DATASET_OBJECT_KIND) {
      if (receipt.sha256 !== entry.objectHash) throw new Error(`Dataset object content hash mismatch: ${entry.objectKey}`);
      objectBytes += receipt.bytes;
      objectCount += 1;
    }
    receipts.push(receipt);
  }
  if (expectedByKey && matchedExpected.size !== expectedByKey.size) {
    throw new Error("Backup source changed its file inventory while copying.");
  }
  const manifest = {
    schema: BACKUP_SCHEMA,
    createdAt: new Date().toISOString(),
    purpose,
    format: {
      controlPlane: "sqlite-v2",
      catalog: "duckdb-v2",
      datasetObjects: "content-addressed-parquet-v2",
    },
    roots: {
      datasetObjects: {
        kind: "content-addressed-parquet",
        objectCount,
        bytes: objectBytes,
      },
    },
    files: receipts,
    excludes: ["source files", "environment secrets", DATASET_LOCK_FILE],
  };
  writeManifest(directory, manifest);
  return manifest;
}

export async function readManifest(directory) {
  const resolvedDirectory = resolve(directory);
  assertDirectory(resolvedDirectory, "Backup directory");
  const manifestPath = join(resolvedDirectory, "manifest.json");
  assertRegularFile(manifestPath, "Backup manifest");
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  } catch (error) {
    throw new Error(`Backup manifest is not valid JSON: ${error.message}`);
  }
  if (
    manifest?.schema !== BACKUP_SCHEMA ||
    !Array.isArray(manifest.files) ||
    manifest.format?.controlPlane !== "sqlite-v2" ||
    manifest.format?.catalog !== "duckdb-v2" ||
    manifest.format?.datasetObjects !== "content-addressed-parquet-v2" ||
    manifest.roots?.datasetObjects?.kind !== "content-addressed-parquet"
  ) {
    throw new Error("Backup manifest is invalid or unsupported; only aibi-local-backup/v2 is accepted.");
  }
  return manifest;
}

function validateManifestEntry(file) {
  if (!file || !["sqlite", "duckdb", DATASET_OBJECT_KIND].includes(file.kind)) {
    throw new Error("Backup manifest contains an invalid file entry kind.");
  }
  const relativeFile = normalizeRelativePath(file.file, "Backup manifest file");
  if (relativeFile === "manifest.json" || !SHA256_RE.test(String(file.sha256 ?? ""))) {
    throw new Error("Backup manifest contains an invalid file receipt.");
  }
  if (!Number.isSafeInteger(file.bytes) || file.bytes < 0) {
    throw new Error("Backup manifest contains an invalid byte count.");
  }
  if (file.kind === DATASET_OBJECT_KIND) {
    const objectKey = normalizeRelativePath(file.objectKey, "Dataset object key");
    const objectHash = String(file.objectHash ?? "");
    if (!OBJECT_KEY_RE.test(objectKey) || !SHA256_RE.test(objectHash) || objectHash !== basename(objectKey, ".parquet")) {
      throw new Error("Backup manifest contains an invalid dataset object entry.");
    }
    if (relativeFile !== `objects/${objectKey}` || objectKey.split("/")[3] !== objectHash.slice(0, 2)) {
      throw new Error("Backup manifest dataset object path is invalid.");
    }
  } else if (!relativeFile.startsWith("databases/") || relativeFile.split("/").length !== 2) {
    throw new Error("Backup manifest database entries must stay under databases/.");
  }
  return relativeFile;
}

export async function verifyManifestFiles(directory, manifest) {
  const resolvedDirectory = resolve(directory);
  assertDirectory(resolvedDirectory, "Backup directory");
  const seenFiles = new Set();
  const seenKinds = new Set();
  const seenObjects = new Set();
  let objectBytes = 0;
  let objectCount = 0;
  for (const file of manifest.files) {
    const relativeFile = validateManifestEntry(file);
    if (seenFiles.has(relativeFile)) throw new Error(`Backup manifest contains duplicate files: ${relativeFile}`);
    seenFiles.add(relativeFile);
    if (file.kind !== DATASET_OBJECT_KIND) {
      if (seenKinds.has(file.kind)) throw new Error(`Backup manifest contains duplicate ${file.kind} entries.`);
      seenKinds.add(file.kind);
    } else {
      if (seenObjects.has(file.objectKey)) throw new Error(`Backup manifest contains duplicate dataset objects: ${file.objectKey}`);
      seenObjects.add(file.objectKey);
      objectBytes += file.bytes;
      objectCount += 1;
    }
    const filePath = resolve(resolvedDirectory, ...relativeFile.split("/"));
    if (!pathWithin(resolvedDirectory, filePath)) throw new Error(`Backup file escaped the backup directory: ${relativeFile}`);
    assertRegularFile(filePath, "Backup file");
    const stats = statSync(filePath);
    if (stats.size !== file.bytes || await sha256(filePath) !== file.sha256) {
      throw new Error(`Backup checksum mismatch: ${relativeFile}`);
    }
  }
  const expectedObjects = manifest.roots.datasetObjects;
  if (expectedObjects.objectCount !== objectCount || expectedObjects.bytes !== objectBytes) {
    throw new Error("Backup manifest dataset object inventory does not match its receipts.");
  }
  if (seenKinds.size !== 2 || !seenKinds.has("sqlite") || !seenKinds.has("duckdb")) {
    throw new Error("Backup must contain exactly one SQLite v18 and one DuckDB v2 database receipt.");
  }
  const actualFiles = [];
  function walkBackup(path) {
    assertDirectory(path, "Backup directory");
    for (const entry of readdirSync(path, { withFileTypes: true })) {
      const entryPath = join(path, entry.name);
      if (entry.isSymbolicLink()) throw new Error(`Backup cannot contain symbolic links: ${entryPath}`);
      if (entry.isDirectory()) walkBackup(entryPath);
      else if (entry.isFile()) actualFiles.push(normalizeRelativePath(relative(resolvedDirectory, entryPath), "Backup file"));
      else throw new Error(`Backup contains an unsupported filesystem entry: ${entryPath}`);
    }
  }
  walkBackup(resolvedDirectory);
  const expectedFiles = new Set(["manifest.json", ...seenFiles]);
  const actualFileSet = new Set(actualFiles);
  const extras = actualFiles.filter((item) => !expectedFiles.has(item));
  const missing = [...expectedFiles].filter((item) => !actualFileSet.has(item));
  if (extras.length || missing.length) {
    throw new Error(`Backup inventory differs from its manifest (extra=${extras.join(",")}; missing=${missing.join(",")}).`);
  }
  return { fileCount: seenFiles.size, objectCount, objectBytes };
}

export function snapshotPathsForManifest(directory, manifest) {
  const resolvedDirectory = resolve(directory);
  const sqlite = manifest.files.find((item) => item.kind === "sqlite");
  const duckdb = manifest.files.find((item) => item.kind === "duckdb");
  if (!sqlite || !duckdb) throw new Error("Backup database receipts are incomplete.");
  return {
    sqlitePath: resolve(resolvedDirectory, ...normalizeRelativePath(sqlite.file).split("/")),
    duckdbPath: resolve(resolvedDirectory, ...normalizeRelativePath(duckdb.file).split("/")),
    objectRoot: resolve(resolvedDirectory, "objects"),
  };
}

export function assertDisjointPath(left, right, label = "Paths") {
  const first = resolve(left);
  const second = resolve(right);
  if (pathWithin(first, second) || pathWithin(second, first)) throw new Error(`${label} must not overlap: ${first} and ${second}`);
}

export async function assertLocalServiceStopped() {
  const port = Number(process.env.AIBI_API_PORT ?? 8787);
  try {
    const response = await fetch(`http://127.0.0.1:${port}/api/health`, { signal: AbortSignal.timeout(600) });
    const payload = await response.json();
    if (response.ok && payload?.service === "aibi-hybrid-api") {
      throw new Error("Stop AIBI-C local services before backup or restore.");
    }
  } catch (error) {
    if (error instanceof Error && error.message.includes("Stop AIBI-C")) throw error;
  }
}
