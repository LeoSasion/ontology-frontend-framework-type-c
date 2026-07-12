import { useEffect, useState } from "react";
import type { ActionDraft, WorkspaceStatus } from "../types";
import { Bilingual, biText, translateName } from "./Bilingual";

type SidebarWorkspaceCardProps = {
  actionDrafts: ActionDraft[];
  createWorkspaceFromInput: () => Promise<Record<string, unknown> | void>;
  deleteWorkspaceFromInput: (workspaceId: string, confirm?: boolean) => Promise<Record<string, unknown> | void>;
  renameWorkspaceFromInput: () => Promise<void>;
  selectWorkspaceFromInput: (workspaceId: string) => Promise<void>;
  setWorkspaceRenameName: (value: string) => void;
  setWorkspaceName: (value: string) => void;
  status: WorkspaceStatus;
  workspaceBusy: boolean;
  workspaceName: string;
  workspaceNotice: string;
  workspaceRenameName: string;
  workspaces: NonNullable<WorkspaceStatus["workspaces"]>;
};

export function SidebarWorkspaceCard({
  actionDrafts,
  createWorkspaceFromInput,
  deleteWorkspaceFromInput,
  renameWorkspaceFromInput,
  selectWorkspaceFromInput,
  setWorkspaceRenameName,
  setWorkspaceName,
  status,
  workspaceBusy,
  workspaceName,
  workspaceNotice,
  workspaceRenameName,
  workspaces,
}: SidebarWorkspaceCardProps) {
  const currentWorkspace = status.workspace ?? workspaces[0] ?? {
    id: "default",
    name: biText("AIBI-C 工作区", "AIBI-C workspace"),
    current_source_run_id: null,
    isActive: true,
  };
  const deletableWorkspaces = workspaces.filter((workspace) => workspace.id !== "default" && workspace.id !== currentWorkspace.id);
  const counts = status.counts ?? { tables: 0, dashboards: 0 };
  const [managedWorkspaceId, setManagedWorkspaceId] = useState("");
  const [deletePreview, setDeletePreview] = useState<Record<string, unknown> | null>(null);
  const managedWorkspace = deletableWorkspaces.find((workspace) => workspace.id === managedWorkspaceId);
  const impact = deletePreview?.impact && typeof deletePreview.impact === "object" ? deletePreview.impact as Record<string, unknown> : null;
  const impactCounts = impact?.counts && typeof impact.counts === "object" ? impact.counts as Record<string, unknown> : {};

  useEffect(() => setDeletePreview(null), [managedWorkspaceId]);

  async function previewWorkspaceDelete() {
    if (!managedWorkspaceId) return;
    const result = await deleteWorkspaceFromInput(managedWorkspaceId, false);
    setDeletePreview(result && typeof result === "object" ? result : null);
  }

  async function confirmWorkspaceDelete() {
    if (!managedWorkspaceId || deletePreview?.requiresConfirmation !== true) return;
    await deleteWorkspaceFromInput(managedWorkspaceId, true);
    setManagedWorkspaceId("");
    setDeletePreview(null);
  }

  return (
    <section className="assetWorkspaceCard" aria-labelledby="workspace-sandbox-title">
      <div className="assetSectionTitle">
        <span className="eyebrow">{biText("工作区沙盒", "Workspace sandbox")}</span>
        <strong id="workspace-sandbox-title" title={currentWorkspace.name}><Bilingual {...translateName(currentWorkspace.name)} /></strong>
      </div>
      <p>
        <Bilingual
          zh="当前选择决定 Agent、看板和证据的默认上下文；写入类动作仍必须先生成草案并确认。"
          en="The current selection drives Agent, dashboards, and evidence context; writes still become drafts before confirmation."
        />
      </p>
      <div className="workspaceSwitcher" data-testid="workspace-switcher">
        {workspaceNotice ? <span className="workspaceNotice" role="status">{workspaceNotice}</span> : null}
        <label>
          <span>{biText("当前沙箱", "Current sandbox")}</span>
          <select
            aria-label={biText("选择工作区", "Select workspace")}
            disabled={workspaceBusy || workspaces.length <= 1}
            onChange={(event) => void selectWorkspaceFromInput(event.target.value)}
            value={currentWorkspace.id}
          >
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}{workspace.isActive ? ` · ${biText("当前", "active")}` : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="workspaceCreateRow">
          <input
            aria-label={biText("新工作区名称", "New workspace name")}
            disabled={workspaceBusy}
            onChange={(event) => setWorkspaceName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void createWorkspaceFromInput();
            }}
            placeholder={biText("新沙箱名称", "New sandbox name")}
            value={workspaceName}
          />
          <button disabled={workspaceBusy || !workspaceName.trim()} onClick={() => void createWorkspaceFromInput()} type="button">
            {workspaceBusy ? biText("处理中", "Working") : biText("创建", "Create")}
          </button>
        </div>
        <details className="workspaceManageDetails">
          <summary>{biText("管理沙盒", "Manage sandboxes")}</summary>
          <div className="workspaceRenameRow">
            <input
              aria-label={biText("当前沙盒名称", "Current sandbox name")}
              disabled={workspaceBusy}
              onChange={(event) => setWorkspaceRenameName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void renameWorkspaceFromInput();
              }}
              value={workspaceRenameName}
            />
            <button
              disabled={workspaceBusy || !workspaceRenameName.trim() || workspaceRenameName.trim() === currentWorkspace.name}
              onClick={() => void renameWorkspaceFromInput()}
              type="button"
            >
              {biText("重命名", "Rename")}
            </button>
          </div>
          <div className="workspaceDeleteList" data-testid="workspace-delete-list">
            <label>
              <span>{biText("选择要管理的沙盒", "Select sandbox to manage")}</span>
              <select disabled={workspaceBusy || !deletableWorkspaces.length} onChange={(event) => setManagedWorkspaceId(event.target.value)} value={managedWorkspaceId}>
                <option value="">{deletableWorkspaces.length ? biText("请选择非当前沙盒", "Choose an inactive sandbox") : biText("没有可删除的沙盒", "No deletable sandbox")}</option>
                {deletableWorkspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
              </select>
            </label>
            <small>{biText("当前沙盒不可删除；如需删除，请先切换到其他沙盒。默认沙盒始终保留。", "The active sandbox cannot be deleted. Switch first; the default sandbox is always retained.")}</small>
            {managedWorkspace && !deletePreview ? <button className="secondaryButton" disabled={workspaceBusy} onClick={() => void previewWorkspaceDelete()} type="button">{biText("预览删除影响", "Preview delete impact")}</button> : null}
            {managedWorkspace && deletePreview ? <div className="workspaceDeletePreview" data-testid="workspace-delete-preview">
              <strong>{biText(`将删除「${managedWorkspace.name}」`, `Delete "${managedWorkspace.name}"`)}</strong>
              <span>{biText(`${Number(impactCounts.table_registry || 0)} 张表 · ${Number(impactCounts.dashboards || 0)} 个看板 · ${Number(impactCounts.action_drafts || 0)} 个草案 · ${Number(impactCounts.source_intelligence_runs || 0)} 条证据`, `${Number(impactCounts.table_registry || 0)} tables · ${Number(impactCounts.dashboards || 0)} dashboards · ${Number(impactCounts.action_drafts || 0)} drafts · ${Number(impactCounts.source_intelligence_runs || 0)} evidence runs`)}</span>
              <small>{biText(`共影响 ${Number(impact?.totalRows || 0)} 条工作区对象。`, `${Number(impact?.totalRows || 0)} workspace objects affected.`)}</small>
              <button className="dangerButton" disabled={workspaceBusy || deletePreview.requiresConfirmation !== true} onClick={() => void confirmWorkspaceDelete()} type="button">{biText("确认删除此沙盒", "Delete this sandbox")}</button>
            </div> : null}
          </div>
        </details>
      </div>
      <dl className="assetCounts">
        <div>
          <dt>{biText("表", "Tables")}</dt>
          <dd>{counts.tables}</dd>
        </div>
        <div>
          <dt>{biText("看板", "Boards")}</dt>
          <dd>{counts.dashboards}</dd>
        </div>
        <div>
          <dt>{biText("草案", "Drafts")}</dt>
          <dd>{actionDrafts.length}</dd>
        </div>
      </dl>
    </section>
  );
}

export default SidebarWorkspaceCard;
