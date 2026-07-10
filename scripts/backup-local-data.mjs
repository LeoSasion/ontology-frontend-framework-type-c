import { existsSync } from "node:fs";
import { basename, resolve } from "node:path";
import { assertLocalServiceStopped, backupRoot, copyWithReceipt, localDataFiles, timestamp, writeManifest } from "./local-data-snapshot.mjs";

const args = process.argv.slice(2);
const outputIndex = args.indexOf("--output");
const outputDirectory = outputIndex >= 0 && args[outputIndex + 1]
  ? resolve(args[outputIndex + 1])
  : resolve(backupRoot(), `aibi-${timestamp()}`);

await assertLocalServiceStopped();
const sourceFiles = localDataFiles().filter((item) => existsSync(item.path));
if (!sourceFiles.length) throw new Error("No local AIBI database files were found to back up.");

const files = sourceFiles.map((item) => copyWithReceipt(item.path, resolve(outputDirectory, basename(item.path)), item.kind));
const manifest = {
  schema: "aibi-local-backup/v1",
  createdAt: new Date().toISOString(),
  purpose: "local-database-backup",
  files,
  excludes: ["source files", "environment secrets"],
};
writeManifest(outputDirectory, manifest);
console.log(JSON.stringify({ ok: true, outputDirectory, manifest }, null, 2));
