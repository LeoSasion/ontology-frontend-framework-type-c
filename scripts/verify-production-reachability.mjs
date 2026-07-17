import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const sourceRoots = [resolve(root, "src"), resolve(root, "server")];
const entrypoints = [resolve(root, "src", "main.tsx"), resolve(root, "server", "index.ts")];
const sourceSuffixes = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".css"];
const sourceExtensions = new Set(sourceSuffixes);

function extension(path) {
  const match = path.match(/\.[^.\\/]+$/u);
  return match?.[0] ?? "";
}

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : sourceExtensions.has(extension(path)) ? [resolve(path)] : [];
  });
}

const files = sourceRoots.flatMap(walk);
const fileSet = new Set(files);
const imports = new Map(files.map((file) => [file, []]));
const importPatterns = [
  /\bfrom\s*["']([^"']+)["']/gu,
  /\bimport\s*["']([^"']+)["']/gu,
  /\bimport\s*\(\s*["']([^"']+)["']\s*\)/gu,
  /@import\s+(?:url\(\s*)?["']([^"']+)["']/gu,
];

function resolveImport(importer, specifier) {
  if (!specifier.startsWith(".")) return null;
  const base = resolve(dirname(importer), specifier.split(/[?#]/u, 1)[0]);
  const candidates = [
    base,
    ...sourceSuffixes.map((suffix) => `${base}${suffix}`),
    ...sourceSuffixes.map((suffix) => join(base, `index${suffix}`)),
  ];
  return candidates.find((candidate) => fileSet.has(candidate)) ?? null;
}

for (const file of files) {
  const source = readFileSync(file, "utf8");
  for (const pattern of importPatterns) {
    for (const match of source.matchAll(pattern)) {
      const target = resolveImport(file, match[1]);
      if (target) imports.get(file).push(target);
    }
  }
}

const reachable = new Set();
const pending = [...entrypoints];
while (pending.length) {
  const file = pending.pop();
  if (!file || reachable.has(file)) continue;
  reachable.add(file);
  pending.push(...(imports.get(file) ?? []));
}

const unreachable = files
  .filter((file) => !reachable.has(file))
  .map((file) => relative(root, file).replaceAll("\\", "/"))
  .sort();
const receipt = {
  ok: unreachable.length === 0,
  schema: "aibi-production-source-reachability/v1",
  generatedBy: "scripts/verify-production-reachability.mjs",
  entrypoints: entrypoints.map((file) => relative(root, file).replaceAll("\\", "/")),
  sourceFileCount: files.length,
  reachableFileCount: reachable.size,
  unreachable,
};

console.log(JSON.stringify(receipt, null, 2));
if (!receipt.ok) process.exitCode = 1;
