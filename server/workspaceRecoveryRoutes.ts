import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type WorkspaceRecoveryRoutesOptions = {
  authorize: (capability: "workspace-recovery:read" | "workspace-recovery:owner", request: IncomingMessage) => boolean | Promise<boolean>;
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

const RECOVERY_KEY = /^rp_[a-f0-9]{24}$/;

function requestKey(request: IncomingMessage, body: Record<string, unknown>) {
  const header = request.headers["x-idempotency-key"];
  const headerValue = Array.isArray(header) ? header[0] : header;
  return String(body.requestKey ?? headerValue ?? "").trim();
}

function mutationInput(
  request: IncomingMessage,
  body: Record<string, unknown>,
  response: ServerResponse,
  options: { recoveryPointRequired?: boolean; reasonRequired?: boolean } = {},
) {
  const key = requestKey(request, body);
  const recoveryPointKey = String(body.recoveryPointKey ?? "").trim();
  const reason = String(body.reason ?? "").trim();
  const confirm = body.confirm === true;
  const expectedPlanFingerprint = String(body.expectedPlanFingerprint ?? "").trim();
  if (!key || key.length > 200) {
    sendJson(response, 400, { ok: false, code: "RECOVERY_REQUEST_KEY_REQUIRED", error: "requestKey is required and must be at most 200 characters" });
    return null;
  }
  if (options.recoveryPointRequired && !RECOVERY_KEY.test(recoveryPointKey)) {
    sendJson(response, 400, { ok: false, code: "RECOVERY_POINT_KEY_INVALID", error: "A valid recoveryPointKey is required" });
    return null;
  }
  if (options.reasonRequired && (!reason || reason.length > 500)) {
    sendJson(response, 400, { ok: false, code: "RECOVERY_REASON_REQUIRED", error: "reason is required and must be at most 500 characters" });
    return null;
  }
  if (confirm && !/^[a-f0-9]{64}$/.test(expectedPlanFingerprint)) {
    sendJson(response, 400, { ok: false, code: "RECOVERY_PLAN_REQUIRED", error: "Confirmed recovery operations require the exact dry-run plan fingerprint" });
    return null;
  }
  return { confirm, expectedPlanFingerprint, key, reason, recoveryPointKey };
}

function mutationStatus(result: Record<string, unknown>) {
  if (result.ok === false) return 409;
  return result.requiresConfirmation === true ? 202 : 200;
}

export async function handleWorkspaceRecoveryApi({ authorize, cli, request, response, url }: WorkspaceRecoveryRoutesOptions) {
  if (url.pathname.startsWith("/api/workspace-recovery")) {
    const capability = request.method === "GET" ? "workspace-recovery:read" : "workspace-recovery:owner";
    if (!await authorize(capability, request)) {
      sendJson(response, 403, { ok: false, code: "RECOVERY_CAPABILITY_DENIED", error: "Workspace recovery requires the local owner capability." });
      return true;
    }
  }
  if (url.pathname === "/api/workspace-recovery" && request.method === "GET") {
    const args = ["workspace-recovery-list", "--limit", url.searchParams.get("limit") ?? "5"];
    if (url.searchParams.get("verify") === "true") args.push("--verify");
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname.startsWith("/api/workspace-recovery/") && url.pathname.endsWith("/compare") && request.method === "GET") {
    let recoveryPointKey = "";
    try {
      recoveryPointKey = decodeURIComponent(url.pathname.slice("/api/workspace-recovery/".length, -"/compare".length));
    } catch {
      recoveryPointKey = "";
    }
    if (!RECOVERY_KEY.test(recoveryPointKey)) {
      sendJson(response, 400, { ok: false, code: "RECOVERY_POINT_KEY_INVALID", error: "A valid recoveryPointKey is required" });
      return true;
    }
    const result = await cli(["workspace-recovery-compare", "--recovery-point", recoveryPointKey]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname.startsWith("/api/workspace-recovery/") && request.method === "GET") {
    let recoveryPointKey = "";
    try {
      recoveryPointKey = decodeURIComponent(url.pathname.slice("/api/workspace-recovery/".length));
    } catch {
      recoveryPointKey = "";
    }
    if (!RECOVERY_KEY.test(recoveryPointKey)) {
      sendJson(response, 400, { ok: false, code: "RECOVERY_POINT_KEY_INVALID", error: "A valid recoveryPointKey is required" });
      return true;
    }
    const args = ["workspace-recovery-inspect", "--recovery-point", recoveryPointKey];
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/workspace-recovery/create" && request.method === "POST") {
    const body = await readBody(request);
    const input = mutationInput(request, body, response, { reasonRequired: true });
    if (!input) return true;
    const args = ["workspace-recovery-create", "--reason", input.reason, "--request-key", input.key];
    if (input.confirm) args.push("--yes", "--expected-plan", input.expectedPlanFingerprint);
    const result = await cli(args);
    sendJson(response, mutationStatus(result), result);
    return true;
  }

  if (url.pathname === "/api/workspace-recovery/restore" && request.method === "POST") {
    const body = await readBody(request);
    const input = mutationInput(request, body, response, { recoveryPointRequired: true });
    if (!input) return true;
    const args = [
      "workspace-recovery-restore",
      "--recovery-point", input.recoveryPointKey,
      "--request-key", input.key,
    ];
    if (input.confirm) args.push("--yes", "--expected-plan", input.expectedPlanFingerprint);
    const result = await cli(args);
    sendJson(response, mutationStatus(result), result);
    return true;
  }

  if (url.pathname === "/api/workspace-recovery/delete" && request.method === "POST") {
    const body = await readBody(request);
    const input = mutationInput(request, body, response, { recoveryPointRequired: true });
    if (!input) return true;
    const args = [
      "workspace-recovery-delete",
      "--recovery-point", input.recoveryPointKey,
      "--request-key", input.key,
    ];
    if (input.confirm) args.push("--yes", "--expected-plan", input.expectedPlanFingerprint);
    const result = await cli(args);
    sendJson(response, mutationStatus(result), result);
    return true;
  }

  return false;
}
