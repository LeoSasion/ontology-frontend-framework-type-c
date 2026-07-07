import { useCallback, type Dispatch, type SetStateAction } from "react";
import { askAgent, askAgentReadOnly, confirmAction } from "./api";
import { actionErrorResult } from "./appWorkspaceModel";
import {
  refreshActionDrafts,
  refreshStatusAndDrafts,
  refreshStatusDashboardsWorkbenchDrafts,
} from "./appRefreshModel";
import type { AppSection } from "./components/Sidebar";
import type { ActionDraft, AgentAskResult, DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";

type AppAgentActionsOptions = {
  setActionDrafts: Dispatch<SetStateAction<ActionDraft[]>>;
  setActiveDashboardKey: Dispatch<SetStateAction<string>>;
  setAgent: Dispatch<SetStateAction<AgentAskResult>>;
  setDashboards: Dispatch<SetStateAction<DashboardPayload>>;
  setLastActionResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  setSection: Dispatch<SetStateAction<AppSection>>;
  setStatus: Dispatch<SetStateAction<WorkspaceStatus>>;
  setWorkbench: Dispatch<SetStateAction<WorkbenchPayload>>;
};

export function useAppAgentActions({
  setActionDrafts,
  setActiveDashboardKey,
  setAgent,
  setDashboards,
  setLastActionResult,
  setSection,
  setStatus,
  setWorkbench,
}: AppAgentActionsOptions) {
  const handleAsk = useCallback(async (prompt: string) => {
    try {
      const nextAgent = await askAgent(prompt);
      setAgent(nextAgent);
      setActionDrafts(await refreshActionDrafts());
      if (nextAgent.requiresConfirmation) {
        setSection("agent");
      }
      return nextAgent;
    } catch (error) {
      setLastActionResult(actionErrorResult("agent-ask", error));
      setSection("agent");
      return null;
    }
  }, [setActionDrafts, setAgent, setLastActionResult, setSection]);

  const handleAskReadOnly = useCallback(async (prompt: string) => {
    try {
      const nextAgent = await askAgentReadOnly(prompt);
      setAgent(nextAgent);
      setActionDrafts(await refreshActionDrafts());
    } catch (error) {
      setLastActionResult(actionErrorResult("agent-explain", error));
    }
  }, [setActionDrafts, setAgent, setLastActionResult]);

  const handleHomeAsk = useCallback(async (prompt: string) => {
    await handleAsk(prompt);
    setSection("agent");
  }, [handleAsk, setSection]);

  const handleDraftDashboard = useCallback(async () => {
    await handleAsk("帮我基于当前 source intelligence 生成一个可确认的经营看板草案");
    setSection("agent");
  }, [handleAsk, setSection]);

  const handleAgentCommandAsk = useCallback(async (prompt: string, targetSection?: AppSection) => {
    const nextAgent = await handleAsk(prompt);
    if (nextAgent?.requiresConfirmation) {
      setSection("agent");
      return;
    }
    setSection(targetSection ?? "agent");
  }, [handleAsk, setSection]);

  const handleConfirmDryRun = useCallback(async (actionKey: string) => {
    setLastActionResult(await confirmAction(actionKey, false));
  }, [setLastActionResult]);

  const handleConfirmAction = useCallback(async (actionKey: string) => {
    const result = await confirmAction(actionKey, true);
    const refreshed = await refreshStatusDashboardsWorkbenchDrafts();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setDashboards(refreshed.dashboards);
    setWorkbench(refreshed.workbench);
    setActionDrafts(refreshed.actionDrafts);
    if (typeof result.createdDashboardKey === "string") {
      setActiveDashboardKey(result.createdDashboardKey);
    }
    setSection("dashboards");
  }, [setActionDrafts, setActiveDashboardKey, setDashboards, setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleRejectAction = useCallback(async (actionKey: string) => {
    const result = await confirmAction(actionKey, true, true);
    const refreshed = await refreshStatusAndDrafts();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setActionDrafts(refreshed.actionDrafts);
    setSection("agent");
  }, [setActionDrafts, setLastActionResult, setSection, setStatus]);

  return {
    handleAgentCommandAsk,
    handleAsk,
    handleAskReadOnly,
    handleConfirmAction,
    handleConfirmDryRun,
    handleDraftDashboard,
    handleHomeAsk,
    handleRejectAction,
  };
}
