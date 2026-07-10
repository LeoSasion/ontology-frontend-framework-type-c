import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const packageJson = JSON.parse(read("package.json"));
const serverIndex = read("server/index.ts");
const serverRuntime = read("server/serverRuntime.ts");
const envExample = read(".env.example");
const gitignore = read(".gitignore");
const workflow = read(".github/workflows/ci.yml");
const configService = read("tools/config_command_service.py");
const backupScript = read("scripts/backup-local-data.mjs");
const restoreScript = read("scripts/restore-local-data.mjs");
const snapshotScript = read("scripts/local-data-snapshot.mjs");

function check(label, ok, detail) {
  return { label, ok: Boolean(ok), detail };
}

const checks = [
  check("loopback-api-default", serverIndex.includes('process.env.AIBI_API_HOST ?? "127.0.0.1"') && serverIndex.includes("loopbackHosts") && !serverIndex.includes('server.listen(port, "0.0.0.0"'), "API defaults to loopback and rejects non-loopback hosts."),
  check("loopback-ui-default", packageJson.scripts?.["dev:ui"]?.includes("--host 127.0.0.1") && packageJson.scripts?.preview?.includes("--host 127.0.0.1"), "Development and preview UI bind only to loopback."),
  check("cors-not-wildcard", !serverRuntime.includes('"access-control-allow-origin": "*"') && serverRuntime.includes("AIBI_CORS_ORIGIN"), "Cross-origin access is disabled unless one explicit origin is configured."),
  check("request-size-limit", serverRuntime.includes("configuredMaxRequestBodyBytes") && serverRuntime.includes("bodyBytes > maxRequestBodyBytes"), "JSON request bodies have a bounded size and read configuration after local .env loading."),
  check("request-errors-are-specific", serverRuntime.includes("RequestBodyTooLargeError") && serverRuntime.includes("InvalidJsonBodyError") && serverIndex.includes("status = error instanceof RequestBodyTooLargeError ? 413"), "Oversized and invalid JSON requests return specific client errors."),
  check("request-trace-and-security-headers", serverIndex.includes('response.setHeader("x-request-id"') && serverIndex.includes('response.setHeader("x-content-type-options", "nosniff")') && serverIndex.includes('response.setHeader("x-frame-options", "DENY")'), "Responses expose a request ID and defensive browser headers."),
  check("safe-env-example", envExample.includes("AIBI_API_HOST=127.0.0.1") && envExample.includes("AIBI_MAX_BODY_BYTES=1048576") && envExample.includes("AIBI_CORS_ORIGIN="), "Documented defaults preserve the local-only boundary."),
  check("local-env-untracked", /^\.env$/m.test(gitignore) || /^\.env\*/m.test(gitignore), "Local secrets stay outside Git."),
  check("config-backup-and-redaction", configService.includes("shutil.copy2(DB_PATH, backup_path)") && configService.includes("redact_secret_value"), "Config restore creates a backup and redacts secret-like values."),
  check("data-backup-manifest", backupScript.includes('schema: "aibi-local-backup/v1"') && snapshotScript.includes("sha256") && snapshotScript.includes("loadLocalEnv") && backupScript.includes("assertLocalServiceStopped"), "Local database backup reads the active local configuration, requires stopped services, and writes checksums."),
  check("data-restore-guard", restoreScript.includes('args.has("--confirm")') && restoreScript.includes("verifyManifestFiles") && restoreScript.includes("createSafetyBackup"), "Restore previews by default, verifies checksums, and preserves current files before writing."),
  check("ci-browser-smoke", workflow.includes("Verify browser smoke paths") && workflow.includes("npm run verify:ui-visual") && workflow.includes("npm run verify:ui-empty") && workflow.includes("if: always()"), "CI exercises rendered empty and responsive flows and always stops services."),
  check("ci-runtime-security", workflow.includes("Verify server security runtime") && workflow.includes("npm run verify:security-runtime"), "CI validates runtime security headers, CORS, and request limits."),
  check("ci-production-gate", packageJson.scripts?.["verify:ci"]?.includes("npm run verify:production"), "Production readiness is part of the CI command."),
];

const failedChecks = checks.filter((item) => !item.ok);
const receipt = {
  ok: failedChecks.length === 0,
  schema: "aibi-production-readiness/v1",
  generatedBy: "scripts/verify-production-readiness.mjs",
  checks,
  failedChecks,
};

console.log(JSON.stringify(receipt, null, 2));
if (failedChecks.length) process.exitCode = 1;
