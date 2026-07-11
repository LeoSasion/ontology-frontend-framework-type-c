import type { ActionDraft, WorkspaceStatus } from "../types";
import { Bilingual, biText, translateName } from "./Bilingual";

type SidebarWorkspaceCardProps = {
  actionDrafts: ActionDraft[];
  createWorkspaceFromInput: () => Promise<void>;
  deleteWorkspaceFromInput: (workspaceId: string) => Promise<void>;
  renameWorkspaceFromInput: () => Promise<void>;
  selectWorkspaceFromInput: (workspaceId: string) => Promise<void>;
  setWorkspaceRenameName: (value: string) => void;
  setWorkspaceName: (value: string) => void;
  status: WorkspaceStatus;
  workspaceBusy: boolean;
  workspaceName: string;
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

  function confirmWorkspaceDelete(workspace: NonNullable<WorkspaceStatus["workspaces"]>[number]) {
    const confirmed = window.confirm(
      biText(
        `删除沙盒「${workspace.name}」？此操作会删除该沙盒内的表、看板、证据和草案。`,
        `Delete sandbox "${workspace.name}"? This removes its tables, dashboards, evidence, and drafts.`,
      ),
    );
    if (confirmed) void deleteWorkspaceFromInput(workspace.id);
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
          {deletableWorkspaces.length > 0 ? (
            <div className="workspaceDeleteList" data-testid="workspace-delete-list">
              {deletableWorkspaces.map((workspace) => (
                <button
                  className="dangerButton"
                  disabled={workspaceBusy}
                  key={workspace.id}
                  onClick={() => confirmWorkspaceDelete(workspace)}
                  title={biText("删除这个非当前沙盒", "Delete this inactive sandbox")}
                  type="button"
                >
                  {biText("删除", "Delete")} {workspace.name}
                </button>
              ))}
            </div>
          ) : null}
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
