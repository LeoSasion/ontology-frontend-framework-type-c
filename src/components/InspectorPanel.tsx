import { useState } from "react";
import { getAppSection } from "../appSections";
import type { ActionDraft, AgentAskResult, EvidenceFocus, ImportPreview, WorkspaceStatus } from "../types";
import { buildObjectInspectorModel } from "../productIntelligenceModel";
import { actionKindLabel, actionNextStep, actionResultSummary, drawerActionsForSection, payloadTarget, sectionContext } from "../inspectorPanelModel";
import { Bilingual, biText, translateName, translatePipelineStage, translateStatus } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type InspectorPanelProps = {
  activeSection: AppSection;
  status: WorkspaceStatus;
  preview: ImportPreview;
  agent: AgentAskResult;
  actionDrafts: ActionDraft[];
  evidenceFocus?: EvidenceFocus | null;
  activeDashboardName?: string;
  activeViewName?: string;
  activeTableName?: string;
  lastActionResult: Record<string, unknown> | null;
  actionQueueDisabled: boolean;
  inspectorCollapsed: boolean;
  inspectorPinned: boolean;
  onConfirmDryRun: (actionKey: string) => Promise<void>;
  onConfirmAction: (actionKey: string) => Promise<void>;
  onRejectAction: (actionKey: string) => Promise<void>;
  onCollapseInspector: () => void;
  onExpandInspector: () => void;
  onPinInspectorToggle: () => void;
  onOpenAgent: () => void;
  onOpenEvidence: () => void;
  onOpenSection: (section: AppSection) => void;
};

export function InspectorPanel({
  activeSection,
  status,
  preview,
  agent,
  actionDrafts,
  evidenceFocus,
  activeDashboardName = "",
  activeViewName = "",
  activeTableName = "",
  lastActionResult,
  actionQueueDisabled,
  inspectorCollapsed,
  inspectorPinned,
  onConfirmDryRun,
  onConfirmAction,
  onRejectAction,
  onCollapseInspector,
  onExpandInspector,
  onPinInspectorToggle,
  onOpenAgent,
  onOpenEvidence,
  onOpenSection,
}: InspectorPanelProps) {
  const [busyAction, setBusyAction] = useState("");
  const pendingDrafts = actionQueueDisabled ? [] : actionDrafts.filter((draft) => draft.status === "draft");
  const latestSummary = actionResultSummary(lastActionResult);
  const recoverySection = latestSummary?.targetSection ? getAppSection(latestSummary.targetSection) : null;
  const fallbackContext = sectionContext(activeSection, activeDashboardName, activeViewName, activeTableName, agent);
  const objectModel = buildObjectInspectorModel({ activeSection, focus: evidenceFocus, status, preview, agent, activeDashboardName, activeViewName, activeTableName });
  const drawerActions = drawerActionsForSection(activeSection);
  const contextTitle = evidenceFocus?.title ?? objectModel.title;
  const focusChips = evidenceFocus
    ? [
      evidenceFocus.source,
      evidenceFocus.dashboardKey ? `${biText("看板", "dashboard")}: ${evidenceFocus.dashboardKey}` : "",
      evidenceFocus.viewKey ? `${biText("视图", "view")}: ${evidenceFocus.viewKey}` : "",
      evidenceFocus.tableKey ? `${biText("表", "table")}: ${evidenceFocus.tableKey}` : "",
      evidenceFocus.widgetType ? `${biText("组件", "widget")}: ${evidenceFocus.widgetType}` : "",
      biText(`${evidenceFocus.refs.length} 条证据线索`, `${evidenceFocus.refs.length} evidence items`),
    ].filter((chip): chip is string => Boolean(chip))
    : fallbackContext.chips;

  async function runAction(actionKey: string, task: () => Promise<void>) {
    setBusyAction(actionKey);
    try {
      await task();
    } finally {
      setBusyAction("");
    }
  }

  if (inspectorCollapsed) {
    const statusLabel = status.health.ok ? biText("就绪", "Ready") : biText("检查", "Review");
    const taskLabel = pendingDrafts.length ? String(pendingDrafts.length) : biText("0", "0");
    return (
      <aside className="inspector inspectorCollapsed" aria-label={biText("上下文抽屉工具条", "Context drawer toolbar")}>
        <button className="inspectorMiniButton status" onClick={onExpandInspector} title={biText("打开上下文抽屉", "Open context drawer")} type="button">
          <span className={status.health.ok ? "miniStatusDot ok" : "miniStatusDot warn"} />
          <strong>{statusLabel}</strong>
        </button>
        <button className="inspectorMiniButton" data-testid="inspector-mini-evidence" onClick={onOpenEvidence} title={biText("查看当前对象证据", "View current evidence")} type="button">
          <Icon name="evidence" />
          <span>{biText("证据", "Proof")}</span>
        </button>
        <button className="inspectorMiniButton" data-testid="inspector-mini-tasks" onClick={onOpenAgent} title={biText("处理 Agent 草案", "Review Agent drafts")} type="button">
          <Icon name="agent" />
          <span>{taskLabel}</span>
        </button>
        <button className="inspectorMiniButton" data-testid="inspector-mini-safety" onClick={onExpandInspector} title={biText("查看写入边界", "View write boundary")} type="button">
          <Icon name="lock" />
          <span>{biText("边界", "Guard")}</span>
        </button>
        <button className="inspectorMiniButton expand" data-testid="inspector-expand" onClick={onExpandInspector} title={biText("展开上下文抽屉", "Expand context drawer")} type="button">
          <span aria-hidden="true">+</span>
          <strong>{biText("抽屉", "Drawer")}</strong>
        </button>
      </aside>
    );
  }

  return (
    <aside className="inspector simplifiedInspector contextDrawer" aria-label={biText("上下文抽屉", "Context drawer")}>
      <div className="inspectorChrome">
        <div className="contextDrawerTitle">
          <strong>{biText("上下文抽屉", "Context drawer")}</strong>
          <span>{inspectorPinned ? biText("固定显示", "Pinned open") : biText("按需展开", "Opens when needed")}</span>
        </div>
        <button className="miniButton" data-testid="inspector-collapse" onClick={onCollapseInspector} type="button">
          <Icon name="collapse" />
          {biText("收起", "Collapse")}
        </button>
        <button className={inspectorPinned ? "miniButton active" : "miniButton"} data-testid="inspector-pin" onClick={onPinInspectorToggle} type="button">
          <Icon name="lock" />
          {inspectorPinned ? biText("已固定", "Pinned") : biText("固定", "Pin")}
        </button>
      </div>

      <section className="inspectorFocusContext" data-testid="inspector-selected-context">
        <div className="inspectorSectionHeader">
          <div>
            <span className="eyebrow">{evidenceFocus ? biText("当前对象", "Current object") : biText("未选中对象", "No object selected")}</span>
            <h2>{contextTitle}</h2>
          </div>
          <button className="miniButton" data-testid="inspector-open-evidence" onClick={onOpenEvidence} type="button">
            <Icon name="evidence" />
            {biText("证据", "Evidence")}
          </button>
        </div>
        <p className="quietText">
          {evidenceFocus?.subtitle ?? biText("选择图表、字段、公式、关系或 Agent 草案后，这里显示对应的编辑与证据入口。", "Select a chart, field, formula, relationship, or Agent draft to show matching edit and evidence controls here.")}
        </p>
        <div className="inspectorFocusChips" data-testid="inspector-selected-context-chips">
          {focusChips.map((chip) => (
            <span key={chip}>{chip}</span>
          ))}
        </div>
      </section>

      <section className="objectInspectorLens" data-testid="object-inspector-lens">
        <div className="objectInspectorLensHeader">
          <span className="storyMode">{objectModel.objectType}</span>
          <strong>{objectModel.subtitle}</strong>
        </div>
        <div className="objectInspectorFacts" data-testid="object-inspector-facts">
          {objectModel.facts.map((fact) => (
            <div className={fact.tone} key={fact.key}>
              <strong>{fact.value}</strong>
              <span>{fact.title}</span>
              <small>{fact.detail}</small>
            </div>
          ))}
        </div>
        <div className="objectInspectorSlots" data-testid="object-inspector-editor-slots">
          {objectModel.editorSlots.map((slot) => (
            <span className={slot.tone} key={slot.key}>
              <strong>{slot.title}</strong>
              <small>{slot.detail}</small>
            </span>
          ))}
        </div>
      </section>

      <section className="contextActionPanel">
        <div className="contextActionHeader">
          <span className="eyebrow">{biText("可做什么", "Available actions")}</span>
          <strong>{objectModel.primaryAction}</strong>
        </div>
        <div className="contextActionGrid">
          <button className="secondaryButton" onClick={onOpenEvidence} type="button">
            <Icon name="evidence" />
            <Bilingual {...drawerActions.evidence} />
          </button>
          <button className="secondaryButton" onClick={onOpenAgent} type="button">
            <Icon name="agent" />
            <Bilingual {...drawerActions.agent} />
          </button>
        </div>
        <p className="quietText"><Bilingual {...drawerActions.hint} /></p>
      </section>

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
                    <button
                      className="miniButton"
                      data-testid={`action-preview-${draft.action_key}`}
                      disabled={isBusy || actionQueueDisabled}
                      onClick={() => runAction(draft.action_key, () => onConfirmDryRun(draft.action_key))}
                      type="button"
                    >
                      <Icon name="evidence" />
                      {biText("预演", "Preview")}
                    </button>
                    <button
                      className="primaryButton compactAction"
                      data-testid={`action-confirm-${draft.action_key}`}
                      disabled={isBusy || actionQueueDisabled}
                      onClick={() => runAction(draft.action_key, () => onConfirmAction(draft.action_key))}
                      type="button"
                    >
                      <Icon name="check" />
                      {biText("确认", "Confirm")}
                    </button>
                    <button
                      className="miniButton dangerButton"
                      data-testid={`action-reject-${draft.action_key}`}
                      disabled={isBusy || actionQueueDisabled}
                      onClick={() => runAction(draft.action_key, () => onRejectAction(draft.action_key))}
                      type="button"
                    >
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
                  {latestSummary.steps.map((step) => (
                    <li key={`${step.zh}-${step.en}`}><Bilingual {...step} /></li>
                  ))}
                </ol>
              ) : null}
              {latestSummary.targetSection && recoverySection && latestSummary.targetSection !== activeSection ? (
                <button
                  className="visibleActionRecoveryAction"
                  data-testid="last-action-recovery-open-section"
                  onClick={() => onOpenSection(latestSummary.targetSection!)}
                  type="button"
                >
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

      <details className="contextReservePanel">
        <summary>{biText("扩展能力", "Extended tools")}</summary>
        <h2><Bilingual zh="需要深度编辑时再展开" en="Expand only for deep editing" /></h2>
        <ul>
          <li>{biText("组件属性、字段语义、公式 DSL", "Widget properties, field semantics, formula DSL")}</li>
          <li>{biText("关系预览、证据链、Agent 影响范围", "Relationship preview, evidence chain, Agent impact scope")}</li>
        </ul>
      </details>

      <details className="advancedDetails inspectorDetails">
        <summary>{biText("技术细节", "Technical details")}</summary>
        <section>
          <span className="eyebrow">{biText("分析链路", "Analysis chain")}</span>
          <ol className="stageList">
            {preview.sourcePipelineContract.stages.map((stage, index) => (
              <li key={stage.id}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{stage.id}</strong>
                <small><Bilingual inline {...translatePipelineStage(stage.label)} /></small>
              </li>
            ))}
          </ol>
        </section>

        <section>
          <span className="eyebrow">{biText("业务语义", "Business semantics")}</span>
          <h2><Bilingual {...translateName(agent.domainPackRuntime.label)} /></h2>
          <div className="chipGrid">
            {agent.domainPackRuntime.semanticHints.map((hint) => (
              <span key={hint.semantic}>{hint.semantic} · {hint.role}</span>
            ))}
          </div>
        </section>

        <section>
          <span className="eyebrow">{biText("证据文件", "Evidence files")}</span>
          <ul className="evidenceList">
            {agent.ontology.evidenceFiles.map((file) => (
              <li key={file}>{file}</li>
            ))}
          </ul>
        </section>

        {lastActionResult ? (
          <section>
            <span className="eyebrow">{biText("动作 JSON", "Action JSON")}</span>
            <pre>{JSON.stringify(lastActionResult, null, 2)}</pre>
          </section>
        ) : null}
      </details>
    </aside>
  );
}
