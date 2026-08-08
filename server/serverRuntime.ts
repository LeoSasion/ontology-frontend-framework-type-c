import { AsyncLocalStorage } from "node:async_hooks";
import type { IncomingMessage, ServerResponse } from "node:http";
import { RuntimeHostCapacityError, RuntimeHostDeadlineError, RuntimeHostPool, RuntimeHostUnavailableError } from "./runtimeHost";

export type JsonValue = Record<string, unknown> | Array<unknown> | string | number | boolean | null;

export class RequestBodyTooLargeError extends Error {}
export class InvalidJsonBodyError extends Error {}
export class UnsupportedMediaTypeError extends Error {}
export class RuntimeCommandLimitError extends Error {}
export { RuntimeHostCapacityError, RuntimeHostUnavailableError };

type JsonResponseCapture = (status: number, body: JsonValue) => void;
const responseCapture = new AsyncLocalStorage<JsonResponseCapture>();
const runtimeTrace = new AsyncLocalStorage<string>();
const parsedRequestBodies = new WeakMap<IncomingMessage, Promise<Record<string, unknown>>>();

export function withJsonResponseCapture<T>(capture: JsonResponseCapture, task: () => Promise<T>) {
  return responseCapture.run(capture, task);
}

export function withRuntimeRequestTrace<T>(traceId: string, task: () => Promise<T>) {
  return runtimeTrace.run(traceId, task);
}

function configuredMaxRequestBodyBytes() {
  const value = Number(process.env.AIBI_MAX_BODY_BYTES ?? 1_048_576);
  return Number.isInteger(value) && value >= 16_384 && value <= 10_485_760 ? value : 1_048_576;
}

export function sendJson(response: ServerResponse, status: number, body: JsonValue) {
  const failedPayload = body !== null
    && typeof body === "object"
    && !Array.isArray(body)
    && body.ok === false;
  const explicitError = failedPayload
    && (Object.prototype.hasOwnProperty.call(body, "error") || Object.prototype.hasOwnProperty.call(body, "errorCode"));
  const effectiveStatus = status >= 200
    && status < 300
    && explicitError
    ? 409
    : status;
  const allowedCorsOrigin = String(process.env.AIBI_CORS_ORIGIN ?? "").trim();
  const headers: Record<string, string> = {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,x-request-id,x-requested-with,x-aibi-envelope-version,x-aibi-runtime-token,x-idempotency-key",
    "cache-control": "no-store",
  };
  if (allowedCorsOrigin) headers["access-control-allow-origin"] = allowedCorsOrigin;
  responseCapture.getStore()?.(effectiveStatus, body);
  response.writeHead(effectiveStatus, headers);
  response.end(JSON.stringify(body, null, 2));
}
export function readBody(request: IncomingMessage): Promise<Record<string, unknown>> {
  const cached = parsedRequestBodies.get(request);
  if (cached) return cached;
  const pending = new Promise<Record<string, unknown>>((resolveBody, reject) => {
    const contentType = String(request.headers["content-type"] ?? "").toLowerCase();
    if (!contentType.startsWith("application/json")) {
      reject(new UnsupportedMediaTypeError("Mutation requests must use application/json"));
      return;
    }
    const maxRequestBodyBytes = configuredMaxRequestBodyBytes();
    const chunks: Buffer[] = [];
    let bodyBytes = 0;
    let settled = false;
    request.on("data", (chunk) => {
      if (settled) return;
      const buffer = Buffer.from(chunk);
      bodyBytes += buffer.byteLength;
      if (bodyBytes > maxRequestBodyBytes) {
        settled = true;
        chunks.length = 0;
        request.resume();
        reject(new RequestBodyTooLargeError(`Request body exceeds ${maxRequestBodyBytes} bytes`));
        return;
      }
      chunks.push(buffer);
    });
    request.on("end", () => {
      if (settled) return;
      settled = true;
      const text = Buffer.concat(chunks).toString("utf8").trim();
      if (!text) {
        resolveBody({});
        return;
      }
      try {
        resolveBody(JSON.parse(text));
      } catch {
        reject(new InvalidJsonBodyError("Request body must contain valid JSON"));
      }
    });
    request.on("error", (error) => {
      if (settled) return;
      settled = true;
      reject(error);
    });
  });
  parsedRequestBodies.set(request, pending);
  return pending;
}

const runtimeHosts = new Map<string, RuntimeHostPool>();

function runtimeHost(root: string) {
  let host = runtimeHosts.get(root);
  if (!host) {
    host = new RuntimeHostPool(root);
    runtimeHosts.set(root, host);
  }
  return host;
}

export async function runCli(root: string, args: string[]): Promise<Record<string, unknown>> {
  try {
    return await runtimeHost(root).run(args, runtimeTrace.getStore() ?? "");
  } catch (error) {
    if (error instanceof RuntimeHostDeadlineError) throw new RuntimeCommandLimitError(error.message);
    throw error;
  }
}

export function runtimeHostHealth(root: string) {
  return runtimeHost(root).health();
}

export async function shutdownRuntimeHosts() {
  await Promise.all([...runtimeHosts.values()].map((host) => host.shutdown()));
  runtimeHosts.clear();
}

export function pushDashboardWidgetStyleArgs(args: string[], body: Record<string, unknown>) {
  const stringOptions: Array<[string, string]> = [
    ["sortBy", "--sort-by"],
    ["sortDirection", "--sort-direction"],
    ["decimalPlaces", "--decimal-places"],
    ["tableColumnLimit", "--table-column-limit"],
    ["slicerDisplay", "--slicer-display"],
    ["rankingMode", "--ranking-mode"],
    ["colorPalette", "--color-palette"],
    ["barOrientation", "--bar-orientation"],
    ["pieShape", "--pie-shape"],
    ["xAxisTitle", "--x-axis-title"],
    ["yAxisTitle", "--y-axis-title"],
    ["legendTitle", "--legend-title"],
  ];
  for (const [key, flag] of stringOptions) {
    if (body[key] !== undefined && body[key] !== null && String(body[key]) !== "") {
      args.push(flag, String(body[key]));
    }
  }
  const booleanOptions: Array<[string, string, string]> = [
    ["slicerMultiSelect", "--slicer-multi-select", "--single-select"],
    ["slicerSearchable", "--slicer-searchable", "--no-slicer-search"],
    ["showLegend", "--show-legend", "--hide-legend"],
    ["showAxis", "--show-axis", "--hide-axis"],
    ["showDataLabel", "--show-data-label", "--hide-data-label"],
    ["lineSmooth", "--line-smooth", "--line-straight"],
    ["areaFill", "--area-fill", "--no-area-fill"],
    ["crossFilter", "--cross-filter", "--no-cross-filter"],
    ["drillDown", "--drill-down", "--no-drill-down"],
    ["globalFilterTarget", "--global-filter-target", "--no-global-filter-target"],
  ];
  for (const [key, enabledFlag, disabledFlag] of booleanOptions) {
    if (body[key] === true) args.push(enabledFlag);
    if (body[key] === false) args.push(disabledFlag);
  }
}
