import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { assertLocalServiceStopped, createSafetyBackup, localDataFiles, readManifest, verifyManifestFiles } from "./local-data-snapshot.mjs";

const args = new Set(process.argv.slice(2));
const values = process.argv.slice(2);
const fromIndex = values.indexOf("--from");
const sourceDirectory = fromIndex >= 0 && values[fromIndex + 1] ? resolve(values[fromIndex + 1]) : "";
if (!sourceDirectory) throw new Error("Use --from <backup-directory> to preview or restore a backup.");

await assertLocalServiceStopped();
const manifest = readManifest(sourceDirectory);
verifyManifestFiles(sourceDirectory, manifest);
const targets = new Map(localDataFiles().map((item) => [item.kind, item.path]));
const restorePlan = manifest.files.map((file) => ({
  kind: file.kind,
  source: resolve(sourceDirectory, file.file),
  target: targets.get(file.kind),
  bytes: file.bytes,
  sha256: file.sha256,
}));
if (restorePlan.some((item) => !item.target)) throw new Error("Backup contains an unsupported database kind.");

if (!args.has("--confirm")) {
  console.log(JSON.stringify({ ok: true, confirmed: false, restorePlan, next: "Run again with --confirm after reviewing the target paths." }, null, 2));
  process.exit(0);
}

const currentFiles = localDataFiles().filter((item) => existsSync(item.path));
const safetyBackup = createSafetyBackup(currentFiles);
for (const item of restorePlan) {
  mkdirSync(dirname(item.target), { recursive: true });
  copyFileSync(item.source, item.target);
}
console.log(JSON.stringify({ ok: true, confirmed: true, safetyBackup, restored: restorePlan }, null, 2));
