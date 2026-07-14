import type { IncomingMessage, ServerResponse } from "node:http";
import { enrichAgentResultWithProvider } from "./agentProviderRuntime";
import { deepSeekProviderForProject } from "./deepseekProvider";
import { readBody, sendJson } from "./serverRuntime";

type AgentRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  root: string;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

export async function handleAgentApi(options: AgentRoutesOptions) {
  const { cli, request, response, root, url } = options;

  if (url.pathname === "/api/agent/provider" && request.method === "GET") {
    sendJson(response, 200, { ok: true, ...deepSeekProviderForProject(root).status(), secretExposed: false });
    return true;
  }

  if (url.pathname === "/api/analysis-runs" && request.method === "GET") {
    const args = ["analysis-runs", "--limit", url.searchParams.get("limit") ?? "30"];
    const run = url.searchParams.get("run");
    if (run) args.push("--run", run);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/ask" && request.method === "POST") {
    const body = await readBody(request);
    const prompt = String(body.prompt ?? "");
    const args = ["ask"];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    if (body.parentRunKey) args.push("--parent-run", String(body.parentRunKey));
    if (body.branchLabel) args.push("--branch-label", String(body.branchLabel));
    args.push(prompt || "生成经营分析计划");
    const deterministicResult = await cli(args);
    const result = await enrichAgentResultWithProvider({ projectRoot: root, prompt, deterministicResult });
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/explain" && request.method === "POST") {
    const body = await readBody(request);
    const prompt = String(body.prompt ?? "");
    const args = ["ask", "--read-only"];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    args.push(prompt || "说明当前工作区可回答的问题");
    const deterministicResult = await cli(args);
    const result = await enrichAgentResultWithProvider({ projectRoot: root, prompt, deterministicResult });
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
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
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
