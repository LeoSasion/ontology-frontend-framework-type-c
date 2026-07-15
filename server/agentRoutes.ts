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

  if (url.pathname === "/api/agent/sessions" && request.method === "GET") {
    const args = ["agent-sessions", "--limit", url.searchParams.get("limit") ?? "30"];
    const workspaceId = url.searchParams.get("workspaceId");
    if (workspaceId) args.push("--workspace", workspaceId);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/sessions" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["agent-session-create", "--title", String(body.title ?? "新分析会话")];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  const sessionActionMatch = url.pathname.match(/^\/api\/agent\/sessions\/([^/]+)\/(resume|fork|compact)$/);
  if (sessionActionMatch && request.method === "POST") {
    const body = await readBody(request);
    const sessionKey = decodeURIComponent(sessionActionMatch[1]);
    const action = sessionActionMatch[2];
    const args = action === "resume"
      ? ["agent-session-resume", sessionKey]
      : action === "fork"
        ? ["agent-session-fork", sessionKey]
        : ["agent-context-compact", "--session", sessionKey, "--level", String(body.level ?? 3)];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    if (action === "fork" && body.fromTurnKey) args.push("--from-turn", String(body.fromTurnKey));
    if (action === "fork" && body.title) args.push("--title", String(body.title));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  const sessionMatch = url.pathname.match(/^\/api\/agent\/sessions\/([^/]+)$/);
  if (sessionMatch && request.method === "GET") {
    const args = ["agent-sessions", "--session", decodeURIComponent(sessionMatch[1])];
    const workspaceId = url.searchParams.get("workspaceId");
    if (workspaceId) args.push("--workspace", workspaceId);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/turns" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["agent-turn-run", String(body.prompt ?? "生成分析计划")];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    if (body.parentTurnKey) args.push("--parent-turn", String(body.parentTurnKey));
    if (body.sessionKey) args.push("--session", String(body.sessionKey));
    if (body.reviewedStaleRefs === true) args.push("--review-stale-context");
    if (body.readOnly === true) args.push("--read-only");
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  const turnEventsMatch = url.pathname.match(/^\/api\/agent\/turns\/([^/]+)\/events$/);
  if (turnEventsMatch && request.method === "GET") {
    const args = ["agent-turns", "--turn", decodeURIComponent(turnEventsMatch[1]), "--after-sequence", url.searchParams.get("after") ?? "0", "--limit", url.searchParams.get("limit") ?? "500"];
    const workspaceId = url.searchParams.get("workspaceId");
    if (workspaceId) args.push("--workspace", workspaceId);
    const result = await cli(args);
    const events = Array.isArray(result.events) ? result.events : [];
    response.writeHead(200, {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-store",
      connection: "close",
    });
    for (const event of events) {
      const value = event && typeof event === "object" && !Array.isArray(event) ? event as Record<string, unknown> : {};
      response.write(`id: ${String(value.sequence ?? "")}\n`);
      response.write(`event: ${String(value.eventType ?? "message")}\n`);
      response.write(`data: ${JSON.stringify(value)}\n\n`);
    }
    response.end();
    return true;
  }

  const turnCancelMatch = url.pathname.match(/^\/api\/agent\/turns\/([^/]+)\/cancel$/);
  if (turnCancelMatch && request.method === "POST") {
    const body = await readBody(request);
    const args = ["agent-turn-cancel", decodeURIComponent(turnCancelMatch[1])];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  const turnMatch = url.pathname.match(/^\/api\/agent\/turns\/([^/]+)$/);
  if (turnMatch && request.method === "GET") {
    const args = ["agent-turns", "--turn", decodeURIComponent(turnMatch[1])];
    const workspaceId = url.searchParams.get("workspaceId");
    if (workspaceId) args.push("--workspace", workspaceId);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/ask" && request.method === "POST") {
    const body = await readBody(request);
    const prompt = String(body.prompt ?? "");
    const args = ["agent-turn-run"];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    if (body.sessionKey) args.push("--session", String(body.sessionKey));
    if (body.reviewedStaleRefs === true) args.push("--review-stale-context");
    args.push(prompt || "生成分析计划");
    const turnResult = await cli(args);
    const deterministicResult = turnResult.answer && typeof turnResult.answer === "object" && !Array.isArray(turnResult.answer)
      ? turnResult.answer as Record<string, unknown>
      : turnResult;
    const result = await enrichAgentResultWithProvider({ projectRoot: root, prompt, deterministicResult });
    sendJson(response, 200, { ...result, agentSession: turnResult.session, sessionContext: turnResult.sessionContext, agentTurn: turnResult.turn, evidencePlan: turnResult.evidencePlan, turnEvents: turnResult.events });
    return true;
  }

  if (url.pathname === "/api/agent/explain" && request.method === "POST") {
    const body = await readBody(request);
    const prompt = String(body.prompt ?? "");
    const args = ["agent-turn-run", "--read-only"];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    if (body.sessionKey) args.push("--session", String(body.sessionKey));
    if (body.reviewedStaleRefs === true) args.push("--review-stale-context");
    args.push(prompt || "说明当前工作区可回答的问题");
    const turnResult = await cli(args);
    const deterministicResult = turnResult.answer && typeof turnResult.answer === "object" && !Array.isArray(turnResult.answer)
      ? turnResult.answer as Record<string, unknown>
      : turnResult;
    const result = await enrichAgentResultWithProvider({ projectRoot: root, prompt, deterministicResult });
    sendJson(response, 200, { ...result, agentSession: turnResult.session, sessionContext: turnResult.sessionContext, agentTurn: turnResult.turn, evidencePlan: turnResult.evidencePlan, turnEvents: turnResult.events });
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
