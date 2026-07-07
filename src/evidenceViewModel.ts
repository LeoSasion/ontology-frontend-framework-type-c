import type { EvidenceFocus, SourceIntelligenceRunSummary } from "./types";
import { biText } from "./components/Bilingual";

export function sourceRunFromFocus(focus: EvidenceFocus | null | undefined, runs: SourceIntelligenceRunSummary[]) {
  const sourceIntelligenceRef = focus?.refs.find((ref) => ref.startsWith("source-intelligence:"));
  const runKey = sourceIntelligenceRef?.replace("source-intelligence:", "");
  return runKey ? runs.find((run) => run.run_key === runKey) : runs[0];
}

export function evidenceLabel(ref: string) {
  if (ref === "query-runtime") return biText("查询回执", "Query receipt");
  if (ref === "dashboard-widget-contract") return biText("看板组件规则", "Dashboard widget rules");
  if (ref === "saved-view-config") return biText("保存视图口径", "Saved view logic");
  if (ref === "table-query-contract") return biText("明细查询回执", "Detail query receipt");
  if (ref === "b-bi-cli-compatible") return biText("本地 BI 能力", "Local BI capability");
  if (ref.startsWith("source-intelligence:")) return biText("证据摘要运行", "Evidence summary run");
  if (ref.startsWith("source-count:")) return biText(`源文件 ${ref.replace("source-count:", "")} 个`, `${ref.replace("source-count:", "")} source files`);
  if (ref.startsWith("metric-sql:")) return biText(`可回答问题 ${ref.replace("metric-sql:", "")} 个`, `${ref.replace("metric-sql:", "")} answerable questions`);
  if (ref.startsWith("relationship:")) return biText("业务连接证据", "Business link evidence");
  return ref;
}

export function evidenceTechnicalLabel(ref: string) {
  if (ref === "query-runtime") return "query-runtime";
  if (ref === "dashboard-widget-contract") return "dashboard-widget-contract";
  if (ref === "saved-view-config") return "saved-view-config";
  if (ref === "table-query-contract") return "table-query-contract";
  if (ref === "b-bi-cli-compatible") return "b-bi-cli-compatible";
  return ref;
}

export function detailLabel(key: string) {
  const labels: Record<string, string> = {
    viewName: biText("视图", "View"),
    tableName: biText("数据表", "Table"),
    tag: biText("标签", "Tag"),
    columnCount: biText("列数", "Columns"),
    filterCount: biText("筛选", "Filters"),
    sortCount: biText("排序", "Sorts"),
    search: biText("搜索", "Search"),
    runtime: biText("执行引擎", "Runtime"),
    filteredRows: biText("筛选后行数", "Filtered rows"),
    totalRows: biText("总行数", "Total rows"),
    page: biText("页码", "Page"),
    pageCount: biText("页数", "Pages"),
    sqlIntent: biText("查询意图", "Query intent"),
  };
  return labels[key] ?? key;
}

export function detailValue(value: unknown) {
  if (Array.isArray(value)) return value.length ? value.map(String).join(", ") : "-";
  if (value === null || typeof value === "undefined" || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function isTechnicalFocusDetail(key: string) {
  return ["runtime", "sqlIntent", "page", "pageCount"].includes(key);
}

export function evidenceCoverageText(run: SourceIntelligenceRunSummary | undefined) {
  if (!run) return biText("等待画像", "Waiting for profile");
  if (run.fileCoverage?.complete) return biText("证据覆盖完整", "Evidence coverage complete");
  return biText("证据可用但需复核覆盖", "Evidence usable, coverage needs review");
}

export function evidenceRunReadinessText(run: SourceIntelligenceRunSummary | undefined) {
  if (!run) return biText("等待证据摘要", "Waiting for evidence summary");
  if (run.metric_sql_executable_count > 0 && run.fileCoverage?.complete) return biText("可用于分析", "Ready for analysis");
  if (run.metric_sql_executable_count > 0) return biText("可用，覆盖需复核", "Usable, coverage needs review");
  return biText("需补充查询证据", "Needs query evidence");
}

export function evidenceDecisionText(run: SourceIntelligenceRunSummary | undefined, refs: string[]) {
  const hasQueryRuntime = refs.includes("query-runtime") || refs.some((ref) => ref.startsWith("metric-sql:"));
  const executableSql = run?.metric_sql_executable_count ?? 0;
  if (hasQueryRuntime && executableSql > 0) {
    return biText("可以支撑当前只读分析和看板解释。", "Supports the current read-only analysis and dashboard explanation.");
  }
  if (run && executableSql > 0) {
    return biText("可以支撑可审计指标问题；涉及写入仍需确认。", "Supports auditable metric questions; writes still require confirmation.");
  }
  return biText("证据不足以直接下结论，先补充画像或查询结果。", "Evidence is not enough for a conclusion; add profiling or query results first.");
}

export function actionReceiptTitle(result: Record<string, unknown> | null | undefined) {
  if (!result) return biText("等待动作回执", "Waiting for action receipt");
  if (result.ok === false) return biText("动作失败", "Action failed");
  if (result.confirmed === true && result.decision === "reject") return biText("草案已拒绝", "Draft rejected");
  if (result.confirmed === true) return biText("动作已确认", "Action confirmed");
  if (result.requiresConfirmation === true || result.dryRun === true) return biText("预演回执", "Preview receipt");
  return biText("动作已记录", "Action recorded");
}

export function actionReceiptKey(result: Record<string, unknown> | null | undefined) {
  if (!result) return "";
  if (typeof result.actionKey === "string") return result.actionKey;
  if (result.action && typeof result.action === "object" && "action_key" in result.action) {
    return String((result.action as { action_key?: unknown }).action_key ?? "");
  }
  return "";
}

export function actionReceiptSubject(result: Record<string, unknown> | null | undefined) {
  if (!result) return biText("当前动作", "current action");
  const dashboardKey = typeof result.createdDashboardKey === "string"
    ? result.createdDashboardKey
    : typeof result.savedDashboardKey === "string"
      ? result.savedDashboardKey
      : typeof result.dashboardKey === "string"
        ? result.dashboardKey
        : "";
  if (dashboardKey) return biText(`看板 ${dashboardKey}`, `dashboard ${dashboardKey}`);
  const actionKey = actionReceiptKey(result);
  if (actionKey.includes("import")) return biText("导入数据", "data import");
  if (actionKey.includes("relationship")) return biText("业务连接", "business link");
  if (actionKey.includes("dashboard")) return biText("看板修改", "dashboard change");
  if (actionKey.includes("formula")) return biText("计算字段或指标", "calculated field or metric");
  if (actionKey.includes("semantic")) return biText("字段用途", "field usage");
  if (actionKey.includes("view")) return biText("保存视图", "saved view");
  if (actionKey.includes("index")) return biText("查询索引", "query index");
  return biText("这次修改", "this change");
}

export function actionReceiptDetail(result: Record<string, unknown> | null | undefined) {
  if (!result) return biText("确认、拒绝或预演动作后，这里会显示最近一次动作边界。", "After a preview, confirmation, or rejection, the latest action boundary appears here.");
  if (result.ok === false) return String(result.error ?? biText("请检查当前工作区和动作参数。", "Check the current workspace and action parameters."));
  const subject = actionReceiptSubject(result);
  if (result.confirmed === true && result.decision === "reject") {
    return biText(`已拒绝${subject}，没有执行写入。`, `Rejected ${subject}; no write was executed.`);
  }
  if (result.confirmed === true) {
    return biText(`已确认${subject}，工作区状态已刷新。`, `Confirmed ${subject}; workspace state was refreshed.`);
  }
  if (result.requiresConfirmation === true || result.dryRun === true) {
    return biText(`${subject}已完成预演，确认前不会写入。`, `${subject} was previewed; nothing writes before confirmation.`);
  }
  return biText("动作结果已记录；上下文抽屉显示摘要，证据页保留完整 JSON。", "Action result recorded; the context drawer shows the summary, and Evidence keeps the full JSON.");
}

export function actionReceiptTechnical(result: Record<string, unknown> | null | undefined) {
  if (!result) return "";
  const actionKey = actionReceiptKey(result);
  const decision = typeof result.decision === "string" ? result.decision : "";
  const flags = [
    result.requiresConfirmation === true ? "requiresConfirmation" : "",
    result.dryRun === true ? "dryRun" : "",
    result.confirmed === true ? "confirmed" : "",
  ].filter(Boolean).join(", ");
  return [actionKey, decision, flags].filter(Boolean).join(" · ");
}

export function agentEvidenceBusinessLabel(ref: Record<string, unknown>) {
  const type = String(ref.type ?? "");
  if (type === "sourceRun" || type === "table") return biText("数据来源已定位", "Data source located");
  if (type === "metricDefinition") return biText("指标口径已匹配", "Metric logic matched");
  if (type === "queryRuntime") return biText("只读查询已完成", "Read-only query completed");
  if (type === "ontologyFunction") return biText("业务规则已引用", "Business rule referenced");
  return biText("证据线索已引用", "Evidence item referenced");
}

export function agentEvidenceBusinessDetail(ref: Record<string, unknown>) {
  const type = String(ref.type ?? "");
  if (type === "sourceRun" || type === "table") return String(ref.name ?? ref.tableKey ?? ref.id ?? biText("当前工作区数据", "Current workspace data"));
  if (type === "metricDefinition") return String(ref.label ?? ref.metric_key ?? biText("当前指标", "Current metric"));
  if (type === "queryRuntime") return biText("可追溯到查询回执，技术信息可展开查看。", "Traceable to a query receipt; technical details are expandable.");
  if (type === "ontologyFunction") return String(ref.id ?? biText("业务规则", "Business rule"));
  return String(ref.id ?? ref.key ?? (type || biText("证据", "Evidence")));
}

export function agentEvidenceTechnicalText(ref: Record<string, unknown>) {
  return Object.entries(ref)
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
    .join(" · ");
}

type ActionBoundaryHint = {
  actionTypeId: string;
  confirmationPolicy: string;
};

export function actionBoundaryBusinessLabel(action: ActionBoundaryHint) {
  if (action.actionTypeId.includes("delete")) return biText("删除前必须确认", "Delete requires confirmation");
  if (action.actionTypeId.includes("import")) return biText("导入前先预演", "Preview before import");
  if (action.actionTypeId.includes("dashboard")) return biText("看板写入需确认", "Dashboard writes need approval");
  if (action.actionTypeId.includes("relationship")) return biText("业务连接需确认", "Business links need approval");
  if (action.actionTypeId.includes("formula") || action.actionTypeId.includes("metric") || action.actionTypeId.includes("semantic")) return biText("分析口径需确认", "Analysis logic needs approval");
  return biText("写入前停下确认", "Stop for approval before write");
}

export function actionBoundaryBusinessDetail(action: ActionBoundaryHint) {
  if (action.confirmationPolicy.includes("explicit")) return biText("必须通过界面按钮确认，Agent 不能静默执行。", "Requires an explicit UI confirmation; Agent cannot execute silently.");
  return biText("动作会先生成计划或预演，确认前不写入。", "The action creates a plan or preview first; nothing writes before confirmation.");
}
