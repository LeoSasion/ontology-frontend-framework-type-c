import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { createHash, randomBytes, randomUUID, timingSafeEqual } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { handleAgentApi } from "./agentRoutes";
import { handleAnalysisUnitApi } from "./analysisUnitRoutes";
import { handleExportApi } from "./exportRoutes";
import { DurableJobRuntime } from "./durableJobRuntime";
import { handleJobApi } from "./jobRoutes";
import { handleImportJobApi } from "./importJobRoutes";
import { handleDashboardApi } from "./dashboardRoutes";
import { handleDecisionFrameworkApi } from "./decisionFrameworkRoutes";
import { handleReviewedPublicationApi } from "./reviewedPublicationRoutes";
import { handleSqlServerSnapshotApi } from "./sqlServerSnapshotRoutes";
import { handleModelApi } from "./modelRoutes";
import { handleQueryApi } from "./queryRoutes";
import {
  InvalidJsonBodyError,
  RequestBodyTooLargeError,
  RuntimeCommandLimitError,
  RuntimeHostCapacityError,
  RuntimeHostUnavailableError,
  UnsupportedMediaTypeError,
  readBody,
  runtimeHostHealth,
  runCli,
  sendJson,
  shutdownRuntimeHosts,
  withJsonResponseCapture,
  withRuntimeRequestTrace,
  type JsonValue,
} from "./serverRuntime";
import { handleSourceApi } from "./sourceRoutes";
import { handleSettingsApi } from "./settingsRoutes";
import { handleStatic } from "./staticServer";
import { handleWorkspaceApi } from "./workspaceRoutes";
import { handleWorkspaceRecoveryApi } from "./workspaceRecoveryRoutes";
import { handleWorkflowApi } from "./workflowRoutes";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));

function unquoteEnvValue(value: string) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function loadLocalEnv(projectRoot: string) {
  const envPath = resolve(projectRoot, ".env");
  if (!existsSync(envPath)) return;

  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const separator = trimmed.indexOf("=");
    if (separator <= 0) continue;

    const key = trimmed.slice(0, separator).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) || process.env[key] !== undefined) continue;

    process.env[key] = unquoteEnvValue(trimmed.slice(separator + 1).trim());
  }
}

loadLocalEnv(root);
const configuredPort = Number(process.env.AIBI_API_PORT ?? 8787);
if (!Number.isInteger(configuredPort) || configuredPort < 1 || configuredPort > 65_535) {
  throw new Error("AIBI_API_PORT must be an integer between 1 and 65535");
}
const port = configuredPort;
const host = String(process.env.AIBI_API_HOST ?? "127.0.0.1").trim().toLowerCase();
const loopbackHosts = new Set(["127.0.0.1", "::1", "localhost"]);
if (!loopbackHosts.has(host)) {
  throw new Error("AIBI-C is local-first and only accepts a loopback AIBI_API_HOST in this release");
}
const runtimeToken = randomBytes(32).toString("base64url");
const configuredCorsOrigin = String(process.env.AIBI_CORS_ORIGIN ?? "").trim();
const allowedBrowserOrigins = new Set([
  `http://127.0.0.1:8686`,
  `http://localhost:8686`,
  `http://127.0.0.1:${port}`,
  `http://localhost:${port}`,
  ...(configuredCorsOrigin ? [configuredCorsOrigin] : []),
]);
const cli = (args: string[]) => runCli(root, args);

// A read through the deterministic CLI is the startup compatibility gate.
// New databases are initialized here; legacy or future schemas stop before the API binds.
const startupCompatibility = await cli(["status"]);
if (startupCompatibility.ok !== true) {
  throw new Error("AIBI-C startup compatibility check failed; run `python tools/aibi_cli.py --json status` for the guarded recovery or migration action.");
}
const workspaceRecovery = await cli(["workspace-recovery-reconcile", "--all"]);
if (workspaceRecovery.ok !== true || (Array.isArray(workspaceRecovery.needsAttention) && workspaceRecovery.needsAttention.length > 0)) {
  throw new Error("Workspace recovery reconciliation failed; API startup is fenced until recovery succeeds.");
}
await cli(["job-recover", "--all", "--yes"]);
const importRecovery = await cli(["import-job-recover", "--all"]);
if (importRecovery.ok !== true) {
  throw new Error("Import activation reconciliation failed; API startup is fenced until recovery succeeds.");
}
const sqlServerActivationRecovery = await cli(["sqlserver-adapter-activation-finalize", "--all", "--yes"]);
if (sqlServerActivationRecovery.ok !== true) {
  throw new Error("SQL Server activation reconciliation failed; API startup is fenced until recovery succeeds.");
}
const jobRuntime = new DurableJobRuntime(root, cli);

type IdempotencyEntry = {
  fingerprint: string;
  method: string;
  path: string;
  completedAt: number;
  response: { status: number; body: JsonValue } | null;
  wait: Promise<void>;
  complete: () => void;
};

const idempotencyEntries = new Map<string, IdempotencyEntry>();
const IDEMPOTENCY_TTL_MS = 15 * 60_000;
const IDEMPOTENCY_MAX_ENTRIES = 500;

function expireIdempotencyEntries() {
  const expiresBefore = Date.now() - IDEMPOTENCY_TTL_MS;
  for (const [key, entry] of idempotencyEntries) {
    if (entry.response && entry.completedAt < expiresBefore) idempotencyEntries.delete(key);
  }
}

function reclaimCompletedIdempotencyEntries() {
  for (const [key, entry] of idempotencyEntries) {
    if (idempotencyEntries.size < IDEMPOTENCY_MAX_ENTRIES) break;
    if (entry.response) idempotencyEntries.delete(key);
  }
}

function canonicalJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalJson(item)]),
    );
  }
  return value;
}

function mutationFingerprint(method: string, url: URL, body: Record<string, unknown>) {
  const query = [...url.searchParams.entries()]
    .sort(([leftKey, leftValue], [rightKey, rightValue]) => (
      leftKey.localeCompare(rightKey) || leftValue.localeCompare(rightValue)
    ));
  return createHash("sha256")
    .update(JSON.stringify({ method, path: url.pathname, query, body: canonicalJson(body) }))
    .digest("hex");
}

function isMutationMethod(method: string) {
  return ["POST", "PUT", "PATCH", "DELETE"].includes(method);
}

function loopbackRemoteAddress(request: IncomingMessage) {
  const address = String(request.socket.remoteAddress ?? "").toLowerCase();
  return address === "127.0.0.1" || address === "::1" || address === "::ffff:127.0.0.1";
}

function loopbackHostHeader(request: IncomingMessage) {
  const value = String(request.headers.host ?? "").trim().toLowerCase();
  if (!value) return false;
  try {
    const parsed = new URL(`http://${value}`);
    return loopbackHosts.has(parsed.hostname.replace(/^\[|\]$/g, ""));
  } catch {
    return false;
  }
}

function equalRuntimeToken(candidate: string) {
  const expected = Buffer.from(runtimeToken);
  const received = Buffer.from(candidate);
  return expected.byteLength === received.byteLength && timingSafeEqual(expected, received);
}

function apiBoundaryFailure(request: IncomingMessage) {
  if (!loopbackRemoteAddress(request) || !loopbackHostHeader(request)) {
    return { status: 403, errorCode: "caller-not-loopback", error: "Local API accepts loopback callers only" };
  }
  const origin = String(request.headers.origin ?? "").trim();
  if (origin && !allowedBrowserOrigins.has(origin)) {
    return { status: 403, errorCode: "origin-not-allowed", error: "Browser origin is not allowed" };
  }
  if (String(request.headers["sec-fetch-site"] ?? "").toLowerCase() === "cross-site") {
    return { status: 403, errorCode: "cross-site-request", error: "Cross-site API requests are forbidden" };
  }
  if (!isMutationMethod(String(request.method ?? "GET").toUpperCase())) return null;
  const contentType = String(request.headers["content-type"] ?? "").toLowerCase();
  if (!contentType.startsWith("application/json")) {
    return { status: 415, errorCode: "json-content-type-required", error: "Mutation requests must use application/json" };
  }
  if (origin) {
    if (request.headers["x-requested-with"] !== "aibi-web" || request.headers["x-aibi-envelope-version"] !== "aibi-command/v1") {
      return { status: 403, errorCode: "browser-command-envelope-required", error: "Browser mutation is missing the local command envelope" };
    }
  }
  // A JSON content type is not an identity. Every mutation, including local
  // non-browser automation, must present the server-owned session token before
  // idempotency middleware is allowed to consume its body.
  if (!equalRuntimeToken(String(request.headers["x-aibi-runtime-token"] ?? ""))) {
    return { status: 403, errorCode: "runtime-token-invalid", error: "Local runtime session is missing or expired" };
  }
  return null;
}

type LocalPrincipalRole = "viewer" | "operator" | "owner";

function localPrincipalRole(request: IncomingMessage): LocalPrincipalRole {
  return equalRuntimeToken(String(request.headers["x-aibi-runtime-token"] ?? "")) ? "owner" : "viewer";
}

function minimumRoleForCapability(capability: string): LocalPrincipalRole {
  // v1 is deliberately a single-user local-owner product. We retain
  // capability labels for auditability: loopback callers may inspect state,
  // while every mutation still requires the server-owned owner session token.
  return capability.endsWith(":read") ? "viewer" : "owner";
}

function authorizeLocalCapability(capability: string, request: IncomingMessage) {
  if (apiBoundaryFailure(request) !== null) return false;
  const rank: Record<LocalPrincipalRole, number> = { viewer: 0, operator: 1, owner: 2 };
  return rank[localPrincipalRole(request)] >= rank[minimumRoleForCapability(capability)];
}

async function handleIdempotentMutation(
  request: IncomingMessage,
  response: ServerResponse,
  url: URL,
  task: () => Promise<void>,
) {
  const method = String(request.method ?? "GET").toUpperCase();
  if (!isMutationMethod(method)) {
    await task();
    return;
  }
  const key = String(request.headers["x-idempotency-key"] ?? "").trim();
  const browserMutation = Boolean(request.headers.origin || request.headers["x-requested-with"]);
  if (!key) {
    if (browserMutation) {
      sendJson(response, 400, { ok: false, action: actionForApiPath(url), errorCode: "idempotency-key-required", error: "Browser mutation requires x-idempotency-key" });
      return;
    }
    await task();
    return;
  }
  if (!/^[A-Za-z0-9._:-]{8,160}$/.test(key)) {
    sendJson(response, 400, { ok: false, action: actionForApiPath(url), errorCode: "idempotency-key-invalid", error: "Invalid x-idempotency-key" });
    return;
  }
  const fingerprint = mutationFingerprint(method, url, await readBody(request));
  expireIdempotencyEntries();
  const existing = idempotencyEntries.get(key);
  if (existing) {
    if (existing.method !== method || existing.path !== url.pathname || existing.fingerprint !== fingerprint) {
      sendJson(response, 409, { ok: false, action: actionForApiPath(url), errorCode: "idempotency-key-conflict", error: "Idempotency key was already used for another operation" });
      return;
    }
    await existing.wait;
    if (!existing.response) {
      sendJson(response, 503, { ok: false, action: actionForApiPath(url), errorCode: "idempotency-result-unavailable", error: "Original operation did not produce a replayable response" });
      return;
    }
    response.setHeader("x-idempotency-replayed", "true");
    sendJson(response, existing.response.status, existing.response.body);
    return;
  }
  reclaimCompletedIdempotencyEntries();
  if (idempotencyEntries.size >= IDEMPOTENCY_MAX_ENTRIES) {
    sendJson(response, 429, {
      ok: false,
      action: actionForApiPath(url),
      errorCode: "idempotency-capacity-reached",
      error: "Too many mutation requests are still in progress; retry after one completes",
    });
    return;
  }
  let complete = () => {};
  const entry: IdempotencyEntry = {
    fingerprint,
    method,
    path: url.pathname,
    completedAt: 0,
    response: null,
    wait: new Promise<void>((resolveWait) => { complete = resolveWait; }),
    complete: () => complete(),
  };
  idempotencyEntries.set(key, entry);
  try {
    await withJsonResponseCapture((status, body) => {
      entry.response = { status, body };
      entry.completedAt = Date.now();
      entry.complete();
    }, task);
  } finally {
    if (!entry.response) {
      idempotencyEntries.delete(key);
      entry.complete();
    }
  }
}

function actionForApiPath(url: URL) {
  if (url.pathname.includes("query-table/batch")) return "query-table-batch";
  if (url.pathname.includes("query-table")) return "query-table";
  if (url.pathname.includes("query")) return "query";
  if (url.pathname.includes("evidence") || url.pathname.includes("export")) return "evidence";
  if (url.pathname.includes("views")) return "view";
  if (url.pathname.includes("dashboard")) return "dashboard";
  if (url.pathname.includes("source") || url.pathname.includes("import") || url.pathname.includes("connector")) return "source";
  if (url.pathname.includes("agent") || url.pathname.includes("actions")) return "agent";
  if (url.pathname.includes("analysis-unit") || url.pathname.includes("analysis-snapshot") || url.pathname.includes("metric-monitor") || url.pathname.includes("forecast-readiness") || url.pathname.includes("chart-adapt")) return "analysis";
  if (url.pathname.includes("jobs")) return "job";
  if (url.pathname.includes("context")) return "context";
  if (url.pathname.includes("domain-packs")) return "domain-pack";
  if (url.pathname.includes("analytical-skills")) return "analytical-skill";
  if (url.pathname.includes("preferences") || url.pathname.includes("theme") || url.pathname.includes("config")) return "settings";
  if (url.pathname.includes("workspace")) return "workspace";
  return "api";
}

async function handleApi(request: IncomingMessage, response: ServerResponse, url: URL) {
  if (request.method === "OPTIONS") {
    const boundaryFailure = apiBoundaryFailure(request);
    sendJson(response, boundaryFailure?.status ?? 200, boundaryFailure ? { ok: false, action: "preflight", ...boundaryFailure } : { ok: true });
    return;
  }

  if (url.pathname === "/api/live" && request.method === "GET") {
    sendJson(response, 200, { ok: true, schema: "aibi-live/v1" });
    return;
  }

  if (url.pathname === "/api/ready" && request.method === "GET") {
    const runtime = runtimeHostHealth(root);
    sendJson(response, runtime.ok ? 200 : 503, { ok: runtime.ok, schema: "aibi-ready/v1", runtime });
    return;
  }

  if (url.pathname === "/api/runtime-session" && request.method === "GET") {
    sendJson(response, 200, {
      ok: true,
      schema: "aibi-runtime-session/v1",
      role: "owner",
      trustBoundary: "same-local-user",
      token: runtimeToken,
    });
    return;
  }

  if (await handleWorkspaceApi({ cli, port, request, response, url })) {
    return;
  }

  if (await handleDashboardApi({ cli, request, response, url })) {
    return;
  }

  if (await handleImportJobApi({
    authorize: authorizeLocalCapability,
    cancelJobProcess: (jobKey) => jobRuntime.cancel(jobKey),
    cli,
    request,
    response,
    resumeImportJob: (jobKey) => jobRuntime.resumeImport(jobKey),
    startImportJob: (body) => jobRuntime.startImport(body),
    url,
  })) {
    return;
  }

  if (await handleSourceApi({
    cli,
    request,
    response,
    startSourceIntelligenceJob: (body) => jobRuntime.startSourceIntelligence(body),
    url,
  })) {
    return;
  }

  if (await handleSettingsApi({ cli, request, response, url })) {
    return;
  }

  if (await handleWorkspaceRecoveryApi({ authorize: authorizeLocalCapability, cli, request, response, url })) {
    return;
  }

  if (await handleModelApi({ cli, request, response, url })) {
    return;
  }

  if (await handleQueryApi({ cli, request, response, url })) {
    return;
  }

  if (await handleAgentApi({ cli, request, response, root, url })) {
    return;
  }

  if (await handleAnalysisUnitApi({ cli, request, response, url })) {
    return;
  }

  if (await handleDecisionFrameworkApi({ authorize: authorizeLocalCapability, cli, request, response, url })) {
    return;
  }

  if (await handleReviewedPublicationApi({ authorize: authorizeLocalCapability, cli, request, response, url })) {
    return;
  }

  if (await handleSqlServerSnapshotApi({
    authorize: authorizeLocalCapability,
    cli,
    request,
    response,
    startActivationJob: (body) => jobRuntime.startSqlServerActivation(body),
    url,
  })) {
    return;
  }

  if (await handleExportApi({ cli, request, response, url })) {
    return;
  }

  if (await handleWorkflowApi({ cli, request, response, url })) {
    return;
  }

  if (await handleJobApi({
    cancelJobProcess: (jobKey) => jobRuntime.cancel(jobKey),
    cli,
    request,
    response,
    url,
  })) {
    return;
  }

  sendJson(response, 404, { ok: false, action: actionForApiPath(url), error: `No route for ${request.method} ${url.pathname}` });
}

let serverDraining = false;

const server = createServer(async (request, response) => {
  const startedAt = Date.now();
  const incomingRequestId = String(request.headers["x-request-id"] ?? "");
  const requestId = /^[A-Za-z0-9._-]{1,100}$/.test(incomingRequestId) ? incomingRequestId : randomUUID();
  response.setHeader("x-request-id", requestId);
  response.setHeader("x-content-type-options", "nosniff");
  response.setHeader("x-frame-options", "DENY");
  response.setHeader("referrer-policy", "no-referrer");
  const url = new URL(request.url ?? "/", "http://127.0.0.1");
  response.once("finish", () => {
    console.log(JSON.stringify({
      event: "http_request",
      requestId,
      method: request.method ?? "GET",
      path: url.pathname,
      status: response.statusCode,
      durationMs: Date.now() - startedAt,
    }));
  });
  if (serverDraining) {
    response.setHeader("connection", "close");
    sendJson(response, 503, {
      ok: false,
      action: url.pathname.startsWith("/api/") ? actionForApiPath(url) : "static",
      errorCode: "server-draining",
      error: "The local service is shutting down and is not accepting new work.",
    });
    return;
  }
  try {
    if (url.pathname.startsWith("/api/")) {
      const boundaryFailure = apiBoundaryFailure(request);
      if (boundaryFailure) {
        sendJson(response, boundaryFailure.status, { ok: false, action: actionForApiPath(url), ...boundaryFailure });
        return;
      }
      await withRuntimeRequestTrace(requestId, () => handleIdempotentMutation(request, response, url, () => handleApi(request, response, url)));
      return;
    }
    await handleStatic(request, response, url.pathname, root);
  } catch (error) {
    const status = error instanceof RequestBodyTooLargeError
      ? 413
      : error instanceof InvalidJsonBodyError
        ? 400
        : error instanceof UnsupportedMediaTypeError
          ? 415
      : error instanceof RuntimeCommandLimitError
            ? 504
            : error instanceof RuntimeHostCapacityError
              ? 429
              : error instanceof RuntimeHostUnavailableError
                ? 503
            : 500;
    const knownError = error instanceof RequestBodyTooLargeError
      || error instanceof InvalidJsonBodyError
      || error instanceof UnsupportedMediaTypeError;
    const errorCode = error instanceof RuntimeCommandLimitError
      ? "runtime-command-limit"
      : error instanceof RuntimeHostCapacityError
        ? "runtime-host-capacity"
        : error instanceof RuntimeHostUnavailableError
          ? "runtime-host-unavailable"
          : status >= 500
            ? "internal-server-error"
            : "request-invalid";
    const publicError = knownError
      ? (error as Error).message
      : error instanceof RuntimeCommandLimitError
        ? "The local analysis command exceeded its execution limit."
        : error instanceof RuntimeHostCapacityError
          ? "The local analysis queue is at capacity; retry shortly."
          : error instanceof RuntimeHostUnavailableError
            ? "The local analysis runtime is unavailable or requires recovery."
            : "The request could not be completed safely.";
    sendJson(response, status, {
      ok: false,
      action: url.pathname.startsWith("/api/") ? actionForApiPath(url) : "static",
      errorCode,
      error: publicError,
    });
  }
});

server.listen(port, host, () => {
  console.log(`AIBI-C API listening on http://${host}:${port}`);
});

let shutdownPromise: Promise<void> | null = null;

function shutdownServer() {
  if (shutdownPromise) return shutdownPromise;
  serverDraining = true;
  const serverClose = new Promise<void>((resolveClose, rejectClose) => {
    server.close((error) => {
      if (error) rejectClose(error);
      else resolveClose();
    });
  });
  shutdownPromise = (async () => {
    // Stop accepting work first, then let already accepted requests finish
    // before their Durable Job and Runtime Host dependencies are drained.
    await serverClose;
    await jobRuntime.shutdown();
    await shutdownRuntimeHosts();
  })();
  return shutdownPromise;
}

function exitAfterShutdown() {
  void shutdownServer().then(
    () => process.exit(0),
    (error) => {
      console.error(JSON.stringify({
        event: "server_shutdown_failed",
        error: error instanceof Error ? error.message : String(error),
      }));
      process.exit(1);
    },
  );
}

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, exitAfterShutdown);
}

// An IPC channel exists only when a trusted parent process explicitly creates
// one. Verification uses it to exercise the real graceful shutdown path on
// Windows, where SIGTERM and taskkill are forceful or permission-dependent.
if (typeof process.send === "function") {
  process.on("message", (message: unknown) => {
    if (!message || typeof message !== "object" || (message as { type?: unknown }).type !== "aibi-runtime-shutdown") return;
    exitAfterShutdown();
  });
}
