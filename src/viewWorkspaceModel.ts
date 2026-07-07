import type { SavedView, SourceIntelligenceRunSummary } from "./types";
import { biText } from "./components/Bilingual";

export type ViewOperationReceipt = {
  title: string;
  detail: string;
  nextStep: string;
  technical: string;
  tone: "ok" | "warn";
};

export type ViewBridgeStep = {
  key: string;
  status: "ready" | "wait";
  title: string;
  detail: string;
  meta: string;
};

export type ViewAgentPrompt = {
  key: string;
  icon: "agent" | "evidence" | "dashboard";
  label: string;
  detail: string;
  prompt: string;
};

export function viewColumns(view?: SavedView) {
  const raw = view?.config?.columns;
  return Array.isArray(raw) ? raw.map(String) : [];
}

export function viewFilters(view?: SavedView) {
  const raw = view?.config?.filters;
  return Array.isArray(raw)
    ? raw
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .map((item) => ({ field: String(item.field ?? ""), operator: String(item.operator ?? "contains"), value: String(item.value ?? "") }))
        .filter((item) => item.field)
    : [];
}

export function viewSort(view?: SavedView) {
  const raw = view?.config?.sort;
  return Array.isArray(raw)
    ? raw
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .map((item) => ({ field: String(item.field ?? ""), direction: String(item.direction ?? "asc") }))
        .filter((item) => item.field)
    : [];
}

export function viewSearch(view?: SavedView) {
  return String(view?.config?.search ?? "");
}

export function viewName(view: SavedView | undefined, fallback: string) {
  return view?.name ?? (fallback || biText("当前视图", "Current view"));
}

export function buildViewBridgeSteps(args: {
  activeView?: SavedView;
  activeViewColumns: string[];
  bridgeFilterScopeCount: number;
  rowCount: number;
  filteredRows: number;
  latestSourceProfile?: SourceIntelligenceRunSummary;
  viewCanFeedDashboard: boolean;
}): ViewBridgeStep[] {
  return [
    {
      key: "scope",
      status: args.activeView ? "ready" : "wait",
      title: biText("固定视图口径", "Lock view scope"),
      detail: biText("字段、筛选、搜索和排序会一起进入证据链。", "Columns, filters, search, and sort stay together in evidence."),
      meta: biText(`${args.activeViewColumns.length} 列 · ${args.bridgeFilterScopeCount} 个筛选`, `${args.activeViewColumns.length} cols · ${args.bridgeFilterScopeCount} filters`),
    },
    {
      key: "runtime",
      status: args.rowCount ? "ready" : "wait",
      title: biText("更新明细结果", "Refresh rows"),
      detail: biText("只按当前字段、筛选和搜索取数，不接收手写查询。", "Uses the current columns, filters, and search only; typed queries are not accepted."),
      meta: biText(`${args.filteredRows} 行 · 受控取数`, `${args.filteredRows} rows · controlled`),
    },
    {
      key: "evidence",
      status: args.latestSourceProfile ? "ready" : "wait",
      title: biText("绑定来源证据", "Bind source evidence"),
      detail: biText("沿用证据摘要里的字段、关系和回执。", "Reuses fields, relationships, and receipts from the evidence summary."),
      meta: args.latestSourceProfile
        ? biText(`${args.latestSourceProfile.source_count} 个源文件 · ${args.latestSourceProfile.relationship_count} 个关系`, `${args.latestSourceProfile.source_count} sources · ${args.latestSourceProfile.relationship_count} relationships`)
        : biText("等待证据摘要", "Waiting for evidence summary"),
    },
    {
      key: "dashboard",
      status: args.viewCanFeedDashboard ? "ready" : "wait",
      title: biText("生成看板修改", "Create dashboard change"),
      detail: biText("Agent 只生成待确认修改，确认前不写入看板。", "Agent creates a pending change only; dashboards are unchanged before approval."),
      meta: args.viewCanFeedDashboard ? biText("可生成待确认修改", "Ready for a pending change") : biText("等待明细结果", "Waiting for rows"),
    },
  ];
}

export function buildViewAgentPrompts(activeName: string): ViewAgentPrompt[] {
  return [
    {
      key: "explain",
      icon: "agent",
      label: biText("解释当前筛选", "Explain current slice"),
      detail: biText("基于当前视图和分页结果", "Use this view and page"),
      prompt: biText(
        `解释视图「${activeName}」当前筛选后的业务含义，列出证据、口径和异常，不要创建待确认修改`,
        `Explain the business meaning of the filtered view "${activeName}", list evidence, scope, and anomalies, and do not create a pending change`,
      ),
    },
    {
      key: "find-anomaly",
      icon: "evidence",
      label: biText("找异常行", "Find anomalies"),
      detail: biText("先给检查计划和证据", "Plan and evidence first"),
      prompt: biText(
        `检查视图「${activeName}」里哪些记录值得复核，说明字段依据和下一步，不要直接修改数据`,
        `Check which records in view "${activeName}" deserve review, explain field evidence and next steps, and do not modify data directly`,
      ),
    },
    {
      key: "dashboard-widget",
      icon: "dashboard",
      label: biText("生成看板修改", "Create dashboard change"),
      detail: biText("生成待确认修改", "Create a pending change"),
      prompt: biText(
        `基于视图「${activeName}」生成一个待确认的看板组件，说明维度、指标、筛选和影响范围，先不要直接写入`,
        `Create a pending dashboard widget from view "${activeName}", explain dimension, measure, filters, and impact, and do not write directly`,
      ),
    },
  ];
}
