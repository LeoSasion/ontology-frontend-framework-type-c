import { lstatSync, readFileSync, readdirSync, realpathSync } from "node:fs";
import { extname, join, relative, resolve, sep } from "node:path";
import { spawnSync } from "node:child_process";

const root = resolve(process.cwd());
const ignoredDirectories = new Set([".git", "node_modules", "dist", "coverage", "data"]);
const textExtensions = new Set([".cjs", ".css", ".env", ".example", ".html", ".js", ".json", ".jsx", ".md", ".mjs", ".py", ".ps1", ".ts", ".tsx", ".txt", ".yaml", ".yml"]);
const forbiddenPatterns = [
  {
    id: "absolute-sibling-project-path",
    pattern: /[A-Za-z]:[\\/][^\r\n"']*?[\\/](?:AIBI-B|AIBI项目杂交|AIBI|财务报表(?:_bak)?)(?=[\\/])/giu,
  },
  {
    id: "relative-aibi-b-data-path",
    pattern: /AIBI-B[\\/]data[\\/]/giu,
  },
  {
    id: "legacy-cross-project-environment-variable",
    pattern: /AIBI_PROJECT_[AB]_PATH/gu,
  },
];

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

const rootResult = git(["rev-parse", "--show-toplevel"]);
const remoteResult = git(["remote", "get-url", "origin"]);
const gitRoot = resolve(String(rootResult.stdout ?? "").trim());
const remote = String(remoteResult.stdout ?? "").trim().replace(/\/$/, "");
const packageJson = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const files = [];
const symlinkEscapes = [];
walk(root, files, symlinkEscapes);

const forbiddenReferences = [];
for (const path of files.filter(isTextFile)) {
  const content = readFileSync(path, "utf8");
  for (const rule of forbiddenPatterns) {
    rule.pattern.lastIndex = 0;
    for (const match of content.matchAll(rule.pattern)) {
      const line = content.slice(0, match.index).split(/\r?\n/).length;
      forbiddenReferences.push({
        rule: rule.id,
        file: relative(root, path).replaceAll("\\", "/"),
        line,
        value: match[0],
      });
    }
  }
}

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
  .filter((item) => /[\\/](?:AIBI-B|AIBI项目杂交|AIBI|财务报表(?:_bak)?)(?:[\\/]|$)/iu.test(resolve(item.value)));

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
