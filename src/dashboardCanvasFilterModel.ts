import { biText } from "./components/Bilingual";
import type { DashboardFilterRule } from "./types";

export const filterOperators = ["contains", "equals", "in", "between", "notEquals", "gt", "gte", "lt", "lte", "empty", "notEmpty"] as const;

export function normalizeDashboardFilterList(value: unknown, scope = "dashboard"): DashboardFilterRule[] {
  const raw = Array.isArray(value) ? value : [];
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item, index) => ({
      id: String(item.id ?? `filter-${index + 1}`),
      field: String(item.field ?? ""),
      operator: String(item.operator ?? "equals"),
      value: String(item.value ?? ""),
      enabled: item.enabled !== false,
      scope: String(item.scope ?? scope),
      createdAt: item.createdAt ? String(item.createdAt) : undefined,
      updatedAt: item.updatedAt ? String(item.updatedAt) : undefined,
    }))
    .filter((item) => item.field);
}

export function normalizeDashboardFilters(layout: Record<string, unknown>): DashboardFilterRule[] {
  return normalizeDashboardFilterList(layout.globalFilters, "dashboard");
}

export function normalizeWidgetFilters(value: unknown): DashboardFilterRule[] {
  return normalizeDashboardFilterList(value, "widget");
}

export function buildNextWidgetFilters({
  currentFilters,
  field,
  operator,
  value,
}: {
  currentFilters: DashboardFilterRule[];
  field: string;
  operator: string;
  value: string;
}) {
  return [
    ...currentFilters.map((filter) => ({ field: filter.field, operator: filter.operator, value: filter.value })),
    { field, operator, value },
  ];
}

export function operatorLabel(operator: string) {
  const labels: Record<string, { zh: string; en: string }> = {
    contains: { zh: "包含", en: "contains" },
    equals: { zh: "等于", en: "equals" },
    in: { zh: "属于", en: "in" },
    between: { zh: "介于", en: "between" },
    notEquals: { zh: "不等于", en: "not equals" },
    gt: { zh: "大于", en: "greater than" },
    gte: { zh: "大于等于", en: "at least" },
    lt: { zh: "小于", en: "less than" },
    lte: { zh: "小于等于", en: "at most" },
    empty: { zh: "为空", en: "empty" },
    notEmpty: { zh: "不为空", en: "not empty" },
  };
  return labels[operator] ? biText(labels[operator].zh, labels[operator].en) : operator;
}
