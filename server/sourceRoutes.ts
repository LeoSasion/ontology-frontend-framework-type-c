import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type SourceRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  startSourceIntelligenceJob?: (body: Record<string, unknown>) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

export async function handleSourceApi(options: SourceRoutesOptions) {
  const { cli, request, response, startSourceIntelligenceJob, url } = options;

  if (url.pathname === "/api/source-intelligence/runs" && request.method === "GET") {
    const limit = url.searchParams.get("limit") ?? "10";
    const result = await cli(["source-intelligence-runs", "--limit", limit]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/source-intelligence/run" && request.method === "POST") {
    const body = await readBody(request);
    if (body.async === true) {
      if (!startSourceIntelligenceJob) {
        sendJson(response, 503, { ok: false, action: "source-intelligence", error: "Durable job runtime is unavailable" });
        return true;
      }
      const result = await startSourceIntelligenceJob(body);
      sendJson(response, result.ok === false ? 400 : 202, result);
      return true;
    }
    const args = ["source-intelligence"];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    if (body.label) args.push("--label", String(body.label));
    if (body.outputDir) args.push("--output-dir", String(body.outputDir));
    if (Array.isArray(body.inputs)) args.push(...body.inputs.map(String));
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/source-intelligence/dashboard-draft" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["source-dashboard-draft"];
    if (body.runKey) args.push("--run", String(body.runKey));
    if (body.name) args.push("--name", String(body.name));
    if (body.limit) args.push("--limit", String(body.limit));
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/sources" && request.method === "GET") {
    const result = await cli(["list-tables"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/sources/inspect" && request.method === "GET") {
    const table = url.searchParams.get("table") ?? "";
    if (!table) {
      sendJson(response, 400, { ok: false, action: "source", error: "table is required" });
      return true;
    }
    const result = await cli(["inspect-table", table]);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }

  if (url.pathname === "/api/sources/rename" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["rename-source", String(body.source ?? ""), "--name", String(body.name ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/sources/delete" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["delete-source", String(body.source ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/import/preview" && request.method === "POST") {
    const body = await readBody(request);
    const filePath = String(body.filePath ?? "");
    const table = body.table ? String(body.table) : undefined;
    const args = ["preview-import", filePath, ...(table ? ["--table", table] : [])];
    if (Array.isArray(body.uniqueFields) && body.uniqueFields.length) args.push("--unique-fields", body.uniqueFields.map(String).join(","));
    if (body.conflictRule) args.push("--conflict-rule", String(body.conflictRule));
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/import/folder/preview" && request.method === "POST") {
    const body = await readBody(request);
    const folderPath = String(body.path ?? body.folderPath ?? "");
    const args = ["preview-import-folder", folderPath];
    if (body.limit) args.push("--limit", String(body.limit));
    if (body.recursive === false) args.push("--no-recursive");
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/import/policy" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "set-import-policy",
      "--table",
      String(body.table ?? ""),
      "--unique-fields",
      Array.isArray(body.uniqueFields) ? body.uniqueFields.map(String).join(",") : String(body.uniqueFields ?? ""),
    ];
    if (body.conflictRule) args.push("--conflict-rule", String(body.conflictRule));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/import/jobs" && request.method === "GET") {
    const args = ["list-import-jobs"];
    const table = url.searchParams.get("table");
    const status = url.searchParams.get("status");
    const search = url.searchParams.get("search");
    const limit = url.searchParams.get("limit") ?? "20";
    if (table) args.push("--table", table);
    if (status) args.push("--status", status);
    if (search) args.push("--search", search);
    args.push("--limit", limit);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/import/jobs/remove" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["remove-import-job", "--job", String(body.jobKey ?? body.job ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/import/commit" && request.method === "POST") {
    const body = await readBody(request);
    const filePath = String(body.filePath ?? "");
    const args = ["import-commit", filePath];
    if (body.table) args.push("--table", String(body.table));
    if (body.name) args.push("--name", String(body.name));
    if (body.mode) args.push("--mode", String(body.mode));
    if (Array.isArray(body.uniqueFields) && body.uniqueFields.length) args.push("--unique-fields", body.uniqueFields.map(String).join(","));
    if (body.conflictRule) args.push("--conflict-rule", String(body.conflictRule));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/import/folder/commit" && request.method === "POST") {
    const body = await readBody(request);
    const folderPath = String(body.path ?? body.folderPath ?? "");
    const args = ["import-folder", folderPath];
    if (body.limit) args.push("--limit", String(body.limit));
    if (body.recursive === false) args.push("--no-recursive");
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/connectors" && request.method === "GET") {
    const args = ["list-connectors"];
    const type = url.searchParams.get("type");
    const status = url.searchParams.get("status");
    const search = url.searchParams.get("search");
    if (type) args.push("--type", type);
    if (status) args.push("--status", status);
    if (search) args.push("--search", search);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/connectors" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["save-connector", "--name", String(body.name ?? "")];
    if (body.connector) args.push("--connector", String(body.connector));
    if (body.type) args.push("--type", String(body.type));
    if (body.provider) args.push("--provider", String(body.provider));
    if (body.status) args.push("--status", String(body.status));
    if (body.endpoint) args.push("--endpoint", String(body.endpoint));
    if (body.resource) args.push("--resource", String(body.resource));
    if (body.pageParam) args.push("--page-param", String(body.pageParam));
    if (body.pageSizeParam) args.push("--page-size-param", String(body.pageSizeParam));
    if (body.pageSize) args.push("--page-size", String(body.pageSize));
    if (body.maxPages) args.push("--max-pages", String(body.maxPages));
    if (body.importMode) args.push("--import-mode", String(body.importMode));
    if (body.targetTable) args.push("--target-table", String(body.targetTable));
    if (Array.isArray(body.uniqueFields)) args.push("--unique-fields", body.uniqueFields.map(String).join(","));
    if (body.conflictRule) args.push("--conflict-rule", String(body.conflictRule));
    if (body.schedule) args.push("--schedule", String(body.schedule));
    if (body.notes) args.push("--notes", String(body.notes));
    if (body.credentialRef) args.push("--credential-ref", String(body.credentialRef));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/connectors/sync" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["sync-connector", "--connector", String(body.connector ?? "")];
    if (body.allowPaused === true) args.push("--allow-paused");
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/connector-adapters" && request.method === "GET") {
    const result = await cli(["list-connector-adapters"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/connectors/discover" && request.method === "POST") {
    const body = await readBody(request);
    const result = await cli(["discover-connector", "--connector", String(body.connector ?? "")]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/connectors/preview" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["preview-connector", "--connector", String(body.connector ?? "")];
    if (body.limit) args.push("--limit", String(body.limit));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/connectors/sync-plan" && request.method === "POST") {
    const body = await readBody(request);
    const result = await cli(["plan-connector-sync", "--connector", String(body.connector ?? "")]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/connectors/federation-proof" && request.method === "POST") {
    const body = await readBody(request);
    const connectors = Array.isArray(body.connectors) ? body.connectors.map(String) : [];
    const relationships = Array.isArray(body.relationships) ? body.relationships.map(String) : [];
    const args = [
      "federation-proof",
      "--connectors", connectors.join(","),
      "--projections", JSON.stringify(body.projections ?? {}),
      "--relationships", relationships.join(","),
      "--grain", String(body.grain ?? ""),
      "--entity-key", String(body.entityKey ?? ""),
      "--filters", JSON.stringify(body.filters ?? []),
    ];
    const budget = body.budget && typeof body.budget === "object" ? body.budget as Record<string, unknown> : {};
    if (budget.maxSources !== undefined) args.push("--max-sources", String(budget.maxSources));
    if (budget.maxProjectedFields !== undefined) args.push("--max-fields", String(budget.maxProjectedFields));
    if (budget.maxRelationships !== undefined) args.push("--max-relationships", String(budget.maxRelationships));
    if (budget.maxFilters !== undefined) args.push("--max-filters", String(budget.maxFilters));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/connectors/remove" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["remove-connector", "--connector", String(body.connector ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname.startsWith("/api/source-runs/") && request.method === "GET") {
    const sourceRunId = decodeURIComponent(url.pathname.replace("/api/source-runs/", ""));
    const result = await cli(["source-run", sourceRunId]);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }

  return false;
}
