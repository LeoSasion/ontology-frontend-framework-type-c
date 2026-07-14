import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const skippedDirectories = new Set([
  ".git",
  "backups",
  "data",
  "dist",
  "logs",
  "node_modules",
]);

function normalize(path) {
  return path.replaceAll("\\", "/");
}

function listMarkdownFiles(directory = root) {
  const files = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory() && skippedDirectories.has(entry.name)) {
      continue;
    }
    const absolute = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...listMarkdownFiles(absolute));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) {
      files.push(absolute);
    }
  }
  return files.sort((left, right) => left.localeCompare(right));
}

function relativeTarget(indexFile, targetFile) {
  return normalize(relative(dirname(indexFile), targetFile));
}

function resolveMarkdownLink(sourceFile, rawTarget) {
  let target = rawTarget.trim();
  if (target.startsWith("<") && target.endsWith(">")) {
    target = target.slice(1, -1);
  }
  target = target.split(/\s+['"]/u, 1)[0];
  if (
    target === "" ||
    target.startsWith("#") ||
    /^(?:https?:|mailto:|data:)/iu.test(target)
  ) {
    return null;
  }
  const pathOnly = decodeURIComponent(target.split("#", 1)[0]);
  return resolve(dirname(sourceFile), pathOnly);
}

const markdownFiles = listMarkdownFiles();
const docsIndexPath = resolve(root, "docs", "README.md");
const artifactsIndexPath = resolve(root, "artifacts", "README.md");
const docsIndex = readFileSync(docsIndexPath, "utf8");
const artifactsIndex = readFileSync(artifactsIndexPath, "utf8");
const failures = [];
const checks = [];

function check(label, ok, detail = "") {
  checks.push({ label, ok, detail });
  if (!ok) {
    failures.push({ label, detail });
  }
}

for (const file of markdownFiles) {
  const source = readFileSync(file, "utf8");
  const relativeFile = normalize(relative(root, file));
  const h1Count = (source.match(/^# /gmu) ?? []).length;
  check(`single-h1:${relativeFile}`, h1Count === 1, `found ${h1Count}`);

  const linkPattern = /!?\[[^\]]*\]\(([^)]+)\)/gu;
  for (const match of source.matchAll(linkPattern)) {
    const target = resolveMarkdownLink(file, match[1]);
    if (target === null) {
      continue;
    }
    check(
      `link:${relativeFile}:${match[1]}`,
      existsSync(target),
      normalize(relative(root, target)),
    );
  }

  if (relativeFile === "docs/README.md" || relativeFile === "artifacts/README.md") {
    continue;
  }
  const indexPath = relativeFile.startsWith("artifacts/")
    ? artifactsIndexPath
    : docsIndexPath;
  const indexSource = relativeFile.startsWith("artifacts/")
    ? artifactsIndex
    : docsIndex;
  const expectedLink = relativeTarget(indexPath, file);
  check(
    `indexed:${relativeFile}`,
    indexSource.includes(`(${expectedLink})`),
    `expected (${expectedLink})`,
  );
}

const agents = readFileSync(resolve(root, "AGENTS.md"), "utf8");
for (const token of [
  "C:\\Users\\Administrator\\Documents\\AIBI-C",
  "https://github.com/LeoSasion/AIBI-C.git",
  "git rev-parse --show-toplevel",
  "git remote get-url origin",
  "AIBI-A",
  "AIBI-B",
  "AIBI-C",
  "AIBI-D",
  "AIBI-E",
  "AIBI项目杂交",
]) {
  check(`agents-boundary:${token}`, agents.includes(token), token);
}

const allMarkdown = markdownFiles
  .map((file) => readFileSync(file, "utf8"))
  .join("\n");
for (const retiredReference of [
  "development-plan.md",
  "reference-project-gap-analysis.md",
  "m7-job-runtime-2026-07-14/SUMMARY.md",
  "m8-workflow-capability-2026-07-14/SUMMARY.md",
  "m9-analysis-unit-2026-07-14/SUMMARY.md",
  "m10-analysis-export-2026-07-14/SUMMARY.md",
  "m11-connector-adapter-2026-07-14/SUMMARY.md",
  "release-readiness-2026-07-13/SUMMARY.md",
]) {
  check(
    `retired-reference-absent:${retiredReference}`,
    !allMarkdown.includes(retiredReference),
    retiredReference,
  );
}

const cliResult = spawnSync(
  "python",
  [resolve(root, "tools", "bi_cli.py"), "--json", "cli-contract"],
  { cwd: root, encoding: "utf8", windowsHide: true },
);
let liveCommandCount = null;
try {
  const parsed = JSON.parse(cliResult.stdout || "{}");
  liveCommandCount = parsed.contract?.commandCount ?? null;
} catch {
  liveCommandCount = null;
}
const cliContractDoc = readFileSync(resolve(root, "docs", "bi-cli-contract.md"), "utf8");
const documentedCommandCount = Number(
  cliContractDoc.match(/Command count: `(\d+)`/u)?.[1] ?? Number.NaN,
);
check(
  "generated-cli-contract-current",
  cliResult.status === 0 &&
    Number.isInteger(liveCommandCount) &&
    documentedCommandCount === liveCommandCount,
  `live=${liveCommandCount}; documented=${documentedCommandCount}; status=${cliResult.status}`,
);

const result = {
  ok: failures.length === 0,
  schema: "aibi-documentation-verify/v1",
  markdownCount: markdownFiles.length,
  files: markdownFiles.map((file) => normalize(relative(root, file))),
  checks,
  failedChecks: failures,
};

console.log(JSON.stringify(result, null, 2));
if (!result.ok) {
  process.exitCode = 1;
}
