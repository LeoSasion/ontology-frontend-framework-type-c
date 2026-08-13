import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type DecisionFrameworkRoutesOptions = {
  authorize: (capability: "decision-framework:read" | "decision-framework:write" | "decision-framework:publish", request: IncomingMessage) => boolean | Promise<boolean>;
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

const FRAMEWORK_KEY = /^decision_framework_[a-f0-9]{20}$/;
const SHA256 = /^[a-f0-9]{64}$/;

function text(value: unknown) {
  return String(value ?? "").trim();
}

function pathKey(pathname: string, suffix = "") {
  const prefix = "/api/decision-frameworks/";
  if (!pathname.startsWith(prefix)) return "";
  const raw = suffix && pathname.endsWith(suffix)
    ? pathname.slice(prefix.length, -suffix.length)
    : pathname.slice(prefix.length);
  try {
    return decodeURIComponent(raw);
  } catch {
    return "";
  }
}

function requestKey(request: IncomingMessage, body: Record<string, unknown>) {
  const header = request.headers["x-idempotency-key"];
  return text(body.requestKey ?? (Array.isArray(header) ? header[0] : header));
}

function rejected(response: ServerResponse, code: string, error: string) {
  sendJson(response, 400, { ok: false, action: "decision-framework", code, error });
}

export async function handleDecisionFrameworkApi({ authorize, cli, request, response, url }: DecisionFrameworkRoutesOptions) {
  if (url.pathname.startsWith("/api/decision-frameworks")) {
    const capability = request.method === "GET"
      ? "decision-framework:read"
      : url.pathname.endsWith("/publish")
        ? "decision-framework:publish"
        : "decision-framework:write";
    if (!await authorize(capability, request)) {
      sendJson(response, 403, { ok: false, code: "DECISION_FRAMEWORK_CAPABILITY_DENIED", error: "The current local operator cannot use this decision-framework capability." });
      return true;
    }
  }
  if (url.pathname === "/api/decision-frameworks" && request.method === "GET") {
    const framework = text(url.searchParams.get("framework"));
    const unit = text(url.searchParams.get("unit"));
    const limit = text(url.searchParams.get("limit")) || "30";
    if (framework && !FRAMEWORK_KEY.test(framework)) {
      rejected(response, "DECISION_FRAMEWORK_KEY_INVALID", "A valid framework key is required");
      return true;
    }
    const args = ["decision-frameworks", "--limit", limit];
    if (framework) args.push("--framework", framework);
    if (unit) args.push("--unit", unit);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/decision-frameworks/create" && request.method === "POST") {
    const body = await readBody(request);
    const unit = text(body.unitKey ?? body.unit);
    const frameworkType = text(body.type ?? body.frameworkType);
    const title = text(body.title);
    const key = requestKey(request, body);
    if (!unit || !["swot", "process"].includes(frameworkType) || !title || title.length > 200 || !key) {
      rejected(response, "DECISION_FRAMEWORK_CREATE_INVALID", "unitKey, type, title, and requestKey are required");
      return true;
    }
    const result = await cli([
      "decision-framework-create",
      "--unit", unit,
      "--framework-type", frameworkType,
      "--title", title,
      "--request-key", key,
    ]);
    sendJson(response, result.ok === false ? 409 : 201, result);
    return true;
  }

  const exportKey = pathKey(url.pathname, "/export");
  if (url.pathname.startsWith("/api/decision-frameworks/") && url.pathname.endsWith("/export") && request.method === "GET") {
    if (!FRAMEWORK_KEY.test(exportKey)) {
      rejected(response, "DECISION_FRAMEWORK_KEY_INVALID", "A valid framework key is required");
      return true;
    }
    const result = await cli(["decision-framework-export", "--framework", exportKey]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  const publishKey = pathKey(url.pathname, "/publish");
  if (url.pathname.startsWith("/api/decision-frameworks/") && url.pathname.endsWith("/publish") && request.method === "POST") {
    if (!FRAMEWORK_KEY.test(publishKey)) {
      rejected(response, "DECISION_FRAMEWORK_KEY_INVALID", "A valid framework key is required");
      return true;
    }
    const body = await readBody(request);
    const confirm = body.confirm === true;
    const expectedPlan = text(body.expectedPlanFingerprint);
    if (confirm && !SHA256.test(expectedPlan)) {
      rejected(response, "DECISION_FRAMEWORK_PLAN_REQUIRED", "Confirmation requires the exact preview fingerprint");
      return true;
    }
    const args = ["decision-framework-publish", "--framework", publishKey];
    if (confirm) args.push("--yes", "--expected-plan", expectedPlan);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : confirm ? 200 : 202, result);
    return true;
  }

  const frameworkKey = pathKey(url.pathname);
  if (FRAMEWORK_KEY.test(frameworkKey) && request.method === "GET") {
    const result = await cli(["decision-frameworks", "--framework", frameworkKey, "--limit", "1"]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (FRAMEWORK_KEY.test(frameworkKey) && request.method === "PUT") {
    const body = await readBody(request);
    const title = text(body.title);
    const expectedContent = text(body.expectedContentFingerprint);
    if (!title || title.length > 200 || !Array.isArray(body.claims) || !SHA256.test(expectedContent)) {
      rejected(response, "DECISION_FRAMEWORK_SAVE_INVALID", "title, claims, and expectedContentFingerprint are required");
      return true;
    }
    const result = await cli([
      "decision-framework-save",
      "--framework", frameworkKey,
      "--title", title,
      "--claims-json", JSON.stringify(body.claims),
      "--expected-content", expectedContent,
    ]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname.startsWith("/api/decision-frameworks/") && ["GET", "PUT"].includes(request.method ?? "")) {
    rejected(response, "DECISION_FRAMEWORK_KEY_INVALID", "A valid framework key is required");
    return true;
  }

  return false;
}
