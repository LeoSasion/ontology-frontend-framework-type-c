import type {
  DashboardFilterRule,
  DashboardPage,
  DashboardWidget,
  QueryResult,
  WorkbenchPayload,
} from "./types";
import { buildNextWidgetFilters } from "./dashboardCanvasFilterModel";
import {
  buildDashboardEvidenceFocus,
  buildDashboardReadinessModel,
} from "./dashboardCanvasReadinessModel";
import { summarizeDashboardWidgetPlan } from "./dashboardCanvasPlanModel";
import { analyzeDashboardSourceSwitch } from "./dashboardCanvasSourceSwitchModel";
import { buildDashboardSourceSwitchViewModel } from "./dashboardCanvasSourceSwitchViewModel";
import { buildDashboardSummaryModel } from "./dashboardCanvasSummaryModel";
import { latestUsableSourceIntelligenceRun } from "./workspaceFlowModel";

type DashboardCanvasViewModelOptions = {
  dashboard: DashboardPage;
  filters: DashboardFilterRule[];
  query: QueryResult;
  sourceSwitchTableKey: string;
  widgetFilterField: string;
  widgetFilterOperator: string;
  widgetFilterValue: string;
  widgetFilters: DashboardFilterRule[];
  widgetPlan: Record<string, unknown> | null;
  widgets: DashboardWidget[];
  workbench: WorkbenchPayload;
};

export function buildDashboardCanvasViewModel({
  dashboard,
  filters,
  query,
  sourceSwitchTableKey,
  widgetFilterField,
  widgetFilterOperator,
  widgetFilterValue,
  widgetFilters,
  widgetPlan,
  widgets,
  workbench,
}: DashboardCanvasViewModelOptions) {
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const latestRun = latestUsableSourceIntelligenceRun(sourceIntelligenceRuns);
  const dashboardSummary = buildDashboardSummaryModel({
    query,
    defaultTableKey: dashboard.default_table_key,
    latestRun,
  });
  const widgetPlanSummary = summarizeDashboardWidgetPlan(widgetPlan);
  const sourceSwitchAnalysis = analyzeDashboardSourceSwitch({
    fields: workbench.fields,
    widgets,
    filters,
    defaultTableKey: dashboard.default_table_key,
    sourceSwitchTableKey,
  });
  const sourceSwitchView = buildDashboardSourceSwitchViewModel(sourceSwitchAnalysis);
  const sourceSwitchChanged = sourceSwitchView.changed;
  const sourceSwitchCleanupCount = sourceSwitchView.cleanupCount;
  const nextWidgetFilters = buildNextWidgetFilters({
    currentFilters: widgetFilters,
    field: widgetFilterField,
    operator: widgetFilterOperator,
    value: widgetFilterValue,
  });
  const dashboardReadiness = buildDashboardReadinessModel({
    dashboard,
    widgets,
    filters,
    latestRun,
    hasPendingPreview: widgetPlan?.requiresConfirmation === true,
    sourceSwitchChanged,
    sourceSwitchCleanupCount,
  });
  const dashboardEvidenceFocus = buildDashboardEvidenceFocus({
    dashboard,
    widgets,
    filters,
    latestRun,
    readiness: dashboardReadiness,
  });

  return {
    ...widgetPlanSummary,
    dashboardCreatedBy: dashboardReadiness.createdBy,
    dashboardEditBoundary: dashboardReadiness.editBoundary,
    dashboardEvidenceFocus,
    dashboardHealthDetail: dashboardReadiness.healthDetail,
    dashboardHealthItems: dashboardReadiness.healthItems,
    dashboardHealthTitle: dashboardReadiness.healthTitle,
    dashboardHealthTone: dashboardReadiness.healthTone,
    dashboardIsAgentManaged: dashboardReadiness.isAgentManaged,
    dashboardReadiness,
    dashboardSourceLabel: dashboardReadiness.sourceLabel,
    dashboardSummary,
    latestRun,
    nextWidgetFilters,
    sourceIntelligenceRuns,
    sourceSwitchAnalysis,
    sourceSwitchChanged,
    sourceSwitchCleanupCount,
    sourceSwitchView,
  };
}
