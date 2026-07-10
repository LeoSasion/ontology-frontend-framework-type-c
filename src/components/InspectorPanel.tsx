import type { ActionDraft, AgentAskResult, EvidenceFocus, ImportPreview, WorkspaceStatus } from "../types";
import { biText } from "./Bilingual";
import { Icon } from "./Icons";
import { InspectorContextPanel } from "./InspectorContextPanel";
import { InspectorEvidenceDetails } from "./InspectorEvidenceDetails";
import { InspectorTaskQueuePanel } from "./InspectorTaskQueuePanel";
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
  const pendingDraftCount = actionQueueDisabled ? 0 : actionDrafts.filter((draft) => draft.status === "draft").length;

  if (inspectorCollapsed) {
    const statusLabel = status.health.ok ? biText("就绪", "Ready") : biText("检查", "Review");
    const taskLabel = pendingDraftCount ? String(pendingDraftCount) : biText("0", "0");
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

      <InspectorContextPanel
        activeDashboardName={activeDashboardName}
        activeSection={activeSection}
        activeTableName={activeTableName}
        activeViewName={activeViewName}
        agent={agent}
        evidenceFocus={evidenceFocus}
        onOpenAgent={onOpenAgent}
        onOpenEvidence={onOpenEvidence}
        preview={preview}
        status={status}
      />
      <InspectorTaskQueuePanel
        actionDrafts={actionDrafts}
        actionQueueDisabled={actionQueueDisabled}
        activeSection={activeSection}
        lastActionResult={lastActionResult}
        onConfirmAction={onConfirmAction}
        onConfirmDryRun={onConfirmDryRun}
        onOpenAgent={onOpenAgent}
        onOpenSection={onOpenSection}
        onRejectAction={onRejectAction}
      />
      <InspectorEvidenceDetails agent={agent} lastActionResult={lastActionResult} preview={preview} />
    </aside>
  );
}
