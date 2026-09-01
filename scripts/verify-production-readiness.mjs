import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const packageJson = JSON.parse(read("package.json"));
const viteConfig = read("vite.config.ts");
const serverIndex = read("server/index.ts");
const serverRuntime = read("server/serverRuntime.ts");
const envExample = read(".env.example");
const gitignore = read(".gitignore");
const workflow = read(".github/workflows/ci.yml");
const configService = read("tools/config_command_service.py");
const backupScript = read("scripts/backup-local-data.mjs");
const restoreScript = read("scripts/restore-local-data.mjs");
const schemaSource = read("tools/bi_cli_schema.py");
const coreSource = read("tools/bi_cli_core.py");
const snapshotScript = read("scripts/local-data-snapshot.mjs");
const restoreTransactionScript = read("scripts/local-data-restore-transaction.mjs");

function check(label, ok, detail) {
  return { label, ok: Boolean(ok), detail };
}

const checks = [
  check("loopback-api-default", serverIndex.includes('process.env.AIBI_API_HOST ?? "127.0.0.1"') && serverIndex.includes("loopbackHosts") && !serverIndex.includes('server.listen(port, "0.0.0.0"'), "API defaults to loopback and rejects non-loopback hosts."),
  check("loopback-ui-default", packageJson.scripts?.["dev:ui"] === "vite" && viteConfig.includes('host: "127.0.0.1"') && packageJson.scripts?.preview?.includes("--host 127.0.0.1"), "Development and preview UI bind only to loopback."),
  check("cors-not-wildcard", !serverRuntime.includes('"access-control-allow-origin": "*"') && serverRuntime.includes("AIBI_CORS_ORIGIN"), "Cross-origin access is disabled unless one explicit origin is configured."),
  check("request-size-limit", serverRuntime.includes("configuredMaxRequestBodyBytes") && serverRuntime.includes("bodyBytes > maxRequestBodyBytes"), "JSON request bodies have a bounded size and read configuration after local .env loading."),
  check("request-errors-are-specific", serverRuntime.includes("RequestBodyTooLargeError")
    && serverRuntime.includes("InvalidJsonBodyError")
    && serverRuntime.includes("UnsupportedMediaTypeError")
    && serverIndex.includes("error instanceof RequestBodyTooLargeError")
    && serverIndex.includes("error instanceof InvalidJsonBodyError")
    && serverIndex.includes("error instanceof UnsupportedMediaTypeError")
    && serverIndex.includes("? 413")
    && serverIndex.includes("? 400")
    && serverIndex.includes("? 415"), "Oversized, invalid, and unsupported JSON requests return specific client errors."),
  check("request-trace-and-security-headers", serverIndex.includes('response.setHeader("x-request-id"') && serverIndex.includes('response.setHeader("x-content-type-options", "nosniff")') && serverIndex.includes('response.setHeader("x-frame-options", "DENY")'), "Responses expose a request ID and defensive browser headers."),
  check("safe-env-example", envExample.includes("AIBI_API_HOST=127.0.0.1") && envExample.includes("AIBI_MAX_BODY_BYTES=1048576") && envExample.includes("AIBI_CORS_ORIGIN="), "Documented defaults preserve the local-only boundary."),
  check("local-env-untracked", /^\.env$/m.test(gitignore) || /^\.env\*/m.test(gitignore), "Local secrets stay outside Git."),
  check("config-backup-and-redaction", configService.includes("shutil.copy2(DB_PATH, backup_path)") && configService.includes("redact_secret_value"), "Config restore creates a backup and redacts secret-like values."),
  check("data-backup-manifest-v2", snapshotScript.includes('BACKUP_SCHEMA = "aibi-local-backup/v2"') && snapshotScript.includes("sha256") && snapshotScript.includes("loadLocalEnv") && backupScript.includes("assertLocalServiceStopped") && snapshotScript.includes("dataset-object"), "Local v2 backup covers both databases and content-addressed Parquet objects with checksums while services are stopped."),
  check("data-restore-guard", restoreScript.includes('args.has("--confirm")')
    && restoreScript.includes("verifyManifestFiles")
    && restoreScript.includes("createRestoreTransaction")
    && restoreScript.includes("recoverRestoreTransactions")
    && restoreTransactionScript.includes("createSafetySnapshot")
    && restoreTransactionScript.includes('phase = "installing"')
    && restoreTransactionScript.includes('installMode === "rollback"'), "Restore previews by default, validates the complete snapshot, and uses a durable safety-backed transaction with crash recovery."),
  check("storage-generation-clean-break", !packageJson.scripts?.["migrate:local"]
    && schemaSource.includes("CURRENT_SQLITE_SCHEMA_VERSION = 18")
    && schemaSource.includes("CURRENT_DUCKDB_SCHEMA_VERSION = 2")
    && coreSource.includes("aibi_control_v2.sqlite")
    && coreSource.includes("aibi_catalog_v2.duckdb"), "Storage v2 uses isolated paths, exact schema guards, and exposes no in-place migration command."),
  check("startup-compatibility-fails-before-reconciliation", serverIndex.includes('const startupCompatibility = await cli(["status"])')
    && serverIndex.includes("startupCompatibility.ok !== true")
    && serverIndex.indexOf("startupCompatibility.ok !== true") < serverIndex.indexOf('workspace-recovery-reconcile'), "The API reports an incompatible local schema before any recovery command can misclassify the startup failure."),
  check("ci-browser-smoke", workflow.includes("Verify complete browser paths")
    && workflow.includes("npm run verify:ui")
    && workflow.includes("Upload browser evidence")
    && workflow.includes("Stop local services")
    && workflow.includes("if: always()"), "CI exercises the complete rendered browser suite, uploads evidence, and always stops services."),
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
