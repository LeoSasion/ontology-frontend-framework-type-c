import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

export type SqlServerSnapshotCapability =
  | "connector:sqlserver:read"
  | "connector:sqlserver:inspect"
  | "connector:sqlserver:snapshot"
  | "connector:sqlserver:activate";

export type SqlServerSnapshotRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  startActivationJob?: (body: Record<string, unknown>) => Promise<Record<string, unknown>>;
  authorize: (capability: SqlServerSnapshotCapability, request: IncomingMessage) => boolean | Promise<boolean>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

const CONNECTOR_KEY = /^[A-Za-z0-9_-]{1,64}$/;
const FINGERPRINT = /^[a-f0-9]{64}$/;
const POST_PATHS = new Set([
  "/api/connectors/sqlserver/test",
  "/api/connectors/sqlserver/discover",
  "/api/connectors/sqlserver/preview",
  "/api/connectors/sqlserver/plan",
  "/api/connectors/sqlserver/snapshot",
  "/api/connectors/sqlserver/activate",
]);

function requestKey(request: IncomingMessage, body: Record<string, unknown>) {
  const header = request.headers["x-idempotency-key"];
  const headerValue = Array.isArray(header) ? header[0] : header;
  return String(body.requestKey ?? headerValue ?? "").trim();
}
function rejectForbiddenSurface(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(rejectForbiddenSurface);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value as Record<string, unknown>).some(([key, nested]) => (
    /^(sql|query|statement|connectionString|password|credentialRef)$/i.test(key) || rejectForbiddenSurface(nested)
  ));
}

async function authorized(
  options: SqlServerSnapshotRoutesOptions,
  capability: SqlServerSnapshotCapability,
) {
  if (await options.authorize(capability, options.request)) return true;
  sendJson(options.response, 403, {
    ok: false,
    code: "SQLSERVER_CAPABILITY_DENIED",
    error: "The current caller cannot use this SQL Server adapter capability.",
  });
  return false;
}

function connectorInput(body: Record<string, unknown>, response: ServerResponse) {
  const connector = String(body.connectorKey ?? body.connector ?? "").trim();
  if (!CONNECTOR_KEY.test(connector)) {
    sendJson(response, 400, { ok: false, code: "SQLSERVER_CONNECTOR_KEY_INVALID", error: "A valid connectorKey is required." });
    return null;
  }
  if (rejectForbiddenSurface(body)) {
    sendJson(response, 400, {
      ok: false,
      code: "SQLSERVER_FORBIDDEN_INPUT_SURFACE",
      error: "SQL text, connection strings, credentials, and Secret Refs are not accepted by this API.",
    });
    return null;
  }
  return connector;
}

function resultStatus(result: Record<string, unknown>) {
  if (result.ok === false) return 409;
  if (result.requiresConfirmation === true) return 202;
  return 200;
}

export async function handleSqlServerSnapshotApi(options: SqlServerSnapshotRoutesOptions) {
  const { cli, request, response, url } = options;
  if (!url.pathname.startsWith("/api/connectors/sqlserver/")) return false;

  if (url.pathname === "/api/connectors/sqlserver/probe" && request.method === "GET") {
    if (!await authorized(options, "connector:sqlserver:read")) return true;
    const args = ["sqlserver-adapter-probe"];
    const connector = url.searchParams.get("connector");
    if (connector && !CONNECTOR_KEY.test(connector)) {
      sendJson(response, 400, { ok: false, code: "SQLSERVER_CONNECTOR_KEY_INVALID", error: "connector must be a valid connector key." });
      return true;
    }
    if (connector) args.push("--connector", connector);
    const result = await cli(args);
    sendJson(response, resultStatus(result), result);
    return true;
  }

  if (url.pathname === "/api/connectors/sqlserver/activation-status" && request.method === "GET") {
    if (!await authorized(options, "connector:sqlserver:read")) return true;
    const connector = String(url.searchParams.get("connector") ?? "").trim();
    const workspaceId = String(url.searchParams.get("workspace") ?? "").trim();
    const key = String(url.searchParams.get("requestKey") ?? "").trim();
    const expectedPlan = String(url.searchParams.get("expectedPlan") ?? "").trim();
    const expectedManifest = String(url.searchParams.get("expectedManifest") ?? "").trim();
    if (!CONNECTOR_KEY.test(connector) || !workspaceId || workspaceId.length > 160 || !key || key.length > 160 || !FINGERPRINT.test(expectedPlan) || !FINGERPRINT.test(expectedManifest)) {
      sendJson(response, 400, {
        ok: false,
        code: "SQLSERVER_ACTIVATION_BINDING_REQUIRED",
        error: "Activation status requires connector, workspace, requestKey, and the exact plan and manifest fingerprints.",
      });
      return true;
    }
    const result = await cli([
      "sqlserver-adapter-activation-status",
      "--connector", connector,
      "--workspace", workspaceId,
      "--request-key", key,
      "--expected-plan", expectedPlan,
      "--expected-manifest", expectedManifest,
    ]);
    sendJson(response, resultStatus(result), result);
    return true;
  }

  if (request.method !== "POST" || !POST_PATHS.has(url.pathname)) return false;

  const capability: SqlServerSnapshotCapability = url.pathname.endsWith("/activate")
    ? "connector:sqlserver:activate"
    : url.pathname.endsWith("/snapshot") || url.pathname.endsWith("/plan")
      ? "connector:sqlserver:snapshot"
      : "connector:sqlserver:inspect";
  if (!await authorized(options, capability)) return true;
  const body = await readBody(request);
  const connector = connectorInput(body, response);
  if (!connector) return true;

  if (url.pathname === "/api/connectors/sqlserver/test") {
    const result = await cli(["sqlserver-adapter-test", "--connector", connector]);
    sendJson(response, resultStatus(result), result);
    return true;
  }

  if (url.pathname === "/api/connectors/sqlserver/discover") {
    const result = await cli(["sqlserver-adapter-discover", "--connector", connector]);
    sendJson(response, resultStatus(result), result);
    return true;
  }

  if (url.pathname === "/api/connectors/sqlserver/preview") {
    const catalogFingerprint = String(body.catalogFingerprint ?? "");
    const resources = Array.isArray(body.resourceKeys) ? body.resourceKeys.map(String) : [];
    if (!FINGERPRINT.test(catalogFingerprint) || resources.length < 1 || resources.length > 32) {
      sendJson(response, 400, { ok: false, code: "SQLSERVER_PREVIEW_INPUT_INVALID", error: "A current catalog and bounded resource selection are required." });
      return true;
    }
    const result = await cli([
      "sqlserver-adapter-preview",
      "--connector", connector,
      "--catalog", catalogFingerprint,
      "--resources", resources.join(","),
    ]);
    sendJson(response, resultStatus(result), result);
    return true;
  }

  if (url.pathname === "/api/connectors/sqlserver/plan") {
    const key = requestKey(request, body);
    const catalogFingerprint = String(body.catalogFingerprint ?? "");
    const selections = Array.isArray(body.selections) ? body.selections : [];
    const selectionsJson = JSON.stringify(selections);
    const budgetJson = JSON.stringify(body.budget ?? {});
    if (!key || key.length > 200 || !FINGERPRINT.test(catalogFingerprint) || selections.length < 1 || selections.length > 32 || selectionsJson.length > 20_000 || budgetJson.length > 2_000) {
      sendJson(response, 400, { ok: false, code: "SQLSERVER_PLAN_INPUT_INVALID", error: "requestKey, current catalog, and bounded selections are required." });
      return true;
    }
    const result = await cli([
      "sqlserver-adapter-plan",
      "--connector", connector,
      "--request-key", key,
      "--catalog", catalogFingerprint,
      "--selections-json", selectionsJson,
      "--budget-json", budgetJson,
    ]);
    sendJson(response, resultStatus(result), result);
    return true;
  }

  if (url.pathname === "/api/connectors/sqlserver/snapshot") {
    const key = requestKey(request, body);
    const expectedPlan = String(body.expectedPlanFingerprint ?? "");
    if (!key || key.length > 200 || body.confirm !== true || !FINGERPRINT.test(expectedPlan)) {
      sendJson(response, 400, {
        ok: false,
        code: "SQLSERVER_SNAPSHOT_CONFIRMATION_REQUIRED",
        error: "Snapshot creation requires requestKey, confirm=true, and the exact reviewed plan fingerprint.",
      });
      return true;
    }
    const result = await cli([
      "sqlserver-adapter-snapshot",
      "--connector", connector,
      "--request-key", key,
      "--expected-plan", expectedPlan,
      "--yes",
    ]);
    sendJson(response, resultStatus(result), result);
    return true;
  }

  if (url.pathname === "/api/connectors/sqlserver/activate") {
    const key = requestKey(request, body);
    const workspaceId = String(body.workspaceId ?? "").trim();
    const expectedPlan = String(body.expectedPlanFingerprint ?? "");
    const expectedManifest = String(body.expectedManifestFingerprint ?? "");
    if (!key || key.length > 160 || !workspaceId || workspaceId.length > 160 || body.confirm !== true || !FINGERPRINT.test(expectedPlan) || !FINGERPRINT.test(expectedManifest)) {
      sendJson(response, 400, {
        ok: false,
        code: "SQLSERVER_ACTIVATION_CONFIRMATION_REQUIRED",
        error: "Activation requires requestKey, workspaceId, confirm=true, and the exact reviewed plan and sealed manifest fingerprints.",
      });
      return true;
    }
    if (!options.startActivationJob) {
      sendJson(response, 503, {
        ok: false,
        code: "SQLSERVER_ACTIVATION_RUNTIME_UNAVAILABLE",
        error: "The durable import runtime is unavailable.",
      });
      return true;
    }
    const result = await options.startActivationJob({
      connectorKey: connector,
      workspaceId,
      requestKey: key,
      expectedPlanFingerprint: expectedPlan,
      expectedManifestFingerprint: expectedManifest,
    });
    sendJson(response, result.ok === false ? 409 : 202, result);
    return true;
  }

  return false;
}
