import { spawn } from "node:child_process";
import type { IncomingMessage, ServerResponse } from "node:http";
import { buildActionRecovery } from "../src/actionRecoveryModel";

export type JsonValue = Record<string, unknown> | Array<unknown> | string | number | boolean | null;

export class RequestBodyTooLargeError extends Error {}
export class InvalidJsonBodyError extends Error {}

function configuredMaxRequestBodyBytes() {
  const value = Number(process.env.AIBI_MAX_BODY_BYTES ?? 1_048_576);
  return Number.isInteger(value) && value >= 16_384 && value <= 10_485_760 ? value : 1_048_576;
}

function enrichedErrorBody(body: JsonValue): JsonValue {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return body;
  }
  if (body.ok !== false || body.recovery) {
    return body;
  }
  const action = typeof body.action === "string" && body.action
    ? body.action
    : typeof body.command === "string" && body.command
      ? body.command
      : "api";
  const error = typeof body.error === "string" && body.error ? body.error : "Local API action failed";
  const recovery = buildActionRecovery(action, error);
  return {
    ...body,
    action,
    category: body.category ?? recovery.category,
    targetSection: body.targetSection ?? recovery.targetSection,
    safeState: body.safeState ?? recovery.safeState.zh,
    evidence: Array.isArray(body.evidence) ? body.evidence : recovery.evidence,
    next: typeof body.next === "string" && body.next ? body.next : recovery.next.zh,
    recovery,
  };
}

export function sendJson(response: ServerResponse, status: number, body: JsonValue) {
  const allowedCorsOrigin = String(process.env.AIBI_CORS_ORIGIN ?? "").trim();
  const headers: Record<string, string> = {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type",
    "cache-control": "no-store",
  };
  if (allowedCorsOrigin) headers["access-control-allow-origin"] = allowedCorsOrigin;
  response.writeHead(status, headers);
  response.end(JSON.stringify(enrichedErrorBody(body), null, 2));
}
export function readBody(request: IncomingMessage): Promise<Record<string, unknown>> {
  return new Promise((resolveBody, reject) => {
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
}

export function runCli(root: string, args: string[]): Promise<Record<string, unknown>> {
  return new Promise((resolveCli, reject) => {
    const child = spawn("python", ["tools/aibi_cli.py", "--json", ...args], {
      cwd: root,
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
      },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    child.stdout.on("data", (chunk) => stdout.push(Buffer.from(chunk)));
    child.stderr.on("data", (chunk) => stderr.push(Buffer.from(chunk)));
    child.on("error", reject);
    child.on("close", (code) => {
      const text = Buffer.concat(stdout).toString("utf8");
      const err = Buffer.concat(stderr).toString("utf8");
      try {
        const parsed = JSON.parse(text);
        if (code === 0 || typeof parsed === "object") {
          resolveCli(parsed as Record<string, unknown>);
          return;
        }
      } catch {
        // Fall through to structured error.
      }
      reject(new Error(err || text || `CLI exited with ${code}`));
    });
  });
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
