import { useCallback, useRef, type Dispatch, type SetStateAction } from "react";
import { askAgent, askAgentReadOnly, confirmAction } from "./api";
import { actionErrorResult } from "./appWorkspaceModel";
import {
  refreshActionDrafts,
  refreshStatusAndDrafts,
  refreshStatusDashboardsWorkbenchDrafts,
} from "./appRefreshModel";
import type { AppSection } from "./components/Sidebar";
import type { AppNavigationTarget } from "./appNavigationModel";
import type { ActionDraft, AgentAskResult, DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";

type AppAgentActionsOptions = {
  activeWorkspaceId: string;
  setActionDrafts: Dispatch<SetStateAction<ActionDraft[]>>;
  setActiveDashboardKey: Dispatch<SetStateAction<string>>;
  setAgent: Dispatch<SetStateAction<AgentAskResult>>;
  setDashboards: Dispatch<SetStateAction<DashboardPayload>>;
  setLastActionResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  navigateTo: (target: AppNavigationTarget) => void;
  setStatus: Dispatch<SetStateAction<WorkspaceStatus>>;
  setWorkbench: Dispatch<SetStateAction<WorkbenchPayload>>;
};

export function useAppAgentActions({
  activeWorkspaceId,
  setActionDrafts,
  setActiveDashboardKey,
  setAgent,
  setDashboards,
  setLastActionResult,
  navigateTo,
  setStatus,
  setWorkbench,
}: AppAgentActionsOptions) {
  const requestRef = useRef(0);
  const handleAsk = useCallback(async (prompt: string) => {
    const requestId = ++requestRef.current;
    try {
      const nextAgent = await askAgent(prompt, { workspaceId: activeWorkspaceId });
      if (requestRef.current !== requestId || nextAgent.workspaceId !== activeWorkspaceId) return null;
      setAgent(nextAgent);
      setActionDrafts(await refreshActionDrafts());
      if (nextAgent.requiresConfirmation) {
        navigateTo({
          section: "agent",
          actionKey: nextAgent.actionDraft?.actionKey,
          tableKey: nextAgent.matched.table?.table_key,
          dashboardKey: nextAgent.matched.dashboard?.dashboard_key,
        });
      }
      return nextAgent;
    } catch (error) {
      setLastActionResult(actionErrorResult("agent-ask", error));
      navigateTo({ section: "agent" });
      return null;
    }
  }, [activeWorkspaceId, navigateTo, setActionDrafts, setAgent, setLastActionResult]);

  const handleAskBranch = useCallback(async (prompt: string, parentRunKey: string, branchLabel = "") => {
    try {
      const nextAgent = await askAgent(prompt, { parentRunKey, branchLabel, workspaceId: activeWorkspaceId });
      if (nextAgent.workspaceId !== activeWorkspaceId) return null;
      setAgent(nextAgent);
      setActionDrafts(await refreshActionDrafts());
      navigateTo({
        section: "agent",
        actionKey: nextAgent.actionDraft?.actionKey,
        tableKey: nextAgent.matched.table?.table_key,
        dashboardKey: nextAgent.matched.dashboard?.dashboard_key,
      });
      return nextAgent;
    } catch (error) {
      setLastActionResult(actionErrorResult("analysis-branch", error));
      navigateTo({ section: "agent" });
      return null;
    }
  }, [activeWorkspaceId, navigateTo, setActionDrafts, setAgent, setLastActionResult]);

  const handleAskReadOnly = useCallback(async (prompt: string) => {
    try {
      const nextAgent = await askAgentReadOnly(prompt, activeWorkspaceId);
      if (nextAgent.workspaceId !== activeWorkspaceId) return;
      setAgent(nextAgent);
      setActionDrafts(await refreshActionDrafts());
    } catch (error) {
      setLastActionResult(actionErrorResult("agent-explain", error));
    }
  }, [activeWorkspaceId, setActionDrafts, setAgent, setLastActionResult]);

  const handleHomeAsk = useCallback(async (prompt: string) => {
    await handleAsk(prompt);
    navigateTo({ section: "agent" });
  }, [handleAsk, navigateTo]);

  const handleDraftDashboard = useCallback(async () => {
    await handleAsk("帮我基于当前 Source Intelligence 生成一个可确认的分析看板草案");
    navigateTo({ section: "agent" });
  }, [handleAsk, navigateTo]);

  const handleAgentCommandAsk = useCallback(async (prompt: string, targetSection?: AppSection) => {
    const nextAgent = await handleAsk(prompt);
    if (nextAgent?.requiresConfirmation) {
      navigateTo({
        section: "agent",
        actionKey: nextAgent.actionDraft?.actionKey,
        tableKey: nextAgent.matched.table?.table_key,
        dashboardKey: nextAgent.matched.dashboard?.dashboard_key,
      });
      return;
    }
    navigateTo({
      section: targetSection ?? "agent",
      tableKey: nextAgent?.matched.table?.table_key,
      dashboardKey: nextAgent?.matched.dashboard?.dashboard_key,
    });
  }, [handleAsk, navigateTo]);

  const handleConfirmDryRun = useCallback(async (actionKey: string) => {
    const result = await confirmAction(actionKey, false, false, activeWorkspaceId);
    if (result.workspaceId === activeWorkspaceId) setLastActionResult(result);
  }, [activeWorkspaceId, setLastActionResult]);

  const handleConfirmAction = useCallback(async (actionKey: string) => {
    const result = await confirmAction(actionKey, true, false, activeWorkspaceId);
    if (result.workspaceId !== activeWorkspaceId) return;
    const refreshed = await refreshStatusDashboardsWorkbenchDrafts();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setDashboards(refreshed.dashboards);
    setWorkbench(refreshed.workbench);
    setActionDrafts(refreshed.actionDrafts);
    if (typeof result.createdDashboardKey === "string") {
      setActiveDashboardKey(result.createdDashboardKey);
    }
    navigateTo({
      section: "dashboards",
      actionKey,
      dashboardKey: typeof result.createdDashboardKey === "string" ? result.createdDashboardKey : undefined,
    });
  }, [activeWorkspaceId, navigateTo, setActionDrafts, setActiveDashboardKey, setDashboards, setLastActionResult, setStatus, setWorkbench]);

  const handleRejectAction = useCallback(async (actionKey: string) => {
    const result = await confirmAction(actionKey, true, true, activeWorkspaceId);
    if (result.workspaceId !== activeWorkspaceId) return;
    const refreshed = await refreshStatusAndDrafts();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setActionDrafts(refreshed.actionDrafts);
    navigateTo({ section: "agent", actionKey });
  }, [activeWorkspaceId, navigateTo, setActionDrafts, setLastActionResult, setStatus]);

  return {
    handleAgentCommandAsk,
    handleAsk,
    handleAskBranch,
    handleAskReadOnly,
    handleConfirmAction,
    handleConfirmDryRun,
    handleDraftDashboard,
    handleHomeAsk,
    handleRejectAction,
  };
}
