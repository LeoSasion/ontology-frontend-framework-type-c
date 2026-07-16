import { existsSync, lstatSync, readFileSync, readdirSync, realpathSync } from "node:fs";
import { extname, join, relative, resolve, sep } from "node:path";
import { spawnSync } from "node:child_process";
import {
  absoluteSiblingProjectPathPattern,
  forbiddenProjectPathPattern,
  legacyCrossProjectEnvironmentVariablePattern,
  patternMatches,
  relativeSiblingProjectPathPattern,
  siblingRepositoryNames,
} from "./repository-boundary-policy.mjs";

const root = resolve(process.cwd());
const ignoredDirectories = new Set([".git", "node_modules", "dist", "coverage", "data"]);
const textExtensions = new Set([".cjs", ".css", ".env", ".example", ".html", ".js", ".json", ".jsx", ".md", ".mjs", ".py", ".ps1", ".ts", ".tsx", ".txt", ".yaml", ".yml"]);
const forbiddenPatterns = [
  {
    id: "absolute-sibling-project-path",
    pattern: absoluteSiblingProjectPathPattern,
  },
  {
    id: "relative-sibling-project-path",
    pattern: relativeSiblingProjectPathPattern,
  },
  {
    id: "legacy-cross-project-environment-variable",
    pattern: legacyCrossProjectEnvironmentVariablePattern,
  },
];
const intentionalSourceFixturePath = [
  "C:",
  "Users",
  "Administrator",
  "Documents",
  "AIBI-D",
  "forbidden.csv",
].join("/");

function git(args) {
  return spawnSync("git", args, { cwd: root, encoding: "utf8", windowsHide: true });
}

function insideRoot(path) {
  const relation = relative(root, path);
  return relation === "" || (!relation.startsWith(`..${sep}`) && relation !== "..");
}

function walk(directory, files, symlinkEscapes) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory() && ignoredDirectories.has(entry.name)) continue;
    const path = join(directory, entry.name);
    const stats = lstatSync(path);
    if (stats.isSymbolicLink()) {
      const target = realpathSync(path);
      if (!insideRoot(target)) symlinkEscapes.push({ path: relative(root, path), target });
      continue;
    }
    if (stats.isDirectory()) walk(path, files, symlinkEscapes);
    else if (stats.isFile()) files.push(path);
  }
}

function isTextFile(path) {
  const extension = extname(path).toLowerCase();
  return textExtensions.has(extension) || ["AGENTS.md", "README", "Dockerfile", "package.json"].includes(path.split(/[\\/]/).at(-1));
}

function isIntentionalNegativeFixtureReference(reference, content) {
  if (
    reference.rule !== "absolute-sibling-project-path" ||
    reference.file !== "scripts/verify-source-intelligence-job.mjs"
  ) {
    return false;
  }
  const lineText = content.split(/\r?\n/u)[reference.line - 1] ?? "";
  return lineText.includes(intentionalSourceFixturePath);
}

const rootResult = git(["rev-parse", "--show-toplevel"]);
const remoteResult = git(["remote", "get-url", "origin"]);
const gitRoot = resolve(String(rootResult.stdout ?? "").trim());
const remote = String(remoteResult.stdout ?? "").trim().replace(/\/$/, "");
const packageJson = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const files = [];
const symlinkEscapes = [];
walk(root, files, symlinkEscapes);

const forbiddenReferences = [];
const intentionalNegativeFixtureReferences = [];
for (const path of files.filter(isTextFile)) {
  const content = readFileSync(path, "utf8");
  for (const rule of forbiddenPatterns) {
    rule.pattern.lastIndex = 0;
    for (const match of content.matchAll(rule.pattern)) {
      const line = content.slice(0, match.index).split(/\r?\n/).length;
      const reference = {
        rule: rule.id,
        file: relative(root, path).replaceAll("\\", "/"),
        line,
        value: match[0],
      };
      if (isIntentionalNegativeFixtureReference(reference, content)) {
        intentionalNegativeFixtureReferences.push(reference);
      } else {
        forbiddenReferences.push(reference);
      }
    }
  }
}

const absolutePathRule = forbiddenPatterns.find((rule) => rule.id === "absolute-sibling-project-path");
const relativePathRule = forbiddenPatterns.find((rule) => rule.id === "relative-sibling-project-path");
const environmentVariableRule = forbiddenPatterns.find((rule) => rule.id === "legacy-cross-project-environment-variable");
const siblingAbsolutePathFixtures = siblingRepositoryNames.flatMap((name) => [
  ["C:", "Users", "Administrator", "Documents", name, "data", "orders.csv"].join("\\"),
  ["D:", "workspaces", name, "data", "orders.csv"].join("/"),
  ["", "", "server", "share", name, "data", "orders.csv"].join("\\"),
  ["", "", "server", "share", name, "data", "orders.csv"].join("/"),
  ["", "mnt", "repos", name, "data", "orders.csv"].join("/"),
]);
const siblingRelativePathFixtures = siblingRepositoryNames.flatMap((name) => [
  ["..", name, "tools", "service.py"].join("/"),
  [name, "data", "orders.csv"].join("/"),
  `import '../${name}/src/index.ts'`,
  `path = '${name}/config/settings.json'`,
]);
const siblingEnvironmentFixtures = siblingRepositoryNames.map((name) => `AIBI_PROJECT_${name.at(-1)}_PATH`);
const legacyRepositoryNames = ["AIBI项目杂交", "AIBI", "财务报表", "财务报表_bak"];
const legacyAbsolutePathFixtures = legacyRepositoryNames.map((name) => ["C:", "Users", "Administrator", "Documents", name, "data"].join("\\"));
const remoteProjectReferenceFixtures = siblingRepositoryNames.map((name) =>
  ["https:", "", "github.com", "example", name, "tree", "main"].join("/"));
const cleanRoomReferenceFixture = "本文未读取 AIBI-D/E 本地仓库，只借鉴公开的问题拆解思路。";
const cleanRoomDocPath = join(root, "docs", "business-understanding-skills.md");
const cleanRoomDocSource = existsSync(cleanRoomDocPath) ? readFileSync(cleanRoomDocPath, "utf8") : "";
const siblingDetectorCoverage = Boolean(absolutePathRule && relativePathRule && environmentVariableRule) &&
  siblingAbsolutePathFixtures.every((path) => patternMatches(absolutePathRule.pattern, path) && patternMatches(forbiddenProjectPathPattern, path)) &&
  siblingRelativePathFixtures.every((path) => patternMatches(relativePathRule.pattern, path)) &&
  siblingEnvironmentFixtures.every((name) => patternMatches(environmentVariableRule.pattern, name));
const legacyDetectorCoverage = Boolean(absolutePathRule) && legacyAbsolutePathFixtures.every((path) =>
  patternMatches(absolutePathRule.pattern, path) && patternMatches(forbiddenProjectPathPattern, path));
const cleanRoomReferencesRemainAllowed = forbiddenPatterns.every((rule) =>
  !patternMatches(rule.pattern, cleanRoomReferenceFixture) && !patternMatches(rule.pattern, cleanRoomDocSource));
const remoteProjectReferencesRemainAllowed = remoteProjectReferenceFixtures.every((reference) =>
  forbiddenPatterns.every((rule) => !patternMatches(rule.pattern, reference)));
const intentionalNegativeFixtureIsExplicit = intentionalNegativeFixtureReferences.length === 1 &&
  intentionalNegativeFixtureReferences[0]?.file === "scripts/verify-source-intelligence-job.mjs" &&
  intentionalNegativeFixtureReferences[0]?.rule === "absolute-sibling-project-path";

const runtimePathKeys = [
  "AIBI_HYBRID_DB_PATH",
  "AIBI_HYBRID_DUCKDB_PATH",
  "AIBI_BACKUP_ROOT",
  "AIBI_REAL_IMPORT_PATH",
  "AIBI_REAL_IMPORT_FILE",
  "AIBI_REAL_IMPORT_FOLDER",
];
const unsafeRuntimePaths = runtimePathKeys
  .map((key) => ({ key, value: String(process.env[key] ?? "").trim() }))
  .filter((item) => item.value)
  .filter((item) => patternMatches(forbiddenProjectPathPattern, resolve(item.value)));

const checks = [
  {
    label: "git-root-is-aibi-c",
    ok: rootResult.status === 0 && gitRoot === root && root.split(/[\\/]/).at(-1)?.toLowerCase() === "aibi-c",
    detail: { root, gitRoot, status: rootResult.status },
  },
  {
    label: "origin-is-aibi-c",
    ok: remoteResult.status === 0 && /(?:^|[/:])LeoSasion\/AIBI-C(?:\.git)?$/i.test(remote),
    detail: { remote, status: remoteResult.status },
  },
  { label: "package-identity-is-aibi-c", ok: packageJson.name === "aibi-c", detail: packageJson.name },
  { label: "sibling-path-detector-covers-a-b-d-e", ok: siblingDetectorCoverage, detail: { siblingRepositoryNames } },
  { label: "legacy-project-path-detectors-remain-covered", ok: legacyDetectorCoverage, detail: { legacyRepositoryNames } },
  { label: "clean-room-project-references-are-not-paths", ok: cleanRoomReferencesRemainAllowed, detail: { cleanRoomDoc: relative(root, cleanRoomDocPath).replaceAll("\\", "/") } },
  { label: "remote-project-references-are-not-local-paths", ok: remoteProjectReferencesRemainAllowed, detail: { remoteProjectReferenceFixtures } },
  { label: "intentional-negative-fixture-is-explicitly-scoped", ok: intentionalNegativeFixtureIsExplicit, detail: intentionalNegativeFixtureReferences },
  { label: "no-external-symlink", ok: symlinkEscapes.length === 0, detail: symlinkEscapes },
  { label: "no-cross-project-reference", ok: forbiddenReferences.length === 0, detail: forbiddenReferences },
  { label: "runtime-paths-do-not-use-other-projects", ok: unsafeRuntimePaths.length === 0, detail: unsafeRuntimePaths },
];
const failedChecks = checks.filter((check) => !check.ok);

console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-c-repository-isolation-verify/v1",
  generatedBy: "scripts/verify-repository-isolation.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
