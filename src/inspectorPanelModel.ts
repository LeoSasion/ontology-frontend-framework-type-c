import type { ActionDraft, AgentAskResult } from "./types";
import type { AppSection } from "./components/Sidebar";
import { actionRecoveryFromResult } from "./actionRecoveryModel";
import { biText } from "./components/Bilingual";

export type LocalizedText = {
  zh: string;
  en: string;
};

export type ActionResultSummary = {
  tone: "ok" | "preview" | "failed";
  title: LocalizedText;
  detail: LocalizedText;
  next?: LocalizedText;
  safeState?: LocalizedText;
  steps?: LocalizedText[];
  targetSection?: AppSection;
  technical?: string;
};

export function actionKindLabel(kind: string) {
  const labels: Record<string, LocalizedText> = {
    "dashboard.create": { zh: "创建看板", en: "Create dashboard" },
    "dashboard.copy": { zh: "复制看板", en: "Copy dashboard" },
    "dashboard.rename": { zh: "重命名看板", en: "Rename dashboard" },
    "dashboard.delete": { zh: "删除看板", en: "Delete dashboard" },
    "dashboard.widget.add": { zh: "新增看板组件", en: "Add dashboard widget" },
    "dashboard.filter.add": { zh: "新增看板筛选", en: "Add dashboard filter" },
    "analysis.plan": { zh: "分析计划", en: "Analysis plan" },
    "import.commit": { zh: "提交导入", en: "Commit import" },
    "relationship.save": { zh: "保存关系", en: "Save relationship" },
    "index.create": { zh: "创建查询索引", en: "Create query index" },
    "formula.save": { zh: "保存公式", en: "Save formula" },
    "view.save": { zh: "保存视图", en: "Save view" },
    "metric.add": { zh: "新增指标", en: "Add metric" },
    "semantic.set": { zh: "设置字段语义", en: "Set field semantics" },
  };
  return labels[kind] ?? { zh: kind, en: kind };
}

export function payloadTarget(draft: ActionDraft) {
  const dashboard = typeof draft.payload.dashboardKey === "string" && draft.payload.dashboardKey ? draft.payload.dashboardKey : "";
  const dashboardName = typeof draft.payload.name === "string" && draft.payload.name ? draft.payload.name : "";
  const widgetType = typeof draft.payload.widgetType === "string" && draft.payload.widgetType ? draft.payload.widgetType : "";
  const widgetTitle = typeof draft.payload.title === "string" && draft.payload.title ? draft.payload.title : "";
  const sourceDashboardName = typeof draft.payload.sourceDashboardName === "string" && draft.payload.sourceDashboardName ? draft.payload.sourceDashboardName : "";
  const table = typeof draft.payload.tableKey === "string" && draft.payload.tableKey ? draft.payload.tableKey : "";
  const filePath = typeof draft.payload.filePath === "string" && draft.payload.filePath ? draft.payload.filePath : "";
  const field = typeof draft.payload.field === "string" && draft.payload.field ? draft.payload.field : "";
  const operator = typeof draft.payload.operator === "string" && draft.payload.operator ? draft.payload.operator : "";
  const value = typeof draft.payload.value === "string" && draft.payload.value ? draft.payload.value : "";
  const leftTable = typeof draft.payload.leftTable === "string" && draft.payload.leftTable ? draft.payload.leftTable : "";
  const rightTable = typeof draft.payload.rightTable === "string" && draft.payload.rightTable ? draft.payload.rightTable : "";
  const leftField = typeof draft.payload.leftField === "string" && draft.payload.leftField ? draft.payload.leftField : "";
  const rightField = typeof draft.payload.rightField === "string" && draft.payload.rightField ? draft.payload.rightField : "";
  const formulaName = typeof draft.payload.name === "string" && draft.payload.name ? draft.payload.name : "";
  const formulaText = typeof draft.payload.formulaText === "string" && draft.payload.formulaText ? draft.payload.formulaText : "";
  const viewName = typeof draft.payload.name === "string" && draft.payload.name ? draft.payload.name : "";
  const metricLabel = typeof draft.payload.label === "string" && draft.payload.label ? draft.payload.label : "";
  const measure = typeof draft.payload.measure === "string" && draft.payload.measure ? draft.payload.measure : "";
  const aggregation = typeof draft.payload.aggregation === "string" && draft.payload.aggregation ? draft.payload.aggregation : "";
  const dimension = typeof draft.payload.dimension === "string" && draft.payload.dimension ? draft.payload.dimension : "";
  const role = typeof draft.payload.role === "string" && draft.payload.role ? draft.payload.role : "";
  const prompt = typeof draft.payload.prompt === "string" && draft.payload.prompt ? draft.payload.prompt : "";

  if (draft.kind === "import.commit" && filePath) {
    const fileName = filePath.split(/[\\/]/).pop() || filePath;
    return { zh: `${fileName} -> ${table || "新数据表"}`, en: `${fileName} -> ${table || "new table"}` };
  }
  if (draft.kind === "dashboard.copy" && dashboardName) {
    return { zh: `${sourceDashboardName || dashboard} -> ${dashboardName}`, en: `${sourceDashboardName || dashboard} -> ${dashboardName}` };
  }
  if (draft.kind === "dashboard.rename" && dashboardName) {
    return { zh: `${sourceDashboardName || dashboard} -> ${dashboardName}`, en: `${sourceDashboardName || dashboard} -> ${dashboardName}` };
  }
  if (draft.kind === "dashboard.delete" && dashboard) {
    return { zh: sourceDashboardName || dashboard, en: sourceDashboardName || dashboard };
  }
  if (draft.kind === "dashboard.widget.add" && widgetTitle) {
    return { zh: `${widgetTitle} -> ${dashboard || "看板"}`, en: `${widgetTitle} -> ${dashboard || "dashboard"}` };
  }
  if (draft.kind === "dashboard.widget.add" && widgetType) {
    return { zh: `${widgetType} -> ${dashboard || "看板"}`, en: `${widgetType} -> ${dashboard || "dashboard"}` };
  }
  if (draft.kind === "dashboard.filter.add" && field) {
    const target = `${field} ${operator || "equals"} ${value || ""} -> ${dashboard || "dashboard"}`.trim();
    return { zh: target, en: target };
  }
  if (draft.kind === "relationship.save" && leftTable && rightTable) {
    return { zh: `${leftTable}.${leftField || "?"} -> ${rightTable}.${rightField || "?"}`, en: `${leftTable}.${leftField || "?"} -> ${rightTable}.${rightField || "?"}` };
  }
  if (draft.kind === "index.create" && table && field) {
    return { zh: `${table}.${field}`, en: `${table}.${field}` };
  }
  if (draft.kind === "semantic.set" && table && field) {
    return { zh: `${table}.${field} -> ${role || "语义"}`, en: `${table}.${field} -> ${role || "semantic"}` };
  }
  if (draft.kind === "formula.save" && formulaName) {
    return { zh: `${formulaName} -> ${table || "当前数据表"}`, en: `${formulaName} -> ${table || "current table"}` };
  }
  if (draft.kind === "formula.save" && formulaText) {
    const shortFormula = formulaText.length > 48 ? `${formulaText.slice(0, 48)}...` : formulaText;
    return { zh: `${shortFormula} -> ${table || "当前数据表"}`, en: `${shortFormula} -> ${table || "current table"}` };
  }
  if (draft.kind === "view.save" && viewName) {
    return { zh: `${viewName} -> ${table || "当前数据表"}`, en: `${viewName} -> ${table || "current table"}` };
  }
  if (draft.kind === "metric.add" && metricLabel) {
    return { zh: `${metricLabel} -> ${table || "当前数据表"}`, en: `${metricLabel} -> ${table || "current table"}` };
  }
  if (draft.kind === "metric.add" && measure) {
    const target = `${aggregation || "metric"}(${measure})${dimension ? ` by ${dimension}` : ""}`;
    return { zh: target, en: target };
  }
  return {
    zh: dashboard ? `看板 ${dashboard}` : table ? `数据表 ${table}` : prompt || "当前工作区",
    en: dashboard ? `Dashboard ${dashboard}` : table ? `Table ${table}` : prompt || "Current workspace",
  };
}

export function actionNextStep(draft: ActionDraft) {
  if (draft.kind === "dashboard.delete") {
    return biText("先确认目标看板名称，再决定是否删除。", "Confirm the dashboard name first, then decide whether to delete.");
  }
  if (draft.kind === "import.commit") {
    return biText("先预览导入影响，确认后才写入数据。", "Preview the import impact first; data writes only after confirmation.");
  }
  if (draft.kind.startsWith("dashboard.")) {
    return biText("先预览看板变化，确认后才更新画布。", "Preview the dashboard change first; the canvas updates only after confirmation.");
  }
  if (draft.kind === "relationship.save") {
    return biText("先核对连接字段，确认后才保存业务连接。", "Check the link fields first; the business link saves only after confirmation.");
  }
  if (draft.kind === "formula.save" || draft.kind === "metric.add" || draft.kind === "semantic.set") {
    return biText("先核对分析口径，确认后才影响后续分析。", "Check the analysis definition first; future analysis changes only after confirmation.");
  }
  if (draft.kind === "index.create" || draft.kind === "view.save") {
    return biText("先预览工作区配置，确认后才保存到本地元数据。", "Preview the workspace config first; local metadata saves only after confirmation.");
  }
  return biText("先预演，再确认是否应用。", "Preview first, then confirm whether to apply.");
}

function friendlyActionError(error: string): Pick<ActionResultSummary, "title" | "detail" | "next"> {
  const normalized = error.toLowerCase();
  if (normalized.includes("no csv/xlsx sources found") || normalized.includes("no sources found")) {
    return {
      title: { zh: "证据摘要没有完成", en: "Evidence summary did not finish" },
      detail: { zh: "没有找到可分析的 CSV/XLSX 表格。数据没有被写坏，这只是证据生成失败。", en: "No analyzable CSV/XLSX spreadsheet was found. No data was damaged; only evidence generation failed." },
      next: { zh: "检查路径是否能打开，并确认目录里有可读取表格。", en: "Check that the path opens and contains readable table files." },
    };
  }
  if (normalized.includes("not found") || normalized.includes("does not exist") || normalized.includes("no such")) {
    return {
      title: { zh: "路径没有找到", en: "Path was not found" },
      detail: { zh: "通常是路径少了一层、目录名写错，或输入框里夹杂了说明文字。", en: "This usually means a missing folder level, a typo, or extra notes in the path input." },
      next: { zh: "从资源管理器复制完整路径，一行放一个路径后重试。", en: "Copy the full path from Explorer, put one path per line, and retry." },
    };
  }
  return {
    title: { zh: "动作没有完成", en: "Action did not finish" },
    detail: { zh: "系统已停下，没有继续写入或覆盖。", en: "The system stopped and did not continue with a write or overwrite." },
    next: { zh: "查看当前页面的恢复建议，再重试或让 Agent 解释下一步。", en: "Review the recovery guidance on the current page, then retry or ask Agent for next steps." },
  };
}

export function actionResultSummary(result: Record<string, unknown> | null): ActionResultSummary | null {
  if (!result) return null;
  if (result.confirmed === true && result.decision === "reject") {
    return { tone: "ok", title: { zh: "草案已拒绝", en: "Draft rejected" }, detail: { zh: "没有执行写入。", en: "No write was executed." } };
  }
  if (result.confirmed === true && typeof result.createdDashboardKey === "string") {
    return { tone: "ok", title: { zh: "看板已创建", en: "Dashboard created" }, detail: { zh: `已创建看板 ${result.createdDashboardKey}。`, en: `Created dashboard ${result.createdDashboardKey}.` } };
  }
  if (result.confirmed === true && typeof result.operation === "string" && typeof result.dashboardKey === "string") {
    const labels: Record<string, LocalizedText> = {
      copy: { zh: "已复制看板", en: "Copied dashboard" },
      rename: { zh: "已重命名看板", en: "Renamed dashboard" },
      delete: { zh: "已删除看板", en: "Deleted dashboard" },
    };
    const label = labels[result.operation] || { zh: "看板动作已执行", en: "Dashboard action completed" };
    return { tone: "ok", title: label, detail: { zh: `${label.zh} ${result.dashboardKey}。`, en: `${label.en} ${result.dashboardKey}.` } };
  }
  if (result.confirmed === true && result.addedWidget && typeof result.addedWidget === "object") {
    const widget = result.addedWidget as { title?: string; widget_key?: string };
    const name = widget.title || widget.widget_key || "widget";
    return { tone: "ok", title: { zh: "组件已新增", en: "Widget added" }, detail: { zh: `已新增看板组件 ${name}。`, en: `Added dashboard widget ${name}.` } };
  }
  if (result.confirmed === true && result.filter && typeof result.filter === "object") {
    const filter = result.filter as { field?: string; value?: string };
    const name = `${filter.field || "filter"}${filter.value ? `=${filter.value}` : ""}`;
    return { tone: "ok", title: { zh: "筛选已新增", en: "Filter added" }, detail: { zh: `已新增看板筛选 ${name}。`, en: `Added dashboard filter ${name}.` } };
  }
  if (result.confirmed === true && result.savedMetric && typeof result.savedMetric === "object") {
    const metric = result.savedMetric as { label?: string; metricKey?: string };
    const name = metric.label || metric.metricKey || "metric";
    return { tone: "ok", title: { zh: "指标已新增", en: "Metric added" }, detail: { zh: `已新增指标 ${name}。`, en: `Added metric ${name}.` } };
  }
  if (result.confirmed === true && result.savedView && typeof result.savedView === "object") {
    const view = result.savedView as { name?: string; view_key?: string };
    const name = view.name || view.view_key || "view";
    return { tone: "ok", title: { zh: "视图已保存", en: "View saved" }, detail: { zh: `已保存视图 ${name}。`, en: `Saved view ${name}.` } };
  }
  if (result.requiresConfirmation === true) {
    return { tone: "preview", title: { zh: "预演完成", en: "Preview completed" }, detail: { zh: "仍需明确确认。", en: "Explicit confirmation is still required." } };
  }
  if (result.ok === false) {
    const error = String(result.error ?? "Action failed");
    const recovery = actionRecoveryFromResult(result);
    if (recovery) {
      return {
        tone: "failed",
        title: recovery.title,
        detail: recovery.detail,
        next: recovery.next,
        safeState: recovery.safeState,
        steps: recovery.steps,
        targetSection: recovery.targetSection,
        technical: recovery.technical,
      };
    }
    const friendly = friendlyActionError(error);
    return { tone: "failed", ...friendly, technical: error };
  }
  return { tone: "ok", title: { zh: "动作已记录", en: "Action recorded" }, detail: { zh: "可以继续下一步。", en: "You can continue to the next step." } };
}

export function sectionContext(section: AppSection, dashboardName: string, viewName: string, tableName: string, agent: AgentAskResult) {
  if (section === "dashboards") {
    return {
      title: dashboardName || biText("当前看板", "Current dashboard"),
      detail: biText("正在查看可编辑看板；组件、筛选和证据入口都应从这里回到同一工作区。", "You are viewing an editable dashboard. Widgets, filters, and evidence should stay in this workspace."),
      chips: [biText("看板画布", "dashboard canvas"), biText("可编辑", "editable")],
    };
  }
  if (section === "views") {
    return {
      title: viewName || biText("当前视图", "Current view"),
      detail: biText("视图保存常用字段、筛选、搜索和排序，可作为明细查询、下钻和看板组件来源。", "Views save common columns, filters, search, and sorting for details, drilldown, and dashboard widgets."),
      chips: [biText("白名单查询", "whitelist query"), biText("可保存", "savable")],
    };
  }
  if (section === "sources") {
    return {
      title: tableName || biText("数据源工作台", "Source workbench"),
      detail: biText("这里处理导入预检、画像、字段语义、公式和关系；危险写入仍需确认。", "This is where import previews, profiling, field semantics, formulas, and relationships are handled. Risky writes still require approval."),
      chips: [biText("预检优先", "preview first"), biText("Source Intelligence", "Source Intelligence")],
    };
  }
  if (section === "agent") {
    const answerTitle = agent.answerCard?.title ? biText(agent.answerCard.title.zh, agent.answerCard.title.en) : biText("Agent 工作区", "Agent workspace");
    return {
      title: answerTitle,
      detail: biText("Agent 可以回答、解释缺口和生成草案；没有确认前不会写入数据或看板。", "The Agent can answer, explain gaps, and draft changes. It does not write data or dashboards before approval."),
      chips: [biText("只读回答", "read-only answer"), biText("草案确认", "draft approval")],
    };
  }
  if (section === "evidence") {
    return {
      title: biText("证据与回执", "Evidence and receipts"),
      detail: biText("当前区域用于核对业务结论、证据摘要、查询回执、业务连接和动作边界。", "This area checks business conclusions, evidence summaries, query receipts, business links, and action boundaries."),
      chips: [biText("业务先读", "business first"), biText("技术可追踪", "technical trace")],
    };
  }
  return {
    title: biText("工作区起步台", "Workspace start"),
    detail: biText("按接入数据、生成摘要、创建看板、自然语言继续的路径推进。", "Proceed through add data, create a summary, create a dashboard, then continue in natural language."),
    chips: [biText("下一步", "next step"), biText("沙盒", "sandbox")],
  };
}

export function drawerActionsForSection(section: AppSection) {
  const actions: Record<AppSection, { evidence: LocalizedText; agent: LocalizedText; hint: LocalizedText }> = {
    home: {
      evidence: { zh: "查看证据", en: "View evidence" },
      agent: { zh: "问一句", en: "Ask" },
      hint: { zh: "保留全局入口，细节回到对应页面处理。", en: "Keep global shortcuts here; handle details on the matching page." },
    },
    sources: {
      evidence: { zh: "检查摘要", en: "Check summary" },
      agent: { zh: "解释缺口", en: "Explain gaps" },
      hint: { zh: "这里适合追溯字段、文件覆盖和导入安全，不重复左侧导航。", en: "Use this for fields, file coverage, and import safety without repeating left navigation." },
    },
    views: {
      evidence: { zh: "核对口径", en: "Check scope" },
      agent: { zh: "保存建议", en: "Draft save" },
      hint: { zh: "视图只保留查询口径和复用路径；看板编辑留在看板页。", en: "Views keep query scope and reuse paths; dashboard edits stay on dashboards." },
    },
    dashboards: {
      evidence: { zh: "看证据", en: "Proof" },
      agent: { zh: "改看板", en: "Edit draft" },
      hint: { zh: "只处理当前看板对象的深操作，避免和左侧页面入口重复。", en: "Only deep actions for the current dashboard object live here." },
    },
    agent: {
      evidence: { zh: "答案证据", en: "Answer proof" },
      agent: { zh: "处理草案", en: "Review drafts" },
      hint: { zh: "Agent 页优先处理回答依据和待确认修改。", en: "The Agent page focuses on answer grounding and pending changes." },
    },
    evidence: {
      evidence: { zh: "完整链路", en: "Full chain" },
      agent: { zh: "解释证据", en: "Explain proof" },
      hint: { zh: "证据页保留追溯和解释，不在抽屉里再铺完整明细。", en: "Evidence stays traceable here without duplicating all details in the drawer." },
    },
    settings: {
      evidence: { zh: "检查边界", en: "Check guardrails" },
      agent: { zh: "生成计划", en: "Draft plan" },
      hint: { zh: "设置页只保留安全边界和下一步计划。", en: "Settings keeps guardrails and next-step plans." },
    },
  };
  return actions[section];
}
