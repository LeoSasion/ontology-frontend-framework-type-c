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
