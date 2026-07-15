import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type WorkflowRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

function nonEmpty(value: unknown) {
  return String(value ?? "").trim();
}

export async function handleWorkflowApi({ cli, request, response, url }: WorkflowRoutesOptions) {
  if (url.pathname === "/api/workflow/operators" && request.method === "GET") {
    const result = await cli(["restricted-workflow-operators"]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/workflow/validate" && request.method === "POST") {
    const body = await readBody(request);
    if (!body.graph || typeof body.graph !== "object" || Array.isArray(body.graph)) {
      sendJson(response, 400, { ok: false, action: "restricted-workflow-validate", error: "graph must be one object" });
      return true;
    }
    const args = ["restricted-workflow-validate", "--graph-json", JSON.stringify(body.graph)];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/workflow/agent-graph" && request.method === "GET") {
    const turn = nonEmpty(url.searchParams.get("turn"));
    if (!turn) {
      sendJson(response, 400, { ok: false, action: "agent-workflow-graph", error: "turn is required" });
      return true;
    }
    const args = ["agent-workflow-graph", "--turn", turn];
    const workspace = nonEmpty(url.searchParams.get("workspaceId"));
    if (workspace) args.push("--workspace", workspace);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }

  if (url.pathname === "/api/capabilities" && request.method === "GET") {
    const args = ["capability-contracts"];
    const command = nonEmpty(url.searchParams.get("command"));
    const domain = nonEmpty(url.searchParams.get("domain"));
    if (command) args.push("--command", command);
    if (domain) args.push("--domain", domain);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/workflow/plan" && request.method === "POST") {
    const body = await readBody(request);
    const command = nonEmpty(body.command ?? body.targetCommand);
    const workspaceId = nonEmpty(body.workspaceId ?? body.workspace);
    if (!command || !workspaceId) {
      sendJson(response, 400, {
        ok: false,
        action: "workflow-plan",
        error: "command and workspaceId are required",
      });
      return true;
    }
    const entrypoint = nonEmpty(body.entrypoint) || "api";
    if (!["cli", "api", "agent", "job"].includes(entrypoint)) {
      sendJson(response, 400, {
        ok: false,
        action: "workflow-plan",
        error: "entrypoint must be cli, api, agent, or job",
      });
      return true;
    }
    const input = body.input && typeof body.input === "object" && !Array.isArray(body.input)
      ? body.input
      : {};
    const args = [
      "workflow-plan",
      command,
      "--entrypoint",
      entrypoint,
      "--workspace",
      workspaceId,
      "--input-json",
      JSON.stringify(input),
    ];
    if (body.confirmed === true) args.push("--confirmed");
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/context/budget" && request.method === "POST") {
    const body = await readBody(request);
    if (!Array.isArray(body.segments)) {
      sendJson(response, 400, {
        ok: false,
        action: "context-budget",
        error: "segments must be an array",
      });
      return true;
    }
    const maxChars = Number(body.maxChars ?? 12_000);
    if (!Number.isInteger(maxChars) || maxChars < 256 || maxChars > 100_000) {
      sendJson(response, 400, {
        ok: false,
        action: "context-budget",
        error: "maxChars must be an integer between 256 and 100000",
      });
      return true;
    }
    const result = await cli([
      "context-budget",
      "--segments-json",
      JSON.stringify(body.segments),
      "--max-chars",
      String(maxChars),
    ]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  return false;
}
