import { useMemo, useState } from "react";
import type { AgentAskResult, QueryResult, WorkbenchPayload, WorkspaceStatus } from "../types";
import type { BusinessDashboardOptions } from "../dashboardCanvasContracts";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import { buildDataQualityDoctor, buildSandboxComparison, buildScenarioPacks, type ScenarioPack } from "../productIntelligenceModel";
import { buildMetricRepairPlan } from "../metricRepairModel";
import { buildHomeGuideSteps, buildHomeReadiness, numberValue, objectRecord, recordArray, stringValue } from "../homeOverviewModel";
import type { BusinessPathStepKey } from "../businessPathModel";
import { buildProductActivation } from "../productActivationModel";
import { useQualityDoctor } from "../useQualityDoctor";
import { Bilingual, biText } from "./Bilingual";
import { HomeActionDock } from "./HomeActionDock";
import { HomeDetailedPathPanel } from "./HomeDetailedPathPanel";
import { HomeOperatingSummaryPanel } from "./HomeOperatingSummaryPanel";
import { HomeProductIntelligencePanel } from "./HomeProductIntelligencePanel";
import { HomeScenarioPacksPanel } from "./HomeScenarioPacksPanel";
import { HomeWorkspaceStartGuide } from "./HomeWorkspaceStartGuide";
import { ProductActivationPanel } from "./ProductActivationPanel";
import type { AppSection } from "./Sidebar";

type HomeOverviewProps = {
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  query: QueryResult;
  agent: AgentAskResult;
  onAsk: (prompt: string) => Promise<void>;
  onQuery: () => Promise<void>;
  onSourceIntelligenceRun: (options?: SourceIntelligenceRunOptions) => Promise<Record<string, unknown> | void>;
  onBusinessDashboardOperation: (options: BusinessDashboardOptions) => Promise<Record<string, unknown>>;
  onSetSemantic: (options: { table: string; field: string; role: string; tags?: string[]; usage?: string[]; confidence?: number; note?: string; confirm?: boolean; stayOnPage?: boolean }) => Promise<Record<string, unknown>>;
  onOpenBusinessStep: (step: BusinessPathStepKey) => void;
  onOpenSection: (section: AppSection) => void;
};

export function HomeOverview({ status, workbench, query, agent, onAsk, onQuery, onSourceIntelligenceRun, onBusinessDashboardOperation, onSetSemantic, onOpenBusinessStep, onOpenSection }: HomeOverviewProps) {
  const [busy, setBusy] = useState<"profile" | "dashboardDraft" | "dashboardCreate" | "query" | "ask" | null>(null);
  const [dashboardPlan, setDashboardPlan] = useState<Record<string, unknown> | null>(null);
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const rows = Array.isArray(query.rows) ? query.rows : [];
  const latestRun = sourceIntelligenceRuns[0];
  const topRow = rows[0];
  const topValue = Number(topRow?.value ?? 0);
  const hasData = status.counts.tables > 0;
  const qualityDoctorResult = useQualityDoctor(hasData, workbench);
  const mainTable = workbench.tables[0];
  const latestDashboardDraft = agent.requiresConfirmation && agent.actionDraft?.status === "draft" ? agent.actionDraft : null;
  const dashboardProposal = objectRecord(dashboardPlan?.proposed);
  const dashboardDraft = objectRecord(dashboardPlan?.draft);
  const dashboardPlanTitle = stringValue(dashboardProposal?.dashboardName) || biText("经营分析看板", "Business dashboard");
  const dashboardPlanKey = stringValue(dashboardPlan?.createdDashboardKey) || stringValue(dashboardPlan?.savedDashboardKey) || stringValue(dashboardProposal?.dashboardKey);
  const dashboardPlanTable = stringValue(dashboardProposal?.defaultTableKey) || stringValue(dashboardDraft?.defaultTableKey) || mainTable?.table_key || "-";
  const dashboardPlanWidgetCount = numberValue(dashboardProposal?.widgetCount) || numberValue(dashboardPlan?.templateCount) || numberValue(dashboardPlan?.savedDashboardModules);
  const dashboardPlanNeedsConfirmation = dashboardPlan?.requiresConfirmation === true || dashboardPlan?.dryRun === true;
  const scenarioPacks = useMemo(() => buildScenarioPacks(status, workbench), [status, workbench]);
  const qualityDoctor = useMemo(() => buildDataQualityDoctor(status, workbench, {
    ok: true,
    dryRun: true,
    file: "",
    suggestedTableKey: mainTable?.table_key ?? "",
    profile: { rowCount: mainTable?.row_count ?? 0, columnCount: mainTable?.column_count ?? 0, fields: [], measures: [], dimensions: [], identityKeys: [], warnings: [] },
    mergePolicyPreview: { mode: "preview", uniqueFields: [], conflictRule: "skip", willWrite: false },
    sourcePipelineContract: { version: 1, stages: [] },
  }), [mainTable, status, workbench]);
  const sandboxComparison = useMemo(() => buildSandboxComparison(status, workbench), [status, workbench]);
  const liveQualityDoctor = objectRecord(qualityDoctorResult);
  const liveMetricSql = objectRecord(liveQualityDoctor?.metricSql);
  const liveQualityIssues = recordArray(liveQualityDoctor?.issues);
  const liveMissingSemantics = recordArray(liveMetricSql?.missingSemantics);
  const liveFailedMetricSamples = recordArray(liveMetricSql?.failedSamples);
  const liveRepairDraft = objectRecord(liveMetricSql?.repairDraft);
  const liveScore = numberValue(liveQualityDoctor?.score) || qualityDoctor.score;
  const liveTone = stringValue(liveQualityDoctor?.tone) || qualityDoctor.tone;
  const liveSummary = stringValue(liveQualityDoctor?.summary) || qualityDoctor.summary;
  const liveMetricPlanned = numberValue(liveMetricSql?.planned) || latestRun?.metric_sql_plan_count || 0;
  const liveMetricExecutable = numberValue(liveMetricSql?.executable) || latestRun?.metric_sql_executable_count || 0;
  const liveMetricBlocked = numberValue(liveMetricSql?.blocked);
  const liveMetricRate = numberValue(liveMetricSql?.rate);
  const metricRepairPlan = useMemo(() => buildMetricRepairPlan(qualityDoctorResult, workbench), [qualityDoctorResult, workbench]);

  const readiness = useMemo(() => buildHomeReadiness({
    dashboardCount: status.counts.dashboards,
    hasData,
    latestRun,
  }), [hasData, latestRun, status.counts.dashboards]);
  const activation = useMemo(() => buildProductActivation({
    status,
    workbench,
    agentRequiresConfirmation: agent.requiresConfirmation,
  }), [agent.requiresConfirmation, status, workbench]);
  const guideSteps = useMemo(() => buildHomeGuideSteps({
    agentRequiresConfirmation: agent.requiresConfirmation,
    dashboardCount: status.counts.dashboards,
    hasData,
    hasLatestDashboardDraft: Boolean(latestDashboardDraft),
    latestRun,
    tableCount: status.counts.tables,
  }), [agent.requiresConfirmation, hasData, latestDashboardDraft, latestRun, status.counts.dashboards, status.counts.tables]);

  async function runBusy<T>(key: Exclude<typeof busy, null>, task: () => Promise<T>, nextSection?: AppSection) {
    setBusy(key);
    try {
      await task();
      if (nextSection) onOpenSection(nextSection);
    } finally {
      setBusy(null);
    }
  }

  async function runDashboardTemplate(confirm: boolean) {
    const result = await onBusinessDashboardOperation({
      op: confirm ? "create" : "draft",
      name: biText("经营分析看板", "Business dashboard"),
      table: mainTable?.table_key,
      limit: 10,
      confirm,
    });
    setDashboardPlan(result);
    if (confirm && (typeof result.createdDashboardKey === "string" || typeof result.savedDashboardKey === "string")) {
      onOpenSection("dashboards");
    }
  }

  async function runScenarioPrompt(pack: ScenarioPack) {
    await runBusy("ask", () => onAsk(pack.prompt), "agent");
  }

  async function previewScenarioTemplate(pack: ScenarioPack) {
    if (!pack.template) {
      await runScenarioPrompt(pack);
      return;
    }
    await runBusy("dashboardDraft", async () => {
      const result = await onBusinessDashboardOperation({
        op: "draft",
        name: pack.title,
        table: mainTable?.table_key,
        template: pack.template,
        limit: pack.template === "cost-monitor" ? 24 : 10,
        confirm: false,
      });
      setDashboardPlan(result);
    }, "dashboards");
  }

  async function askMetricRepairReason() {
    await runBusy("ask", () => onAsk(biText(
      "解释当前指标 SQL 为什么不可执行，优先说明缺失字段语义、影响哪些指标、哪些字段可以作为确认草案。只读回答，不写入。",
      "Explain why current metric SQL is not executable. Prioritize missing field semantics, affected metrics, and candidate field-confirmation drafts. Read-only answer, no writes.",
    )), "agent");
  }

  return (
    <section className="mainPanel overviewPanel" aria-labelledby="overview-title">
      <div className="overviewHero">
        <div>
          <p className="kicker">{biText("经营起步台", "Operating start")}</p>
          <h2 id="overview-title">
            <Bilingual zh="从一条业务路径进入，不在首页重复配置" en="Use one business path instead of repeated setup" />
          </h2>
          <p>
            <Bilingual
              zh="同一件事只保留一个承接页：数据源负责接入，看板负责生成图表，证据页负责核对，AI 助手负责确认写入。"
              en="Each business task has one owning page: sources connect data, dashboards create charts, evidence verifies, and AI approves writes."
            />
          </p>
        </div>
        <div className="readinessCard">
          <span className={hasData ? "statusBadge ok" : "statusBadge warn"}>
            {readiness.label}
          </span>
          <strong>{status.counts.tables}</strong>
          <span>{biText("张数据表可用", "tables available")}</span>
          <p>{readiness.detail}</p>
        </div>
      </div>

      <ProductActivationPanel
        activation={activation}
        currentStep={activation.primaryStep.route}
        onOpenStep={onOpenBusinessStep}
      />

      {hasData ? (
        <>
          <details className="advancedDetails homeShortcutDetails" data-testid="home-shortcut-details">
            <summary>{biText("其他快捷入口", "Other shortcuts")}</summary>
            <HomeActionDock
              agentRequiresConfirmation={agent.requiresConfirmation}
              hasData={hasData}
              onOpenStep={onOpenBusinessStep}
              tableCount={status.counts.tables}
            />
          </details>

          <details className="advancedDetails homeBetaDetails">
            <summary>{biText("更多：行业看板 Beta", "More: industry dashboard beta")}</summary>
            <HomeScenarioPacksPanel
              busy={busy}
              onPreviewScenarioTemplate={(pack) => void previewScenarioTemplate(pack)}
              onRunScenarioPrompt={(pack) => void runScenarioPrompt(pack)}
              scenarioPacks={scenarioPacks}
            />
          </details>

          <details className="advancedDetails homeProductIntelligenceDetails">
            <summary>{biText("查看数据质量和语义建议", "Review data quality and semantic suggestions")}</summary>
            <HomeProductIntelligencePanel
              askMetricRepairReason={askMetricRepairReason}
              busy={busy}
              liveFailedMetricSamples={liveFailedMetricSamples}
              liveMetricBlocked={liveMetricBlocked}
              liveMetricExecutable={liveMetricExecutable}
              liveMetricPlanned={liveMetricPlanned}
              liveMetricRate={liveMetricRate}
              liveMissingSemantics={liveMissingSemantics}
              liveQualityDoctor={liveQualityDoctor}
              liveQualityIssues={liveQualityIssues}
              liveRepairDraft={liveRepairDraft}
              liveScore={liveScore}
              liveSummary={liveSummary}
              liveTone={liveTone}
              metricRepairPlan={metricRepairPlan}
              onOpenSection={onOpenSection}
              onSetSemantic={onSetSemantic}
              onSourceIntelligenceRun={onSourceIntelligenceRun}
              qualityDoctor={qualityDoctor}
              sandboxComparison={sandboxComparison}
              workbench={workbench}
            />
          </details>
        </>
      ) : null}

      {hasData ? (
        <details className="advancedDetails homeSecondaryDetails" data-testid="home-secondary-path-details">
          <summary>{biText("查看工作区路径和后续动作", "View workspace path and next actions")}</summary>
          <HomeWorkspaceStartGuide guideSteps={guideSteps} onOpenSection={onOpenSection} readiness={readiness} />
        </details>
      ) : null}

      {hasData ? (
        <details className="advancedDetails homeSecondaryDetails" data-testid="home-detailed-path-details">
          <summary>{biText("查看数据到看板的完整路径", "View full data-to-dashboard path")}</summary>
          <HomeDetailedPathPanel
            agentRequiresConfirmation={agent.requiresConfirmation}
            busy={busy}
            dashboardPlan={dashboardPlan}
            dashboardPlanKey={dashboardPlanKey}
            dashboardPlanNeedsConfirmation={dashboardPlanNeedsConfirmation}
            dashboardPlanTable={dashboardPlanTable}
            dashboardPlanTitle={dashboardPlanTitle}
            dashboardPlanWidgetCount={dashboardPlanWidgetCount}
            mainTable={mainTable}
            onAsk={onAsk}
            onOpenSection={onOpenSection}
            onSourceIntelligenceRun={onSourceIntelligenceRun}
            runBusy={runBusy}
            runDashboardTemplate={runDashboardTemplate}
          />
        </details>
      ) : null}

      {hasData ? (
        <details className="advancedDetails homeSecondaryDetails" data-testid="home-operating-summary-details">
          <summary>{biText("查看运营摘要和快捷问题", "View operating summary and quick questions")}</summary>
          <HomeOperatingSummaryPanel
            busy={busy}
            latestDashboardDraft={latestDashboardDraft}
            latestRun={latestRun}
            onAsk={onAsk}
            onOpenSection={onOpenSection}
            onQuery={onQuery}
            runBusy={runBusy}
            topRow={topRow}
            topValue={topValue}
          />
        </details>
      ) : null}
    </section>
  );
}
