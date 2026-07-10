import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, isAbsolute, join, resolve, sep } from "node:path";

export const root = resolve(import.meta.dirname, "..");

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

export function localDataFiles() {
  return [
    { kind: "sqlite", path: configuredPath("AIBI_HYBRID_DB_PATH", join("data", "local", "aibi_hybrid.sqlite")) },
    { kind: "duckdb", path: configuredPath("AIBI_HYBRID_DUCKDB_PATH", join("data", "local", "aibi_hybrid.duckdb")) },
  ];
}

export function backupRoot() {
  return configuredPath("AIBI_BACKUP_ROOT", "backups");
}

export function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
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

export function copyWithReceipt(sourcePath, targetPath, kind) {
  mkdirSync(dirname(targetPath), { recursive: true });
  copyFileSync(sourcePath, targetPath);
  const stats = statSync(targetPath);
  return { kind, file: basename(targetPath), bytes: stats.size, sha256: sha256(targetPath) };
}

export function writeManifest(directory, manifest) {
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
}

export function readManifest(directory) {
  const manifestPath = join(directory, "manifest.json");
  if (!existsSync(manifestPath)) throw new Error(`Backup manifest not found: ${manifestPath}`);
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  if (manifest?.schema !== "aibi-local-backup/v1" || !Array.isArray(manifest.files)) {
    throw new Error("Backup manifest is invalid or unsupported.");
  }
  return manifest;
}

export function verifyManifestFiles(directory, manifest) {
  const resolvedBackupRoot = `${resolve(directory)}${sep}`;
  const seenKinds = new Set();
  for (const file of manifest.files) {
    if (!file || !["sqlite", "duckdb"].includes(file.kind) || basename(String(file.file ?? "")) !== file.file) {
      throw new Error("Backup manifest contains an invalid file entry.");
    }
    if (seenKinds.has(file.kind)) throw new Error(`Backup manifest contains duplicate ${file.kind} entries.`);
    seenKinds.add(file.kind);
    const filePath = resolve(directory, file.file);
    if (!`${filePath}`.startsWith(resolvedBackupRoot) || !existsSync(filePath)) {
      throw new Error(`Backup file is missing or outside the backup directory: ${file.file}`);
    }
    if (sha256(filePath) !== file.sha256 || statSync(filePath).size !== file.bytes) {
      throw new Error(`Backup checksum mismatch: ${file.file}`);
    }
  }
}

export function createSafetyBackup(files, label = `pre-restore-${timestamp()}`) {
  const directory = resolve(backupRoot(), label);
  const receipts = files.filter((item) => existsSync(item.path)).map((item) => copyWithReceipt(item.path, join(directory, basename(item.path)), item.kind));
  writeManifest(directory, {
    schema: "aibi-local-backup/v1",
    createdAt: new Date().toISOString(),
    purpose: "pre-restore-safety-copy",
    files: receipts,
    excludes: ["source files", "environment secrets"],
  });
  return directory;
}
