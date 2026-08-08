import { useCallback, useRef, type Dispatch, type SetStateAction } from "react";
import { askAgent, askAgentReadOnly, confirmAction } from "./api";
import { actionErrorResult } from "./appWorkspaceModel";
import {
  refreshActionDrafts,
  refreshStatusAndDrafts,
  refreshStatusDashboardsWorkbenchDrafts,
} from "./appRefreshModel";
import { confirmedActionNavigationTarget } from "./agentActionNavigationModel";
import type { AppSection } from "./components/Sidebar";
import type { AppNavigationTarget } from "./appNavigationModel";
import type { ActionDraft, AgentAskResult, DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";
import { ApiPayloadError } from "./apiClient";

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
  const storageKey = `aibi.agentSession.${activeWorkspaceId}`;
  const activeSessionKey = () => {
    if (typeof window === "undefined") return "";
    try {
      return window.localStorage.getItem(storageKey) ?? "";
    } catch {
      return "";
    }
  };
  const rememberSession = (sessionKey: string) => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(storageKey, sessionKey);
    } catch {
      // Session continuity is optional when browser storage is disabled.
    }
  };
  const requestWithSessionRecovery = (request: (sessionKey?: string) => Promise<AgentAskResult>) => {
    const sessionKey = activeSessionKey() || undefined;
    return request(sessionKey).catch((error) => {
      const payloadCode = error instanceof ApiPayloadError ? String(error.payload.errorCode ?? error.payload.code ?? "") : "";
      const unknownSession = payloadCode === "unknown-agent-session"
        || (error instanceof Error ? error.message : String(error)).toLowerCase().includes("unknown agent session");
      if (!sessionKey || !unknownSession) throw error;
      rememberSession("");
      return request();
    });
  };
  const handleAsk = useCallback(async (prompt: string) => {
    const requestId = ++requestRef.current;
    setLastActionResult(null);
    try {
      const nextAgent = await requestWithSessionRecovery((sessionKey) => askAgent(prompt, { workspaceId: activeWorkspaceId, sessionKey }));
      if (requestRef.current !== requestId || nextAgent.workspaceId !== activeWorkspaceId) return null;
      setAgent(nextAgent);
      if (nextAgent.agentSession?.sessionKey) rememberSession(nextAgent.agentSession.sessionKey);
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
      const nextAgent = await requestWithSessionRecovery((sessionKey) => askAgent(prompt, { parentRunKey, branchLabel, workspaceId: activeWorkspaceId, sessionKey }));
      if (nextAgent.workspaceId !== activeWorkspaceId) return null;
      setAgent(nextAgent);
      if (nextAgent.agentSession?.sessionKey) rememberSession(nextAgent.agentSession.sessionKey);
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
      const nextAgent = await requestWithSessionRecovery((sessionKey) => askAgentReadOnly(prompt, activeWorkspaceId, sessionKey));
      if (nextAgent.workspaceId !== activeWorkspaceId) return;
      setAgent(nextAgent);
      if (nextAgent.agentSession?.sessionKey) rememberSession(nextAgent.agentSession.sessionKey);
      setActionDrafts(await refreshActionDrafts());
    } catch (error) {
      setLastActionResult(actionErrorResult("agent-explain", error));
    }
  }, [activeWorkspaceId, setActionDrafts, setAgent, setLastActionResult]);

  const handleHomeAsk = useCallback(async (prompt: string) => {
    return handleAsk(prompt);
  }, [handleAsk]);

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

  const handleConfirmAction = useCallback(async (actionKey: string, draft?: ActionDraft) => {
    const result = await confirmAction(actionKey, true, false, activeWorkspaceId);
    if (result.workspaceId !== activeWorkspaceId) return;
    const refreshed = await refreshStatusDashboardsWorkbenchDrafts();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setDashboards(refreshed.dashboards);
    setWorkbench(refreshed.workbench);
    setActionDrafts(refreshed.actionDrafts);
    const target = confirmedActionNavigationTarget(actionKey, result, draft);
    if (target.section === "dashboards" && target.dashboardKey) setActiveDashboardKey(target.dashboardKey);
    navigateTo(target);
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
