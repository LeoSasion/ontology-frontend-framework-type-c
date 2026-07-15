import type { ActionDraft } from "../types";
import {
  actionEvidenceChips,
  actionKindText,
  actionNextStepText,
  actionResultDetail,
  actionResultHeadline,
} from "../agentPanelModel";
import { Bilingual, biText } from "./Bilingual";

type DraftImpactItem = {
  key: string;
  label: string;
  count: number;
  detail: string;
};

type AgentPendingChangesPanelProps = {
  activeActionKey: string;
  activeActionKind: string;
  activeActionResult: Record<string, unknown> | null;
  canConfirmCurrent: boolean;
  currentDraft?: ActionDraft;
  currentDraftBusinessSummary: string;
  draftImpactItems: DraftImpactItem[];
  pendingDrafts: ActionDraft[];
  riskyDraftCount: number;
  runningActionKey: string | null;
  resolveDraftTarget: (draft: ActionDraft) => string;
  onConfirmDryRun: (actionKey: string) => Promise<void>;
  onConfirmAction: (actionKey: string, draft?: ActionDraft) => Promise<void>;
  onRejectAction: (actionKey: string) => Promise<void>;
  onRunAction: (actionKey: string, task: () => Promise<void>) => Promise<void>;
};

export function AgentPendingChangesPanel({
  activeActionKey,
  activeActionKind,
  activeActionResult,
  canConfirmCurrent,
  currentDraft,
  currentDraftBusinessSummary,
  draftImpactItems,
  pendingDrafts,
  riskyDraftCount,
  runningActionKey,
  resolveDraftTarget,
  onConfirmDryRun,
  onConfirmAction,
  onRejectAction,
  onRunAction,
}: AgentPendingChangesPanelProps) {
  const otherDrafts = pendingDrafts.filter((draft) => draft.action_key !== activeActionKey);
  return (
    <article className="wideArticle agentApprovalPanel">
      <div className="tileHeader">
        <h3><Bilingual zh="待确认修改" en="Pending changes" /></h3>
        <span>{pendingDrafts.length ? biText(`${pendingDrafts.length} 个待确认`, `${pendingDrafts.length} pending`) : biText("无待确认写入", "no pending writes")}</span>
      </div>
      <div className="actionDraft">
        <div>
          <strong>{actionKindText(activeActionKind)}</strong>
          <span>{currentDraft ? resolveDraftTarget(currentDraft) : biText("只读回答，无需确认", "Read-only answer, no approval needed")}</span>
          {currentDraftBusinessSummary ? <small className="agentDraftBusinessSummary" data-testid="agent-current-draft-summary">{currentDraftBusinessSummary}</small> : null}
          <small className="agentActionNextStep" data-testid="agent-current-draft-next-step">{actionNextStepText(currentDraft)}</small>
        </div>
        {canConfirmCurrent ? (
          <div className="buttonRow agentDraftStickyActions">
            <button className="secondaryButton" data-testid="agent-current-draft-preview" onClick={() => onConfirmDryRun(activeActionKey)} type="button">
              {biText("预演", "Preview")}
            </button>
            <button
              className="primaryButton"
              data-testid="agent-current-draft-confirm"
              disabled={runningActionKey === activeActionKey}
              onClick={async () => {
                await onRunAction(activeActionKey, () => onConfirmAction(activeActionKey, currentDraft));
              }}
              type="button"
            >
              {biText("确认", "Confirm")}
            </button>
            <button
              className="secondaryButton dangerButton"
              data-testid="agent-current-draft-reject"
              disabled={runningActionKey === activeActionKey}
              onClick={async () => {
                await onRunAction(activeActionKey, () => onRejectAction(activeActionKey));
              }}
              type="button"
            >
              {biText("拒绝", "Reject")}
            </button>
          </div>
        ) : (
          <span className="readOnlyDraftNote" data-testid="agent-current-draft-readonly">
            <Bilingual zh="只读计划，无需确认" en="Read-only plan, no approval needed" />
          </span>
        )}
      </div>
      <div className="agentDraftImpactSummary" data-testid="agent-draft-impact-summary">
        <div className="agentDraftImpactLead">
          <strong>{pendingDrafts.length ? biText("先看影响，再确认动作", "Review impact before approval") : biText("当前没有待确认写入", "No pending write approvals")}</strong>
          <span>
            {pendingDrafts.length
              ? biText(`${pendingDrafts.length} 个修改待处理，其中 ${riskyDraftCount} 个涉及数据写入或删除风险。`, `${pendingDrafts.length} changes are pending; ${riskyDraftCount} involve data writes or delete risk.`)
              : biText("Agent 的只读回答不会改动数据、看板或模型。", "Read-only Agent answers do not change data, dashboards, or models.")}
          </span>
        </div>
        <div className="agentDraftImpactGrid" data-testid="agent-draft-impact-grid">
          {draftImpactItems.map((item) => (
            <div className={item.count ? "active" : ""} data-testid={`agent-draft-impact-${item.key}`} key={item.key}>
              <strong>{item.count}</strong>
              <span>{item.label}</span>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
      </div>
      {activeActionResult ? (
        <div className={`agentActionResult ${activeActionResult.confirmed === true ? "confirmed" : activeActionResult.ok === false ? "failed" : "preview"}`} data-testid="agent-action-result">
          <strong data-testid="agent-action-result-headline">{actionResultHeadline(activeActionResult)}</strong>
          <span data-testid="agent-action-result-detail">{actionResultDetail(activeActionResult, currentDraft)}</span>
        </div>
      ) : null}
      {otherDrafts.length ? <details className="agentDraftQueue" data-testid="agent-draft-queue">
        <summary>{biText(`其他 ${otherDrafts.length} 个待处理修改`, `${otherDrafts.length} other pending changes`)}</summary>
        {otherDrafts.map((draft) => (
          <div className="agentDraftQueueItem" data-testid="agent-draft-queue-item" key={draft.action_key}>
            <div>
              <strong>{actionKindText(draft.kind)}</strong>
              <span>{resolveDraftTarget(draft)}</span>
              <small>{actionNextStepText(draft)}</small>
              <details className="agentDraftQueueTechnical" data-testid={`agent-draft-queue-technical-${draft.action_key}`}>
                <summary>{biText("查看证据和编号", "View evidence and id")}</summary>
                <div>
                  {actionEvidenceChips(draft).map((chip) => <span key={chip}>{chip}</span>)}
                </div>
                <code>{draft.kind}</code>
                <code>{draft.action_key}</code>
              </details>
            </div>
            <div className="buttonRow">
              <button className="secondaryButton" data-testid={`agent-draft-preview-${draft.action_key}`} disabled={runningActionKey === draft.action_key} onClick={() => onConfirmDryRun(draft.action_key)} type="button">
                {biText("预演", "Preview")}
              </button>
              <button className="primaryButton" data-testid={`agent-draft-confirm-${draft.action_key}`} disabled={runningActionKey === draft.action_key} onClick={() => onRunAction(draft.action_key, () => onConfirmAction(draft.action_key, draft))} type="button">
                {biText("确认", "Confirm")}
              </button>
              <button className="secondaryButton dangerButton" data-testid={`agent-draft-reject-${draft.action_key}`} disabled={runningActionKey === draft.action_key} onClick={() => onRunAction(draft.action_key, () => onRejectAction(draft.action_key))} type="button">
                {biText("拒绝", "Reject")}
              </button>
            </div>
          </div>
        ))}
      </details> : null}
      <details className="advancedDetails compactAdvanced agentActionTechnical" data-testid="agent-action-technical-details">
        <summary>{biText("查看动作技术详情", "View action technical details")}</summary>
        <dl className="definitionGrid">
          <div><dt>{biText("动作类型", "Action kind")}</dt><dd>{activeActionKind}</dd></div>
          <div><dt>{biText("动作编号", "Action key")}</dt><dd>{activeActionKey || "-"}</dd></div>
          <div><dt>{biText("队列数量", "Queue size")}</dt><dd>{pendingDrafts.length}</dd></div>
        </dl>
      </details>
    </article>
  );
}
