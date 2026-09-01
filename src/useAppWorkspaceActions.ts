import { useCallback, type Dispatch, type SetStateAction } from "react";
import { createWorkspace, deleteWorkspace, renameWorkspace, selectWorkspace } from "./api";
import type { AppSection } from "./components/Sidebar";
import { emptyAgentResult, emptyImportPreview, emptyQueryResult, emptyTableQuery } from "./emptyWorkspaceData";
import { refreshStatusDashboardsWorkbenchDrafts } from "./appRefreshModel";
import { preferredLandingSection } from "./appWorkspaceModel";
import { invalidateRelationshipRequests } from "./relationshipRequestGuard";
const loadTableQueryRuntime = () => import("./dashboardWidgetQueryRuntime");

async function activateTableQueryWorkspace(workspaceId: string) {
  const { activateTableQueryWorkspace: activate } = await loadTableQueryRuntime();
  activate(workspaceId);
}

async function resetTableQueryRuntime() {
  const { resetTableQueryRuntime: reset } = await loadTableQueryRuntime();
  reset();
}
import type { ActionDraft, AgentAskResult, DashboardPayload, ImportPreview, QueryResult, TableQueryPayload, WorkbenchPayload, WorkspaceStatus } from "./types";
import type { AppNavigationContext } from "./appNavigationModel";
import type { EvidenceFocus } from "./types";

type StateSetter<T> = Dispatch<SetStateAction<T>>;

type AppWorkspaceActionsOptions = {
  activeWorkspaceId: string;
  setActionDrafts: StateSetter<ActionDraft[]>;
  setActiveDashboardKey: StateSetter<string>;
  setActiveViewKey: StateSetter<string>;
  setAgent: StateSetter<AgentAskResult>;
  setDashboards: StateSetter<DashboardPayload>;
  setLastActionResult: StateSetter<Record<string, unknown> | null>;
  setPreview: StateSetter<ImportPreview>;
  setQuery: StateSetter<QueryResult>;
  setTableQuery: StateSetter<TableQueryPayload>;
  setNavigationContext: StateSetter<AppNavigationContext>;
  setEvidenceFocus: StateSetter<EvidenceFocus | null>;
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
  setPreview,
  setQuery,
  setTableQuery,
  setNavigationContext,
  setEvidenceFocus,
  setSection,
  setStatus,
  setWorkbench,
}: AppWorkspaceActionsOptions) {
  const reloadWorkspaceSurface = useCallback(async () => {
    invalidateRelationshipRequests();
    const surface = await refreshStatusDashboardsWorkbenchDrafts();
    await activateTableQueryWorkspace(surface.status.workspace.id);
    setStatus(surface.status);
    setWorkbench(surface.workbench);
    setDashboards(surface.dashboards);
    setAgent(emptyAgentResult);
    setPreview(emptyImportPreview);
    setQuery(emptyQueryResult);
    setTableQuery(emptyTableQuery);
    setActionDrafts(surface.actionDrafts);
    setActiveDashboardKey(surface.dashboards.dashboards[0]?.dashboard_key ?? "default");
    setActiveViewKey(surface.workbench.savedViews[0]?.view_key ?? "");
    return surface;
  }, [setActionDrafts, setActiveDashboardKey, setActiveViewKey, setAgent, setDashboards, setPreview, setQuery, setStatus, setTableQuery, setWorkbench]);

  const openWorkspaceLanding = useCallback(async (forceHome = false) => {
    const surface = await reloadWorkspaceSurface();
    setNavigationContext({});
    setEvidenceFocus(null);
    setSection(forceHome ? "home" : preferredLandingSection(surface.status, surface.workbench, surface.dashboards, surface.actionDrafts.length));
    return surface;
  }, [reloadWorkspaceSurface, setEvidenceFocus, setNavigationContext, setSection]);

  const handleWorkspaceCreate = useCallback(async (name: string) => {
    const previewResult = await createWorkspace(name, false);
    if (previewResult.requiresConfirmation !== true) {
      setLastActionResult(previewResult);
      return previewResult;
    }
    await resetTableQueryRuntime();
    let createdWorkspaceActivated = false;
    let result: Record<string, unknown>;
    try {
      result = await createWorkspace(name, true);
      const created = result.created && typeof result.created === "object" ? result.created as Record<string, unknown> : null;
      const createdWorkspaceId = typeof created?.id === "string" ? created.id : "";
      if (result.ok !== false && createdWorkspaceId) {
        createdWorkspaceActivated = true;
        await activateTableQueryWorkspace(createdWorkspaceId);
      } else {
        await activateTableQueryWorkspace(activeWorkspaceId);
      }
    } catch (error) {
      await activateTableQueryWorkspace(activeWorkspaceId);
      throw error;
    }
    setLastActionResult(result);
    const created = result.created && typeof result.created === "object" ? result.created as Record<string, unknown> : null;
    const createdWorkspaceId = typeof created?.id === "string" ? created.id : "";
    if (result.ok !== false && createdWorkspaceId) {
      setLastActionResult({ ...result, enteredWorkspace: createdWorkspaceId });
      const surface = await openWorkspaceLanding(true);
      if (surface.status.workspace.id !== createdWorkspaceId) throw new Error("Created workspace was not activated.");
      return { ...result, enteredWorkspace: createdWorkspaceId };
    }
    if (!createdWorkspaceActivated) await activateTableQueryWorkspace(activeWorkspaceId);
    return result;
  }, [activeWorkspaceId, openWorkspaceLanding, setLastActionResult]);

  const handleWorkspaceSelect = useCallback(async (workspaceId: string) => {
    if (!workspaceId || workspaceId === activeWorkspaceId) return;
    await resetTableQueryRuntime();
    let switched = false;
    try {
      const result = await selectWorkspace(workspaceId, true);
      setLastActionResult(result);
      if (result.ok === false) {
        await activateTableQueryWorkspace(activeWorkspaceId);
        return;
      }
      switched = true;
      await activateTableQueryWorkspace(workspaceId);
      await openWorkspaceLanding();
    } catch (error) {
      await activateTableQueryWorkspace(switched ? workspaceId : activeWorkspaceId);
      throw error;
    }
  }, [activeWorkspaceId, openWorkspaceLanding, setLastActionResult]);

  const handleWorkspaceDelete = useCallback(async (
    workspaceId: string,
    confirm = false,
    requestKey = "",
    expectedPlan = "",
  ) => {
    if (!workspaceId || workspaceId === "default" || workspaceId === activeWorkspaceId) return;
    const result = await deleteWorkspace(workspaceId, confirm, requestKey, expectedPlan);
    setLastActionResult(result);
    if (confirm && result.ok !== false) await openWorkspaceLanding();
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
