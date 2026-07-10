import { useCallback, type Dispatch, type SetStateAction } from "react";
import { createWorkspace, deleteWorkspace, renameWorkspace, selectWorkspace } from "./api";
import type { AppSection } from "./components/Sidebar";
import { emptyAgentResult } from "./emptyWorkspaceData";
import { refreshStatusDashboardsWorkbenchDrafts } from "./appRefreshModel";
import { preferredLandingSection } from "./appWorkspaceModel";
import type { ActionDraft, AgentAskResult, DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";

type StateSetter<T> = Dispatch<SetStateAction<T>>;

type AppWorkspaceActionsOptions = {
  activeWorkspaceId: string;
  setActionDrafts: StateSetter<ActionDraft[]>;
  setActiveDashboardKey: StateSetter<string>;
  setActiveViewKey: StateSetter<string>;
  setAgent: StateSetter<AgentAskResult>;
  setDashboards: StateSetter<DashboardPayload>;
  setLastActionResult: StateSetter<Record<string, unknown> | null>;
  setSection: StateSetter<AppSection>;
  setStatus: StateSetter<WorkspaceStatus>;
  setWorkbench: StateSetter<WorkbenchPayload>;
};

export function useAppWorkspaceActions({
  activeWorkspaceId,
  setActionDrafts,
  setActiveDashboardKey,
  setActiveViewKey,
  setAgent,
  setDashboards,
  setLastActionResult,
  setSection,
  setStatus,
  setWorkbench,
}: AppWorkspaceActionsOptions) {
  const reloadWorkspaceSurface = useCallback(async () => {
    const surface = await refreshStatusDashboardsWorkbenchDrafts();
    setStatus(surface.status);
    setWorkbench(surface.workbench);
    setDashboards(surface.dashboards);
    setAgent(emptyAgentResult);
    setActionDrafts(surface.actionDrafts);
    setActiveDashboardKey(surface.dashboards.dashboards[0]?.dashboard_key ?? "default");
    setActiveViewKey(surface.workbench.savedViews[0]?.view_key ?? "");
    return surface;
  }, [setActionDrafts, setActiveDashboardKey, setActiveViewKey, setAgent, setDashboards, setStatus, setWorkbench]);

  const openWorkspaceLanding = useCallback(async () => {
    const surface = await reloadWorkspaceSurface();
    setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards));
    return surface;
  }, [reloadWorkspaceSurface, setSection]);

  const handleWorkspaceCreate = useCallback(async (name: string) => {
    const previewResult = await createWorkspace(name, false);
    if (previewResult.requiresConfirmation !== true) {
      setLastActionResult(previewResult);
      return previewResult;
    }
    const result = await createWorkspace(name, true);
    setLastActionResult(result);
    if (result.ok !== false) await openWorkspaceLanding();
    return result;
  }, [openWorkspaceLanding, setLastActionResult]);

  const handleWorkspaceSelect = useCallback(async (workspaceId: string) => {
    if (!workspaceId || workspaceId === activeWorkspaceId) return;
    const result = await selectWorkspace(workspaceId, true);
    setLastActionResult(result);
    if (result.ok !== false) await openWorkspaceLanding();
  }, [activeWorkspaceId, openWorkspaceLanding, setLastActionResult]);

  const handleWorkspaceDelete = useCallback(async (workspaceId: string) => {
    if (!workspaceId || workspaceId === "default" || workspaceId === activeWorkspaceId) return;
    const previewResult = await deleteWorkspace(workspaceId, false);
    if (previewResult.requiresConfirmation !== true) {
      setLastActionResult(previewResult);
      return previewResult;
    }
    const result = await deleteWorkspace(workspaceId, true);
    setLastActionResult(result);
    if (result.ok !== false) await openWorkspaceLanding();
    return result;
  }, [activeWorkspaceId, openWorkspaceLanding, setLastActionResult]);

  const handleWorkspaceRename = useCallback(async (workspaceId: string, name: string) => {
    const nextName = name.trim();
    if (!workspaceId || !nextName) return;
    const previewResult = await renameWorkspace(workspaceId, nextName, false);
    if (previewResult.requiresConfirmation !== true) {
      setLastActionResult(previewResult);
      return previewResult;
    }
    const result = await renameWorkspace(workspaceId, nextName, true);
    setLastActionResult(result);
    if (result.ok !== false) await reloadWorkspaceSurface();
    return result;
  }, [reloadWorkspaceSurface, setLastActionResult]);

  return {
    handleWorkspaceCreate,
    handleWorkspaceDelete,
    handleWorkspaceRename,
    handleWorkspaceSelect,
  };
}
