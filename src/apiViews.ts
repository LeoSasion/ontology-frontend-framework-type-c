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

export function runTableQuery(options: {
  table?: string;
  view?: string;
  mode?: "detail" | "aggregate";
  columns?: string[];
  filters?: Array<{ field: string; operator: string; value?: string }>;
  sort?: Array<{ field: string; direction?: string }>;
  search?: string;
  offset?: number;
  limit?: number;
  groupFields?: string[];
  measure?: string;
  aggregation?: string;
}, signal?: AbortSignal) {
  return fetchJsonStrict<TableQueryPayload>("/api/query-table", {
    method: "POST",
    body: JSON.stringify(options),
    signal,
  });
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
