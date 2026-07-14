import {
  B_DASHBOARD_WIDGET_CATALOG,
  type BiDashboardColorPalette,
  type BiDashboardWidget,
  type BiDashboardWidgetCatalogItem,
  type BiDashboardWidgetType,
} from "./biDashboardModel";

const paletteMap: Record<BiDashboardColorPalette, string[]> = {
  default: ["#17745b", "#0f5f4a", "#245c88", "#6c7a76", "#a56512", "#a83f38"],
  fresh: ["#0e7490", "#14a38b", "#58b9a7", "#9bd9cf", "#4f8ea8", "#6d8e99"],
  warm: ["#17745b", "#0f5f4a", "#a56512", "#c7792f", "#7a6b5a", "#a83f38"],
  contrast: ["#0f5f4a", "#1d2326", "#17745b", "#a83f38", "#2b8a3e", "#a56512"],
  mono: ["#0f5f4a", "#17745b", "#25896d", "#7db5a6", "#b7d8cf", "#dceee8"],
};

function clampDisplayInteger(value: unknown, fallback: number, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, Math.round(parsed)));
}

function formatPlainNumber(value: number, decimalPlaces: number): string {
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces,
  });
}

function formatChineseUnit(value: number, decimalPlaces: number): string {
  const abs = Math.abs(value);
  if (abs >= 100000000) return `${formatPlainNumber(value / 100000000, decimalPlaces)}亿`;
  if (abs >= 10000) return `${formatPlainNumber(value / 10000, decimalPlaces)}万`;
  return formatPlainNumber(value, decimalPlaces);
}

export function formatWidgetValue(value: number, widget: BiDashboardWidget): string {
  const decimalPlaces = widget.aggregation === "count" ? 0 : clampDisplayInteger(widget.decimalPlaces, 2, 0, 4);
  if (widget.valueFormat === "plain") return formatPlainNumber(value, decimalPlaces);
  if (widget.valueFormat === "compact") return formatChineseUnit(value, decimalPlaces);
  if (widget.valueFormat === "currency") return `¥${formatChineseUnit(value, decimalPlaces)}`;
  if (widget.valueFormat === "percent") return `${formatPlainNumber(value * 100, decimalPlaces)}%`;
  return widget.aggregation === "count" ? formatPlainNumber(value, 0) : formatChineseUnit(value, decimalPlaces);
}

export function paletteColors(palette: BiDashboardColorPalette): string[] {
  return paletteMap[palette] ?? paletteMap.default;
}

export function catalogByType(type: BiDashboardWidgetType): BiDashboardWidgetCatalogItem {
  return B_DASHBOARD_WIDGET_CATALOG.find((item) => item.type === type) ?? B_DASHBOARD_WIDGET_CATALOG[0];
}
