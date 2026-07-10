import { getAppSection } from "../appSections";
import type { ActionDraft } from "../types";
import { actionKindLabel, actionNextStep, actionResultSummary, payloadTarget } from "../inspectorPanelModel";
import { Bilingual, biText, translateName } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type InspectorTaskQueuePanelProps = {
  actionDrafts: ActionDraft[];
  actionQueueDisabled: boolean;
  activeSection: AppSection;
  lastActionResult: Record<string, unknown> | null;
  onOpenAgent: () => void;
  onOpenSection: (section: AppSection) => void;
};

export function InspectorTaskQueuePanel({
  actionDrafts,
  actionQueueDisabled,
  activeSection,
  lastActionResult,
  onOpenAgent,
  onOpenSection,
}: InspectorTaskQueuePanelProps) {
  const pendingDrafts = actionQueueDisabled ? [] : actionDrafts.filter((draft) => draft.status === "draft");
  const latestSummary = actionResultSummary(lastActionResult);
  const recoverySection = latestSummary?.targetSection ? getAppSection(latestSummary.targetSection) : null;

  return (
    <section className="actionQueue" data-testid="action-queue">
      <div className="inspectorSectionHeader">
        <div>
          <span className="eyebrow">{biText("待确认草案", "Pending drafts")}</span>
          <h2>{pendingDrafts.length ? biText(`${pendingDrafts.length} 个待确认`, `${pendingDrafts.length} pending`) : biText("没有待确认任务", "No pending tasks")}</h2>
        </div>
        <button className="miniButton" onClick={onOpenAgent} type="button">
          <Icon name="agent" />
          {biText("去确认", "Review")}
        </button>
      </div>
      {actionQueueDisabled ? (
        <div className="emptyTaskQueue">
          <strong><Bilingual zh="正在连接本地服务" en="Connecting to local service" /></strong>
          <p><Bilingual zh="连接完成后可在 AI 助手中统一预演、确认或拒绝草案。" en="Once connected, preview, confirm, or reject drafts in the AI assistant." /></p>
        </div>
      ) : pendingDrafts.length ? (
        <ul className="draftList taskQueueList">
          {pendingDrafts.slice(0, 4).map((draft) => {
            const target = payloadTarget(draft);
            const actionLabel = actionKindLabel(draft.kind);
            return (
              <li className="taskQueueItem" data-testid="action-queue-item" key={draft.action_key}>
                <div className="taskQueueTopline">
                  <span className="taskKind"><Bilingual {...actionLabel} /></span>
                  <span>{biText("等待 AI 处理", "Review in AI")}</span>
                </div>
                <strong><Bilingual {...translateName(draft.label)} /></strong>
                <p><Bilingual {...target} /></p>
                <small className="taskNextStep" data-testid="action-queue-next-step">{actionNextStep(draft)}</small>
                <details className="taskEvidenceRow" data-testid={`action-queue-technical-${draft.action_key}`}>
                  <summary>{biText("查看证据和编号", "View evidence and id")}</summary>
                  <span>{biText(`${draft.evidence.length} 条证据线索`, `${draft.evidence.length} evidence items`)}</span>
                  <span>{actionLabel.en}: {draft.kind}</span>
                  <span>{draft.action_key}</span>
                </details>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="emptyTaskQueue">
          <strong><Bilingual zh="暂无需要处理的草案" en="No drafts need review" /></strong>
          <p><Bilingual zh="导入、覆盖、关系保存和看板修改会在这里等待确认。" en="Imports, overwrites, relationship saves, and dashboard edits wait here for approval." /></p>
        </div>
      )}
      {latestSummary ? (
        <div className={`visibleActionSummary ${latestSummary.tone}`} data-testid="last-action-summary">
          <Icon name="evidence" />
          <div className="visibleActionSummaryBody">
            <strong><Bilingual {...latestSummary.title} /></strong>
            <span><Bilingual {...latestSummary.detail} /></span>
            {latestSummary.safeState ? <small className="visibleActionSafeState"><Bilingual {...latestSummary.safeState} /></small> : null}
            {latestSummary.next ? <small><Bilingual {...latestSummary.next} /></small> : null}
            {latestSummary.steps?.length ? (
              <ol className="visibleActionRecoverySteps" data-testid="last-action-recovery-steps">
                {latestSummary.steps.map((step) => <li key={`${step.zh}-${step.en}`}><Bilingual {...step} /></li>)}
              </ol>
            ) : null}
            {latestSummary.targetSection && recoverySection && latestSummary.targetSection !== activeSection ? (
              <button className="visibleActionRecoveryAction" data-testid="last-action-recovery-open-section" onClick={() => onOpenSection(latestSummary.targetSection!)} type="button">
                <Icon name={recoverySection.icon} />
                <Bilingual zh={`去${recoverySection.shortZh}`} en={`Open ${recoverySection.shortEn}`} />
              </button>
            ) : null}
            {latestSummary.technical ? (
              <details className="visibleActionTechnical" data-testid="last-action-technical">
                <summary>{biText("查看错误原文", "View raw error")}</summary>
                <span>{latestSummary.technical}</span>
              </details>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
