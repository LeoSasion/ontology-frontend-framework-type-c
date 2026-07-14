import { useCallback, type Dispatch, type SetStateAction } from "react";
import { applyConfig, exportConfig, savePreferences, saveThemePalette, setDomainPack, validateConfig } from "./api";
import { refreshStatusWorkbenchDashboards, refreshWorkbench } from "./appRefreshModel";
import type { AppSection } from "./components/Sidebar";
import type { DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";

type AppSettingsActionsOptions = {
  setDashboards: Dispatch<SetStateAction<DashboardPayload>>;
  setLastActionResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  setSection: Dispatch<SetStateAction<AppSection>>;
  setStatus: Dispatch<SetStateAction<WorkspaceStatus>>;
  setWorkbench: Dispatch<SetStateAction<WorkbenchPayload>>;
};

export function useAppSettingsActions({ setDashboards, setLastActionResult, setSection, setStatus, setWorkbench }: AppSettingsActionsOptions) {
  const handleSavePreferences = useCallback(async (options: Parameters<typeof savePreferences>[0]) => {
    const result = await savePreferences(options);
    setLastActionResult(result);
    setWorkbench(await refreshWorkbench());
    setSection("settings");
  }, [setLastActionResult, setSection, setWorkbench]);

  const handleSaveThemePalette = useCallback(async (options: Parameters<typeof saveThemePalette>[0]) => {
    const result = await saveThemePalette(options);
    setLastActionResult(result);
    setWorkbench(await refreshWorkbench());
    setSection("settings");
  }, [setLastActionResult, setSection, setWorkbench]);

  const handleValidateConfig = useCallback(async () => {
    const result = await validateConfig();
    setLastActionResult(result);
    return result;
  }, [setLastActionResult]);

  const handleExportConfig = useCallback(async () => {
    const result = await exportConfig();
    setLastActionResult(result);
    return result;
  }, [setLastActionResult]);

  const handleApplyConfig = useCallback(async (options: Parameters<typeof applyConfig>[0]) => {
    const result = await applyConfig(options);
    setLastActionResult(result);
    if (options.confirm) {
      const refreshed = await refreshStatusWorkbenchDashboards();
      setStatus(refreshed.status);
      setWorkbench(refreshed.workbench);
      setDashboards(refreshed.dashboards);
    }
    setSection("settings");
    return result;
  }, [setDashboards, setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleSetDomainPack = useCallback(async (options: Parameters<typeof setDomainPack>[0]) => {
    const result = await setDomainPack(options);
    setLastActionResult(result);
    if (options.confirm) {
      const refreshed = await refreshStatusWorkbenchDashboards();
      setStatus(refreshed.status);
      setWorkbench(refreshed.workbench);
      setDashboards(refreshed.dashboards);
    }
    setSection("settings");
    return result;
  }, [setDashboards, setLastActionResult, setSection, setStatus, setWorkbench]);

  return {
    handleApplyConfig,
    handleExportConfig,
    handleSavePreferences,
    handleSaveThemePalette,
    handleSetDomainPack,
    handleValidateConfig,
  };
}
