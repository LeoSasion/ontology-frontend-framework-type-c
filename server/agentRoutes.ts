import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type AgentRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

export async function handleAgentApi(options: AgentRoutesOptions) {
  const { cli, request, response, url } = options;

  if (url.pathname === "/api/agent/ask" && request.method === "POST") {
    const body = await readBody(request);
    const prompt = String(body.prompt ?? "");
    const result = await cli(["ask", prompt || "生成经营分析计划"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/explain" && request.method === "POST") {
    const body = await readBody(request);
    const prompt = String(body.prompt ?? "");
    const result = await cli(["ask", "--read-only", prompt || "说明当前工作区可回答的问题"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/actions/confirm" && request.method === "POST") {
    const body = await readBody(request);
    const actionKey = String(body.actionKey ?? "");
    if (!actionKey) {
      sendJson(response, 400, { ok: false, error: "actionKey is required" });
      return true;
    }
    const args = ["confirm-action", actionKey];
    if (body.reject === true) args.push("--reject");
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/actions" && request.method === "GET") {
    const limit = url.searchParams.get("limit") ?? "12";
    const result = await cli(["action-drafts", "--limit", limit]);
    sendJson(response, 200, result);
    return true;
  }

  return false;
}
