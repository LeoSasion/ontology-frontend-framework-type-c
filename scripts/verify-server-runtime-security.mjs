import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
let service = null;
let serviceLogs = "";
let tempRoot = null;

async function freePort() {
  const probe = createServer();
  await new Promise((resolveListen, reject) => {
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", resolveListen);
  });
  const address = probe.address();
  const port = typeof address === "object" && address ? address.port : 0;
  await new Promise((resolveClose) => probe.close(resolveClose));
  if (!port) throw new Error("Unable to allocate an isolated API port");
  return port;
}

async function waitForApi(url, timeoutMs = 60_000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (service?.exitCode !== null) throw new Error(`Isolated API exited early (${service?.exitCode})\n${serviceLogs}`);
    try {
      const response = await fetch(`${url}/api/live`);
      if (response.ok) return;
    } catch {
      // Startup is expected to race the first few probes.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 200));
  }
  throw new Error(`Isolated API did not become live\n${serviceLogs}`);
}

const configuredBaseUrl = String(process.env.AIBI_API_BASE_URL ?? "").trim();
let apiBaseUrl = configuredBaseUrl;
if (!apiBaseUrl) {
  const port = await freePort();
  apiBaseUrl = `http://127.0.0.1:${port}`;
  tempRoot = mkdtempSync(join(tmpdir(), "aibi-server-security-"));
  service = spawn(process.execPath, ["--import", "tsx", "server/index.ts"], {
    cwd: root,
    env: {
      ...process.env,
      AIBI_API_HOST: "127.0.0.1",
      AIBI_API_PORT: String(port),
      AIBI_CORS_ORIGIN: "",
      AIBI_HYBRID_DB_PATH: join(tempRoot, "security.sqlite"),
      AIBI_HYBRID_DUCKDB_PATH: join(tempRoot, "security.duckdb"),
      AIBI_EVIDENCE_BUNDLE_ROOT: join(tempRoot, "evidence"),
      PYTHONIOENCODING: "utf-8",
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  service.stdout.setEncoding("utf8");
  service.stderr.setEncoding("utf8");
  service.stdout.on("data", (chunk) => { serviceLogs = `${serviceLogs}${chunk}`.slice(-20_000); });
  service.stderr.on("data", (chunk) => { serviceLogs = `${serviceLogs}${chunk}`.slice(-20_000); });
  await waitForApi(apiBaseUrl);
}

function check(label, ok, detail) {
  return { label, ok: Boolean(ok), detail };
}

try {
  const healthResponse = await fetch(`${apiBaseUrl}/api/health`, {
    headers: { "x-request-id": "aibi-security-check" },
  });
  const health = await healthResponse.json();
  const optionsResponse = await fetch(`${apiBaseUrl}/api/health`, {
    method: "OPTIONS",
    headers: { origin: "https://untrusted.invalid" },
  });
  const untrustedOriginResponse = await fetch(`${apiBaseUrl}/api/health`, {
    headers: { origin: "https://untrusted.invalid" },
  });
  const invalidJsonResponse = await fetch(`${apiBaseUrl}/api/agent/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{invalid",
  });
  const invalidJson = await invalidJsonResponse.json();
  const oversizedResponse = await fetch(`${apiBaseUrl}/api/agent/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt: "x".repeat(1_100_000) }),
  });
  const oversized = await oversizedResponse.json();
  const sessionResponse = await fetch(`${apiBaseUrl}/api/runtime-session`);
  const session = await sessionResponse.json();
  const browserHeaders = {
    "content-type": "application/json",
    origin: apiBaseUrl,
    "x-requested-with": "aibi-web",
    "x-aibi-envelope-version": "aibi-command/v1",
    "x-aibi-runtime-token": String(session.token ?? ""),
  };
  const missingIdempotency = await fetch(`${apiBaseUrl}/api/query`, {
    method: "POST",
    headers: browserHeaders,
    body: JSON.stringify({ table: "missing_table", measure: "*", aggregation: "count" }),
  });
  const idempotencyHeaders = { ...browserHeaders, "x-idempotency-key": "security-runtime-query-1" };
  const firstMutation = await fetch(`${apiBaseUrl}/api/query`, {
    method: "POST",
    headers: idempotencyHeaders,
    body: JSON.stringify({ table: "missing_table", measure: "*", aggregation: "count" }),
  });
  const secondMutation = await fetch(`${apiBaseUrl}/api/query`, {
    method: "POST",
    headers: idempotencyHeaders,
    body: JSON.stringify({ table: "missing_table", measure: "*", aggregation: "count" }),
  });
  const conflictingMutation = await fetch(`${apiBaseUrl}/api/query`, {
    method: "POST",
    headers: idempotencyHeaders,
    body: JSON.stringify({ table: "another_missing_table", measure: "*", aggregation: "count" }),
  });
  const conflictingPayload = await conflictingMutation.json();

  const checks = [
    check("health-readable", healthResponse.ok && health.ok === true, { status: healthResponse.status }),
    check("request-id-preserved", healthResponse.headers.get("x-request-id") === "aibi-security-check", healthResponse.headers.get("x-request-id")),
    check("security-headers-present", healthResponse.headers.get("x-content-type-options") === "nosniff" && healthResponse.headers.get("x-frame-options") === "DENY" && healthResponse.headers.get("referrer-policy") === "no-referrer", Object.fromEntries(["x-content-type-options", "x-frame-options", "referrer-policy"].map((name) => [name, healthResponse.headers.get(name)]))),
    check("cors-disabled-by-default", !healthResponse.headers.get("access-control-allow-origin") && !optionsResponse.headers.get("access-control-allow-origin"), { get: healthResponse.headers.get("access-control-allow-origin"), options: optionsResponse.headers.get("access-control-allow-origin") }),
    check("untrusted-origin-rejected", untrustedOriginResponse.status === 403, untrustedOriginResponse.status),
    check("invalid-json-rejected", invalidJsonResponse.status === 400 && String(invalidJson.error ?? "").includes("valid JSON"), { status: invalidJsonResponse.status, error: invalidJson.error }),
    check("oversized-body-rejected", oversizedResponse.status === 413 && String(oversized.error ?? "").includes("exceeds"), { status: oversizedResponse.status, error: oversized.error }),
    check("runtime-session-token-issued", sessionResponse.ok && String(session.token ?? "").length >= 32, { status: sessionResponse.status }),
    check("browser-idempotency-required", missingIdempotency.status === 400, missingIdempotency.status),
    check("idempotency-result-replayed", secondMutation.status === firstMutation.status && secondMutation.headers.get("x-idempotency-replayed") === "true", { first: firstMutation.status, second: secondMutation.status, replayed: secondMutation.headers.get("x-idempotency-replayed") }),
    check("idempotency-key-binds-request-content", conflictingMutation.status === 409 && conflictingPayload.errorCode === "idempotency-key-conflict", { status: conflictingMutation.status, payload: conflictingPayload }),
  ];

  const failedChecks = checks.filter((item) => !item.ok);
  const receipt = {
    ok: failedChecks.length === 0,
    schema: "aibi-server-runtime-security/v1",
    generatedBy: "scripts/verify-server-runtime-security.mjs",
    apiBaseUrl,
    isolatedService: !configuredBaseUrl,
    checks,
    failedChecks,
  };

  console.log(JSON.stringify(receipt, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  if (service && service.exitCode === null) {
    service.kill("SIGTERM");
    await Promise.race([
      new Promise((resolveExit) => service.once("exit", resolveExit)),
      new Promise((resolveTimeout) => setTimeout(resolveTimeout, 5_000)),
    ]);
  }
  if (tempRoot) {
    rmSync(tempRoot, {
      recursive: true,
      force: true,
      maxRetries: 10,
      retryDelay: 200,
    });
  }
}
