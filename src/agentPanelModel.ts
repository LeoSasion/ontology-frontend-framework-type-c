import type { ActionDraft, MetricDefinition, SavedView, SourceIntelligenceRunSummary } from "./types";
import { biText } from "./components/Bilingual";
import { objectRecord } from "./safeValue";

export { objectRecord };

export function defaultAgentPrompt(language: "zh" | "en") {
  return language === "zh" ? "帮我分析销售趋势并生成待确认的看板修改" : "Analyze sales trends and create a pending dashboard change";
}

export function actionKindText(kind: string) {
  if (kind === "dashboard.create") return biText("创建看板", "Create dashboard");
  if (kind === "dashboard.copy") return biText("复制看板", "Copy dashboard");
  if (kind === "dashboard.rename") return biText("重命名看板", "Rename dashboard");
  if (kind === "dashboard.delete") return biText("删除看板", "Delete dashboard");
  if (kind === "dashboard.widget.add") return biText("新增看板组件", "Add dashboard widget");
  if (kind === "dashboard.filter.add") return biText("新增看板筛选", "Add dashboard filter");
  if (kind === "import.commit") return biText("提交导入", "Commit import");
  if (kind === "relationship.save") return biText("保存关系", "Save relationship");
  if (kind === "index.create") return biText("创建查询索引", "Create query index");
  if (kind === "formula.save") return biText("保存公式", "Save formula");
  if (kind === "view.save") return biText("保存视图", "Save view");
  if (kind === "metric.add") return biText("新增指标", "Add metric");
  if (kind === "semantic.set") return biText("设置字段语义", "Set field semantics");
  return kind;
}

export function actionTarget(draft: ActionDraft) {
  const dashboardKey = typeof draft.payload?.dashboardKey === "string" ? draft.payload.dashboardKey : "";
  const dashboardName = typeof draft.payload?.name === "string" ? draft.payload.name : "";
  const widgetType = typeof draft.payload?.widgetType === "string" ? draft.payload.widgetType : "";
  const widgetTitle = typeof draft.payload?.title === "string" ? draft.payload.title : "";
  const sourceDashboardName = typeof draft.payload?.sourceDashboardName === "string" ? draft.payload.sourceDashboardName : "";
  const tableKey = typeof draft.payload?.tableKey === "string" ? draft.payload.tableKey : "";
  const filePath = typeof draft.payload?.filePath === "string" ? draft.payload.filePath : "";
  const field = typeof draft.payload?.field === "string" ? draft.payload.field : "";
  const operator = typeof draft.payload?.operator === "string" ? draft.payload.operator : "";
  const value = typeof draft.payload?.value === "string" ? draft.payload.value : "";
  const leftTable = typeof draft.payload?.leftTable === "string" ? draft.payload.leftTable : "";
  const rightTable = typeof draft.payload?.rightTable === "string" ? draft.payload.rightTable : "";
  const leftField = typeof draft.payload?.leftField === "string" ? draft.payload.leftField : "";
  const rightField = typeof draft.payload?.rightField === "string" ? draft.payload.rightField : "";
  const formulaName = typeof draft.payload?.name === "string" ? draft.payload.name : "";
  const formulaText = typeof draft.payload?.formulaText === "string" ? draft.payload.formulaText : "";
  const viewName = typeof draft.payload?.name === "string" ? draft.payload.name : "";
  const metricLabel = typeof draft.payload?.label === "string" ? draft.payload.label : "";
  const measure = typeof draft.payload?.measure === "string" ? draft.payload.measure : "";
  const aggregation = typeof draft.payload?.aggregation === "string" ? draft.payload.aggregation : "";
  const dimension = typeof draft.payload?.dimension === "string" ? draft.payload.dimension : "";
  const role = typeof draft.payload?.role === "string" ? draft.payload.role : "";
  if (draft.kind === "index.create" && tableKey && field) return `${tableKey}.${field}`;
  if (draft.kind === "dashboard.copy" && dashboardName) return `${sourceDashboardName || dashboardKey} -> ${dashboardName}`;
  if (draft.kind === "dashboard.rename" && dashboardName) return `${sourceDashboardName || dashboardKey} -> ${dashboardName}`;
  if (draft.kind === "dashboard.delete" && dashboardKey) return sourceDashboardName || dashboardKey;
  if (draft.kind === "dashboard.widget.add" && widgetTitle) return `${widgetTitle} -> ${dashboardKey || "dashboard"}`;
  if (draft.kind === "dashboard.widget.add" && widgetType) return `${widgetType} -> ${dashboardKey || "dashboard"}`;
  if (draft.kind === "dashboard.filter.add" && field) return `${field} ${operator || "equals"} ${value || ""} -> ${dashboardKey || "dashboard"}`.trim();
  if (draft.kind === "semantic.set" && tableKey && field) return `${tableKey}.${field} -> ${role || "semantic"}`;
  if (draft.kind === "relationship.save" && leftTable && rightTable) return `${leftTable}.${leftField || "?"} -> ${rightTable}.${rightField || "?"}`;
  if (draft.kind === "import.commit" && filePath) return `${filePath.split(/[\\/]/).pop()} -> ${tableKey || "new table"}`;
  if (draft.kind === "formula.save" && formulaName) return `${formulaName} -> ${tableKey || "current table"}`;
  if (draft.kind === "formula.save" && formulaText) return `${formulaText.slice(0, 48)} -> ${tableKey || "current table"}`;
  if (draft.kind === "view.save" && viewName) return `${viewName} -> ${tableKey || "current table"}`;
  if (draft.kind === "metric.add" && metricLabel) return `${metricLabel} -> ${tableKey || "current table"}`;
  if (draft.kind === "metric.add" && measure) return `${aggregation || "metric"}(${measure})${dimension ? ` by ${dimension}` : ""}`;
  if (dashboardKey && tableKey) return `${dashboardKey} · ${tableKey}`;
  return dashboardKey || tableKey || biText("当前工作区", "Current workspace");
}

export function pairText(value: { zh: string; en: string } | undefined) {
  return value ? biText(value.zh, value.en) : "";
}

export function evidenceRefText(ref: Record<string, unknown>) {
  const type = String(ref.type ?? "");
  if (type === "sourceRun") {
    return `${biText("数据来源", "Data source")}: ${String(ref.name ?? ref.id ?? "-")}`;
  }
  if (type === "metricDefinition") {
    return `${biText("指标口径", "Metric logic")}: ${String(ref.label ?? ref.metric_key ?? "-")}`;
  }
  if (type === "queryRuntime") {
    return `${biText("查询回执", "Query receipt")}: ${biText("只读查询已完成", "Read-only query completed")}`;
  }
  if (type === "ontologyFunction") {
    return `${biText("业务规则", "Business rule")}: ${String(ref.id ?? "-")}`;
  }
  return `${type || biText("证据", "Evidence")}: ${String(ref.id ?? ref.key ?? "-")}`;
}

export function confidenceText(value?: string) {
  if (value === "explicit") return biText("明确命中", "Explicit match");
  if (value === "fallback") return biText("系统推断", "System inferred");
  if (value === "missing") return biText("未命中", "Missing");
  if (value === "ambiguous") return biText("需确认", "Needs selection");
  if (value === "none") return biText("不适用", "Not needed");
  return value || biText("未知", "Unknown");
}

export function confidenceClass(value?: string) {
  if (value === "explicit" || value === "draft") return "ok";
  if (value === "missing" || value === "ambiguous") return "warn";
  return "neutral";
}

export function actionNeedsDashboard(kind: string) {
  return kind.startsWith("dashboard.");
}

export function actionRiskText(draft?: ActionDraft) {
  if (!draft) {
    return biText("只读计划，不会改动工作区。", "Read-only plan; no workspace changes.");
  }
  if (draft.kind === "dashboard.delete") {
    return biText("高风险：会删除看板，必须确认。", "High risk: deletes a dashboard and requires confirmation.");
  }
  if (draft.kind === "import.commit") {
    return biText("写入数据：确认后才会提交导入。", "Data write: import commits only after confirmation.");
  }
  if (draft.kind === "dashboard.widget.add" || draft.kind === "dashboard.filter.add" || draft.kind === "dashboard.create") {
    return biText("看板变更：确认后才会写入仪表盘配置。", "Dashboard change: writes dashboard config only after confirmation.");
  }
  if (draft.kind === "relationship.save" || draft.kind === "formula.save" || draft.kind === "metric.add" || draft.kind === "semantic.set") {
    return biText("模型变更：确认后才会影响后续分析口径。", "Model change: affects future analysis only after confirmation.");
  }
  if (draft.kind === "index.create" || draft.kind === "view.save") {
    return biText("工作区配置变更：确认后保存到本地元数据。", "Workspace config change: saves local metadata only after confirmation.");
  }
  return biText("需要确认的工作区修改。", "Workspace change that requires confirmation.");
}

export function actionNextStepText(draft?: ActionDraft) {
  if (!draft) {
    return biText("可以继续提问；没有需要确认的写入。", "You can keep asking; no write approval is needed.");
  }
  if (draft.kind === "dashboard.delete") {
    return biText("先核对目标看板，再决定确认或拒绝。", "Check the target dashboard first, then confirm or reject.");
  }
  if (draft.kind === "import.commit") {
    return biText("先预演导入结果，再决定是否写入。", "Preview the import result first, then decide whether to write.");
  }
  if (draft.kind.startsWith("dashboard.")) {
    return biText("先预览看板变化，再决定是否更新画布。", "Preview the dashboard change first, then decide whether to update the canvas.");
  }
  if (draft.kind === "relationship.save") {
    return biText("先核对左右表连接字段，再确认保存。", "Check the left and right link fields first, then confirm saving.");
  }
  if (draft.kind === "formula.save" || draft.kind === "metric.add" || draft.kind === "semantic.set") {
    return biText("先核对分析口径，再确认是否影响后续分析。", "Check the analysis definition first, then confirm whether future analysis should change.");
  }
  return biText("先预演工作区配置变化，再确认是否保存。", "Preview the workspace config change first, then confirm whether to save.");
}

export function actionImpactGroup(kind: string) {
  if (kind === "import.commit") return "data";
  if (kind.startsWith("dashboard.")) return "dashboard";
  if (kind === "relationship.save" || kind === "formula.save" || kind === "metric.add" || kind === "semantic.set") return "model";
  if (kind === "index.create" || kind === "view.save") return "workspace";
  return "workspace";
}

export function actionEvidenceChips(draft?: ActionDraft) {
  if (!draft) {
    return [biText("无写入", "No write"), biText("只读", "Read-only")];
  }
  const evidence = draft.evidence.length ? draft.evidence : ["action-registry"];
  const labelMap: Record<string, string> = {
    "action-registry": biText("动作登记", "Action registry"),
    "dashboardSelectionConfidence": biText("看板匹配", "Dashboard match"),
    "source-profile": biText("证据摘要", "Evidence summary"),
    "metric-definition": biText("指标口径", "Metric logic"),
    "query-runtime": biText("查询回执", "Query receipt"),
    "dashboard-widget-catalog": biText("看板组件", "Dashboard widgets"),
    "erp-unit-library": biText("ERP 单元", "ERP units"),
  };
  const chips = evidence.slice(0, 3).map((item) => labelMap[item] ?? item);
  if (draft.kind.startsWith("dashboard.")) chips.unshift(labelMap.dashboardSelectionConfidence);
  return Array.from(new Set(chips)).slice(0, 4);
}

export function stringField(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === "string" ? value : "";
}

export function dashboardCreateDraft(draft?: ActionDraft) {
  if (!draft || draft.kind !== "dashboard.create") return null;
  return objectRecord(draft.payload.dashboardDraft);
}

export function dashboardDraftWidgets(draft: Record<string, unknown>) {
  const widgets = Array.isArray(draft.previewWidgets) ? draft.previewWidgets : Array.isArray(draft.widgets) ? draft.widgets : [];
  return widgets.filter((item): item is Record<string, unknown> => Boolean(objectRecord(item))).slice(0, 6);
}

export function dashboardWidgetLine(widget: Record<string, unknown>) {
  const type = stringField(widget, "type") || biText("组件", "widget");
  const measure = stringField(widget, "measure");
  const dimension = stringField(widget, "dimension");
  const aggregation = stringField(widget, "aggregation");
  const metric = measure ? `${aggregation || "sum"}(${measure})` : "";
  return [type, metric, dimension ? `${biText("按", "by")} ${dimension}` : ""].filter(Boolean).join(" · ");
}

export function resultActionKey(result: Record<string, unknown> | null) {
  if (!result) return "";
  const direct = stringField(result, "actionKey");
  if (direct) return direct;
  const action = objectRecord(result.action);
  return action ? stringField(action, "action_key") : "";
}

export function resultRecord(result: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const record = objectRecord(result[key]);
    if (record) return record;
  }
  return null;
}

export function actionResultHeadline(result: Record<string, unknown>) {
  if (result.ok === false) return biText("动作失败", "Action failed");
  if (result.confirmed === true && result.decision === "reject") return biText("修改已拒绝", "Change rejected");
  if (result.confirmed === true) return biText("已确认写入", "Write confirmed");
  if (result.requiresConfirmation === true || result.dryRun === true) return biText("预演完成", "Preview ready");
  return biText("动作已记录", "Action recorded");
}

export function actionResultDetail(result: Record<string, unknown>, draft?: ActionDraft) {
  if (result.ok === false) return String(result.error ?? biText("请检查动作参数或当前工作区。", "Check the action parameters or current workspace."));
  if (result.confirmed === true && result.decision === "reject") return biText("没有执行任何写入，修改已从待确认队列移除。", "No write was executed; the change was removed from the pending queue.");
  if (result.confirmed === true) {
    const dashboardKey = stringField(result, "createdDashboardKey") || stringField(result, "savedDashboardKey") || stringField(result, "dashboardKey");
    if (dashboardKey) return biText(`已写入看板 ${dashboardKey}，可以继续编辑和查看证据。`, `Dashboard ${dashboardKey} was written; you can keep editing and inspect evidence.`);
    return biText("已执行确认动作，相关工作区状态已刷新。", "The confirmed action ran and workspace state was refreshed.");
  }
  const proposedDashboard = resultRecord(result, ["proposedDashboard", "proposedDashboardOperation", "proposed"]);
  const proposedWidget = resultRecord(result, ["proposedWidget", "addedWidget"]);
  const proposedMetric = resultRecord(result, ["proposedMetric", "savedMetric"]);
  const proposedFormula = resultRecord(result, ["proposedFormula", "savedFormula"]);
  const proposedView = resultRecord(result, ["proposedView", "savedView"]);
  const relationship = resultRecord(result, ["relationship", "savedRelationship"]);
  const proposedExecution = resultRecord(result, ["proposedExecution", "createdIndex"]);
  if (proposedDashboard) {
    const name = stringField(proposedDashboard, "dashboardName") || stringField(proposedDashboard, "name") || stringField(proposedDashboard, "dashboardKey");
    const widgetCount = typeof proposedDashboard.widgetCount === "number" ? proposedDashboard.widgetCount : undefined;
    return widgetCount
      ? biText(`${name || "看板"} 将写入 ${widgetCount} 个组件，确认前不会改动看板。`, `${name || "Dashboard"} will write ${widgetCount} widgets; nothing changes before confirmation.`)
      : biText(`${name || "看板"} 已完成预演，确认前不会写入。`, `${name || "Dashboard"} was previewed; nothing writes before confirmation.`);
  }
  if (proposedWidget) {
    const title = stringField(proposedWidget, "title") || stringField(proposedWidget, "widget_type") || stringField(proposedWidget, "type");
    return biText(`组件 ${title || "未命名"} 已完成预演，确认后才加入看板。`, `Widget ${title || "untitled"} was previewed and is added only after confirmation.`);
  }
  if (proposedMetric) {
    const label = stringField(proposedMetric, "label") || stringField(proposedMetric, "metricKey");
    return biText(`指标 ${label || "未命名"} 已完成预演，确认后才保存口径。`, `Metric ${label || "untitled"} was previewed and is saved only after confirmation.`);
  }
  if (proposedFormula) {
    const name = stringField(proposedFormula, "name") || stringField(proposedFormula, "formulaKey");
    return biText(`公式 ${name || "未命名"} 已完成预演，确认后才影响后续分析。`, `Formula ${name || "untitled"} was previewed and affects analysis only after confirmation.`);
  }
  if (proposedView) {
    const name = stringField(proposedView, "name") || stringField(proposedView, "viewKey");
    return biText(`视图 ${name || "未命名"} 已完成预演，确认后才保存。`, `View ${name || "untitled"} was previewed and is saved only after confirmation.`);
  }
  if (relationship) {
    const name = stringField(relationship, "name") || stringField(relationship, "relationKey") || stringField(relationship, "relation_key");
    return biText(`关系 ${name || "未命名"} 已完成覆盖预览，确认后才保存。`, `Relationship ${name || "untitled"} was previewed and is saved only after confirmation.`);
  }
  if (proposedExecution) {
    const field = stringField(proposedExecution, "field") || stringField(proposedExecution, "indexKey");
    return biText(`查询索引 ${field || ""} 已完成预演，确认后才创建。`, `Query index ${field || ""} was previewed and is created only after confirmation.`);
  }
  return draft
    ? biText(`${actionKindText(draft.kind)} 已完成预演，确认前不会写入。`, `${actionKindText(draft.kind)} was previewed; nothing writes before confirmation.`)
    : biText("预演完成，确认前不会写入工作区。", "Preview completed; nothing writes before confirmation.");
}

export function draftDashboardLabel(draft?: ActionDraft, fallback?: { name: string } | null) {
  if (!draft) return fallback?.name || "";
  const dashboardDraft = objectRecord(draft.payload.dashboardDraft);
  return stringField(draft.payload, "dashboardName") ||
    stringField(dashboardDraft ?? {}, "dashboardName") ||
    stringField(draft.payload, "name") ||
    stringField(draft.payload, "sourceDashboardName") ||
    stringField(draft.payload, "dashboardKey") ||
    fallback?.name ||
    "";
}

export function metricPrompt(metric: MetricDefinition) {
  return {
    zh: `分析 ${metric.label}${metric.dimension ? ` 按 ${metric.dimension}` : ""} 的变化，并给出证据`,
    en: `Analyze ${metric.label}${metric.dimension ? ` by ${metric.dimension}` : ""} and show the evidence`,
  };
}

export function viewPrompt(view: SavedView) {
  return {
    zh: `解释保存视图「${view.name}」里的关键明细，并给出证据`,
    en: `Explain the key records in saved view "${view.name}" with evidence`,
  };
}

export function sourceRunPrompt(run: SourceIntelligenceRunSummary) {
  return {
    zh: `基于 ${run.label} 告诉我当前工作区能回答什么`,
    en: `Using ${run.label}, tell me what this workspace can answer`,
  };
}

export type CheckedItem = {
  key: string;
  label: string;
  detail: string;
  tone: "ok" | "warn" | "neutral";
};

export type AnswerEvidenceStep = {
  key: string;
  label: string;
  detail: string;
  badge: string;
  tone: "ok" | "warn" | "neutral";
};
