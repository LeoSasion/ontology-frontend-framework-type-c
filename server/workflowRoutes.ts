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

  if (url.pathname === "/api/workflow/recipes" && request.method === "GET") {
    const requestedLimit = Number.parseInt(url.searchParams.get("limit") ?? "50", 10);
    const result = await cli(["workflow-recipes", "--limit", String(Number.isFinite(requestedLimit) ? Math.min(100, Math.max(1, requestedLimit)) : 50)]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if ((url.pathname === "/api/workflow/recipes/preview" || url.pathname === "/api/workflow/recipes/publish") && request.method === "POST") {
    const body = await readBody(request);
    const requestKey = nonEmpty(body.requestKey);
    const name = nonEmpty(body.name);
    const stages = Array.isArray(body.stages) ? body.stages : [];
    const publish = url.pathname.endsWith("/publish");
    const expectedPlan = nonEmpty(body.expectedPlanFingerprint);
    if (requestKey.length < 8 || requestKey.length > 200 || !name || name.length > 160 || stages.length < 1 || stages.length > 12 || stages.some((stage) => !stage || typeof stage !== "object" || Array.isArray(stage) || !nonEmpty((stage as Record<string, unknown>).command))) {
      sendJson(response, 400, { ok: false, code: "WORKFLOW_RECIPE_INPUT_INVALID", error: "Bounded requestKey, name, and 1-12 capability stages are required." });
      return true;
    }
    if (publish && (body.confirm !== true || !/^[a-f0-9]{64}$/.test(expectedPlan))) {
      sendJson(response, 400, { ok: false, code: "WORKFLOW_RECIPE_CONFIRMATION_REQUIRED", error: "Publish requires confirm=true and the exact preview fingerprint." });
      return true;
    }
    const args = [publish ? "workflow-recipe-publish" : "workflow-recipe-preview", "--request-key", requestKey, "--name", name];
    if (body.description) args.push("--description", String(body.description));
    for (const stage of stages) args.push("--stage-json", JSON.stringify(stage));
    if (publish) args.push("--expected-plan", expectedPlan, "--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/workflow/recipes/plan" && request.method === "POST") {
    const body = await readBody(request);
    const recipeKey = nonEmpty(body.recipeKey);
    const bindings = body.bindings && typeof body.bindings === "object" && !Array.isArray(body.bindings) ? body.bindings : {};
    if (!/^recipe_[a-f0-9]{20}$/.test(recipeKey) || JSON.stringify(bindings).length > 8_000) {
      sendJson(response, 400, { ok: false, code: "WORKFLOW_RECIPE_PLAN_INPUT_INVALID", error: "A valid recipe and bounded bindings are required." });
      return true;
    }
    const result = await cli(["workflow-recipe-plan", "--recipe", recipeKey, "--bindings-json", JSON.stringify(bindings)]);
    sendJson(response, result.ok === false && !Array.isArray(result.stages) ? 409 : 200, result);
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
