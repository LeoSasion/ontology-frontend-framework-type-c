import { fetchJson, fetchJsonStrict } from "./apiClient";
import type { QueryResult, TableQueryPayload } from "./types";

export function runQuery(options: {
  table: string;
  group?: string;
  measure?: string;
  aggregation?: string;
  limit?: number;
}) {
  return fetchJsonStrict<QueryResult>("/api/query", {
    method: "POST",
    body: JSON.stringify({
      table: options.table,
      group: options.group,
      measure: options.measure,
      aggregation: options.aggregation ?? "count",
      limit: options.limit ?? 10,
    }),
  });
}

export type TableQueryOptions = {
  table?: string;
  view?: string;
  mode?: "detail" | "aggregate";
  columns?: string[];
  filters?: Array<{ field: string; operator: string; value?: string }>;
  sort?: Array<{ field: string; direction?: string }>;
  search?: string;
  cursor?: string;
  limit?: number;
  groupFields?: string[];
  measure?: string;
  aggregation?: string;
};

export type TableQueryBatchItem = {
  index: number;
  ok: boolean;
  tableQuery?: TableQueryPayload["tableQuery"];
  errorCode?: string;
  error?: string;
};

export type TableQueryBatchPayload = {
  ok: boolean;
  batchQuery: {
    schema: "aibi-query-table-batch/v1";
    planCount: number;
    succeeded: number;
    failed: number;
    responseBytes: number;
    truncatedByBytes?: boolean;
    results: TableQueryBatchItem[];
  };
};

function requiredWorkspaceId(workspaceId: string) {
  const normalized = workspaceId.trim();
  if (!normalized) throw new Error("A workspace is required for table queries");
  return normalized;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function tableQueryBatchContractError(message: string) {
  const error = new Error(message);
  error.name = "TableQueryBatchContractError";
  return error;
}

export function assertTableQueryWorkspace(result: TableQueryPayload, workspaceId: string) {
  const expectedWorkspaceId = requiredWorkspaceId(workspaceId);
  if (result.tableQuery.workspaceId !== expectedWorkspaceId) {
    const error = new Error("Table query result belongs to another workspace");
    error.name = "TableQueryWorkspaceMismatchError";
    throw error;
  }
  return result;
}

export function assertTableQueryBatchWorkspace(
  result: TableQueryBatchPayload,
  workspaceId: string,
  expectedPlanCount: number,
) {
  const expectedWorkspaceId = requiredWorkspaceId(workspaceId);
  const batchQuery = isRecord(result) && isRecord(result.batchQuery) ? result.batchQuery : null;
  if (
    result?.ok !== true
    || !batchQuery
    || batchQuery.schema !== "aibi-query-table-batch/v1"
    || !Number.isInteger(expectedPlanCount)
    || expectedPlanCount < 1
    || batchQuery.planCount !== expectedPlanCount
    || !Array.isArray(batchQuery.results)
    || batchQuery.results.length !== expectedPlanCount
  ) {
    throw tableQueryBatchContractError("Table query batch does not match the expected response contract");
  }
  const indices = new Set<number>();
  for (const item of batchQuery.results) {
    if (!isRecord(item)) {
      throw tableQueryBatchContractError("Table query batch contains an invalid item");
    }
    const index = item.index;
    if (
      !Number.isInteger(index)
      || Number(index) < 0
      || Number(index) >= expectedPlanCount
      || indices.has(Number(index))
      || (item.ok !== true && item.ok !== false)
    ) {
      throw tableQueryBatchContractError("Table query batch item indices are incomplete or invalid");
    }
    indices.add(Number(index));
    if (item.ok === true) {
      if (!isRecord(item.tableQuery)) {
        throw tableQueryBatchContractError("Successful table query batch items require a tableQuery payload");
      }
      if (item.tableQuery.workspaceId !== expectedWorkspaceId) {
        const error = new Error("Table query batch contains a result from another workspace");
        error.name = "TableQueryWorkspaceMismatchError";
        throw error;
      }
    }
  }
  return result;
}

export function runTableQuery(workspaceId: string, options: TableQueryOptions, signal?: AbortSignal) {
  const expectedWorkspaceId = requiredWorkspaceId(workspaceId);
  return fetchJsonStrict<TableQueryPayload>("/api/query-table", {
    method: "POST",
    body: JSON.stringify({ ...options, workspaceId: expectedWorkspaceId }),
    signal,
  }).then((result) => assertTableQueryWorkspace(result, expectedWorkspaceId));
}

export function runTableQueryBatch(workspaceId: string, plans: TableQueryOptions[], signal?: AbortSignal) {
  const expectedWorkspaceId = requiredWorkspaceId(workspaceId);
  return fetchJsonStrict<TableQueryBatchPayload>("/api/query-table/batch", {
    method: "POST",
    body: JSON.stringify({ workspaceId: expectedWorkspaceId, plans }),
    signal,
  }).then((result) => assertTableQueryBatchWorkspace(result, expectedWorkspaceId, plans.length));
}

export function saveView(options: {
  view?: string;
  table: string;
  name: string;
  tag?: string;
  mode?: "detail" | "aggregate";
  columns?: string[];
  filters?: Array<{ field: string; operator: string; value?: string }>;
  sort?: Array<{ field: string; direction?: string }>;
  search?: string;
  agent?: boolean;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/views/save", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function copyView(options: { view: string; name?: string; tag?: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/views/copy", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function deleteView(options: { view: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/views/delete", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}
