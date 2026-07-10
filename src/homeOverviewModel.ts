import type { SourceIntelligenceDashboardCandidate, SourceIntelligenceRunSummary } from "./types";
import type { AppSection } from "./components/Sidebar";
import { biText } from "./components/Bilingual";
import { numberValue, objectRecord, recordArray, stringValue } from "./safeValue";

export { numberValue, objectRecord, recordArray, stringValue };

export function buildStarterQuestions(latestRun?: SourceIntelligenceRunSummary) {
  const analyses = latestRun?.fileCoverage?.dashboardCandidate?.analyses
    ?.filter((item) => item.status === "executed" && item.label.trim())
    .slice(0, 2) ?? [];
  const questions = analyses.map((analysis) => ({
    zh: `解释「${analysis.label}」的变化，并列出证据`,
    en: `Explain changes in "${analysis.label}" and list the evidence`,
  }));
  questions.push({
    zh: "根据当前字段推荐一个最值得先看的图表",
    en: "Recommend the most useful first chart from the current fields",
  });
  if (questions.length < 3) {
    questions.push({
      zh: "当前证据还能可靠回答哪些问题？",
      en: "What else can the current evidence answer reliably?",
    });
  }
  return questions.slice(0, 3);
}

export type GuideStep = {
  key: "source" | "profile" | "dashboard" | "ask";
  label: string;
  detail: string;
  icon: "source" | "dashboard" | "agent" | "evidence";
  state: "done" | "current" | "pending";
  actionLabel: string;
  actionSection: AppSection;
};

export function buildHomeReadiness(options: {
  dashboardCount: number;
  hasData: boolean;
  latestRun?: SourceIntelligenceRunSummary;
}) {
  const { dashboardCount, hasData, latestRun } = options;
  if (!hasData) {
    return {
      label: biText("先接入数据", "Add data first"),
      detail: biText("还没有可分析的数据表。请先导入本地文件或文件夹。", "No analysis table is available. Import local files or folders first."),
      next: "sources" as AppSection,
    };
  }
  if (!latestRun) {
    return {
      label: biText("生成证据摘要", "Create evidence summary"),
      detail: biText("数据表已就绪，下一步让系统读一遍文件和业务口径，形成可追溯摘要。", "Tables are ready. Next, let the system read files and business logic into a traceable summary."),
      next: "sources" as AppSection,
    };
  }
  if (!dashboardCount) {
    return {
      label: biText("生成首个看板", "Create first dashboard"),
      detail: biText("证据摘要已经生成，可以创建可编辑经营看板。", "The evidence summary is ready. Create an editable business dashboard."),
      next: "dashboards" as AppSection,
    };
  }
  return {
    label: biText("可以直接提问", "Ready for questions"),
    detail: biText("数据源、看板和证据链都已连接。可以用自然语言继续分析或调整看板。", "Sources, dashboards, and evidence are connected. Continue with natural language analysis or dashboard changes."),
    next: "agent" as AppSection,
  };
}

export function buildHomeGuideSteps(options: {
  agentRequiresConfirmation: boolean;
  dashboardCount: number;
  hasData: boolean;
  hasLatestDashboardDraft: boolean;
  latestRun?: SourceIntelligenceRunSummary;
  tableCount: number;
}): GuideStep[] {
  const { agentRequiresConfirmation, dashboardCount, hasData, hasLatestDashboardDraft, latestRun, tableCount } = options;
  const hasProfile = Boolean(latestRun);
  const hasDashboard = dashboardCount > 0;
  const hasDraft = hasLatestDashboardDraft || agentRequiresConfirmation;
  return [
    {
      key: "source",
      label: biText("接入数据", "Add data"),
      detail: hasData
        ? biText(`${tableCount} 张表已在工作区`, `${tableCount} tables in workspace`)
        : biText("先预检文件，不直接写入", "Preview files before writing"),
      icon: "source",
      state: hasData ? "done" : "current",
      actionLabel: hasData ? biText("检查数据源", "Check sources") : biText("开始导入", "Start import"),
      actionSection: "sources",
    },
    {
      key: "profile",
      label: biText("生成证据摘要", "Create evidence summary"),
      detail: hasProfile
        ? biText(`${latestRun?.source_count ?? 0} 文件，${latestRun?.metric_sql_executable_count ?? 0} 个可用指标`, `${latestRun?.source_count ?? 0} files, ${latestRun?.metric_sql_executable_count ?? 0} usable metrics`)
        : biText("自动整理可用问题、口径和缺口", "Summarize answerable questions, logic, and gaps"),
      icon: "evidence",
      state: hasProfile ? "done" : hasData ? "current" : "pending",
      actionLabel: hasProfile ? biText("查看证据", "View evidence") : biText("生成摘要", "Create summary"),
      actionSection: hasProfile ? "evidence" : "sources",
    },
    {
      key: "dashboard",
      label: biText("生成看板", "Create dashboard"),
      detail: hasDashboard
        ? biText(`${dashboardCount} 个看板可编辑`, `${dashboardCount} editable dashboards`)
        : biText("先出草案，再确认写入", "Draft first, then confirm"),
      icon: "dashboard",
      state: hasDashboard ? "done" : hasProfile ? "current" : "pending",
      actionLabel: hasDashboard ? biText("打开看板", "Open dashboard") : biText("预览草案", "Preview draft"),
      actionSection: "dashboards",
    },
    {
      key: "ask",
      label: biText("自然语言继续", "Continue in language"),
      detail: hasDraft
        ? biText("有草案等待确认", "Draft waiting for approval")
        : biText("提问只读，写入仍需确认", "Ask read-only; writes still need approval"),
      icon: "agent",
      state: hasDashboard ? "current" : "pending",
      actionLabel: hasDraft ? biText("确认草案", "Review draft") : biText("直接提问", "Ask directly"),
      actionSection: "agent",
    },
  ];
}

export function sourceDashboardCandidate(value: unknown): SourceIntelligenceDashboardCandidate | null {
  const record = objectRecord(value);
  if (!record || !Array.isArray(record.analyses)) return null;
  return record as unknown as SourceIntelligenceDashboardCandidate;
}
