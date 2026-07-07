import { useCallback, type Dispatch, type SetStateAction } from "react";
import {
  businessDashboardOperation,
  dashboardFilterOperation,
  dashboardOperation,
  dashboardWidgetOperation,
  saveDashboardModules,
} from "./api";
import { actionErrorResult } from "./appWorkspaceModel";
import {
  refreshDashboardsAndWorkbench,
  refreshDashboards,
  refreshStatusAndDashboards,
  refreshStatusWorkbenchDashboards,
} from "./appRefreshModel";
import type { DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";

type AppDashboardActionsOptions = {
  setActiveDashboardKey: Dispatch<SetStateAction<string>>;
  setDashboards: Dispatch<SetStateAction<DashboardPayload>>;
  setLastActionResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  setStatus: Dispatch<SetStateAction<WorkspaceStatus>>;
  setWorkbench: Dispatch<SetStateAction<WorkbenchPayload>>;
};

export function useAppDashboardActions({
  setActiveDashboardKey,
  setDashboards,
  setLastActionResult,
  setStatus,
  setWorkbench,
}: AppDashboardActionsOptions) {
  const handleDashboardOperation = useCallback(async (options: { op: "create" | "copy" | "rename" | "delete"; dashboardKey?: string; sourceDashboardKey?: string; name?: string; table?: string; confirm?: boolean }) => {
    try {
      const result = await dashboardOperation(options);
      const refreshed = await refreshStatusAndDashboards();
      setLastActionResult(result);
      setStatus(refreshed.status);
      setDashboards(refreshed.dashboards);
      if (typeof result.dashboardKey === "string" && options.op !== "delete") {
        setActiveDashboardKey(result.dashboardKey);
      } else if (options.op === "delete") {
        setActiveDashboardKey(refreshed.dashboards.dashboards[0]?.dashboard_key ?? "default");
      }
    } catch (error) {
      setLastActionResult(actionErrorResult("dashboard-operation", error));
    }
  }, [setActiveDashboardKey, setDashboards, setLastActionResult, setStatus]);

  const handleDashboardFilterOperation = useCallback(async (options: Parameters<typeof dashboardFilterOperation>[0]) => {
    try {
      const result = await dashboardFilterOperation(options);
      const dashboards = await refreshDashboards();
      setLastActionResult(result as unknown as Record<string, unknown>);
      setDashboards(dashboards);
    } catch (error) {
      setLastActionResult(actionErrorResult("dashboard-filter", error));
    }
  }, [setDashboards, setLastActionResult]);

  const handleDashboardWidgetOperation = useCallback(async (options: Parameters<typeof dashboardWidgetOperation>[0]) => {
    try {
      const result = await dashboardWidgetOperation(options);
      const refreshed = await refreshDashboardsAndWorkbench();
      setLastActionResult(result);
      setDashboards(refreshed.dashboards);
      setWorkbench(refreshed.workbench);
      if (typeof result.dashboardKey === "string") {
        setActiveDashboardKey(result.dashboardKey);
      }
      return result;
    } catch (error) {
      const result = actionErrorResult("dashboard-widget", error);
      setLastActionResult(result);
      return result;
    }
  }, [setActiveDashboardKey, setDashboards, setLastActionResult, setWorkbench]);

  const handleDashboardModulesSave = useCallback(async (options: Parameters<typeof saveDashboardModules>[0]) => {
    try {
      const result = await saveDashboardModules(options);
      const refreshed = await refreshStatusWorkbenchDashboards();
      setLastActionResult(result);
      setStatus(refreshed.status);
      setDashboards(refreshed.dashboards);
      setWorkbench(refreshed.workbench);
      if (typeof result.savedDashboardKey === "string") {
        setActiveDashboardKey(result.savedDashboardKey);
      }
      return result;
    } catch (error) {
      const result = actionErrorResult("dashboard-modules", error);
      setLastActionResult(result);
      return result;
    }
  }, [setActiveDashboardKey, setDashboards, setLastActionResult, setStatus, setWorkbench]);

  const handleBusinessDashboardOperation = useCallback(async (options: Parameters<typeof businessDashboardOperation>[0]) => {
    try {
      const result = await businessDashboardOperation(options);
      const refreshed = await refreshStatusWorkbenchDashboards();
      setLastActionResult(result);
      setStatus(refreshed.status);
      setDashboards(refreshed.dashboards);
      setWorkbench(refreshed.workbench);
      const nextKey = typeof result.createdDashboardKey === "string"
        ? result.createdDashboardKey
        : typeof result.savedDashboardKey === "string"
          ? result.savedDashboardKey
          : "";
      if (nextKey) setActiveDashboardKey(nextKey);
      return result;
    } catch (error) {
      const result = actionErrorResult("business-dashboard", error);
      setLastActionResult(result);
      return result;
    }
  }, [setActiveDashboardKey, setDashboards, setLastActionResult, setStatus, setWorkbench]);

  return {
    handleBusinessDashboardOperation,
    handleDashboardFilterOperation,
    handleDashboardModulesSave,
    handleDashboardOperation,
    handleDashboardWidgetOperation,
  };
}
