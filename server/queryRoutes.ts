import type { IncomingMessage, ServerResponse } from "node:http";
import { appendCliFilters, appendCliSorts } from "./cliArgBuilders";
import { readBody, sendJson } from "./serverRuntime";

type QueryRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

export async function handleQueryApi(options: QueryRoutesOptions) {
  const { cli, request, response, url } = options;

  if (url.pathname === "/api/query" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["query", "--table", String(body.table ?? ""), "--agg", String(body.aggregation ?? body.agg ?? "count")];
    if (body.group) args.push("--group", String(body.group));
    if (body.measure) args.push("--measure", String(body.measure));
    if (body.limit) args.push("--limit", String(body.limit));
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/query-table" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["query-table"];
    if (body.table) args.push("--table", String(body.table));
    if (body.view) args.push("--view", String(body.view));
    if (body.mode) args.push("--mode", String(body.mode));
    if (Array.isArray(body.columns)) body.columns.map(String).forEach((column) => args.push("--column", column));
    appendCliFilters(args, body.filters);
    appendCliSorts(args, body.sort);
    if (body.search !== undefined) args.push("--search", String(body.search));
    if (body.offset !== undefined) args.push("--offset", String(body.offset));
    if (body.limit !== undefined) args.push("--limit", String(body.limit));
    if (Array.isArray(body.groupFields)) body.groupFields.map(String).forEach((group) => args.push("--group", group));
    if (body.measure) args.push("--measure", String(body.measure));
    if (body.aggregation) args.push("--agg", String(body.aggregation));
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/views/save" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["save-view", "--table", String(body.table ?? ""), "--name", String(body.name ?? "")];
    if (body.view) args.push("--view", String(body.view));
    if (body.tag) args.push("--tag", String(body.tag));
    if (body.mode) args.push("--mode", String(body.mode));
    if (Array.isArray(body.columns)) args.push("--columns", body.columns.map(String).join(","));
    appendCliFilters(args, body.filters);
    appendCliSorts(args, body.sort);
    if (body.search !== undefined) args.push("--search", String(body.search));
    if (body.agent === true) args.push("--agent");
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/views/copy" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["copy-view", "--view", String(body.view ?? "")];
    if (body.name) args.push("--name", String(body.name));
    if (body.tag) args.push("--tag", String(body.tag));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/views/delete" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["delete-view", "--view", String(body.view ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  return false;
}
