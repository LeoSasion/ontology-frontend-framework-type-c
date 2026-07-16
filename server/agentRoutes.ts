import type { IncomingMessage, ServerResponse } from "node:http";
import { buildGroundedAgentContext, enrichAgentResultWithProvider } from "./agentProviderRuntime";
import { agentRuntimeRegistryForProject, shadowEvaluateProviders } from "./agentRuntimeProfile";
import { readBody, sendJson } from "./serverRuntime";

type AgentRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  root: string;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

async function selectedRuntimeProfile(cli: AgentRoutesOptions["cli"], workspaceId: string) {
  const result = await cli(["agent-runtime-profiles", "--workspace", workspaceId]);
  return String(result.selectedProfileId ?? "deterministic");
}

async function persistProviderEvaluation(
  cli: AgentRoutesOptions["cli"],
  workspaceId: string,
  auditValue: unknown,
  shadow = false,
) {
  const audit = record(auditValue);
  const usage = record(audit.usage);
  const validation = record(audit.validation);
  const outboundValidation = record(audit.outboundValidation);
  const providerStatus = String(audit.status ?? "skipped");
  const status = providerStatus === "ready" ? "passed"
    : providerStatus === "fallback" ? "fallback"
      : providerStatus.includes("blocked") ? "blocked" : "skipped";
  const args = [
    "agent-provider-evaluation-record",
    "--workspace", workspaceId,
    "--profile", String(audit.profileId ?? "deterministic"),
    "--profile-fingerprint", String(audit.profileFingerprint ?? ""),
    "--provider", String(audit.provider ?? "deterministic"),
    "--model", String(audit.model ?? "local-bi-runtime"),
    "--request-fingerprint", String(audit.requestHash ?? ""),
    "--context-fingerprint", String(outboundValidation.contextFingerprint ?? ""),
    "--status", status,
    "--validation-status", String(validation.status ?? "not-run"),
    "--duration-ms", String(audit.durationMs ?? 0),
    "--estimated-cost-usd", String(audit.estimatedCostUsd ?? 0),
    "--attempts", String(audit.attempts ?? 0),
    "--fallback-reason", String(audit.fallbackReason ?? ""),
    "--audit-json", JSON.stringify({
      schema: "aibi-agent-provider-audit/v1",
      serverSideOnly: true,
      secretExposed: false,
      rawRowsExposed: false,
      providerCanWrite: false,
      semanticAuthority: "deterministic-local-bi",
      validationStatus: String(validation.status ?? "not-run"),
      validationChecks: record(validation.checks),
    }),
  ];
  if (usage.promptTokens !== null && usage.promptTokens !== undefined) args.push("--prompt-tokens", String(usage.promptTokens));
  if (usage.completionTokens !== null && usage.completionTokens !== undefined) args.push("--completion-tokens", String(usage.completionTokens));
  if (usage.totalTokens !== null && usage.totalTokens !== undefined) args.push("--total-tokens", String(usage.totalTokens));
  if (shadow) args.push("--shadow");
  return cli(args);
}

export function buildAgentAskTurnArgs(body: Record<string, unknown>, prompt: string) {
  const args = ["agent-turn-run"];
  if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
  if (body.sessionKey) args.push("--session", String(body.sessionKey));
  if (body.parentRunKey) args.push("--parent-run", String(body.parentRunKey));
  if (body.branchLabel) args.push("--branch-label", String(body.branchLabel));
  if (body.reviewedStaleRefs === true) args.push("--review-stale-context");
  args.push(prompt || "生成分析计划");
  return args;
}

export async function handleAgentApi(options: AgentRoutesOptions) {
  const { cli, request, response, root, url } = options;

  if (url.pathname === "/api/agent/provider" && request.method === "GET") {
    const workspaceId = url.searchParams.get("workspaceId") ?? "default";
    const selectedProfileId = await selectedRuntimeProfile(cli, workspaceId);
    const registry = agentRuntimeRegistryForProject(root, selectedProfileId);
    sendJson(response, 200, { ok: true, ...registry.provider.status(), profiles: registry.profiles, secretExposed: false, providerCanWrite: false });
    return true;
  }

  if (url.pathname === "/api/agent/runtime-profiles" && request.method === "GET") {
    const workspaceId = url.searchParams.get("workspaceId") ?? "default";
    const persisted = await cli(["agent-runtime-profiles", "--workspace", workspaceId]);
    const registry = agentRuntimeRegistryForProject(root, String(persisted.selectedProfileId ?? "deterministic"));
    sendJson(response, 200, { ...persisted, runtimeProfiles: registry.profiles, providerCanWrite: false });
    return true;
  }

  if (url.pathname === "/api/agent/runtime-profiles/select" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["agent-runtime-profile-set", "--workspace", String(body.workspaceId ?? "default"), "--profile", String(body.profileId ?? "deterministic")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/provider/evaluations" && request.method === "GET") {
    const args = ["agent-provider-evaluations", "--workspace", url.searchParams.get("workspaceId") ?? "default", "--limit", url.searchParams.get("limit") ?? "30"];
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/plan-quality/cases" && request.method === "GET") {
    const result = await cli(["business-expression-cases"]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/plan-quality/evaluate" && request.method === "POST") {
    const result = await cli(["plan-quality-evaluate"]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/plan-quality/scorecards" && request.method === "GET") {
    const result = await cli(["plan-quality-scorecards", "--limit", url.searchParams.get("limit") ?? "20"]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/exploration-threads" && request.method === "GET") {
    const args = ["exploration-threads", "--limit", url.searchParams.get("limit") ?? "30"];
    const threadKey = url.searchParams.get("thread");
    if (threadKey) args.push("--thread", threadKey);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/exploration-threads/create" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["exploration-thread-create", "--run", String(body.analysisRunKey ?? "")];
    if (body.analysisUnitKey) args.push("--unit", String(body.analysisUnitKey));
    if (body.sessionKey) args.push("--session", String(body.sessionKey));
    if (body.turnKey) args.push("--turn", String(body.turnKey));
    if (body.title) args.push("--title", String(body.title));
    if (body.label) args.push("--label", String(body.label));
    if (body.confirm === true) {
      args.push("--yes", "--expected-plan", String(body.expectedPlanFingerprint ?? ""));
    }
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/exploration-threads/add-anchor" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "exploration-anchor-add",
      "--thread", String(body.threadKey ?? ""),
      "--run", String(body.analysisRunKey ?? ""),
    ];
    if (body.parentAnchorKey) args.push("--parent-anchor", String(body.parentAnchorKey));
    if (body.analysisUnitKey) args.push("--unit", String(body.analysisUnitKey));
    if (body.sessionKey) args.push("--session", String(body.sessionKey));
    if (body.turnKey) args.push("--turn", String(body.turnKey));
    if (body.label) args.push("--label", String(body.label));
    if (body.confirm === true) {
      args.push("--yes", "--expected-plan", String(body.expectedPlanFingerprint ?? ""));
    }
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/exploration-threads/board" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "exploration-board-set",
      "--thread", String(body.threadKey ?? ""),
      "--anchor", String(body.anchorKey ?? ""),
      "--state", String(body.state ?? "pinned"),
    ];
    if (body.position) args.push("--position", String(body.position));
    if (body.confirm === true) {
      args.push("--yes", "--expected-plan", String(body.expectedPlanFingerprint ?? ""));
    }
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/research-runs" && request.method === "GET") {
    const args = ["research-runs", "--limit", url.searchParams.get("limit") ?? "30"];
    const researchKey = url.searchParams.get("research");
    if (researchKey) args.push("--research", researchKey);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/research-runs/create" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "research-run-create",
      "--thread", String(body.threadKey ?? ""),
      "--goal", String(body.goal ?? ""),
    ];
    if (body.anchorKey) args.push("--anchor", String(body.anchorKey));
    if (body.skillRef) args.push("--skill", String(body.skillRef));
    if (body.maxObservations) args.push("--max-observations", String(body.maxObservations));
    if (body.maxRevisions) args.push("--max-revisions", String(body.maxRevisions));
    for (const item of Array.isArray(body.hypotheses) ? body.hypotheses : []) args.push("--hypothesis", String(item));
    for (const item of Array.isArray(body.counterexampleChecks) ? body.counterexampleChecks : []) args.push("--counterexample", String(item));
    for (const item of Array.isArray(body.sensitivityChecks) ? body.sensitivityChecks : []) args.push("--sensitivity", String(item));
    if (body.confirm === true) args.push("--yes", "--expected-plan", String(body.expectedPlanFingerprint ?? ""));
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/research-runs/revise" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "research-run-revise",
      "--research", String(body.researchKey ?? ""),
      "--reason", String(body.reason ?? ""),
      "--expected-revision", String(body.expectedRevisionFingerprint ?? ""),
    ];
    if (body.goal) args.push("--goal", String(body.goal));
    if (body.skillRef !== undefined) args.push("--skill", String(body.skillRef));
    if (Array.isArray(body.hypotheses)) {
      args.push("--clear-hypotheses");
      for (const item of body.hypotheses) args.push("--hypothesis", String(item));
    }
    if (Array.isArray(body.counterexampleChecks)) {
      args.push("--clear-counterexamples");
      for (const item of body.counterexampleChecks) args.push("--counterexample", String(item));
    }
    if (Array.isArray(body.sensitivityChecks)) {
      args.push("--clear-sensitivities");
      for (const item of body.sensitivityChecks) args.push("--sensitivity", String(item));
    }
    if (body.confirm === true) args.push("--yes", "--expected-plan", String(body.expectedPlanFingerprint ?? ""));
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/research-runs/observe" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "research-run-observe",
      "--research", String(body.researchKey ?? ""),
      "--anchor", String(body.anchorKey ?? ""),
      "--kind", String(body.kind ?? ""),
      "--step", String(body.stepKey ?? ""),
      "--verdict", String(body.verdict ?? ""),
      "--note", String(body.note ?? ""),
      "--expected-revision", String(body.expectedRevisionFingerprint ?? ""),
    ];
    if (body.confirm === true) args.push("--yes", "--expected-plan", String(body.expectedPlanFingerprint ?? ""));
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/agent/research-runs/finalize" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "research-run-finalize",
      "--research", String(body.researchKey ?? ""),
      "--expected-revision", String(body.expectedRevisionFingerprint ?? ""),
    ];
    if (body.confirm === true) args.push("--yes", "--expected-plan", String(body.expectedPlanFingerprint ?? ""));
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
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
    const turnResult = await cli(buildAgentAskTurnArgs(body, prompt));
    const deterministicResult = turnResult.answer && typeof turnResult.answer === "object" && !Array.isArray(turnResult.answer)
      ? turnResult.answer as Record<string, unknown>
      : turnResult;
    const workspaceId = String(turnResult.workspaceId ?? body.workspaceId ?? "default");
    const selectedProfileId = await selectedRuntimeProfile(cli, workspaceId);
    const registry = agentRuntimeRegistryForProject(root, selectedProfileId);
    const result = await enrichAgentResultWithProvider({ projectRoot: root, prompt, deterministicResult, provider: registry.provider });
    const evaluation = await persistProviderEvaluation(cli, workspaceId, record(record(result.llm).audit)).catch(() => null);
    const shadowProfiles = Array.isArray(body.shadowProfiles) ? body.shadowProfiles.map(String) : [];
    const shadow = shadowProfiles.length && deterministicResult.answerCard
      ? await shadowEvaluateProviders(root, shadowProfiles, buildGroundedAgentContext(prompt, deterministicResult))
      : null;
    if (shadow) {
      for (const run of shadow.runs) {
        await persistProviderEvaluation(cli, workspaceId, {
          ...run,
          status: run.ok ? "ready" : "fallback",
          requestHash: run.requestHash,
          outboundValidation: { contextFingerprint: run.requestHash },
        }, true).catch(() => null);
      }
    }
    sendJson(response, 200, { ...result, runtimeProfile: registry.profiles.find((item) => item.selected), providerEvaluation: evaluation, shadowEvaluation: shadow, agentSession: turnResult.session, sessionContext: turnResult.sessionContext, agentTurn: turnResult.turn, evidencePlan: turnResult.evidencePlan, turnEvents: turnResult.events });
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
    const workspaceId = String(turnResult.workspaceId ?? body.workspaceId ?? "default");
    const selectedProfileId = await selectedRuntimeProfile(cli, workspaceId);
    const registry = agentRuntimeRegistryForProject(root, selectedProfileId);
    const result = await enrichAgentResultWithProvider({ projectRoot: root, prompt, deterministicResult, provider: registry.provider });
    const evaluation = await persistProviderEvaluation(cli, workspaceId, record(record(result.llm).audit)).catch(() => null);
    sendJson(response, 200, { ...result, runtimeProfile: registry.profiles.find((item) => item.selected), providerEvaluation: evaluation, agentSession: turnResult.session, sessionContext: turnResult.sessionContext, agentTurn: turnResult.turn, evidencePlan: turnResult.evidencePlan, turnEvents: turnResult.events });
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
