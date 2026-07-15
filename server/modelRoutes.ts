import type { IncomingMessage, ServerResponse } from "node:http";
import { appendCliFilters } from "./cliArgBuilders";
import { readBody, sendJson } from "./serverRuntime";

type ModelRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

export function appendRelationshipMappingArgs(args: string[], body: Record<string, unknown>) {
  const mappings = Array.isArray(body.fieldMappings)
    ? body.fieldMappings
    : Array.isArray(body.mappings)
      ? body.mappings
      : [];
  const validMappings = mappings.filter((item): item is Record<string, unknown> => Boolean(
    item && typeof item === "object" && !Array.isArray(item) && item.leftField && item.rightField,
  ));
  if (validMappings.length) {
    for (const mapping of validMappings) {
      args.push("--map-json", JSON.stringify({ leftField: String(mapping.leftField), rightField: String(mapping.rightField) }));
    }
    return;
  }
  args.push(
    "--left-field",
    String(body.leftField ?? ""),
    "--right-field",
    String(body.rightField ?? ""),
  );
}

export function appendRelationshipFilterArgs(args: string[], body: Record<string, unknown>) {
  if (!Array.isArray(body.filters)) return;
  for (const filter of body.filters) {
    if (!filter || typeof filter !== "object" || Array.isArray(filter)) continue;
    const value = filter as Record<string, unknown>;
    if (!value.field || !value.operator) continue;
    args.push("--filter-json", JSON.stringify({
      phase: value.phase === "pre" ? "pre" : "post",
      side: String(value.side ?? ""),
      field: String(value.field),
      operator: String(value.operator),
      value: value.value ?? "",
      enabled: value.enabled !== false,
    }));
  }
}

export function appendRelationshipPreaggregationArg(args: string[], body: Record<string, unknown>) {
  const value = body.preaggregation;
  if (value && typeof value === "object" && !Array.isArray(value)) {
    args.push("--preaggregate-json", JSON.stringify(value));
  }
}

export async function handleModelApi(options: ModelRoutesOptions) {
  const { cli, request, response, url } = options;

  if (url.pathname === "/api/semantic-query" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["semantic-query", String(body.prompt ?? "")];
    if (body.table) args.push("--table", String(body.table));
    if (body.limit) args.push("--limit", String(body.limit));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/relationships/preview" && request.method === "POST") {
    const body = await readBody(request);
    const workspaceId = String(body.workspaceId ?? "").trim();
    if (!workspaceId) {
      sendJson(response, 400, { ok: false, error: "workspaceId is required for relationship preview" });
      return true;
    }
    const args = [
      "relationship-preview",
      "--workspace",
      workspaceId,
      "--left-table",
      String(body.leftTable ?? ""),
      "--right-table",
      String(body.rightTable ?? ""),
    ];
    appendRelationshipMappingArgs(args, body);
    appendRelationshipFilterArgs(args, body);
    appendRelationshipPreaggregationArg(args, body);
    if (body.joinType) args.push("--join-type", String(body.joinType));
    if (body.limit) args.push("--limit", String(body.limit));
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/relationships" && request.method === "GET") {
    const result = await cli(["list-relationships"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/relationships/recommend" && request.method === "GET") {
    const args = ["recommend-relationships"];
    const limit = url.searchParams.get("limit");
    if (limit) args.push("--limit", limit);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/relationships/query" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["query-relationship"];
    if (body.relationship || body.relation) {
      args.push("--relationship", String(body.relationship ?? body.relation));
    } else {
      args.push(
        "--left-table",
        String(body.leftTable ?? ""),
        "--right-table",
        String(body.rightTable ?? ""),
      );
      appendRelationshipMappingArgs(args, body);
      if (body.joinType) args.push("--join-type", String(body.joinType));
    }
    if (Array.isArray(body.groupFields)) body.groupFields.map(String).forEach((group) => args.push("--group", group));
    if (body.group) args.push("--group", String(body.group));
    if (body.measure) args.push("--measure", String(body.measure));
    if (body.aggregation) args.push("--agg", String(body.aggregation));
    if (body.limit) args.push("--limit", String(body.limit));
    if (body.sortBy) args.push("--sort-by", String(body.sortBy));
    if (body.sortDirection) args.push("--sort-direction", String(body.sortDirection));
    appendRelationshipFilterArgs(args, body);
    appendRelationshipPreaggregationArg(args, body);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/relationships/remove" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["remove-relationship", "--relationship", String(body.relationship ?? body.relation ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/relationships/save" && request.method === "POST") {
    const body = await readBody(request);
    const workspaceId = String(body.workspaceId ?? "").trim();
    if (!workspaceId) {
      sendJson(response, 400, { ok: false, error: "workspaceId is required for relationship save" });
      return true;
    }
    const args = [
      "relationship-save",
      "--workspace",
      workspaceId,
      "--left-table",
      String(body.leftTable ?? ""),
      "--right-table",
      String(body.rightTable ?? ""),
    ];
    appendRelationshipMappingArgs(args, body);
    appendRelationshipFilterArgs(args, body);
    appendRelationshipPreaggregationArg(args, body);
    if (body.joinType) args.push("--join-type", String(body.joinType));
    if (body.limit) args.push("--limit", String(body.limit));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/formulas/preview" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["formula-preview", String(body.expression ?? "")];
    if (body.table) args.push("--table", String(body.table));
    if (body.mode) args.push("--mode", String(body.mode));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/formulas" && request.method === "GET") {
    const args = ["list-formulas"];
    const table = url.searchParams.get("table");
    if (table) args.push("--table", table);
    if (url.searchParams.get("all") === "true") args.push("--all");
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/formulas/save" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "save-formula",
      "--name",
      String(body.name ?? "公式指标"),
      "--table",
      String(body.table ?? ""),
      "--expression",
      String(body.expression ?? ""),
      "--mode",
      String(body.mode ?? "aggregate"),
    ];
    if (body.id) args.push("--id", String(body.id));
    if (body.dimension) args.push("--dimension", String(body.dimension));
    if (body.timeField) args.push("--time-field", String(body.timeField));
    if (body.valueFormat) args.push("--value-format", String(body.valueFormat));
    if (body.description) args.push("--description", String(body.description));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/formulas/delete" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["delete-formula", String(body.formula ?? body.id ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/indexes/recommend" && request.method === "GET") {
    const args = ["recommend-indexes"];
    const table = url.searchParams.get("table");
    const limit = url.searchParams.get("limit");
    if (table) args.push("--table", table);
    if (limit) args.push("--limit", limit);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/indexes/create" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["create-index", "--table", String(body.table ?? ""), "--field", String(body.field ?? "")];
    if (body.index) args.push("--index", String(body.index));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/fields/update" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "field-update",
      "--table",
      String(body.table ?? ""),
      "--field",
      String(body.field ?? ""),
      "--role",
      String(body.role ?? ""),
      "--usage",
      String(body.usage ?? ""),
      "--confidence",
      String(body.confidence ?? "0.9"),
    ];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/semantics/infer" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["infer-semantics"];
    if (body.table) args.push("--table", String(body.table));
    if (body.overwriteManual === true) args.push("--overwrite-manual");
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/semantics" && request.method === "GET") {
    const args = ["list-semantics"];
    const table = url.searchParams.get("table");
    if (table) args.push("--table", table);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/semantics" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "set-semantic",
      String(body.table ?? ""),
      String(body.field ?? ""),
      "--role",
      String(body.role ?? "dimension"),
    ];
    if (Array.isArray(body.tags)) body.tags.map(String).forEach((tag) => args.push("--tag", tag));
    if (Array.isArray(body.usage)) body.usage.map(String).forEach((usage) => args.push("--usage", usage));
    if (body.confidence !== undefined) args.push("--confidence", String(body.confidence));
    if (body.note) args.push("--note", String(body.note));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/metrics/infer" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["infer-metrics"];
    if (body.table) args.push("--table", String(body.table));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/metrics" && request.method === "GET") {
    const args = ["list-metrics"];
    const table = url.searchParams.get("table");
    if (table) args.push("--table", table);
    if (url.searchParams.get("all") === "true") args.push("--all");
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/metrics" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["add-metric", "--name", String(body.name ?? ""), "--table", String(body.table ?? "")];
    if (body.id) args.push("--id", String(body.id));
    if (body.field) args.push("--field", String(body.field));
    if (body.aggregation || body.agg) args.push("--agg", String(body.aggregation ?? body.agg));
    if (body.dimension) args.push("--dimension", String(body.dimension));
    if (body.timeField) args.push("--time-field", String(body.timeField));
    appendCliFilters(args, body.filters);
    if (body.valueFormat) args.push("--value-format", String(body.valueFormat));
    if (body.description) args.push("--description", String(body.description));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/metrics/query" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["query-metric", String(body.metric ?? body.metricKey ?? "")];
    if (Array.isArray(body.group)) body.group.map(String).forEach((group) => args.push("--group", group));
    if (Array.isArray(body.groups)) body.groups.map(String).forEach((group) => args.push("--group", group));
    appendCliFilters(args, body.filters);
    if (body.sort) args.push("--sort", String(body.sort));
    if (body.limit) args.push("--limit", String(body.limit));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  return false;
}
