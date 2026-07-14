import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type JobRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  cancelJobProcess?: (jobKey: string) => { ownedProcess: boolean; signalRequested: boolean };
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

export async function handleJobApi({ cancelJobProcess, cli, request, response, url }: JobRoutesOptions) {
  if (url.pathname === "/api/jobs" && request.method === "GET") {
    const args = ["jobs", "--limit", url.searchParams.get("limit") ?? "50"];
    const job = url.searchParams.get("job");
    if (job) args.push("--job", job);
    for (const status of url.searchParams.getAll("status")) args.push("--status", status);
    if (url.searchParams.get("includeEvents") === "true") args.push("--include-events");
    const eventsAfter = url.searchParams.get("eventsAfter");
    if (eventsAfter) args.push("--events-after", eventsAfter);
    const eventLimit = url.searchParams.get("eventLimit");
    if (eventLimit) args.push("--event-limit", eventLimit);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/jobs/cancel" && request.method === "POST") {
    const body = await readBody(request);
    const jobKey = String(body.jobKey ?? body.job ?? "").trim();
    if (!jobKey) {
      sendJson(response, 400, { ok: false, action: "job-cancel", error: "jobKey is required" });
      return true;
    }
    const args = ["job-cancel", jobKey];
    if (body.reason) args.push("--reason", String(body.reason));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    const job = result.job;
    const status = job && typeof job === "object" && !Array.isArray(job)
      ? String((job as Record<string, unknown>).status ?? "")
      : "";
    const execution = body.confirm === true && status === "cancel_requested" && cancelJobProcess
      ? cancelJobProcess(jobKey)
      : undefined;
    sendJson(
      response,
      result.requiresConfirmation ? 202 : result.ok === false ? 400 : 200,
      execution ? { ...result, execution } : result,
    );
    return true;
  }

  return false;
}
