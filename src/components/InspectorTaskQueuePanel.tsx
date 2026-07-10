import { useState } from "react";
import { getAppSection } from "../appSections";
import type { ActionDraft } from "../types";
import { actionKindLabel, actionNextStep, actionResultSummary, payloadTarget } from "../inspectorPanelModel";
import { Bilingual, biText, translateName, translateStatus } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type InspectorTaskQueuePanelProps = {
  actionDrafts: ActionDraft[];
  actionQueueDisabled: boolean;
  activeSection: AppSection;
  lastActionResult: Record<string, unknown> | null;
  onConfirmAction: (actionKey: string) => Promise<void>;
  onConfirmDryRun: (actionKey: string) => Promise<void>;
  onOpenAgent: () => void;
  onOpenSection: (section: AppSection) => void;
  onRejectAction: (actionKey: string) => Promise<void>;
};

export function InspectorTaskQueuePanel({
  actionDrafts,
  actionQueueDisabled,
  activeSection,
  lastActionResult,
  onConfirmAction,
  onConfirmDryRun,
  onOpenAgent,
  onOpenSection,
  onRejectAction,
}: InspectorTaskQueuePanelProps) {
  const [busyAction, setBusyAction] = useState("");
  const pendingDrafts = actionQueueDisabled ? [] : actionDrafts.filter((draft) => draft.status === "draft");
  const latestSummary = actionResultSummary(lastActionResult);
  const recoverySection = latestSummary?.targetSection ? getAppSection(latestSummary.targetSection) : null;

  async function runAction(actionKey: string, task: () => Promise<void>) {
    setBusyAction(actionKey);
    try {
      await task();
    } finally {
      setBusyAction("");
    }
  }

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
          <p><Bilingual zh="确认、拒绝和预演只会在真实 API 连接后启用，避免误操作未同步的草案。" en="Preview, confirm, and reject are enabled only after the live API is connected, so unsynced drafts cannot be acted on." /></p>
        </div>
      ) : pendingDrafts.length ? (
        <ul className="draftList taskQueueList">
          {pendingDrafts.slice(0, 4).map((draft) => {
            const target = payloadTarget(draft);
            const actionLabel = actionKindLabel(draft.kind);
            const isBusy = busyAction === draft.action_key;
            return (
              <li className="taskQueueItem" data-testid="action-queue-item" key={draft.action_key}>
                <div className="taskQueueTopline">
                  <span className="taskKind"><Bilingual {...actionLabel} /></span>
                  <span>{biText(translateStatus(draft.status).zh, translateStatus(draft.status).en)}</span>
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
                <div className="taskQueueActions">
                  <button className="miniButton" data-testid={`action-preview-${draft.action_key}`} disabled={isBusy || actionQueueDisabled} onClick={() => runAction(draft.action_key, () => onConfirmDryRun(draft.action_key))} type="button">
                    <Icon name="evidence" />
                    {biText("预演", "Preview")}
                  </button>
                  <button className="primaryButton compactAction" data-testid={`action-confirm-${draft.action_key}`} disabled={isBusy || actionQueueDisabled} onClick={() => runAction(draft.action_key, () => onConfirmAction(draft.action_key))} type="button">
                    <Icon name="check" />
                    {biText("确认", "Confirm")}
                  </button>
                  <button className="miniButton dangerButton" data-testid={`action-reject-${draft.action_key}`} disabled={isBusy || actionQueueDisabled} onClick={() => runAction(draft.action_key, () => onRejectAction(draft.action_key))} type="button">
                    <Icon name="close" />
                    {biText("拒绝", "Reject")}
                  </button>
                </div>
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
