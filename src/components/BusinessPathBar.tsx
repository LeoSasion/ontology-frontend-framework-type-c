import { businessPathSteps, businessStepForSection, type BusinessPathStep, type BusinessPathStepKey } from "../businessPathModel";
import { isBusinessStepLockedByFlow, type WorkspaceFlowModel } from "../workspaceFlowModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type BusinessPathBarProps = {
  activeSection: AppSection;
  flow: WorkspaceFlowModel;
  onOpenStep: (step: BusinessPathStepKey) => void;
};

function stepDetail(step: BusinessPathStep, flow: WorkspaceFlowModel) {
  if (step.key === "data") {
    return flow.counts.tableCount
      ? biText(`${flow.counts.tableCount} 张表可用`, `${flow.counts.tableCount} tables ready`)
      : biText("先预检文件或文件夹", "Preview files or folders first");
  }
  if (step.key === "chart") {
    return flow.counts.dashboardCount
      ? biText(`${flow.counts.dashboardCount} 个看板可继续`, `${flow.counts.dashboardCount} dashboards available`)
      : biText("说出想看的单个图表", "Describe one chart to create");
  }
  if (step.key === "evidence") {
    const receiptCount = flow.counts.sourceProfileCount;
    return receiptCount
      ? biText(`${receiptCount} 条运行回执`, `${receiptCount} run receipts`)
      : biText("查看来源、口径和缺口", "Trace sources, definitions, and gaps");
  }
  return flow.counts.pendingDraftCount
    ? biText(`${flow.counts.pendingDraftCount} 个草案待处理`, `${flow.counts.pendingDraftCount} drafts pending`)
    : biText("写入前在这里停住", "Writes stop here first");
}

export function BusinessPathBar({ activeSection, flow, onOpenStep }: BusinessPathBarProps) {
  const visibleSteps = flow.hasPendingDraft
    ? businessPathSteps
    : businessPathSteps.filter((step) => step.key !== "confirm");
  const activeStepKey = businessStepForSection(activeSection);
  const resolvedActiveStepKey = activeStepKey && visibleSteps.some((step) => step.key === activeStepKey)
    ? activeStepKey
    : flow.nextStep;
  const activeIndex = visibleSteps.findIndex((step) => step.key === resolvedActiveStepKey);
  const compact = activeSection !== "home";
  const mobileStepIndex = activeIndex >= 0 ? activeIndex : 0;
  const mobileStep = visibleSteps[mobileStepIndex];

  function stepIsLocked(step: BusinessPathStep) {
    return isBusinessStepLockedByFlow(step.key, flow);
  }

  function stepState(step: BusinessPathStep, index: number, forceActive = false) {
    if (forceActive || step.key === resolvedActiveStepKey) return "active";
    if (activeIndex > index) return "complete";
    return "";
  }

  function renderStepContent(step: BusinessPathStep, index: number, state: string, locked: boolean) {
    const actionCopy = locked
      ? { zh: step.key === "chart" ? "先生成证据" : "先完成上一步", en: step.key === "chart" ? "Profile data first" : "Finish previous step" }
      : state === "active"
      ? { zh: "当前步骤", en: "Current" }
      : { zh: step.actionZh, en: step.actionEn };
    const detailCopy = locked
      ? step.key === "chart"
        ? biText("生成证据摘要后可用", "Available after evidence summary")
        : biText("有真实回执后可用", "Available after real receipts")
      : stepDetail(step, flow);

    return (
      <>
        <span className="businessPathIndex">{index + 1}</span>
        <span className="businessPathIcon"><Icon name={step.icon} /></span>
        <span className="businessPathText">
          <strong><Bilingual zh={step.zh} en={step.en} /></strong>
          <small>{detailCopy}</small>
        </span>
        <em><Bilingual zh={actionCopy.zh} en={actionCopy.en} /></em>
      </>
    );
  }

  function renderStepButton(step: BusinessPathStep, index: number, forceActive = false) {
    const state = stepState(step, index, forceActive);
    const locked = stepIsLocked(step);
    const classes = ["businessPathStep"];
    if (state) classes.push(state);
    if (locked) classes.push("locked");
    return (
      <button
        aria-current={state === "active" ? "step" : undefined}
        aria-label={locked ? biText(`${step.zh}，先完成上一步`, `${step.en}, finish previous step first`) : undefined}
        className={classes.join(" ")}
        data-testid={`business-path-${step.key}`}
        onClick={() => onOpenStep(locked ? flow.nextStep : step.key)}
        title={locked ? biText("先完成当前必要步骤", "Finish the current required step first") : undefined}
        type="button"
      >
        {renderStepContent(step, index, state, locked)}
      </button>
    );
  }

  const mobileStepState = stepState(mobileStep, mobileStepIndex, activeIndex < 0) || "active";
  const mobileStepLocked = stepIsLocked(mobileStep);

  return (
    <nav className={compact ? "businessPathBar compact" : "businessPathBar"} data-testid="global-business-path" aria-label={biText("全局业务路径", "Global business path")}>
      <div className="businessPathLead">
        <strong><Bilingual zh="业务路径唯一" en="One business path" /></strong>
        <span><Bilingual zh="每一步跳到唯一页面处理" en="Each step opens its owning page" /></span>
      </div>
      <div className="businessPathMobileCurrent">
        <div
          aria-current="step"
          className={`businessPathStep ${mobileStepState}${mobileStepLocked ? " locked" : ""}`}
          data-testid={`business-path-mobile-${mobileStep.key}`}
        >
          {renderStepContent(mobileStep, mobileStepIndex, mobileStepState, mobileStepLocked)}
        </div>
      </div>
      <ol className="businessPathSteps">
        {visibleSteps.map((step, index) => (
          <li key={step.key}>
            {renderStepButton(step, index)}
          </li>
        ))}
      </ol>
    </nav>
  );
}
