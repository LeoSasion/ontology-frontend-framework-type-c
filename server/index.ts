import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { randomUUID } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { handleAgentApi } from "./agentRoutes";
import { handleAnalysisUnitApi } from "./analysisUnitRoutes";
import { handleExportApi } from "./exportRoutes";
import { DurableJobRuntime } from "./durableJobRuntime";
import { handleJobApi } from "./jobRoutes";
import { handleDashboardApi } from "./dashboardRoutes";
import { handleModelApi } from "./modelRoutes";
import { handleQueryApi } from "./queryRoutes";
import { InvalidJsonBodyError, RequestBodyTooLargeError, runCli, sendJson } from "./serverRuntime";
import { handleSourceApi } from "./sourceRoutes";
import { handleSettingsApi } from "./settingsRoutes";
import { handleStatic } from "./staticServer";
import { handleWorkspaceApi } from "./workspaceRoutes";
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
const cli = (args: string[]) => runCli(root, args);

// A read through the deterministic CLI is the startup compatibility gate.
// New databases are initialized here; legacy or future schemas stop before the API binds.
await cli(["status"]);
await cli(["job-recover", "--all", "--yes"]);
const jobRuntime = new DurableJobRuntime(root, cli);

function actionForApiPath(url: URL) {
  if (url.pathname.includes("query-table")) return "query-table";
  if (url.pathname.includes("query")) return "query";
  if (url.pathname.includes("evidence") || url.pathname.includes("export")) return "evidence";
  if (url.pathname.includes("views")) return "view";
  if (url.pathname.includes("dashboard")) return "dashboard";
  if (url.pathname.includes("source") || url.pathname.includes("import") || url.pathname.includes("connector")) return "source";
  if (url.pathname.includes("agent") || url.pathname.includes("actions")) return "agent";
  if (url.pathname.includes("analysis-unit") || url.pathname.includes("forecast-readiness") || url.pathname.includes("chart-adapt")) return "analysis";
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
    sendJson(response, 200, { ok: true });
    return;
  }

  if (await handleWorkspaceApi({ cli, port, request, response, url })) {
    return;
  }

  if (await handleDashboardApi({ cli, request, response, url })) {
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
  try {
    if (url.pathname.startsWith("/api/")) {
      await handleApi(request, response, url);
      return;
    }
    await handleStatic(response, url.pathname, root);
  } catch (error) {
    const status = error instanceof RequestBodyTooLargeError ? 413 : error instanceof InvalidJsonBodyError ? 400 : 500;
    sendJson(response, status, {
      ok: false,
      action: url.pathname.startsWith("/api/") ? actionForApiPath(url) : "static",
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

server.listen(port, host, () => {
  console.log(`AIBI-C API listening on http://${host}:${port}`);
});

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => {
    void (async () => {
      await jobRuntime.shutdown();
      server.close(() => process.exit(0));
    })();
  });
}
