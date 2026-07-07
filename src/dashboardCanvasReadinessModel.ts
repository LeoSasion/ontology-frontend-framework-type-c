import { biText } from "./components/Bilingual";
import type { DashboardFilterRule, DashboardPage, DashboardWidget, EvidenceFocus, SourceIntelligenceRunSummary } from "./types";

export type DashboardHealthTone = "ok" | "info" | "warn";

export type DashboardHealthItem = {
  key: string;
  label: string;
  value: string;
  state: string;
};

export type DashboardReadinessModel = {
  createdBy: string;
  isAgentManaged: boolean;
  sourceLabel: string;
  editBoundary: string;
  hasEvidence: boolean;
  hasWidgets: boolean;
  hasPendingPreview: boolean;
  needsSourcePreview: boolean;
  healthTone: DashboardHealthTone;
  healthTitle: string;
  healthDetail: string;
  healthItems: DashboardHealthItem[];
};

export function buildDashboardReadinessModel({
  dashboard,
  widgets,
  filters,
  latestRun,
  hasPendingPreview,
  sourceSwitchChanged,
  sourceSwitchCleanupCount,
}: {
  dashboard: DashboardPage;
  widgets: DashboardWidget[];
  filters: DashboardFilterRule[];
  latestRun?: SourceIntelligenceRunSummary | null;
  hasPendingPreview: boolean;
  sourceSwitchChanged: boolean;
  sourceSwitchCleanupCount: number;
}): DashboardReadinessModel {
  const createdBy = String(dashboard.created_by || "manual");
  const isAgentManaged = createdBy === "agent" || Number(dashboard.agent_managed) === 1;
  const hasEvidence = Boolean(latestRun);
  const hasWidgets = widgets.length > 0;
  const needsSourcePreview = sourceSwitchChanged && sourceSwitchCleanupCount > 0;
  const healthTone = !hasWidgets || !hasEvidence
    ? "warn"
    : hasPendingPreview || needsSourcePreview
      ? "info"
      : "ok";

  return {
    createdBy,
    isAgentManaged,
    sourceLabel: createdBy === "agent"
      ? biText("Agent 生成", "Agent generated")
      : createdBy === "system"
        ? biText("系统模板", "System template")
        : biText("手动维护", "Manual"),
    editBoundary: isAgentManaged
      ? biText("可编辑；写入前确认。", "Editable; writes require approval.")
      : biText("只起草，不覆盖。", "Drafts only; no overwrite."),
    hasEvidence,
    hasWidgets,
    hasPendingPreview,
    needsSourcePreview,
    healthTone,
    healthTitle: !hasWidgets
      ? biText("先补组件，这张看板还不能承载结论", "Add widgets first; this dashboard cannot carry a readout yet")
      : !hasEvidence
        ? biText("先补证据画像，再让 Agent 解读", "Add evidence profiling before asking the Agent to interpret it")
        : hasPendingPreview
          ? biText("已有预演结果，确认前不会写入", "A preview is ready; nothing writes before confirmation")
          : needsSourcePreview
            ? biText("数据源切换会影响字段，先预演", "Source switching affects fields; preview it first")
            : biText("看板可用，可解释或优化", "Usable; explain or improve"),
    healthDetail: hasWidgets && hasEvidence
      ? biText("组件、筛选、证据和写入边界已连到同一张工作台。", "Widgets, filters, evidence, and write boundaries are connected in one workbench.")
      : biText("系统会把复杂配置留在高级工作台，入门路径只暴露下一步。", "Complex configuration stays in the advanced workbench; the beginner path only exposes the next step."),
    healthItems: [
      {
        key: "widgets",
        label: biText("组件", "Widgets"),
        value: String(widgets.length),
        state: hasWidgets ? biText("可读", "Readable") : biText("缺失", "Missing"),
      },
      {
        key: "filters",
        label: biText("筛选", "Filters"),
        value: String(filters.length),
        state: filters.length ? biText("已入元数据", "In metadata") : biText("跟随全局口径", "Global scope"),
      },
      {
        key: "evidence",
        label: biText("证据", "Evidence"),
        value: latestRun ? String(latestRun.metric_sql_executable_count) : "0",
        state: hasEvidence ? biText("可追溯", "Traceable") : biText("待画像", "Needs profiling"),
      },
      {
        key: "writes",
        label: biText("写入", "Writes"),
        value: hasPendingPreview ? "1" : "0",
        state: hasPendingPreview ? biText("待确认", "Needs approval") : biText("安全", "Safe"),
      },
    ],
  };
}

export function buildDashboardEvidenceFocus({
  dashboard,
  widgets,
  filters,
  latestRun,
  readiness,
}: {
  dashboard: DashboardPage;
  widgets: DashboardWidget[];
  filters: DashboardFilterRule[];
  latestRun?: SourceIntelligenceRunSummary | null;
  readiness: DashboardReadinessModel;
}): EvidenceFocus {
  return {
    source: "dashboard-summary",
    title: dashboard.name,
    subtitle: biText("当前看板的来源、指标、筛选和动作边界", "Sources, metrics, filters, and action boundary for the current dashboard"),
    refs: [
      "dashboard-widget-contract",
      ...(latestRun ? [`source-intelligence:${latestRun.run_key}`] : []),
      `dashboard:${dashboard.dashboard_key}`,
      `table:${dashboard.default_table_key}`,
      `filter-count:${filters.length}`,
      `widget-count:${widgets.length}`,
    ],
    dashboardKey: dashboard.dashboard_key,
    tableKey: dashboard.default_table_key,
    detail: {
      dashboardKey: dashboard.dashboard_key,
      dashboardName: dashboard.name,
      defaultTableKey: dashboard.default_table_key,
      widgetCount: widgets.length,
      filterCount: filters.length,
      createdBy: readiness.createdBy,
      agentManaged: readiness.isAgentManaged,
      sourceIntelligenceRun: latestRun?.run_key ?? null,
    },
  };
}
