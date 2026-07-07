import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { handleAgentApi } from "./agentRoutes";
import { handleDashboardApi } from "./dashboardRoutes";
import { handleModelApi } from "./modelRoutes";
import { handleQueryApi } from "./queryRoutes";
import { runCli, sendJson } from "./serverRuntime";
import { handleSourceApi } from "./sourceRoutes";
import { handleSettingsApi } from "./settingsRoutes";
import { handleStatic } from "./staticServer";
import { handleWorkspaceApi } from "./workspaceRoutes";

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
const port = Number(process.env.AIBI_API_PORT ?? 8787);
const cli = (args: string[]) => runCli(root, args);

function actionForApiPath(url: URL) {
  if (url.pathname.includes("query-table")) return "query-table";
  if (url.pathname.includes("query")) return "query";
  if (url.pathname.includes("views")) return "view";
  if (url.pathname.includes("dashboard")) return "dashboard";
  if (url.pathname.includes("source") || url.pathname.includes("import") || url.pathname.includes("connector")) return "source";
  if (url.pathname.includes("agent") || url.pathname.includes("actions")) return "agent";
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

  if (await handleDashboardApi({ cli, request, response, root, url })) {
    return;
  }

  if (await handleSourceApi({ cli, request, response, url })) {
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

  if (await handleAgentApi({ cli, request, response, url })) {
    return;
  }

  sendJson(response, 404, { ok: false, action: actionForApiPath(url), error: `No route for ${request.method} ${url.pathname}` });
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "127.0.0.1"}`);
  try {
    if (url.pathname.startsWith("/api/")) {
      await handleApi(request, response, url);
      return;
    }
    await handleStatic(response, url.pathname, root);
  } catch (error) {
    sendJson(response, 500, {
      ok: false,
      action: url.pathname.startsWith("/api/") ? actionForApiPath(url) : "static",
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

server.listen(port, "0.0.0.0", () => {
  console.log(`AIBI Hybrid API listening on http://127.0.0.1:${port}`);
});
