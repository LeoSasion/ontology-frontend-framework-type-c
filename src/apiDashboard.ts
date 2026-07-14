import { fetchJson, fetchJsonStrict } from "./apiClient";
import type { DashboardFilterPayload } from "./types";

export function getDashboardWidgetCatalog() {
  return fetchJson<Record<string, unknown>>("/api/dashboard/widget-catalog", { ok: false });
}

export function recommendDashboardWidgets(options: { table?: string; limit?: number }) {
  const params = new URLSearchParams();
  if (options.table) params.set("table", options.table);
  if (options.limit) params.set("limit", String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Record<string, unknown>>(`/api/dashboard/recommend-widgets${suffix}`, { ok: false });
}

export function saveDashboardModules(options: {
  dashboardKey: string;
  dashboardName?: string;
  defaultTableKey?: string;
  canvasWidthMode?: "stretch" | "center";
  widgets: Array<Record<string, unknown>>;
  layout: Array<Record<string, unknown>>;
  filters: Array<Record<string, unknown>>;
  confirm?: boolean;
}) {
  return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/modules", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function businessDashboardOperation(options: {
  op: "draft" | "create" | "overwrite";
  dashboardKey?: string;
  name?: string;
  table?: string;
  template?: "business" | "erp-units";
  limit?: number;
  confirm?: boolean;
}) {
  return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/business-template", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function dashboardWidgetOperation(options: {
  op: "recommend" | "addRecommended" | "add" | "addRelationship" | "set" | "copy" | "remove";
  dashboardKey?: string;
  widgetKey?: string;
  relationship?: string;
  relation?: string;
  table?: string;
  view?: string;
  type?: string;
  title?: string;
  subtitle?: string;
  group?: string;
  dimension?: string;
  measure?: string;
  aggregation?: string;
  topN?: number;
  valueFormat?: string;
  textContent?: string;
  sortBy?: string;
  sortDirection?: string;
  decimalPlaces?: number;
  tableColumnLimit?: number;
  slicerDisplay?: string;
  slicerMultiSelect?: boolean;
  slicerSearchable?: boolean;
  showLegend?: boolean;
  showAxis?: boolean;
  showDataLabel?: boolean;
  rankingMode?: string;
  colorPalette?: string;
  barOrientation?: string;
  lineSmooth?: boolean;
  areaFill?: boolean;
  pieShape?: string;
  crossFilter?: boolean;
  drillDown?: boolean;
  globalFilterTarget?: boolean;
  xAxisTitle?: string;
  yAxisTitle?: string;
  legendTitle?: string;
  filters?: Array<{ field: string; operator: string; value?: string }>;
  clearFilters?: boolean;
  limit?: number;
  allowDuplicates?: boolean;
  confirm?: boolean;
}) {
  return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/widgets", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function dashboardOperation(options: {
  op: "create" | "copy" | "rename" | "delete";
  dashboardKey?: string;
  sourceDashboardKey?: string;
  name?: string;
  table?: string;
  confirm?: boolean;
}) {
  return fetchJsonStrict<Record<string, unknown>>("/api/dashboards/operation", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function dashboardFilterOperation(options: {
  op: "list" | "add" | "set" | "remove" | "removeStale" | "clear";
  dashboardKey: string;
  filterId?: string;
  field?: string;
  operator?: string;
  value?: string;
  disabled?: boolean;
  confirm?: boolean;
}) {
  return fetchJsonStrict<DashboardFilterPayload>("/api/dashboards/filters", {
    method: "POST",
    body: JSON.stringify(options),
  });
}
