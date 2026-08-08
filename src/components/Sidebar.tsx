import { useEffect, useMemo, useState } from "react";
import { getAppSection, type AppSection } from "../appSections";
import type { ActionDraft, WorkspaceStatus } from "../types";
import { isSectionLockedByFlow, resolveSectionForFlow, type WorkspaceFlowModel } from "../workspaceFlowModel";
import { buildProductReadiness } from "../productReadinessModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

export type { AppSection } from "../appSections";

type SidebarProps = {
  activeSection: AppSection;
  onSectionChange: (section: AppSection) => void;
  status: WorkspaceStatus;
  flow: WorkspaceFlowModel;
  actionDrafts: ActionDraft[];
  onWorkspaceCreate: (name: string) => Promise<Record<string, unknown> | void>;
  onWorkspaceDelete: (workspaceId: string, confirm?: boolean) => Promise<Record<string, unknown> | void>;
  onWorkspaceRename: (workspaceId: string, name: string) => Promise<Record<string, unknown> | void>;
  onWorkspaceSelect: (workspaceId: string) => Promise<void>;
};

const primarySections: AppSection[] = ["home", "sources", "agent", "dashboards", "evidence"];

function navigationBadge(section: AppSection, flow: WorkspaceFlowModel) {
  if (section === "sources") return flow.counts.tableCount;
  if (section === "agent") return flow.counts.pendingDraftCount;
  if (section === "dashboards") return flow.counts.dashboardCount;
  if (section === "evidence") return flow.counts.sourceProfileCount;
  return 0;
}

function numberValue(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function Sidebar({
  activeSection,
  onSectionChange,
  status,
  flow,
  actionDrafts,
  onWorkspaceCreate,
  onWorkspaceDelete,
  onWorkspaceRename,
  onWorkspaceSelect,
}: SidebarProps) {
  const currentWorkspace = status.workspace ?? {
    id: "default",
    name: biText("AIBI-C 工作区", "AIBI-C workspace"),
    current_source_run_id: null,
    isActive: true,
  };
  const workspaces = Array.isArray(status.workspaces) && status.workspaces.length
    ? status.workspaces.filter((workspace) => workspace && workspace.id)
    : [currentWorkspace];
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceRenameName, setWorkspaceRenameName] = useState(currentWorkspace.name);
  const [managedWorkspaceId, setManagedWorkspaceId] = useState("");
  const [deletePreview, setDeletePreview] = useState<Record<string, unknown> | null>(null);
  const [workspaceNotice, setWorkspaceNotice] = useState<{ message: string; tone: "ok" | "error" } | null>(null);
  const readiness = buildProductReadiness(status, {
    hasData: flow.hasData,
    hasEvidence: flow.hasEvidence,
    hasPendingDraft: flow.hasPendingDraft,
  });
  const pendingDraftCount = useMemo(
    () => actionDrafts.filter((draft) => draft.status === "draft").length,
    [actionDrafts],
  );
  const deletableWorkspaces = workspaces.filter(
    (workspace) => workspace.id !== "default" && workspace.id !== currentWorkspace.id,
  );
  const managedWorkspace = deletableWorkspaces.find((workspace) => workspace.id === managedWorkspaceId);
  const impact = deletePreview?.impact && typeof deletePreview.impact === "object"
    ? deletePreview.impact as Record<string, unknown>
    : null;
  const impactCounts = impact?.counts && typeof impact.counts === "object"
    ? impact.counts as Record<string, unknown>
    : {};

  useEffect(() => {
    setWorkspaceRenameName(currentWorkspace.name);
    setManagedWorkspaceId("");
    setDeletePreview(null);
  }, [currentWorkspace.id, currentWorkspace.name]);

  useEffect(() => setDeletePreview(null), [managedWorkspaceId]);

  function openSection(section: AppSection) {
    onSectionChange(resolveSectionForFlow(section, flow));
  }

  function sectionHref(section: AppSection) {
    const url = new URL(window.location.href);
    url.searchParams.set("section", section);
    return `${url.pathname}${url.search}${url.hash}`;
  }

  async function runWorkspaceTask(task: () => Promise<unknown>) {
    setWorkspaceBusy(true);
    setWorkspaceNotice(null);
    try {
      return await task();
    } catch (error) {
      setWorkspaceNotice({
        message: error instanceof Error ? error.message : String(error),
        tone: "error",
      });
      return null;
    } finally {
      setWorkspaceBusy(false);
    }
  }

  async function createWorkspace() {
    const name = workspaceName.trim();
    if (!name) return;
    const result = await runWorkspaceTask(() => onWorkspaceCreate(name));
    if (result && typeof result === "object") {
      setWorkspaceName("");
      setWorkspaceNotice({ message: biText("已创建并进入新工作区", "Created and entered the new workspace"), tone: "ok" });
    }
  }

  async function renameWorkspace() {
    const name = workspaceRenameName.trim();
    if (!name || name === currentWorkspace.name) return;
    const result = await runWorkspaceTask(() => onWorkspaceRename(currentWorkspace.id, name));
    if (result && typeof result === "object") setWorkspaceNotice({ message: biText("工作区已重命名", "Workspace renamed"), tone: "ok" });
  }

  async function previewWorkspaceDelete() {
    if (!managedWorkspaceId) return;
    const result = await runWorkspaceTask(() => onWorkspaceDelete(managedWorkspaceId, false));
    setDeletePreview(result && typeof result === "object" ? result as Record<string, unknown> : null);
  }

  async function confirmWorkspaceDelete() {
    if (!managedWorkspaceId || deletePreview?.requiresConfirmation !== true) return;
    const result = await runWorkspaceTask(() => onWorkspaceDelete(managedWorkspaceId, true));
    if (!result || typeof result !== "object") return;
    setManagedWorkspaceId("");
    setDeletePreview(null);
    setWorkspaceNotice({ message: biText("工作区已删除", "Workspace deleted"), tone: "ok" });
  }

  return (
    <aside className="workspaceSidebar" aria-label={biText("BI 工作台导航", "BI workspace navigation")}>
      <a className="workspaceBrand" href={sectionHref("home")} onClick={(event) => { event.preventDefault(); openSection("home"); }} aria-label="AIBI-C">
        <span className="workspaceBrandMark" aria-hidden="true">A</span>
        <span className="workspaceBrandCopy">
          <strong>AIBI-C</strong>
          <small><Bilingual zh="可信分析工作台" en="Trusted analytics" /></small>
        </span>
      </a>

      <div className="sidebarWorkspaceControl">
        <label htmlFor="workspace-switcher">
          <span><Bilingual zh="当前工作区" en="Workspace" /></span>
          <select
            id="workspace-switcher"
            aria-label={biText("选择工作区", "Select workspace")}
            disabled={workspaceBusy || workspaces.length <= 1}
            onChange={(event) => void runWorkspaceTask(() => onWorkspaceSelect(event.target.value))}
            value={currentWorkspace.id}
          >
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
            ))}
          </select>
        </label>
        <div className="sidebarReadiness" title={readiness.label}>
          <span className={`dot ${readiness.tone}`} />
          <span>{readiness.label}</span>
          {pendingDraftCount > 0 ? <strong>{pendingDraftCount}</strong> : null}
        </div>
      </div>

      <nav className="workspaceNav" aria-label={biText("主导航", "Primary navigation") }>
        {primarySections.map((sectionKey) => {
          const item = getAppSection(sectionKey);
          const locked = isSectionLockedByFlow(sectionKey, flow);
          const badge = navigationBadge(sectionKey, flow);
          return (
            <a
              aria-label={locked
                ? biText(`${item.zh}，先完成数据准备`, `${item.en}, finish data preparation first`)
                : biText(item.zh, item.en)}
              aria-current={activeSection === sectionKey ? "page" : undefined}
              className={`workspaceNavItem${activeSection === sectionKey ? " active" : ""}${locked ? " locked" : ""}`}
              href={sectionHref(sectionKey)}
              key={sectionKey}
              onClick={(event) => { event.preventDefault(); openSection(sectionKey); }}
            >
              <Icon name={item.icon} />
              <span><Bilingual zh={item.zh} en={item.en} /></span>
              {badge > 0 ? <small>{badge}</small> : null}
            </a>
          );
        })}
      </nav>

      <details className="sidebarAdvancedNav">
        <summary><Bilingual zh="高级工具" en="Advanced tools" /></summary>
        <a
          aria-current={activeSection === "views" ? "page" : undefined}
          className={activeSection === "views" ? "workspaceNavItem active" : "workspaceNavItem"}
          href={sectionHref("views")}
          onClick={(event) => { event.preventDefault(); openSection("views"); }}
        >
          <Icon name="source" />
          <span><Bilingual zh="明细视图" en="Detail views" /></span>
        </a>
      </details>

      <div className="sidebarFooter">
        <details className="sidebarWorkspaceManager">
          <summary><Bilingual zh="管理工作区" en="Manage workspaces" /></summary>
          <div className="sidebarWorkspaceManagerBody">
            <label>
              <span><Bilingual zh="新建工作区" en="New workspace" /></span>
              <span className="sidebarInlineControl">
                <input
                  aria-label={biText("新工作区名称", "New workspace name")}
                  disabled={workspaceBusy}
                  onChange={(event) => setWorkspaceName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void createWorkspace();
                  }}
                  placeholder={biText("名称", "Name")}
                  value={workspaceName}
                />
                <button disabled={workspaceBusy || !workspaceName.trim()} onClick={() => void createWorkspace()} type="button">
                  <Bilingual zh="创建" en="Create" />
                </button>
              </span>
            </label>
            <label>
              <span><Bilingual zh="重命名当前工作区" en="Rename current workspace" /></span>
              <span className="sidebarInlineControl">
                <input
                  aria-label={biText("当前工作区名称", "Current workspace name")}
                  disabled={workspaceBusy}
                  onChange={(event) => setWorkspaceRenameName(event.target.value)}
                  value={workspaceRenameName}
                />
                <button
                  disabled={workspaceBusy || !workspaceRenameName.trim() || workspaceRenameName.trim() === currentWorkspace.name}
                  onClick={() => void renameWorkspace()}
                  type="button"
                >
                  <Bilingual zh="保存" en="Save" />
                </button>
              </span>
            </label>
            {deletableWorkspaces.length ? (
              <div className="sidebarDeleteWorkspace">
                <label>
                  <span><Bilingual zh="删除其他工作区" en="Delete another workspace" /></span>
                  <select disabled={workspaceBusy} onChange={(event) => setManagedWorkspaceId(event.target.value)} value={managedWorkspaceId}>
                    <option value="">{biText("选择工作区", "Choose workspace")}</option>
                    {deletableWorkspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
                  </select>
                </label>
                {managedWorkspace && !deletePreview ? (
                  <button className="secondaryButton" disabled={workspaceBusy} onClick={() => void previewWorkspaceDelete()} type="button">
                    <Bilingual zh="预览删除影响" en="Preview impact" />
                  </button>
                ) : null}
                {managedWorkspace && deletePreview ? (
                  <div className="sidebarDeletePreview" role="status">
                    <span>
                      {biText(
                        `${numberValue(impactCounts.table_registry)} 张表 · ${numberValue(impactCounts.dashboards)} 个看板`,
                        `${numberValue(impactCounts.table_registry)} tables · ${numberValue(impactCounts.dashboards)} dashboards`,
                      )}
                    </span>
                    <button className="dangerButton" disabled={workspaceBusy || deletePreview.requiresConfirmation !== true} onClick={() => void confirmWorkspaceDelete()} type="button">
                      <Bilingual zh="确认删除" en="Delete" />
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}
            {workspaceNotice ? <span className={`sidebarWorkspaceNotice ${workspaceNotice.tone}`} role={workspaceNotice.tone === "error" ? "alert" : "status"}>{workspaceNotice.message}</span> : null}
          </div>
        </details>

        <a
          aria-current={activeSection === "settings" ? "page" : undefined}
          className={`workspaceNavItem utility${activeSection === "settings" ? " active" : ""}`}
          href={sectionHref("settings")}
          onClick={(event) => { event.preventDefault(); onSectionChange("settings"); }}
        >
          <Icon name="settings" />
          <span><Bilingual zh="设置" en="Settings" /></span>
        </a>
      </div>
    </aside>
  );
}
