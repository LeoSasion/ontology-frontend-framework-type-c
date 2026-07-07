import type { AgentAskResult, EvidenceFocus, ImportPreview, WorkbenchPayload, WorkspaceStatus } from "./types";

export type ProductSignalTone = "ok" | "warn" | "info" | "muted";

export type ProductSignal = {
  key: string;
  tone: ProductSignalTone;
  title: string;
  detail: string;
  value?: string;
};

export type ScenarioPack = {
  key: "cost-monitor" | "sales-ops" | "refund-risk" | "cashflow" | "policy-ops" | "custom";
  title: string;
  detail: string;
  prompt: string;
  template?: "business" | "cost-monitor";
  readiness: ProductSignalTone;
  facts: string[];
};

export type DataQualityDoctor = {
  score: number;
  tone: ProductSignalTone;
  summary: string;
  issues: ProductSignal[];
  nextActions: ProductSignal[];
};

export type ObjectInspectorModel = {
  objectType: string;
  title: string;
  subtitle: string;
  primaryAction: string;
  secondaryAction: string;
  facts: ProductSignal[];
  editorSlots: ProductSignal[];
};

export type EvidenceNarrative = {
  title: string;
  summary: string;
  calculationSteps: ProductSignal[];
  trustChecks: ProductSignal[];
};

export type SandboxComparison = {
  title: string;
  summary: string;
  facts: ProductSignal[];
  versionHints: ProductSignal[];
};

function countEnabled<T>(items: T[] | undefined | null) {
  return Array.isArray(items) ? items.length : 0;
}

function percent(value: number) {
  return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
}

function latestSourceRun(workbench: WorkbenchPayload) {
  return Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns[0] : undefined;
}

export function buildScenarioPacks(status: WorkspaceStatus, workbench: WorkbenchPayload): ScenarioPack[] {
  const run = latestSourceRun(workbench);
  const hasData = status.counts.tables > 0;
  const metricCount = status.counts.metrics || countEnabled(workbench.metrics);
  const relationshipCount = status.counts.relationships || countEnabled(workbench.relationships);
  const executable = run?.metric_sql_executable_count ?? 0;
  const baseReadiness: ProductSignalTone = hasData ? (executable > 0 ? "ok" : "info") : "warn";
  return [
    {
      key: "cost-monitor",
      title: "费用监控",
      detail: "基于当前字段证据检查服务费、佣金、保费、退款、动账净额和收入缺口。",
      prompt: "帮我生成费用监控看板草案，说明资金表、保单明细、动账净额、收入、缺口和证据，先不要直接写入。",
      template: "cost-monitor",
      readiness: hasData ? "ok" : "warn",
      facts: ["字段证据驱动", "费用口径预演", "写入前确认"],
    },
    {
      key: "sales-ops",
      title: "销售经营",
      detail: "按渠道、时间和订单表现生成老板晨会版看板，先给结论，再追证据。",
      prompt: "基于当前工作区生成销售经营看板草案，包含渠道排名、趋势、订单数、净销售额和可追溯证据，先不要直接写入。",
      template: "business",
      readiness: baseReadiness,
      facts: [`${metricCount} 个指标`, `${executable} 条可执行问题`, "可编辑看板"],
    },
    {
      key: "refund-risk",
      title: "退款与异常",
      detail: "先找退款压力、异常渠道和需要复核的明细，再生成可确认修改。",
      prompt: "检查当前工作区的退款压力和异常记录，列出证据、影响范围和下一步，涉及看板修改时只生成草案。",
      readiness: relationshipCount ? "ok" : "info",
      facts: [`${relationshipCount} 条关系`, "明细下钻", "只读诊断"],
    },
    {
      key: "cashflow",
      title: "现金流与动账",
      detail: "围绕入账、出账、净额和缺口组织指标，适合财务负责人先看风险。",
      prompt: "帮我做现金流和动账净额分析，说明入账、出账、净额、缺口和证据来源；如果要改看板，只起草不写入。",
      readiness: hasData ? "info" : "warn",
      facts: ["财务视角", "缺口解释", "证据优先"],
    },
    {
      key: "policy-ops",
      title: "保单/订单履约",
      detail: "把订单、保单、渠道和状态字段串起来，找履约、退款和收入问题。",
      prompt: "基于订单和保单相关字段生成履约分析计划，说明可回答问题、缺字段和推荐看板，不要直接写入。",
      readiness: relationshipCount ? "ok" : baseReadiness,
      facts: ["跨表关系", "状态字段", "缺口计划"],
    },
  ];
}

export function buildDataQualityDoctor(status: WorkspaceStatus, workbench: WorkbenchPayload, preview: ImportPreview): DataQualityDoctor {
  const run = latestSourceRun(workbench);
  const sourceCoverageComplete = run?.fileCoverage?.complete === true;
  const executableRatio = run?.metric_sql_plan_count ? (run.metric_sql_executable_count / run.metric_sql_plan_count) * 100 : 0;
  const fields = Array.isArray(workbench.fields) ? workbench.fields : [];
  const lowConfidenceFields = fields.filter((field) => Number(field.confidence ?? 0) < 0.65);
  const missingRelationships = status.counts.tables > 1 && status.counts.relationships === 0;
  const previewWarnings = preview.profile?.warnings ?? [];
  const issues: ProductSignal[] = [
    !status.counts.tables ? {
      key: "no-table",
      tone: "warn",
      title: "还没有工作区数据",
      detail: "先导入或扫描文件，后续看板和 Agent 才有可靠上下文。",
      value: "0",
    } : {
      key: "table-ready",
      tone: "ok",
      title: "数据表已接入",
      detail: "已有可查询数据，下一步看证据摘要和指标可执行率。",
      value: String(status.counts.tables),
    },
    sourceCoverageComplete ? {
      key: "coverage-ready",
      tone: "ok",
      title: "证据覆盖完整",
      detail: "Source Intelligence 已覆盖当前输入，适合作为看板和 Agent 证据。",
      value: `${run?.source_count ?? 0}`,
    } : {
      key: "coverage-gap",
      tone: run ? "warn" : "info",
      title: run ? "证据覆盖需复核" : "证据摘要待生成",
      detail: run ? "部分文件或表可能没有进入画像，关键结论前建议复核。" : "先生成证据摘要，系统才能说明能回答什么。",
      value: run ? `${run.source_count}` : "0",
    },
    executableRatio >= 70 ? {
      key: "metric-sql-ready",
      tone: "ok",
      title: "指标 SQL 可用",
      detail: "大部分推荐问题可以被查询运行时验证。",
      value: percent(executableRatio),
    } : {
      key: "metric-sql-gap",
      tone: run ? "warn" : "muted",
      title: "指标可执行率不足",
      detail: "字段语义或指标定义需要补齐，否则 Agent 只能给缺口计划。",
      value: run ? percent(executableRatio) : "-",
    },
    missingRelationships ? {
      key: "relationship-gap",
      tone: "warn",
      title: "多表但缺少业务连接",
      detail: "建议先预览关系，否则跨表看板和下钻会受限。",
      value: "0",
    } : {
      key: "relationship-ready",
      tone: status.counts.relationships ? "ok" : "muted",
      title: status.counts.relationships ? "业务连接可用" : "暂不需要跨表连接",
      detail: status.counts.relationships ? "关系证据可以支撑跨表组件。" : "单表分析可先继续，跨表时再建关系。",
      value: String(status.counts.relationships),
    },
    lowConfidenceFields.length ? {
      key: "field-confidence-gap",
      tone: "warn",
      title: "部分字段语义不稳",
      detail: "低置信字段会影响指标、筛选和看板推荐。",
      value: String(lowConfidenceFields.length),
    } : {
      key: "field-confidence-ready",
      tone: fields.length ? "ok" : "muted",
      title: fields.length ? "字段语义较稳定" : "字段语义待推断",
      detail: fields.length ? "当前字段可用于推荐指标和看板。" : "导入或画像后会生成字段语义。",
      value: String(fields.length),
    },
  ];
  if (previewWarnings.length) {
    issues.push({
      key: "preview-warning",
      tone: "warn",
      title: "导入预检有提示",
      detail: previewWarnings.slice(0, 2).join("；"),
      value: String(previewWarnings.length),
    });
  }
  const score = issues.reduce((sum, item) => sum + (item.tone === "ok" ? 20 : item.tone === "info" ? 12 : item.tone === "muted" ? 8 : 2), 0);
  const normalizedScore = Math.min(100, Math.round(score / Math.max(1, issues.length) * 5));
  const tone: ProductSignalTone = normalizedScore >= 75 ? "ok" : normalizedScore >= 45 ? "info" : "warn";
  return {
    score: normalizedScore,
    tone,
    summary: tone === "ok" ? "当前数据足以支撑看板和只读 Agent 分析。" : tone === "info" ? "当前数据可继续分析，但建议先补一轮证据或字段口径。" : "先修复数据入口、证据覆盖或关系口径，再生成关键看板。",
    issues,
    nextActions: [
      { key: "check-file", tone: preview.ok ? "ok" : "info", title: "检查文件", detail: "先看行列、字段和合并影响，再决定是否导入。" },
      { key: "refresh-profile", tone: run ? "ok" : "info", title: "生成证据摘要", detail: "把可回答问题、指标 SQL、关系候选和缺口整理出来。" },
      { key: "draft-dashboard", tone: status.counts.dashboards ? "ok" : "info", title: "生成看板草案", detail: "先预演组件和证据，确认后才写入。" },
    ],
  };
}

export function buildObjectInspectorModel(args: {
  activeSection: string;
  focus?: EvidenceFocus | null;
  status: WorkspaceStatus;
  preview: ImportPreview;
  agent: AgentAskResult;
  activeDashboardName?: string;
  activeViewName?: string;
  activeTableName?: string;
}): ObjectInspectorModel {
  const { activeSection, focus, status, preview, agent, activeDashboardName, activeViewName, activeTableName } = args;
  const source = focus?.source ?? activeSection;
  const objectType = focus?.widgetType ? "看板组件" : source === "dashboard-widget" || activeSection === "dashboards" ? "看板" : activeSection === "sources" ? "数据源" : activeSection === "views" ? "明细视图" : activeSection === "agent" ? "Agent 草案" : activeSection === "evidence" ? "证据" : "工作区";
  const title = focus?.title || activeDashboardName || activeViewName || activeTableName || (agent.answerCard?.title ? agent.answerCard.title.zh : "当前工作区");
  const subtitle = focus?.subtitle || (focus ? "当前对象已绑定证据，可以继续追溯或起草修改。" : "选择图表、字段、视图或草案后，这里会切换到对应编辑器。");
  const refs = focus?.refs ?? agent.ontology.evidenceFiles ?? [];
  return {
    objectType,
    title,
    subtitle,
    primaryAction: objectType === "证据" ? "解释证据" : objectType === "数据源" ? "检查质量" : "起草修改",
    secondaryAction: "查看完整证据",
    facts: [
      { key: "refs", tone: refs.length ? "ok" : "muted", title: "证据线索", detail: "当前对象可追溯引用", value: String(refs.length) },
      { key: "tables", tone: status.counts.tables ? "ok" : "warn", title: "数据表", detail: "当前沙箱可用表", value: String(status.counts.tables) },
      { key: "drafts", tone: status.counts.actionDrafts ? "warn" : "ok", title: "待确认", detail: "写入前停在草案队列", value: String(status.counts.actionDrafts) },
    ],
    editorSlots: [
      { key: "definition", tone: focus ? "ok" : "muted", title: "口径", detail: focus?.tableKey || preview.suggestedTableKey || "等待对象选择" },
      { key: "impact", tone: agent.requiresConfirmation ? "warn" : "info", title: "影响", detail: agent.requiresConfirmation ? "已有待确认修改" : "当前仅预留草案入口" },
      { key: "version", tone: "info", title: "版本", detail: "后续支持确认前后对比和撤销" },
    ],
  };
}

export function buildEvidenceNarrative(focus: EvidenceFocus | null | undefined, agent: AgentAskResult, workbench: WorkbenchPayload): EvidenceNarrative {
  const run = sourceRunFromRefs(focus?.refs, workbench) ?? latestSourceRun(workbench);
  const refs = focus?.refs?.length ? focus.refs : agent.ontology.evidenceFiles;
  const answerTitle = agent.answerCard?.title?.zh;
  return {
    title: focus?.title || answerTitle || "当前数字说明书",
    summary: run ? `这组证据来自 ${run.source_count} 个源文件，${run.metric_sql_executable_count}/${run.metric_sql_plan_count} 个指标问题可执行。` : "尚未生成完整证据摘要，当前只能解释已知引用和动作边界。",
    calculationSteps: [
      { key: "source", tone: run ? "ok" : "warn", title: "1. 定位来源", detail: run ? run.label : "等待 Source Intelligence 运行" },
      { key: "metric", tone: run?.metric_sql_executable_count ? "ok" : "info", title: "2. 匹配口径", detail: run ? `${run.metric_sql_executable_count} 条可执行指标 SQL` : "需要字段语义和指标定义" },
      { key: "query", tone: refs.includes("query-runtime") ? "ok" : "info", title: "3. 运行查询", detail: refs.includes("query-runtime") ? "已有查询回执" : "当前证据可继续补查询回执" },
      { key: "action", tone: "ok", title: "4. 写入边界", detail: "导入、看板、关系和公式写入前均需确认" },
    ],
    trustChecks: [
      { key: "coverage", tone: run?.fileCoverage?.complete ? "ok" : "warn", title: "覆盖", detail: run?.fileCoverage?.complete ? "源文件覆盖完整" : "覆盖需复核或重新画像" },
      { key: "relationship", tone: (run?.relationship_count ?? 0) > 0 ? "ok" : "info", title: "关系", detail: `${run?.relationship_count ?? 0} 条关系证据` },
      { key: "refs", tone: refs.length ? "ok" : "muted", title: "引用", detail: `${refs.length} 条证据引用` },
    ],
  };
}

function sourceRunFromRefs(refs: string[] | undefined, workbench: WorkbenchPayload) {
  const key = refs?.find((ref) => ref.startsWith("source-intelligence:"))?.replace("source-intelligence:", "");
  return key ? workbench.sourceIntelligenceRuns.find((run) => run.run_key === key) : undefined;
}

export function buildSandboxComparison(status: WorkspaceStatus, workbench: WorkbenchPayload): SandboxComparison {
  const workspaces = Array.isArray(status.workspaces) ? status.workspaces : [status.workspace];
  const active = workspaces.find((workspace) => workspace.isActive) ?? status.workspace;
  const otherCount = Math.max(0, workspaces.length - 1);
  return {
    title: "沙箱版本与影响面",
    summary: otherCount ? `当前沙箱是 ${active.name}，还有 ${otherCount} 个沙箱可用于对比或复制配置。` : `当前沙箱是 ${active.name}，后续可以创建分支来试验看板和字段口径。`,
    facts: [
      { key: "tables", tone: "ok", title: "表", detail: "当前沙箱数据资产", value: String(status.counts.tables) },
      { key: "dashboards", tone: "ok", title: "看板", detail: "当前沙箱看板资产", value: String(status.counts.dashboards) },
      { key: "views", tone: workbench.savedViews.length ? "ok" : "muted", title: "明细视图", detail: "可复用查询口径", value: String(workbench.savedViews.length) },
      { key: "drafts", tone: status.counts.actionDrafts ? "warn" : "ok", title: "草案", detail: "确认前不会写入", value: String(status.counts.actionDrafts) },
    ],
    versionHints: [
      { key: "preview", tone: "info", title: "确认前对比", detail: "看板、导入、关系和配置都先生成预演结果。" },
      { key: "branch", tone: "info", title: "沙箱分支", detail: "适合做老板版、财务版、运营版的看板变体。" },
      { key: "rollback", tone: "muted", title: "撤销基础", detail: "下一步可把确认回执升级为可回滚版本链。" },
    ],
  };
}
