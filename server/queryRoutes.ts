import type { IncomingMessage, ServerResponse } from "node:http";
import { appendCliFilters, appendCliSorts } from "./cliArgBuilders";
import { readBody, sendJson } from "./serverRuntime";

type QueryRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

function requestedWorkspaceId(value: unknown) {
  const workspaceId = String(value ?? "").trim();
  return workspaceId && workspaceId.length <= 160 ? workspaceId : "";
}

function tableQueryMatchesWorkspace(result: Record<string, unknown>, workspaceId: string) {
  const tableQuery = result.tableQuery;
  return tableQuery && typeof tableQuery === "object" && !Array.isArray(tableQuery)
    && String((tableQuery as Record<string, unknown>).workspaceId ?? "") === workspaceId;
}

function batchQueryValidationFailure(
  result: Record<string, unknown>,
  workspaceId: string,
  expectedPlanCount: number,
): "contract" | "workspace" | null {
  const batchQuery = result.batchQuery;
  if (!batchQuery || typeof batchQuery !== "object" || Array.isArray(batchQuery)) return "contract";
  const batchRecord = batchQuery as Record<string, unknown>;
  const items = batchRecord.results;
  if (
    result.ok !== true
    || batchRecord.schema !== "aibi-query-table-batch/v1"
    || batchRecord.planCount !== expectedPlanCount
    || !Array.isArray(items)
    || items.length !== expectedPlanCount
  ) return "contract";
  const indices = new Set<number>();
  for (const item of items) {
    if (!item || typeof item !== "object" || Array.isArray(item)) return "contract";
    const record = item as Record<string, unknown>;
    const index = record.index;
    if (
      !Number.isInteger(index)
      || Number(index) < 0
      || Number(index) >= expectedPlanCount
      || indices.has(Number(index))
      || (record.ok !== true && record.ok !== false)
    ) return "contract";
    indices.add(Number(index));
    if (record.ok !== true) continue;
    const tableQuery = record.tableQuery;
    if (!tableQuery || typeof tableQuery !== "object" || Array.isArray(tableQuery)) return "contract";
    if (String((tableQuery as Record<string, unknown>).workspaceId ?? "") !== workspaceId) return "workspace";
  }
  return null;
}

export async function handleQueryApi(options: QueryRoutesOptions) {
  const { cli, request, response, url } = options;

  if (url.pathname === "/api/query-receipts" && request.method === "GET") {
    const args = ["query-receipts", "--limit", url.searchParams.get("limit") ?? "20"];
    const receipt = url.searchParams.get("receipt");
    if (receipt) args.push("--receipt", receipt);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/evidence/export" && request.method === "POST") {
    const body = await readBody(request);
    const receipt = String(body.receipt ?? "");
    if (!receipt) {
      sendJson(response, 400, { ok: false, action: "export-evidence", error: "receipt is required" });
      return true;
    }
    const args = ["export-evidence", "--receipt", receipt];
    if (body.output) args.push("--output", String(body.output));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/query" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["query", "--table", String(body.table ?? ""), "--agg", String(body.aggregation ?? body.agg ?? "count")];
    if (body.group) args.push("--group", String(body.group));
    if (body.measure) args.push("--measure", String(body.measure));
    if (body.limit) args.push("--limit", String(body.limit));
    if (body.request) args.push("--request", String(body.request));
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/query-table" && request.method === "POST") {
    const body = await readBody(request);
    const workspaceId = requestedWorkspaceId(body.workspaceId);
    if (!workspaceId) {
      sendJson(response, 400, {
        ok: false,
        action: "query-table",
        errorCode: "query-table-workspace-required",
        error: "workspaceId is required for table queries",
      });
      return true;
    }
    const args = ["query-table", "--workspace", workspaceId];
    if (body.table) args.push("--table", String(body.table));
    if (body.view) args.push("--view", String(body.view));
    if (body.mode) args.push("--mode", String(body.mode));
    if (Array.isArray(body.columns)) body.columns.map(String).forEach((column) => args.push("--column", column));
    appendCliFilters(args, body.filters);
    appendCliSorts(args, body.sort);
    if (body.search !== undefined) args.push("--search", String(body.search));
    if (body.cursor) args.push("--cursor", String(body.cursor));
    if (body.limit !== undefined) args.push("--limit", String(body.limit));
    if (Array.isArray(body.groupFields)) body.groupFields.map(String).forEach((group) => args.push("--group", group));
    if (body.measure) args.push("--measure", String(body.measure));
    if (body.aggregation) args.push("--agg", String(body.aggregation));
    const result = await cli(args);
    if (result.ok !== false && !tableQueryMatchesWorkspace(result, workspaceId)) {
      sendJson(response, 409, {
        ok: false,
        action: "query-table",
        errorCode: "query-table-workspace-changed",
        error: "The active workspace changed while the table query was running",
      });
      return true;
    }
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/query-table/batch" && request.method === "POST") {
    const body = await readBody(request);
    const workspaceId = requestedWorkspaceId(body.workspaceId);
    if (!workspaceId) {
      sendJson(response, 400, {
        ok: false,
        action: "query-table-batch",
        errorCode: "query-table-batch-workspace-required",
        error: "workspaceId is required for table query batches",
      });
      return true;
    }
    const plans = body.plans;
    if (!Array.isArray(plans) || plans.length < 1 || plans.length > 32) {
      sendJson(response, 400, {
        ok: false,
        action: "query-table-batch",
        errorCode: "query-table-batch-plan-count-invalid",
        error: "plans must contain between 1 and 32 query plans",
      });
      return true;
    }
    const args = ["query-table-batch", "--workspace", workspaceId];
    for (const plan of plans) {
      if (!plan || typeof plan !== "object" || Array.isArray(plan)) {
        sendJson(response, 400, {
          ok: false,
          action: "query-table-batch",
          errorCode: "query-table-batch-plan-invalid",
          error: "Each query plan must be an object",
        });
        return true;
      }
      const encoded = JSON.stringify(plan);
      if (Buffer.byteLength(encoded, "utf8") > 16 * 1024) {
        sendJson(response, 413, {
          ok: false,
          action: "query-table-batch",
          errorCode: "query-table-batch-plan-too-large",
          error: "Each query plan must be at most 16 KiB",
        });
        return true;
      }
      args.push("--plan", encoded);
    }
    const result = await cli(args);
    const validationFailure = result.ok !== false
      ? batchQueryValidationFailure(result, workspaceId, plans.length)
      : null;
    if (validationFailure) {
      sendJson(response, 409, {
        ok: false,
        action: "query-table-batch",
        errorCode: validationFailure === "workspace"
          ? "query-table-batch-workspace-changed"
          : "query-table-batch-contract-mismatch",
        error: validationFailure === "workspace"
          ? "The active workspace changed while the table query batch was running"
          : "The table query batch did not satisfy the expected response contract",
      });
      return true;
    }
    sendJson(response, result.ok === false ? 409 : 200, result);
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
