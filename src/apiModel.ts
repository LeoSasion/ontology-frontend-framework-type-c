import { fetchJson, fetchJsonStrict } from "./apiClient";
import { emptyFormulaPreview } from "./emptyWorkspaceData";
import type { FormulaMutationPayload, FormulaPreviewPayload, QueryResult } from "./types";

export function updateFieldConfig(options: {
  table: string;
  field: string;
  role: string;
  usage: string;
  confidence?: number;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/fields/update", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function inferSemantics(options: { table?: string; overwriteManual?: boolean; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/semantics/infer", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function setSemantic(options: {
  table: string;
  field: string;
  role: string;
  tags?: string[];
  usage?: string[];
  confidence?: number;
  note?: string;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/semantics", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function inferMetrics(options: { table?: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/metrics/infer", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function addMetric(options: {
  id?: string;
  name: string;
  table: string;
  field?: string;
  aggregation?: string;
  dimension?: string;
  timeField?: string;
  filters?: Array<{ field: string; operator: string; value?: string }>;
  valueFormat?: string;
  description?: string;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/metrics", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function queryMetric(options: {
  metric: string;
  group?: string[];
  filters?: Array<{ field: string; operator: string; value?: string }>;
  sort?: string;
  limit?: number;
}) {
  return fetchJson<Record<string, unknown>>("/api/metrics/query", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function runSemanticQuery(options: { prompt: string; table?: string; limit?: number }) {
  return fetchJsonStrict<Record<string, unknown>>("/api/semantic-query", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function recommendRelationships(options: { limit?: number } = {}) {
  const params = new URLSearchParams();
  if (options.limit) params.set("limit", String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Record<string, unknown>>(`/api/relationships/recommend${suffix}`, { ok: false });
}

export function queryRelationship(options: {
  relationship?: string;
  relation?: string;
  leftTable?: string;
  rightTable?: string;
  leftField?: string;
  rightField?: string;
  fieldMappings?: Array<{ leftField: string; rightField: string }>;
  joinType?: string;
  group?: string;
  groupFields?: string[];
  measure?: string;
  aggregation?: string;
  filters?: Array<{ phase?: "pre" | "post"; side?: string; field: string; operator: string; value?: string; enabled?: boolean }>;
  preaggregation?: { side: "right"; groupFields: string[]; measures: Array<{ field: string; aggregation: string }> };
  limit?: number;
  sortBy?: string;
  sortDirection?: string;
}) {
  return fetchJsonStrict<QueryResult>("/api/relationships/query", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function previewFormula(options: {
  expression: string;
  table?: string;
  mode?: string;
}) {
  return fetchJson<FormulaPreviewPayload>("/api/formulas/preview", emptyFormulaPreview, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function saveFormula(options: {
  id?: string;
  name: string;
  table: string;
  expression: string;
  mode?: string;
  dimension?: string;
  timeField?: string;
  valueFormat?: string;
  description?: string;
  confirm?: boolean;
}) {
  return fetchJson<FormulaMutationPayload>("/api/formulas/save", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function deleteFormula(options: {
  formula: string;
  confirm?: boolean;
}) {
  return fetchJson<FormulaMutationPayload>("/api/formulas/delete", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function recommendIndexes(options: { table?: string; limit?: number } = {}) {
  const params = new URLSearchParams();
  if (options.table) params.set("table", options.table);
  if (options.limit) params.set("limit", String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Record<string, unknown>>(`/api/indexes/recommend${suffix}`, { ok: false });
}

export function createIndex(options: { table: string; field: string; index?: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/indexes/create", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}
