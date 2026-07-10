import type { BusinessPathIcon, BusinessPathStepKey } from "./businessPathModel";
import { biText } from "./components/Bilingual";
import type { WorkbenchPayload, WorkspaceStatus } from "./types";
import { buildWorkspaceFlow } from "./workspaceFlowModel";

export type ProductActivationStepKey = "connect" | "profile" | "chart" | "evidence" | "confirm";

export type ProductActivationStepStatus = "complete" | "active" | "locked";

export type ProductActivationStep = {
  key: ProductActivationStepKey;
  route: BusinessPathStepKey;
  icon: BusinessPathIcon;
  title: string;
  detail: string;
  actionLabel: string;
  status: ProductActivationStepStatus;
};

export type ProductActivationFactTone = "neutral" | "ok" | "warn";

export type ProductActivationFact = {
  label: string;
  value: string;
  tone: ProductActivationFactTone;
};

export type ProductActivationModel = {
  hasData: boolean;
  hasProfile: boolean;
  hasDashboard: boolean;
  hasEvidence: boolean;
  hasPendingDraft: boolean;
  activeStepKey: ProductActivationStepKey;
  primaryStep: ProductActivationStep;
  progressLabel: string;
  stateLabel: string;
  stateDetail: string;
  facts: ProductActivationFact[];
  trustFacts: ProductActivationFact[];
  steps: ProductActivationStep[];
};

export type ProductActivationOptions = {
  status?: WorkspaceStatus;
  workbench: WorkbenchPayload;
  dashboardCount?: number;
  pendingDraftCount?: number;
  agentRequiresConfirmation?: boolean;
};

function stepStatus(complete: boolean, active: boolean): ProductActivationStepStatus {
  if (complete) return "complete";
  if (active) return "active";
  return "locked";
}

export function buildProductActivation({
  status,
  workbench,
  dashboardCount,
  pendingDraftCount,
  agentRequiresConfirmation = false,
}: ProductActivationOptions): ProductActivationModel {
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const flow = buildWorkspaceFlow({ status, workbench, dashboardCount, pendingDraftCount, agentRequiresConfirmation });
  const {
    tableCount,
    fieldCount,
    metricCount,
    relationshipCount,
    sourceProfileCount,
    dashboardCount: resolvedDashboardCount,
    pendingDraftCount: resolvedDraftCount,
  } = flow.counts;
  const latestProfile = sourceIntelligenceRuns[0];
  const activeStepKey: ProductActivationStepKey = flow.activeStage;

  const allSteps: ProductActivationStep[] = [
    {
      key: "connect",
      route: "data",
      icon: "source",
      title: biText("接入数据", "Connect data"),
      detail: flow.hasData ? biText(`${tableCount} 张表可用`, `${tableCount} tables ready`) : biText("先选择文件或文件夹", "Choose files or folders first"),
      actionLabel: biText("去数据源", "Open sources"),
      status: stepStatus(flow.hasData, activeStepKey === "connect"),
    },
    {
      key: "profile",
      route: "data",
      icon: "evidence",
      title: biText("生成证据摘要", "Create evidence summary"),
      detail: flow.hasProfile
        ? biText(`${fieldCount} 字段 · ${metricCount} 指标`, `${fieldCount} fields · ${metricCount} metrics`)
        : biText("导入后再自动识别字段、关系和指标", "After import, detect fields, links, and metrics"),
      actionLabel: biText("去数据源", "Open sources"),
      status: stepStatus(flow.hasProfile, flow.hasData && activeStepKey === "profile"),
    },
    {
      key: "chart",
      route: "chart",
      icon: "dashboard",
      title: biText("生成一个图表", "Create one chart"),
      detail: flow.hasDashboard ? biText(`${resolvedDashboardCount} 个看板可编辑`, `${resolvedDashboardCount} dashboards editable`) : biText("说出想看的折线图、柱状图或指标卡", "Describe the line, bar, or metric card"),
      actionLabel: biText("去仪表盘", "Open dashboards"),
      status: stepStatus(flow.hasDashboard, flow.hasProfile && activeStepKey === "chart"),
    },
    {
      key: "evidence",
      route: "evidence",
      icon: "evidence",
      title: biText("核对证据", "Review evidence"),
      detail: flow.hasEvidence
        ? biText(`${sourceProfileCount} 条证据画像`, `${sourceProfileCount} evidence profiles`)
        : biText("只显示真实来源和回执", "Show only real sources and receipts"),
      actionLabel: biText("去证据页", "Open evidence"),
      status: stepStatus(flow.hasDashboard && flow.hasEvidence, flow.hasDashboard && activeStepKey === "evidence"),
    },
    {
      key: "confirm",
      route: "confirm",
      icon: "check",
      title: biText("确认写入", "Approve writes"),
      detail: flow.hasPendingDraft ? biText(`${resolvedDraftCount} 个草案待处理`, `${resolvedDraftCount} drafts pending`) : biText("没有待确认写入", "No writes waiting"),
      actionLabel: biText("去 AI 助手", "Open AI"),
      status: stepStatus(false, flow.hasPendingDraft),
    },
  ];
  const steps = allSteps.filter((step) => step.key !== "confirm" || flow.hasPendingDraft);

  const primaryStep = steps.find((step) => step.key === activeStepKey) ?? steps[0];
  const stateLabel = !flow.hasData
    ? biText("当前没有数据", "No data yet")
    : !flow.hasProfile
      ? biText("数据已接入，等待证据摘要", "Data connected, evidence pending")
      : !flow.hasDashboard
        ? biText("证据已就绪，下一步生成图表", "Evidence ready, create a chart next")
        : flow.hasPendingDraft
          ? biText("有草案待确认", "Drafts need approval")
          : biText("结果已生成，建议核对证据", "Results are ready; review the evidence next");
  const stateDetail = !flow.hasData
    ? biText("导入真实数据后再显示图表和证据。", "Charts and evidence appear only after a real import.")
    : !flow.hasProfile
      ? biText("运行证据摘要后，字段、关系、指标缺口会进入可核对状态。", "Run evidence summary to make fields, links, and metric gaps reviewable.")
      : !flow.hasDashboard
        ? biText("默认通过一次对话创建一个可确认图表，行业整套看板留在 Beta。", "Default to one confirmable chart per conversation; full industry boards remain beta.")
        : flow.hasPendingDraft
          ? biText("写入前先看目标、影响和证据；可确认也可拒绝。", "Review target, impact, and evidence before confirming or rejecting.")
          : biText("可以继续查看证据、编辑图表或让 AI 起草下一步。", "Continue reviewing evidence, editing charts, or asking AI for the next draft.");

  return {
    hasData: flow.hasData,
    hasProfile: flow.hasProfile,
    hasDashboard: flow.hasDashboard,
    hasEvidence: flow.hasEvidence,
    hasPendingDraft: flow.hasPendingDraft,
    activeStepKey,
    primaryStep,
    progressLabel: !flow.hasData
      ? biText("待接入", "Connect data")
      : !flow.hasProfile
        ? biText("待画像", "Create profile")
        : !flow.hasDashboard
          ? biText("待生成", "Create chart")
          : flow.hasPendingDraft
            ? biText("待确认", "Review draft")
            : biText("可核对", "Review evidence"),
    stateLabel,
    stateDetail,
    steps,
    facts: [
      { label: biText("数据表", "Tables"), value: String(tableCount), tone: flow.hasData ? "ok" : "warn" },
      { label: biText("证据摘要", "Evidence runs"), value: String(sourceProfileCount), tone: flow.hasEvidence ? "ok" : "neutral" },
      { label: biText("看板", "Dashboards"), value: String(resolvedDashboardCount), tone: flow.hasDashboard ? "ok" : "neutral" },
      { label: biText("待确认", "Pending"), value: String(resolvedDraftCount), tone: flow.hasPendingDraft ? "warn" : "ok" },
    ],
    trustFacts: [
      { label: biText("字段", "Fields"), value: String(fieldCount || latestProfile?.field_candidate_count || 0), tone: fieldCount || latestProfile ? "ok" : "neutral" },
      { label: biText("关系", "Links"), value: String(relationshipCount || latestProfile?.relationship_count || 0), tone: relationshipCount || latestProfile ? "ok" : "neutral" },
      { label: biText("指标", "Metrics"), value: String(metricCount || latestProfile?.metric_sql_executable_count || 0), tone: metricCount || latestProfile ? "ok" : "neutral" },
      { label: biText("写入边界", "Write gate"), value: flow.hasPendingDraft ? biText("待审", "review") : biText("安全", "safe"), tone: flow.hasPendingDraft ? "warn" : "ok" },
    ],
  };
}
