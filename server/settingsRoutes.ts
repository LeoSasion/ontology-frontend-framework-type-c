import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type SettingsRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

export async function handleSettingsApi(options: SettingsRoutesOptions) {
  const { cli, request, response, url } = options;

  if (url.pathname === "/api/context" && request.method === "GET") {
    const result = await cli(["context-pack"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/context/terms" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "context-term",
      "--name", String(body.name ?? ""),
      "--definition", String(body.definition ?? ""),
      "--scope-type", String(body.scopeType ?? "workspace"),
      "--scope-ref", String(body.scopeRef ?? ""),
      "--status", String(body.status ?? "draft"),
      "--source", String(body.source ?? "manual"),
    ];
    if (body.termKey) args.push("--term", String(body.termKey));
    if (Array.isArray(body.aliases)) for (const alias of body.aliases) args.push("--alias", String(alias));
    if (Array.isArray(body.evidenceRefs)) for (const ref of body.evidenceRefs) args.push("--evidence", String(ref));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/context/rules" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "context-rule",
      "--title", String(body.title ?? ""),
      "--statement", String(body.statement ?? ""),
      "--type", String(body.ruleType ?? "other"),
      "--status", String(body.status ?? "draft"),
      "--source", String(body.source ?? "manual"),
    ];
    if (body.ruleKey) args.push("--rule", String(body.ruleKey));
    if (Array.isArray(body.appliesTo)) for (const target of body.appliesTo) args.push("--applies-to", String(target));
    if (Array.isArray(body.evidenceRefs)) for (const ref of body.evidenceRefs) args.push("--evidence", String(ref));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/knowledge-source-adapters" && request.method === "GET") {
    const result = await cli(["knowledge-source-adapters"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/knowledge-sources" && request.method === "GET") {
    const result = await cli(["knowledge-sources", "--limit", url.searchParams.get("limit") ?? "50"]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/knowledge-sources/propose" && request.method === "POST") {
    const body = await readBody(request);
    const input = String(body.input ?? "").trim();
    const adapter = String(body.adapter ?? "auto").trim();
    const sourceType = String(body.sourceType ?? "documentation").trim();
    const sourceName = String(body.sourceName ?? "").trim();
    if (!input || input.length > 2048 || !new Set(["auto", "knowledge-json-v1", "knowledge-markdown-v1"]).has(adapter) || !new Set(["data-dictionary", "documentation"]).has(sourceType) || sourceName.length > 160) {
      sendJson(response, 400, { ok: false, code: "KNOWLEDGE_SOURCE_INPUT_INVALID", error: "A bounded local JSON/Markdown input and supported adapter are required." });
      return true;
    }
    const args = ["semantic-patch-propose", "--input", input, "--adapter", adapter, "--source-type", sourceType];
    if (sourceName) args.push("--source-name", sourceName);
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/semantic-patches" && request.method === "GET") {
    const args = ["semantic-patch-proposals", "--limit", url.searchParams.get("limit") ?? "100"];
    const proposal = url.searchParams.get("proposal");
    const status = url.searchParams.get("status");
    if (proposal) args.push("--proposal", proposal);
    if (status) args.push("--status", status);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/semantic-patches/propose" && request.method === "POST") {
    const body = await readBody(request);
    const kind = String(body.kind ?? "");
    if (!new Set(["term", "rule", "field-semantic"]).has(kind)) {
      sendJson(response, 400, { ok: false, error: "kind must be term, rule, or field-semantic" });
      return true;
    }
    const args = [
      "semantic-patch-propose", "--adapter", "user-correction-v1", "--source-type", "user-correction",
      "--source-name", String(body.sourceName ?? "User correction"), "--kind", kind,
      "--confidence", String(body.confidence ?? 1),
    ];
    if (kind === "term") {
      args.push("--name", String(body.name ?? ""), "--definition", String(body.definition ?? ""));
      if (body.termKey) args.push("--term", String(body.termKey));
      args.push("--scope-type", String(body.scopeType ?? "workspace"), "--scope-ref", String(body.scopeRef ?? ""));
      if (Array.isArray(body.aliases)) for (const alias of body.aliases) args.push("--alias", String(alias));
    } else if (kind === "rule") {
      args.push("--title", String(body.title ?? ""), "--statement", String(body.statement ?? ""), "--type", String(body.ruleType ?? "other"));
      if (body.ruleKey) args.push("--rule", String(body.ruleKey));
      if (Array.isArray(body.appliesTo)) for (const target of body.appliesTo) args.push("--applies-to", String(target));
    } else {
      args.push(
        "--table", String(body.tableKey ?? ""), "--field", String(body.fieldName ?? ""),
        "--role", String(body.role ?? ""), "--note", String(body.note ?? ""),
      );
      if (Array.isArray(body.usage)) for (const usage of body.usage) args.push("--usage", String(usage));
      if (Array.isArray(body.tags)) for (const tag of body.tags) args.push("--tag", String(tag));
    }
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/semantic-patches/review" && request.method === "POST") {
    const body = await readBody(request);
    const proposalKey = String(body.proposalKey ?? "");
    const decision = String(body.decision ?? "");
    if (!proposalKey || !new Set(["accept", "reject"]).has(decision)) {
      sendJson(response, 400, { ok: false, error: "proposalKey and a valid decision are required" });
      return true;
    }
    const args = ["semantic-patch-review", "--proposal", proposalKey, "--decision", decision, "--note", String(body.note ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/semantic-releases" && request.method === "GET") {
    const requestedLimit = Number.parseInt(url.searchParams.get("limit") ?? "50", 10);
    const boundedLimit = Number.isFinite(requestedLimit) ? Math.min(100, Math.max(1, requestedLimit)) : 50;
    const args = ["semantic-releases", "--limit", String(boundedLimit)];
    const release = url.searchParams.get("release");
    if (release) args.push("--release", release);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname.startsWith("/api/semantic-releases/") && request.method === "POST") {
    const body = await readBody(request);
    const requestKey = String(body.requestKey ?? "").trim();
    const proposalKeys = Array.isArray(body.proposalKeys) ? body.proposalKeys.map(String) : [];
    const expectedPlan = String(body.expectedPlanFingerprint ?? "").trim();
    if (!requestKey || requestKey.length > 200 || proposalKeys.length > 100 || proposalKeys.some((item) => !/^patch_[a-f0-9]{20}$/.test(item))) {
      sendJson(response, 400, { ok: false, code: "SEMANTIC_RELEASE_INPUT_INVALID", error: "A bounded requestKey and valid proposal keys are required." });
      return true;
    }
    if (url.pathname === "/api/semantic-releases/preview") {
      if (proposalKeys.length < 1) {
        sendJson(response, 400, { ok: false, code: "SEMANTIC_RELEASE_PROPOSALS_REQUIRED", error: "Select at least one semantic proposal." });
        return true;
      }
      const args = ["semantic-release-preview", "--request-key", requestKey, "--label", String(body.label ?? "Semantic release")];
      for (const proposal of proposalKeys) args.push("--proposal", proposal);
      const result = await cli(args);
      sendJson(response, result.ok === false ? 409 : 200, result);
      return true;
    }
    if (url.pathname === "/api/semantic-releases/publish") {
      if (body.confirm !== true || proposalKeys.length < 1 || !/^[a-f0-9]{64}$/.test(expectedPlan)) {
        sendJson(response, 400, { ok: false, code: "SEMANTIC_RELEASE_CONFIRMATION_REQUIRED", error: "Publish requires confirm=true and the exact preview fingerprint." });
        return true;
      }
      const args = ["semantic-release-publish", "--request-key", requestKey, "--label", String(body.label ?? "Semantic release"), "--expected-plan", expectedPlan, "--yes"];
      for (const proposal of proposalKeys) args.push("--proposal", proposal);
      const result = await cli(args);
      sendJson(response, result.ok === false ? 409 : 200, result);
      return true;
    }
    if (url.pathname === "/api/semantic-releases/rollback") {
      const releaseKey = String(body.releaseKey ?? "").trim();
      if (!/^release_[a-f0-9]{20}$/.test(releaseKey) || (body.confirm === true && !/^[a-f0-9]{64}$/.test(expectedPlan))) {
        sendJson(response, 400, { ok: false, code: "SEMANTIC_RELEASE_ROLLBACK_INPUT_INVALID", error: "Rollback requires a valid release and exact preview binding when confirmed." });
        return true;
      }
      const args = ["semantic-release-rollback", "--release", releaseKey, "--request-key", requestKey];
      if (body.confirm === true) args.push("--expected-plan", expectedPlan, "--yes");
      const result = await cli(args);
      sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
      return true;
    }
  }

  if (url.pathname === "/api/confirmed-queries" && request.method === "GET") {
    const args = ["confirmed-queries", "--limit", url.searchParams.get("limit") ?? "20"];
    const status = url.searchParams.get("status");
    if (status) args.push("--status", status);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/confirmed-queries/confirm" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["confirm-query", "--query", String(body.queryKey ?? ""), "--status", String(body.status ?? "confirmed")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/confirmed-plans" && request.method === "GET") {
    const args = ["confirmed-plans", "--limit", url.searchParams.get("limit") ?? "20"];
    const status = url.searchParams.get("status");
    if (status) args.push("--status", status);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/recall-receipts" && request.method === "GET") {
    const args = ["recall-receipts", "--limit", url.searchParams.get("limit") ?? "20"];
    const receipt = url.searchParams.get("receipt");
    if (receipt) args.push("--receipt", receipt);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/preferences" && request.method === "GET") {
    const result = await cli(["preferences"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/preferences" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["preferences"];
    const preferences = typeof body.preferences === "object" && body.preferences ? body.preferences as Record<string, unknown> : body;
    const booleanFlags: Array<[string, string]> = [
      ["requireDeleteNameConfirmation", "--require-delete-name-confirmation"],
      ["autoSaveDashboardOnSwitch", "--auto-save-dashboard-on-switch"],
      ["agentCanManageGeneratedAssets", "--agent-can-manage-generated-assets"],
      ["agentCanManageManualAssets", "--agent-can-manage-manual-assets"],
    ];
    if (preferences.themeKey) args.push("--theme-key", String(preferences.themeKey));
    for (const [key, flag] of booleanFlags) {
      if (typeof preferences[key] === "boolean") {
        args.push(flag, preferences[key] ? "true" : "false");
      }
    }
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/theme-palettes" && request.method === "GET") {
    const result = await cli(["theme-palettes"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/theme-palettes" && request.method === "POST") {
    const body = await readBody(request);
    const action = String(body.action ?? "save");
    const theme = typeof body.theme === "object" && body.theme ? body.theme as Record<string, unknown> : body;
    const args = ["theme-palettes", "--action", action];
    if (body.themeKey || theme.themeKey) args.push("--theme-key", String(body.themeKey ?? theme.themeKey));
    if (theme.name) args.push("--name", String(theme.name));
    if (theme.mode) args.push("--mode", String(theme.mode));
    if (theme.tokens && typeof theme.tokens === "object") args.push("--tokens-json", JSON.stringify(theme.tokens));
    if (theme.sortOrder !== undefined) args.push("--sort", String(theme.sortOrder));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/config/validate" && request.method === "GET") {
    const result = await cli(["validate-config"]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/config/export" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["export-config"];
    if (body.output) args.push(String(body.output));
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/config/apply" && request.method === "POST") {
    const body = await readBody(request);
    const input = String(body.input ?? "");
    if (!input) {
      sendJson(response, 400, { ok: false, error: "input is required" });
      return true;
    }
    const args = ["apply-config", input];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  return false;
}
