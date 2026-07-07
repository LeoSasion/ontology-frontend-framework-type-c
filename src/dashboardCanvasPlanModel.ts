import { biText } from "./components/Bilingual";
import type { DashboardCanvasWidthMode } from "./dashboardCanvasWidgetModel";

export type DashboardWidgetPlanSummary = {
  plannedWidgets: Array<Record<string, unknown>>;
  moduleSaveResult: Record<string, unknown> | null;
  businessDraft: Record<string, unknown> | null;
  businessCategories: Array<Record<string, unknown>>;
  businessTemplateCount: number;
};

export type DashboardModuleSaveReceipt = {
  title: string;
  impact: string;
  nextStep: string;
  widgetCount: number;
  filterCount: number;
  widthMode: string;
};

function moduleResultNumber(result: Record<string, unknown> | null, primaryKey: string, fallbackKey: string, fallbackValue: number) {
  const primary = result?.[primaryKey];
  if (typeof primary === "number" && Number.isFinite(primary)) return primary;
  const fallback = result?.[fallbackKey];
  if (typeof fallback === "number" && Number.isFinite(fallback)) return fallback;
  return fallbackValue;
}

export function summarizeDashboardWidgetPlan(widgetPlan: Record<string, unknown> | null): DashboardWidgetPlanSummary {
  const plannedWidgets = Array.isArray(widgetPlan?.plannedWidgets)
    ? widgetPlan.plannedWidgets as Array<Record<string, unknown>>
    : Array.isArray(widgetPlan?.proposedWidgets)
      ? widgetPlan.proposedWidgets as Array<Record<string, unknown>>
      : Array.isArray(widgetPlan?.recommendations)
        ? widgetPlan.recommendations as Array<Record<string, unknown>>
        : [];
  const moduleSaveResult = widgetPlan?.proposed && typeof widgetPlan.proposed === "object"
    ? widgetPlan.proposed as Record<string, unknown>
    : widgetPlan?.savedDashboardKey
      ? widgetPlan
      : null;
  const businessDraft = widgetPlan?.draft && typeof widgetPlan.draft === "object"
    ? widgetPlan.draft as Record<string, unknown>
    : null;
  const businessCategories = Array.isArray(businessDraft?.categories) ? businessDraft.categories as Array<Record<string, unknown>> : [];
  const businessTemplateCount = typeof widgetPlan?.templateCount === "number"
    ? widgetPlan.templateCount
    : Array.isArray(businessDraft?.templates)
      ? businessDraft.templates.length
      : 0;

  return {
    plannedWidgets,
    moduleSaveResult,
    businessDraft,
    businessCategories,
    businessTemplateCount,
  };
}

export function dashboardModuleSaveReceipt(
  result: Record<string, unknown> | null,
  requiresConfirmation: boolean,
  widgetFallback: number,
  filterFallback: number,
  canvasWidthMode: DashboardCanvasWidthMode,
): DashboardModuleSaveReceipt {
  const widgetCount = moduleResultNumber(result, "widgetCount", "savedDashboardModules", widgetFallback);
  const filterCount = moduleResultNumber(result, "filterCount", "savedDashboardFilters", filterFallback);
  const widthMode = String(result?.canvasWidthMode ?? canvasWidthMode);
  if (requiresConfirmation || result?.requiresConfirmation === true) {
    return {
      title: biText("预演完成，确认前不会写入", "Preview ready; nothing is written yet"),
      impact: biText(
        `确认后会用 ${widgetCount} 个组件和 ${filterCount} 条筛选重建当前看板，画布宽度为${widthMode === "center" ? "居中" : "拉伸"}。`,
        `Confirming will rebuild this dashboard with ${widgetCount} widgets and ${filterCount} filters, using ${widthMode} canvas width.`,
      ),
      nextStep: biText("先检查画布是否符合预期；确认后 Agent 和证据链会读取这版看板。", "Check the canvas first. After confirmation, Agent and evidence can read this dashboard version."),
      widgetCount,
      filterCount,
      widthMode,
    };
  }
  return {
    title: biText("看板组件已保存", "Dashboard modules saved"),
    impact: biText(
      `已保存 ${widgetCount} 个组件、${filterCount} 条筛选和画布布局，刷新后仍会保留。`,
      `${widgetCount} widgets, ${filterCount} filters, and the canvas layout are saved and will survive refresh.`,
    ),
    nextStep: biText("下一步可以问 Agent 解读这张看板，或继续调整组件。", "Next, ask Agent to explain the dashboard or keep tuning widgets."),
    widgetCount,
    filterCount,
    widthMode,
  };
}
