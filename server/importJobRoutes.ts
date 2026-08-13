import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type ImportJobRoutesOptions = {
  authorize: (capability: "import:read" | "import:write", request: IncomingMessage) => boolean | Promise<boolean>;
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  startImportJob?: (body: Record<string, unknown>) => Promise<Record<string, unknown>>;
  resumeImportJob?: (jobKey: string) => Promise<Record<string, unknown>>;
  cancelJobProcess?: (jobKey: string) => { ownedProcess: boolean; signalRequested: boolean };
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

const JOB_KEY = /^job_[a-f0-9]{20}$/;

function jobPath(pathname: string) {
  const match = pathname.match(/^\/api\/import\/jobs\/([^/]+)(?:\/(cancel|resume))?$/);
  if (!match) return null;
  try {
    return { jobKey: decodeURIComponent(match[1]), action: match[2] ?? "get", valid: true };
  } catch {
    return { jobKey: "", action: match[2] ?? "get", valid: false };
  }
}

export async function handleImportJobApi({
  authorize,
  cancelJobProcess,
  cli,
  request,
  response,
  resumeImportJob,
  startImportJob,
  url,
}: ImportJobRoutesOptions) {
  const capability = request.method === "GET" ? "import:read" : "import:write";
  if (url.pathname.startsWith("/api/import/jobs") && !await authorize(capability, request)) {
    sendJson(response, 403, { ok: false, code: "IMPORT_CAPABILITY_DENIED", error: "The current local operator cannot use this import capability." });
    return true;
  }
  if (url.pathname === "/api/import/jobs" && request.method === "GET") {
    const limit = Math.max(1, Math.min(Number(url.searchParams.get("limit") ?? 20) || 20, 100));
    const result = await cli(["jobs", "--limit", String(limit)]);
    const jobs = Array.isArray(result.jobs)
      ? result.jobs.filter((job) => job && typeof job === "object" && !Array.isArray(job) && (job as Record<string, unknown>).kind === "import")
      : [];
    sendJson(response, result.ok === false ? 409 : 200, {
      ...result,
      jobs,
      count: jobs.length,
      activeCount: jobs.filter((job) => !["canceled", "succeeded", "failed"].includes(String((job as Record<string, unknown>).status ?? ""))).length,
    });
    return true;
  }
  if (url.pathname === "/api/import/jobs" && request.method === "POST") {
    const body = await readBody(request);
    if (!startImportJob) {
      sendJson(response, 503, { ok: false, code: "IMPORT_JOB_RUNTIME_UNAVAILABLE", error: "Durable import runtime is unavailable." });
      return true;
    }
    const requestKey = String(body.requestKey ?? "").trim();
    const expectedPlan = String(body.expectedPlan ?? "").trim();
    const importKind = String(body.importKind ?? "single");
    if (!requestKey || requestKey.length > 200 || !/^[a-f0-9]{64}$/.test(expectedPlan)) {
      sendJson(response, 400, { ok: false, code: "IMPORT_JOB_BINDING_REQUIRED", error: "requestKey and expectedPlan are required." });
      return true;
    }
    if (!new Set(["single", "folder"]).has(importKind)) {
      sendJson(response, 400, { ok: false, code: "IMPORT_JOB_KIND_INVALID", error: "importKind must be single or folder." });
      return true;
    }
    const result = await startImportJob({
      importKind,
      path: String(body.path ?? body.filePath ?? body.folderPath ?? ""),
      requestKey,
      expectedPlan,
      label: body.label,
      table: body.table,
      name: body.name,
      mode: body.mode,
      uniqueFields: body.uniqueFields,
      conflictRule: body.conflictRule,
      limit: body.limit,
      recursive: body.recursive,
    });
    sendJson(response, result.ok === false ? 409 : 202, result);
    return true;
  }

  const path = jobPath(url.pathname);
  if (!path) return false;
  if (!path.valid || !JOB_KEY.test(path.jobKey)) {
    sendJson(response, 400, { ok: false, code: "IMPORT_JOB_KEY_INVALID", error: "A valid jobKey is required." });
    return true;
  }
  if (path.action === "get" && request.method === "GET") {
    const result = await cli(["jobs", "--job", path.jobKey, "--event-limit", url.searchParams.get("eventLimit") ?? "200"]);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }
  if (path.action === "cancel" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["job-cancel", path.jobKey, "--yes"];
    if (body.reason) args.push("--reason", String(body.reason));
    const result = await cli(args);
    const status = String((result.job as Record<string, unknown> | undefined)?.status ?? "");
    const execution = ["cancel_requested", "canceled"].includes(status) && cancelJobProcess
      ? cancelJobProcess(path.jobKey)
      : undefined;
    sendJson(response, result.ok === false ? 409 : 200, execution ? { ...result, execution } : result);
    return true;
  }
  if (path.action === "resume" && request.method === "POST") {
    await readBody(request);
    if (!resumeImportJob) {
      sendJson(response, 503, { ok: false, code: "IMPORT_JOB_RUNTIME_UNAVAILABLE", error: "Durable import runtime is unavailable." });
      return true;
    }
    const result = await resumeImportJob(path.jobKey);
    sendJson(response, result.ok === false ? 409 : 202, result);
    return true;
  }
  return false;
}
