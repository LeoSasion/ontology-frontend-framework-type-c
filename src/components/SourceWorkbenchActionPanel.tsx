import type { Dispatch, SetStateAction } from "react";
import type { SourceIntelligenceRunSummary } from "../types";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import { SourceWorkbenchAgentStarter, type SourceAgentPrompt } from "./SourceWorkbenchAgentStarter";

type BeginnerPlanItem = {
  key: string;
  state: string;
  title: string;
  detail: string;
};

type DashboardRecipeCard = {
  key: string;
  title: string;
  detail: string;
  state: string;
};

type RecommendedPrimaryAction = "check-file" | "import-data" | "refresh-profile" | "draft-dashboard";

type SourceWorkbenchActionPanelProps = {
  busy: string | null;
  recommendedPrimaryAction: RecommendedPrimaryAction;
  beginnerPlan: BeginnerPlanItem[];
  sourceProfileRunning: boolean;
  sourceProfileComplete: boolean;
  latestSourceProfile?: SourceIntelligenceRunSummary;
  relationshipsCount: number;
  selectedMetricsCount: number;
  dashboardRecipeReady: boolean;
  dashboardRecipeEvidenceCount: number;
  dashboardRecipeCards: DashboardRecipeCard[];
  businessDashboardResult: Record<string, unknown> | null;
  selectedTableKey: string;
  dashboardDimensionName: string;
  dashboardMeasureName: string;
  dashboardTimeName: string;
  indexCandidateName: string;
  showAdvanced: boolean;
  setShowAdvanced: Dispatch<SetStateAction<boolean>>;
  sourceAgentPrompts: SourceAgentPrompt[];
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  sourceProfileOptions: () => SourceIntelligenceRunOptions;
  runSourceProfile: (label: string, options: SourceIntelligenceRunOptions) => Promise<void>;
  runBusinessDashboard: (confirm: boolean) => Promise<void>;
  onAsk: (prompt: string) => Promise<void>;
  onOpenDashboard: () => void;
};

export function SourceWorkbenchActionPanel({
  busy,
  recommendedPrimaryAction,
  beginnerPlan,
  sourceProfileRunning,
  sourceProfileComplete,
  latestSourceProfile,
  relationshipsCount,
  selectedMetricsCount,
  dashboardRecipeReady,
  dashboardRecipeEvidenceCount,
  dashboardRecipeCards,
  businessDashboardResult,
  selectedTableKey,
  dashboardDimensionName,
  dashboardMeasureName,
  dashboardTimeName,
  indexCandidateName,
  showAdvanced,
  setShowAdvanced,
  sourceAgentPrompts,
  runBusy,
  sourceProfileOptions,
  runSourceProfile,
  runBusinessDashboard,
  onAsk,
  onOpenDashboard,
}: SourceWorkbenchActionPanelProps) {
  const currentPlanKey = recommendedPrimaryAction === "check-file"
    ? "file"
    : recommendedPrimaryAction === "import-data"
      ? "workspace"
      : recommendedPrimaryAction === "refresh-profile"
        ? "profile"
        : "";
  const currentPlan = beginnerPlan.find((item) => item.key === currentPlanKey);

  return (
    <article className="workbenchPanel simpleGuide" data-testid="beginner-import-plan">
      <div className="tileHeader">
        <h3><Bilingual zh="下一步建议" en="Next best action" /></h3>
        <span>{recommendedPrimaryAction === "draft-dashboard" ? biText("可生成", "Ready") : biText("需一步确认", "One step")}</span>
      </div>
      <div className="beginnerPlanLead">
        <strong>
          {recommendedPrimaryAction === "check-file"
            ? biText("先检查文件能不能回答业务问题", "Check whether the file can answer the question first")
            : recommendedPrimaryAction === "import-data"
              ? biText("预检已通过，下一步由你确认导入", "Preflight passed; you control the import")
              : recommendedPrimaryAction === "refresh-profile"
                ? biText("数据已在工作区，建议生成证据摘要", "Data is in the workspace; create the evidence summary")
                : biText("证据已就绪，下一步生成一个图表", "Evidence is ready; create one chart next")}
        </strong>
        <span>
          {biText("系统会把字段、关系、指标和公式放到后台推荐；你只需要按当前步骤继续。", "Fields, relationships, metrics, and formulas stay behind the recommendation layer; follow the current step.")}
        </span>
      </div>
      {currentPlan ? <div className="beginnerPlanList">
        {[currentPlan].map((item) => (
          <div className="beginnerPlanItem" data-testid={`beginner-plan-${item.key}`} key={item.key}>
            <span>{item.state}</span>
            <strong>{item.title}</strong>
            <small>{item.detail}</small>
          </div>
        ))}
      </div> : null}
      {!sourceProfileComplete ? <div className="beginnerActionGrid">
        <button
          className={recommendedPrimaryAction === "refresh-profile" ? "primaryButton compactAction" : "miniButton"}
          data-testid="beginner-plan-refresh-profile"
          disabled={sourceProfileRunning}
          onClick={() => runSourceProfile("source-intelligence", sourceProfileOptions())}
          type="button"
        >
          <Icon name="agent" />
          <Bilingual zh="更新画像" en="Refresh profile" />
        </button>
      </div> : null}
      <div className={sourceProfileComplete ? "beginnerImportGuard ok" : "beginnerImportGuard warn"} data-testid="beginner-evidence-guard">
        <Icon name={sourceProfileComplete ? "check" : "evidence"} />
        {!sourceProfileComplete ? <span>{biText("先生成证据摘要；字段、关系和指标缺口确认后再进入看板。", "Create the evidence summary first; review fields, links, and metric gaps before dashboarding.")}</span> : null}
        {sourceProfileComplete ? (
          <button className="primaryButton compactAction" data-testid="source-next-dashboard" onClick={onOpenDashboard} type="button">
            <Icon name="dashboard" />
            <Bilingual zh="去生成图表" en="Create a chart" />
          </button>
        ) : null}
      </div>
      <details className="sourceGuideDetails" data-testid="source-guide-details">
        <summary>{biText("更多引导和高级建议", "More guidance and advanced suggestions")}</summary>
      {sourceProfileComplete ? <button className="miniButton" data-testid="beginner-plan-refresh-profile" disabled={sourceProfileRunning} onClick={() => runSourceProfile("source-intelligence", sourceProfileOptions())} type="button">
        <Icon name="evidence" />
        <Bilingual zh="更新证据摘要" en="Refresh evidence" />
      </button> : null}
      <div className="importToDashboardWizard" data-testid="import-to-dashboard-wizard">
        <div className="wizardLead">
          <span className="storyMode"><Bilingual zh="导入到看板向导" en="Import-to-dashboard guide" /></span>
          <strong>{biText("只问三个业务问题，其余交给系统预演", "Ask three business questions; preview the rest")}</strong>
        </div>
        <div className="wizardQuestionGrid">
          <div>
            <span>1</span>
            <strong>{biText("这些文件是什么业务？", "What business do these files describe?")}</strong>
            <small>{biText("只识别当前字段和证据能够支持的业务主题。", "Only identify business topics supported by current fields and evidence.")}</small>
          </div>
          <div>
            <span>2</span>
            <strong>{biText("证据摘要是否完整？", "Is the evidence summary complete?")}</strong>
            <small>{sourceProfileComplete ? biText("已可进入看板配方。", "Ready for the dashboard recipe.") : biText("先生成证据再判断。", "Create evidence before deciding.")}</small>
          </div>
          <div>
            <span>3</span>
            <strong>{biText("先看什么问题？", "What should be answered first?")}</strong>
            <small>{dashboardRecipeReady ? biText("可直接预演看板。", "Dashboard preview is ready.") : biText("先生成证据摘要。", "Create evidence first.")}</small>
          </div>
        </div>
        <div className="wizardActions">
          <button className="miniButton" disabled={busy === "source-agent-import-guide"} onClick={() => runBusy("source-agent-import-guide", () => onAsk(biText(
            `帮我把 ${selectedTableKey} 从导入到看板梳理成三步：业务类型、合并方式、先看的指标。只生成计划和证据，不直接写入。`,
            `Turn ${selectedTableKey} from import to dashboard into three steps: business type, merge choice, and first metrics. Create only a plan and evidence, no writes.`,
          )))} type="button">
            <Icon name="agent" />
            <Bilingual zh="让 Agent 带路" en="Let Agent guide" />
          </button>
          <button className="miniButton" disabled={sourceProfileRunning} onClick={() => runSourceProfile("wizard-source-intelligence", sourceProfileOptions())} type="button">
            <Icon name="evidence" />
            <Bilingual zh="生成证据" en="Create evidence" />
          </button>
        </div>
      </div>
      <SourceWorkbenchAgentStarter
        busy={busy}
        sourceProfileComplete={sourceProfileComplete}
        sourceAgentPrompts={sourceAgentPrompts}
        runBusy={runBusy}
        onAsk={onAsk}
      />
      <div className="simpleNextAction" data-testid="source-dashboard-next-action">
        <strong>{biText("下一步：生成可编辑看板", "Next: create an editable dashboard")}</strong>
        <span>
          {sourceProfileComplete
            ? biText("证据摘要完整，可生成分析看板草案。", "The evidence summary is complete, so an analysis dashboard draft can be generated now.")
            : biText("建议先生成证据摘要，再生成看板。", "Create the evidence summary before generating a dashboard.")}
        </span>
        <div className={dashboardRecipeReady ? "sourceDashboardRecipe ready" : "sourceDashboardRecipe"} data-testid="source-dashboard-recipe">
          <div className="sourceDashboardRecipeHeader">
            <span className="storyMode">{biText("证据到看板配方", "Evidence-to-dashboard recipe")}</span>
            <strong>
              {dashboardRecipeReady
                ? biText("系统已选好默认组件，先预演再确认", "Default widgets are selected; preview before confirmation")
                : biText("先补画像或字段语义，再生成看板", "Refresh profiling or field semantics before dashboarding")}
            </strong>
          </div>
          <div className="sourceDashboardRecipeFacts" data-testid="source-dashboard-recipe-facts">
            <span>{latestSourceProfile ? `${latestSourceProfile.source_count} ${biText("文件", "files")}` : biText("等待画像", "waiting profile")}</span>
            <span>{latestSourceProfile ? `${latestSourceProfile.relationship_count} ${biText("关系", "relations")}` : `${relationshipsCount} ${biText("已存关系", "saved relations")}`}</span>
            <span>{latestSourceProfile ? biText(`${latestSourceProfile.metric_sql_plan_count} 个候选问题中 ${latestSourceProfile.metric_sql_executable_count} 个可执行`, `${latestSourceProfile.metric_sql_executable_count} of ${latestSourceProfile.metric_sql_plan_count} candidate questions executable`) : `${selectedMetricsCount} ${biText("指标", "metrics")}`}</span>
            <span>{dashboardRecipeEvidenceCount} {biText("证据", "evidence")}</span>
          </div>
          <div className="sourceDashboardRecipeCards" data-testid="source-dashboard-recipe-cards">
            {dashboardRecipeCards.map((card) => (
              <div className="sourceDashboardRecipeCard" key={card.key}>
                <span>{card.state}</span>
                <strong>{card.title}</strong>
                <small>{card.detail}</small>
              </div>
            ))}
          </div>
        </div>
        <div className="buttonRow tight">
          <button
            className="miniButton"
            data-testid="source-business-dashboard-preview"
            disabled={!dashboardRecipeReady || busy === "source-business-dashboard-preview"}
            onClick={() => runBusy("source-business-dashboard-preview", () => runBusinessDashboard(false))}
            type="button"
          >
            {biText("预演看板", "Preview dashboard")}
          </button>
          <button
            className="primaryButton compactAction"
            data-testid="source-business-dashboard-create"
            disabled={!dashboardRecipeReady || busy === "source-business-dashboard-create"}
            onClick={() => runBusy("source-business-dashboard-create", () => runBusinessDashboard(true))}
            type="button"
          >
            <Icon name="dashboard" />
            <Bilingual zh="生成并打开" en="Create and open" />
          </button>
          <button
            className="miniButton"
            data-testid="source-dashboard-agent-draft"
            disabled={!dashboardRecipeReady || busy === "source-dashboard-agent-draft"}
            onClick={() => runBusy("source-dashboard-agent-draft", () => onAsk(biText(
              `基于 ${selectedTableKey} 和当前证据摘要起草一个分析看板，优先使用 ${dashboardDimensionName}、${dashboardMeasureName}${dashboardTimeName ? `、${dashboardTimeName}` : ""}，说明组件和证据，先不要直接写入`,
              `Draft a business dashboard from ${selectedTableKey} and the current evidence summary, prefer ${dashboardDimensionName}, ${dashboardMeasureName}${dashboardTimeName ? `, ${dashboardTimeName}` : ""}, explain widgets and evidence, and do not write directly`,
            )))}
            type="button"
          >
            <Icon name="agent" />
            <Bilingual zh="让 Agent 起草" en="Ask Agent to draft" />
          </button>
        </div>
        {businessDashboardResult ? (
          <div className="simpleActionResult" data-testid="source-business-dashboard-result">
            <span>
              {businessDashboardResult.draft
                ? biText("已生成预演，确认后才会写入。", "Preview ready; confirmation is required before writing.")
                : biText("看板已生成，可继续编辑组件。", "Dashboard generated and ready to edit.")}
            </span>
            <strong>
              {String(businessDashboardResult.createdDashboardKey ?? businessDashboardResult.savedDashboardKey ?? (businessDashboardResult.templateCount ? `${businessDashboardResult.templateCount} ${biText("个组件", "widgets")}` : "-"))}
            </strong>
          </div>
        ) : null}
      </div>
      <div className="sourceIndexSuggestion" data-testid="source-index-suggestion">
        <strong>{biText("查询变慢时：让 Agent 起草索引", "If queries slow down: ask Agent to draft an index")}</strong>
        <span>
          {indexCandidateName
            ? biText(`当前表可先考虑 ${indexCandidateName}。Agent 只会生成索引草案，确认前不会创建 DuckDB 索引。`, `For this table, start with ${indexCandidateName}. The Agent only creates an index draft; no DuckDB index is created before confirmation.`)
            : biText("当前表还没有可推荐字段；先更新画像或字段语义。", "No field can be recommended yet; refresh profiling or field semantics first.")}
        </span>
        <div className="sourceIndexFacts">
          <span>{selectedTableKey}</span>
          <span>{indexCandidateName || biText("等待字段", "waiting for field")}</span>
          <span>{biText("草案确认制", "draft approval")}</span>
        </div>
        <button
          className="miniButton"
          data-testid="source-index-agent-draft"
          disabled={!indexCandidateName || busy === "index-agent-draft"}
          onClick={() => runBusy("index-agent-draft", () => onAsk(biText(`给 ${selectedTableKey} 的 ${indexCandidateName} 建索引来优化查询`, `Create an index draft for ${selectedTableKey}.${indexCandidateName} to optimize queries`)))}
          type="button"
        >
          <Icon name="agent" />
          <Bilingual zh="让 Agent 起草索引" en="Ask Agent to draft index" />
        </button>
      </div>
      </details>
      <button className="secondaryButton fullWidthButton" data-testid="source-expert-toggle" onClick={() => setShowAdvanced((current) => !current)} type="button">
        {showAdvanced ? biText("收起数据模型与管理", "Hide data model and management") : biText("数据模型与管理", "Data model and management")}
      </button>
    </article>
  );
}
