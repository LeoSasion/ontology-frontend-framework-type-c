import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { getAppSection, primaryAppSections, utilityAppSections, type AppSection } from "../appSections";
import type { ActionDraft, AgentAskResult, DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "../types";
import { isSectionLockedByFlow, resolveSectionForFlow, type WorkspaceFlowModel } from "../workspaceFlowModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import { SidebarAssetSections } from "../sidebarAssetModules";
import { buildProductReadiness } from "../productReadinessModel";

export type { AppSection } from "../appSections";

const SidebarWorkspaceCard = lazy(() => import("./SidebarWorkspaceCard"));

type SidebarProps = {
  activeSection: AppSection;
  onSectionChange: (section: AppSection) => void;
  status: WorkspaceStatus;
  dashboards: DashboardPayload;
  activeDashboardKey: string;
  onDashboardSelect: (dashboardKey: string) => void;
  workbench: WorkbenchPayload;
  flow: WorkspaceFlowModel;
  agent: AgentAskResult;
  actionDrafts: ActionDraft[];
  onWorkspaceCreate: (name: string) => Promise<Record<string, unknown> | void>;
  onWorkspaceDelete: (workspaceId: string, confirm?: boolean) => Promise<Record<string, unknown> | void>;
  onWorkspaceRename: (workspaceId: string, name: string) => Promise<Record<string, unknown> | void>;
  onWorkspaceSelect: (workspaceId: string) => Promise<void>;
};

export function Sidebar({
  activeSection,
  onSectionChange,
  status,
  dashboards,
  activeDashboardKey,
  onDashboardSelect,
  workbench,
  flow,
  agent,
  actionDrafts,
  onWorkspaceCreate,
  onWorkspaceDelete,
  onWorkspaceRename,
  onWorkspaceSelect,
}: SidebarProps) {
  const activeRailSection = activeSection;
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [assetSectionsMounted, setAssetSectionsMounted] = useState(false);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceNotice, setWorkspaceNotice] = useState("");
  const currentWorkspace = status.workspace ?? {
    id: "default",
    name: biText("AIBI-C 工作区", "AIBI-C workspace"),
    current_source_run_id: null,
    isActive: true,
  };
  const workspaces = Array.isArray(status.workspaces) && status.workspaces.length
    ? status.workspaces.filter((workspace) => workspace && workspace.id)
    : [currentWorkspace];
  const safeStatus = { ...status, workspace: currentWorkspace, workspaces };
  const [workspaceRenameName, setWorkspaceRenameName] = useState(currentWorkspace.name);
  const readiness = buildProductReadiness(status, {
    hasData: flow.hasData,
    hasEvidence: flow.hasEvidence,
    hasPendingDraft: flow.hasPendingDraft,
  });

  const activeRailItem = useMemo(
    () => getAppSection(activeRailSection),
    [activeRailSection],
  );

  function openSection(section: AppSection) {
    onSectionChange(resolveSectionForFlow(section, flow));
  }

  useEffect(() => {
    setWorkspaceRenameName(currentWorkspace.name);
  }, [currentWorkspace.id, currentWorkspace.name]);

  useEffect(() => {
    setAssetSectionsMounted(true);
  }, []);

  async function createWorkspaceFromInput() {
    const name = workspaceName.trim();
    if (!name) return;
    setWorkspaceBusy(true);
    try {
      const result = await onWorkspaceCreate(name);
      if (result && typeof result.enteredWorkspace === "string") setWorkspaceNotice(biText("已进入新工作区", "Entered the new workspace"));
      setWorkspaceName("");
      return result;
    } finally {
      setWorkspaceBusy(false);
    }
  }

  async function selectWorkspaceFromInput(workspaceId: string) {
    if (!workspaceId || workspaceId === currentWorkspace.id) return;
    setWorkspaceBusy(true);
    try {
      await onWorkspaceSelect(workspaceId);
    } finally {
      setWorkspaceBusy(false);
    }
  }

  async function deleteWorkspaceFromInput(workspaceId: string, confirm = false) {
    if (!workspaceId || workspaceId === "default" || workspaceId === currentWorkspace.id) return;
    setWorkspaceBusy(true);
    try {
      return await onWorkspaceDelete(workspaceId, confirm);
    } finally {
      setWorkspaceBusy(false);
    }
  }

  async function renameWorkspaceFromInput() {
    const name = workspaceRenameName.trim();
    if (!name || name === currentWorkspace.name) return;
    setWorkspaceBusy(true);
    try {
      await onWorkspaceRename(currentWorkspace.id, name);
    } finally {
      setWorkspaceBusy(false);
    }
  }

  return (
    <aside className="biSidebarShell" aria-label={biText("BI 工作台导航", "BI workspace navigation")}>
      <div className="biRail">
        <button className="railBrand" onClick={() => openSection("home")} type="button" aria-label="AIBI">
          <span>A</span>
        </button>
        <nav className="railNav" aria-label={biText("主导航", "Primary navigation")}>
          {primaryAppSections.map((sectionKey) => {
            const item = getAppSection(sectionKey);
            const locked = isSectionLockedByFlow(item.key, flow);
            const classes = ["railButton"];
            if (item.key === activeRailSection) classes.push("active");
            if (locked) classes.push("locked");
            return (
            <button
              aria-label={locked
                ? biText(`${item.zh}，先完成当前步骤`, `${item.en}, finish the current step first`)
                : biText(item.zh, item.en)}
              aria-pressed={item.key === activeRailSection}
              className={classes.join(" ")}
              key={item.key}
              onClick={() => openSection(item.key)}
              title={locked ? biText("先完成当前必要步骤", "Finish the current required step first") : biText(item.zh, item.en)}
              type="button"
            >
              <Icon name={item.icon} />
              <span><Bilingual zh={item.zh} en={item.en} /></span>
            </button>
            );
          })}
        </nav>
        {utilityAppSections.map((sectionKey) => {
          const item = getAppSection(sectionKey);
          return (
            <button
              aria-label={biText(item.zh, item.en)}
              aria-pressed={activeRailSection === item.key}
              className={activeRailSection === item.key ? "railButton railUtility active" : "railButton railUtility"}
              key={item.key}
              onClick={() => onSectionChange(item.key)}
              title={biText(item.zh, item.en)}
              type="button"
            >
              <Icon name={item.icon} />
              <span><Bilingual zh={item.zh} en={item.en} /></span>
            </button>
          );
        })}
        <div className="railStatus" title={readiness.label}>
          <span className={`dot ${readiness.tone}`} />
        </div>
      </div>

      <div className="assetPanel">
        <div className="assetPanelHeader">
          <div>
            <p className="kicker">{biText(activeRailItem.zh, activeRailItem.en)}</p>
            <h2><Bilingual zh="工作区资产" en="Workspace assets" /></h2>
          </div>
          <span className="assetModeChip"><Bilingual zh="沙盒" en="Sandbox" /></span>
        </div>

        <Suspense fallback={<div className="assetWorkspaceCard" aria-hidden="true" />}><SidebarWorkspaceCard
          actionDrafts={actionDrafts}
          createWorkspaceFromInput={createWorkspaceFromInput}
          deleteWorkspaceFromInput={deleteWorkspaceFromInput}
          renameWorkspaceFromInput={renameWorkspaceFromInput}
          selectWorkspaceFromInput={selectWorkspaceFromInput}
          setWorkspaceRenameName={setWorkspaceRenameName}
          setWorkspaceName={setWorkspaceName}
          status={safeStatus}
          workspaceBusy={workspaceBusy}
          workspaceName={workspaceName}
          workspaceNotice={workspaceNotice}
          workspaceRenameName={workspaceRenameName}
          workspaces={workspaces}
        /></Suspense>

        {assetSectionsMounted ? <Suspense fallback={null}>
          <SidebarAssetSections
            activeDashboardKey={activeDashboardKey}
            activeRailSection={activeRailSection}
            actionDrafts={actionDrafts}
            agent={agent}
            dashboards={dashboards}
            onDashboardSelect={onDashboardSelect}
            onSectionChange={onSectionChange}
            status={status}
            workbench={workbench}
          />
        </Suspense> : null}
      </div>
    </aside>
  );
}
