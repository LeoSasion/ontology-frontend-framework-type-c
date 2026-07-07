import type { QueryResult } from "./types";
import type { BiDashboardDatum, BiDashboardFilterRule, BiDashboardWidget } from "./biDashboardModel";

export function safeQueryInfo(query: QueryResult): QueryResult["query"] {
  const info = query && typeof query.query === "object" && query.query ? query.query : null;
  return {
    table: info?.table ?? "unknown_table",
    mode: info?.mode ?? "aggregate",
    group: info?.group,
    measure: info?.measure ?? "value",
    aggregation: info?.aggregation ?? "sum",
    sqlIntent: info?.sqlIntent ?? "pending query runtime",
    runtime: info?.runtime,
    fallbackReason: info?.fallbackReason,
  };
}

export function toNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (value === null || value === undefined) return 0;
  const normalized = String(value).replace(/,/g, "").trim();
  if (!normalized) return 0;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function rowsFromQuery(query: QueryResult): BiDashboardDatum[] {
  const queryInfo = safeQueryInfo(query);
  const rows = Array.isArray(query.rows) ? query.rows : [];
  return rows.map((row, index) => {
    const label = String(row.label ?? `Row ${index + 1}`);
    const value = toNumber(row.value);
    const groupField = queryInfo.group || "label";
    const measureField = queryInfo.measure || "value";
    return {
      label,
      value,
      raw: {
        label,
        value,
        rank: index + 1,
        table: queryInfo.table,
        measure: queryInfo.measure,
        aggregation: queryInfo.aggregation,
        [groupField]: label,
        [measureField]: value,
      },
    };
  });
}

export function applyBiDashboardFilters(rows: BiDashboardDatum[], filters: BiDashboardFilterRule[]): BiDashboardDatum[] {
  const active = filters.filter((filter) => filter.enabled && filter.field);
  if (!active.length) return rows;
  return rows.filter((row) => active.every((filter) => {
    const raw = row.raw[filter.field] ?? (filter.field === "label" ? row.label : filter.field === "value" ? row.value : "");
    const text = raw === null || raw === undefined ? "" : String(raw);
    const value = filter.value.trim();
    if (filter.operator === "empty") return text.trim() === "";
    if (filter.operator === "notEmpty") return text.trim() !== "";
    if (filter.operator === "equals") return text === value;
    if (filter.operator === "notEquals") return text !== value;
    if (filter.operator === "in") return value.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean).includes(text);
    if (filter.operator === "gt") return toNumber(text) > toNumber(value);
    if (filter.operator === "gte") return toNumber(text) >= toNumber(value);
    if (filter.operator === "lt") return toNumber(text) < toNumber(value);
    if (filter.operator === "lte") return toNumber(text) <= toNumber(value);
    if (filter.operator === "between") {
      const [left, right] = value.split(/[,，]/).map((item) => toNumber(item));
      const current = toNumber(text);
      return current >= (Number.isFinite(left) ? left : Number.NEGATIVE_INFINITY) &&
        current <= (Number.isFinite(right) ? right : Number.POSITIVE_INFINITY);
    }
    return text.includes(value);
  }));
}

function rowsForWidget(widget: BiDashboardWidget, query: QueryResult): BiDashboardDatum[] {
  return rowsFromQuery(query).map((row) => ({
    ...row,
    raw: {
      ...row.raw,
      ...(widget.dimension ? { [widget.dimension]: row.label } : {}),
      ...(widget.measure ? { [widget.measure]: row.value } : {}),
    },
  }));
}

export function aggregateWidgetRows(widget: BiDashboardWidget, query: QueryResult, dashboardFilters: BiDashboardFilterRule[] = []): BiDashboardDatum[] {
  const source = applyBiDashboardFilters(rowsForWidget(widget, query), [...dashboardFilters, ...widget.filters]);
  const rows = [...source].sort((left, right) => {
    if (widget.sortBy === "dimension") {
      return widget.sortDirection === "asc" ? left.label.localeCompare(right.label) : right.label.localeCompare(left.label);
    }
    return widget.sortDirection === "asc" ? left.value - right.value : right.value - left.value;
  });
  return rows.slice(0, Math.max(1, widget.topN));
}

export function calculateWidgetMetricValue(widget: BiDashboardWidget, query: QueryResult, dashboardFilters: BiDashboardFilterRule[] = []): number {
  const rows = aggregateWidgetRows(widget, query, dashboardFilters);
  if (widget.aggregation === "count") return rows.length;
  if (!rows.length) return 0;
  if (widget.aggregation === "avg") return rows.reduce((sum, row) => sum + row.value, 0) / rows.length;
  if (widget.aggregation === "max") return Math.max(...rows.map((row) => row.value));
  if (widget.aggregation === "min") return Math.min(...rows.map((row) => row.value));
  return rows.reduce((sum, row) => sum + row.value, 0);
}
