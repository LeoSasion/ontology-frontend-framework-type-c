import type { Dispatch, SetStateAction } from "react";
import type { SourceIntelligenceRunSummary } from "../types";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import type { BeginnerPlanItem, RecommendedPrimaryAction } from "../sourceWorkbenchGuidanceModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type SourceWorkbenchActionPanelProps = {
  recommendedPrimaryAction: RecommendedPrimaryAction;
  beginnerPlan: BeginnerPlanItem[];
  sourceProfileRunning: boolean;
  sourceProfileAvailable: boolean;
  sourceProfileComplete: boolean;
  latestSourceProfile?: SourceIntelligenceRunSummary;
  showAdvanced: boolean;
  setShowAdvanced: Dispatch<SetStateAction<boolean>>;
  sourceProfileOptions: () => SourceIntelligenceRunOptions;
  runSourceProfile: (label: string, options: SourceIntelligenceRunOptions) => Promise<void>;
  onOpenAnalysis: () => void;
};

function recommendationCopy(action: RecommendedPrimaryAction) {
  if (action === "check-file") {
    return {
      title: biText("先检查一个数据来源", "Check one data source first"),
      detail: biText("在左侧输入文件或文件夹路径；系统会自动识别来源类型。", "Enter a file or folder path on the left; the system detects the source type."),
    };
  }
  if (action === "import-data") {
    return {
      title: biText("预检完成，等待你确认导入", "Preflight is ready for your confirmation"),
      detail: biText("核对新增、更新和跳过行数，再执行唯一一次写入确认。", "Review inserted, updated, and skipped rows before the single write confirmation."),
    };
  }
  if (action === "refresh-profile") {
    return {
      title: biText("生成证据摘要", "Prepare the evidence summary"),
      detail: biText("系统会检查字段、关系和可执行口径；不确定项会明确阻断。", "The system checks fields, relationships, and executable definitions, and blocks unresolved items."),
    };
  }
  return {
    title: biText("数据已经可以用于分析", "The data is ready for analysis"),
    detail: biText("下一步只描述一个问题或图表；高级建模继续保持收起。", "Next, describe one question or chart. Advanced modeling stays collapsed."),
  };
}

export function SourceWorkbenchActionPanel(props: SourceWorkbenchActionPanelProps) {
  const {
    recommendedPrimaryAction,
    beginnerPlan,
    sourceProfileRunning,
    sourceProfileAvailable,
    sourceProfileComplete,
    latestSourceProfile,
    showAdvanced,
    setShowAdvanced,
    sourceProfileOptions,
    runSourceProfile,
    onOpenAnalysis,
  } = props;
  const recommendation = recommendationCopy(recommendedPrimaryAction);
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
        <h3><Bilingual zh="下一步" en="Next step" /></h3>
        <span>{sourceProfileComplete
          ? biText("可分析", "Ready")
          : sourceProfileAvailable
            ? biText("可分析 · 建议更新", "Ready · refresh suggested")
            : biText("需准备", "Prepare")}</span>
      </div>

      <div className="beginnerPlanLead">
        <strong>{recommendation.title}</strong>
        <span>{recommendation.detail}</span>
      </div>

      {currentPlan ? (
        <div className="beginnerPlanList">
          <div className="beginnerPlanItem" data-testid={`beginner-plan-${currentPlan.key}`}>
            <span>{currentPlan.state}</span>
            <strong>{currentPlan.title}</strong>
            <small>{currentPlan.detail}</small>
          </div>
        </div>
      ) : null}

      {recommendedPrimaryAction === "refresh-profile" ? (
        <button
          className="primaryButton compactAction sourcePrimaryNext"
          data-testid="beginner-plan-refresh-profile"
          disabled={sourceProfileRunning}
          onClick={() => runSourceProfile("source-intelligence", sourceProfileOptions())}
          type="button"
        >
          <Icon name="evidence" />
          {sourceProfileRunning ? biText("正在生成…", "Preparing…") : biText("生成证据摘要", "Prepare evidence")}
        </button>
      ) : null}

      {sourceProfileAvailable ? (
        <button className="primaryButton compactAction sourcePrimaryNext" data-testid="source-next-analysis" onClick={onOpenAnalysis} type="button">
          <Icon name="agent" />
          <Bilingual zh="开始分析" en="Start analysis" />
        </button>
      ) : null}

      <div className={sourceProfileAvailable ? "beginnerImportGuard ok" : "beginnerImportGuard warn"} data-testid="beginner-evidence-guard">
        <Icon name={sourceProfileAvailable ? "check" : "evidence"} />
        <span>
          {sourceProfileComplete
            ? biText(
              `证据摘要完整${latestSourceProfile ? ` · ${latestSourceProfile.metric_sql_executable_count}/${latestSourceProfile.metric_sql_plan_count} 个候选问题可执行` : ""}`,
              `Evidence is complete${latestSourceProfile ? ` · ${latestSourceProfile.metric_sql_executable_count}/${latestSourceProfile.metric_sql_plan_count} candidate questions executable` : ""}`,
            )
            : sourceProfileAvailable
              ? biText(
                `当前证据可用于分析${latestSourceProfile ? ` · ${latestSourceProfile.metric_sql_executable_count}/${latestSourceProfile.metric_sql_plan_count} 个候选问题可执行` : ""}；文件覆盖不完整，可按需更新。`,
                `Current evidence can be analyzed${latestSourceProfile ? ` · ${latestSourceProfile.metric_sql_executable_count}/${latestSourceProfile.metric_sql_plan_count} candidate questions executable` : ""}; file coverage is incomplete, so refresh when needed.`,
              )
            : biText("生成证据摘要后再进入分析与看板。", "Prepare evidence before analysis and dashboards.")}
        </span>
      </div>

      {sourceProfileAvailable ? (
        <details className="sourceGuideDetails" data-testid="source-guide-details">
          <summary>{biText("其他数据动作", "Other data actions")}</summary>
          <div className="sourceGuideCompactActions">
            <button className="miniButton" data-testid="beginner-plan-refresh-profile-secondary" disabled={sourceProfileRunning} onClick={() => runSourceProfile("source-intelligence", sourceProfileOptions())} type="button">
              <Icon name="evidence" />
              <Bilingual zh="更新证据摘要" en="Refresh evidence" />
            </button>
          </div>
        </details>
      ) : null}

      <button className="secondaryButton fullWidthButton" data-testid="source-expert-toggle" onClick={() => setShowAdvanced((current) => !current)} type="button">
        {showAdvanced ? biText("收起数据模型与管理", "Hide data model and management") : biText("数据模型与管理", "Data model and management")}
      </button>
    </article>
  );
}
