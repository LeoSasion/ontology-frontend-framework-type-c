import { useCallback, useRef, type Dispatch, type SetStateAction } from "react";
import {
  commitImport,
  commitFolderImport,
  copyView,
  createSourceDashboardDraft,
  deleteSource,
  deleteView,
  inspectSource,
  navigationOperation,
  previewFolderImport,
  previewImportWithOptions,
  removeConnector,
  removeImportJob,
  renameSource,
  runQuery,
  runSourceIntelligence,
  runTableQuery,
  saveConnector,
  saveView,
  setImportPolicy,
  syncConnector,
} from "./api";
import type { AppNavigationTarget } from "./appNavigationModel";
import type { AppSection } from "./appSections";
import { actionErrorResult, normalizeQuery } from "./appWorkspaceModel";
import type { RelationshipSaveOptions } from "./dashboardCanvasContracts";
import {
  refreshStatusAndWorkbench,
  refreshStatusWorkbenchDashboards,
  refreshStatusWorkbenchDrafts,
  refreshWorkbench,
} from "./appRefreshModel";
import type { SourceIntelligenceRunOptions } from "./sourceIntelligenceRunModel";
import { fetchAnalysisJobs } from "./apiJobs";
import type { AnalysisJob } from "./typesJobs";
import type {
  ActionDraft,
  DashboardPayload,
  FormulaPreviewPayload,
  ImportPreview,
  QueryResult,
  TableQueryPayload,
  WorkbenchPayload,
  WorkspaceStatus,
} from "./types";

type ApiModel = typeof import("./apiModel");
const loadApiModel = () => import("./apiModel");
const loadRelationshipWorkspaceActions = () => import("./relationshipWorkspaceActions");

type AppDataActionsOptions = {
  activeWorkspaceId: string;
  setActionDrafts: Dispatch<SetStateAction<ActionDraft[]>>;
  setActiveViewKey: Dispatch<SetStateAction<string>>;
  setDashboards: Dispatch<SetStateAction<DashboardPayload>>;
  setFormulaPreview: Dispatch<SetStateAction<FormulaPreviewPayload>>;
  setLastActionResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  setPreview: Dispatch<SetStateAction<ImportPreview>>;
  setQuery: Dispatch<SetStateAction<QueryResult>>;
  navigateTo: (target: AppNavigationTarget) => void;
  setStatus: Dispatch<SetStateAction<WorkspaceStatus>>;
  setTableQuery: Dispatch<SetStateAction<TableQueryPayload>>;
  setWorkbench: Dispatch<SetStateAction<WorkbenchPayload>>;
};

function resultString(result: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const value = result[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return undefined;
}

const TERMINAL_JOB_STATUSES = new Set(["succeeded", "failed", "canceled"]);

function waitForJobPoll(milliseconds: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));
}

function jobFailureMessage(job: AnalysisJob) {
  const detail = job.error?.message ?? job.error?.reason ?? job.error?.code;
  return String(detail || (job.status === "canceled" ? "任务已取消。" : "Source Intelligence 任务未完成。"));
}

export function useAppDataActions({
  activeWorkspaceId,
  setActionDrafts,
  setActiveViewKey,
  setDashboards,
  setFormulaPreview,
  setLastActionResult,
  setPreview,
  setQuery,
  navigateTo,
  setStatus,
  setTableQuery,
  setWorkbench,
}: AppDataActionsOptions) {
  const sourceIntelligenceRequestRef = useRef(0);
  const setSection = useCallback((section: AppSection) => navigateTo({ section }), [navigateTo]);
  const handlePreview = useCallback(async (options: { filePath: string; table?: string; uniqueFields?: string[]; conflictRule?: string }) => {
    const result = await previewImportWithOptions(options);
    setPreview(result);
    setSection("sources");
    return result;
  }, [setPreview, setSection]);

  const handleCommitImport = useCallback(async (options: { filePath: string; table?: string; name?: string; mode?: string; uniqueFields?: string[]; conflictRule?: string; confirm?: boolean }) => {
    const result = await commitImport(options);
    const refreshed = await refreshStatusAndWorkbench();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    navigateTo({
      section: "sources",
      tableKey: resultString(result, "tableKey", "table_key") ?? options.table ?? refreshed.workbench.tables[0]?.table_key,
    });
  }, [navigateTo, setLastActionResult, setStatus, setWorkbench]);

  const handlePreviewFolderImport = useCallback(async (options: { path: string; limit?: number; recursive?: boolean; uniqueFields?: string[]; conflictRule?: string }) => {
    const result = await previewFolderImport(options);
    setSection("sources");
    return result;
  }, [setSection]);

  const handleCommitFolderImport = useCallback(async (options: { path: string; limit?: number; recursive?: boolean; uniqueFields?: string[]; conflictRule?: string; expectedPlan?: string; confirm?: boolean }) => {
    const result = await commitFolderImport(options);
    const refreshed = await refreshStatusAndWorkbench();
    setLastActionResult(result as unknown as Record<string, unknown>);
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    navigateTo({ section: "sources", tableKey: result.groups[0]?.tableKey ?? refreshed.workbench.tables[0]?.table_key });
    return result;
  }, [navigateTo, setLastActionResult, setStatus, setWorkbench]);

  const handleImportPolicy = useCallback(async (options: { table: string; uniqueFields: string[]; conflictRule?: string; confirm?: boolean }) => {
    const result = await setImportPolicy(options);
    setLastActionResult(result);
    setWorkbench(await refreshWorkbench());
    setSection("sources");
  }, [setLastActionResult, setSection, setWorkbench]);

  const handleRemoveImportJob = useCallback(async (options: { jobKey: string; confirm?: boolean }) => {
    const result = await removeImportJob(options);
    setLastActionResult(result);
    setWorkbench(await refreshWorkbench());
    setSection("sources");
  }, [setLastActionResult, setSection, setWorkbench]);

  const handleInspectSource = useCallback(async (table: string) => {
    const result = await inspectSource(table);
    setLastActionResult(result);
    navigateTo({ section: "sources", tableKey: table });
  }, [navigateTo, setLastActionResult]);

  const handleRenameSource = useCallback(async (options: { source: string; name: string; confirm?: boolean }) => {
    const result = await renameSource(options);
    const refreshed = await refreshStatusWorkbenchDashboards();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    setDashboards(refreshed.dashboards);
    setSection("sources");
  }, [setDashboards, setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleNavigationOperation = useCallback(async (options: Parameters<typeof navigationOperation>[0]) => {
    const result = await navigationOperation(options);
    setLastActionResult(result);
    if (options.confirm) {
      const refreshed = await refreshStatusWorkbenchDashboards();
      setStatus(refreshed.status);
      setWorkbench(refreshed.workbench);
      setDashboards(refreshed.dashboards);
    }
    setSection("sources");
    return result;
  }, [setDashboards, setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleDeleteSource = useCallback(async (options: { source: string; confirm?: boolean }) => {
    const result = await deleteSource(options);
    const refreshed = await refreshStatusWorkbenchDashboards();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    setDashboards(refreshed.dashboards);
    setSection("sources");
  }, [setDashboards, setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleSaveConnector = useCallback(async (options: Parameters<typeof saveConnector>[0]) => {
    const result = await saveConnector(options);
    const refreshed = await refreshStatusAndWorkbench();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    setSection("sources");
  }, [setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleSyncConnector = useCallback(async (options: Parameters<typeof syncConnector>[0]) => {
    const result = await syncConnector(options);
    const refreshed = await refreshStatusAndWorkbench();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleRemoveConnector = useCallback(async (options: Parameters<typeof removeConnector>[0]) => {
    const result = await removeConnector(options);
    const refreshed = await refreshStatusAndWorkbench();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    setSection("sources");
  }, [setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleQuery = useCallback(async (options?: { table?: string; group?: string; measure?: string; aggregation?: string; limit?: number }) => {
    if (!options?.table) {
      setLastActionResult(actionErrorResult("query", new Error("请选择数据表后再运行查询。")));
      setSection("sources");
      return;
    }
    try {
      setQuery(normalizeQuery(await runQuery({ ...options, table: options.table })));
    } catch (error) {
      setLastActionResult(actionErrorResult("query", error));
    }
    setSection("sources");
  }, [setLastActionResult, setQuery, setSection]);

  const handleTableQuery = useCallback(async (options: Parameters<typeof runTableQuery>[0]) => {
    try {
      const result = await runTableQuery(options);
      setTableQuery(result);
      navigateTo({
        section: "views",
        tableKey: result.tableQuery.tableKey,
        viewKey: result.tableQuery.viewKey,
      });
    } catch (error) {
      setLastActionResult(actionErrorResult("query-table", error));
      navigateTo({ section: "views" });
    }
  }, [navigateTo, setLastActionResult, setTableQuery]);

  const handleSaveView = useCallback(async (options: Parameters<typeof saveView>[0]) => {
    const result = await saveView(options);
    const nextWorkbench = await refreshWorkbench();
    setLastActionResult(result);
    setWorkbench(nextWorkbench);
    if (typeof (result as Record<string, unknown>).savedView === "object") {
      const savedView = (result as { savedView?: { view_key?: string } }).savedView;
      if (savedView?.view_key) setActiveViewKey(savedView.view_key);
      navigateTo({ section: "views", viewKey: savedView?.view_key });
      return;
    }
    navigateTo({ section: "views" });
  }, [navigateTo, setActiveViewKey, setLastActionResult, setWorkbench]);

  const handleCopyView = useCallback(async (options: Parameters<typeof copyView>[0]) => {
    const result = await copyView(options);
    const nextWorkbench = await refreshWorkbench();
    setLastActionResult(result);
    setWorkbench(nextWorkbench);
    const savedView = (result as { savedView?: { view_key?: string } }).savedView;
    if (savedView?.view_key) setActiveViewKey(savedView.view_key);
    navigateTo({ section: "views", viewKey: savedView?.view_key });
  }, [navigateTo, setActiveViewKey, setLastActionResult, setWorkbench]);

  const handleDeleteView = useCallback(async (options: Parameters<typeof deleteView>[0]) => {
    const result = await deleteView(options);
    const nextWorkbench = await refreshWorkbench();
    setLastActionResult(result);
    setWorkbench(nextWorkbench);
    setActiveViewKey(nextWorkbench.savedViews[0]?.view_key ?? "");
    navigateTo({ section: "views", viewKey: nextWorkbench.savedViews[0]?.view_key });
  }, [navigateTo, setActiveViewKey, setLastActionResult, setWorkbench]);

  const handleFieldUpdate = useCallback(async (options: Parameters<ApiModel["updateFieldConfig"]>[0]) => {
    const { updateFieldConfig } = await loadApiModel();
    const result = await updateFieldConfig(options);
    setLastActionResult(result);
    if (options.confirm) {
      setWorkbench(await refreshWorkbench());
    }
  }, [setLastActionResult, setWorkbench]);

  const handleInferSemantics = useCallback(async (options: Parameters<ApiModel["inferSemantics"]>[0]) => {
    const { inferSemantics } = await loadApiModel();
    const result = await inferSemantics(options);
    setLastActionResult(result);
    if (options.confirm) {
      const refreshed = await refreshStatusAndWorkbench();
      setWorkbench(refreshed.workbench);
      setStatus(refreshed.status);
    }
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleSetSemantic = useCallback(async (options: Parameters<ApiModel["setSemantic"]>[0] & { stayOnPage?: boolean }) => {
    const { setSemantic } = await loadApiModel();
    const { stayOnPage = false, ...semanticOptions } = options;
    const result = await setSemantic(semanticOptions);
    setLastActionResult(result);
    if (semanticOptions.confirm) {
      const refreshed = await refreshStatusAndWorkbench();
      setWorkbench(refreshed.workbench);
      setStatus(refreshed.status);
    }
    if (!stayOnPage) setSection("sources");
    return result;
  }, [setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleInferMetrics = useCallback(async (options: Parameters<ApiModel["inferMetrics"]>[0]) => {
    const { inferMetrics } = await loadApiModel();
    const result = await inferMetrics(options);
    setLastActionResult(result);
    if (options.confirm) {
      const refreshed = await refreshStatusAndWorkbench();
      setWorkbench(refreshed.workbench);
      setStatus(refreshed.status);
    }
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleAddMetric = useCallback(async (options: Parameters<ApiModel["addMetric"]>[0]) => {
    const { addMetric } = await loadApiModel();
    const result = await addMetric(options);
    setLastActionResult(result);
    if (options.confirm) {
      const refreshed = await refreshStatusAndWorkbench();
      setWorkbench(refreshed.workbench);
      setStatus(refreshed.status);
    }
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleQueryMetric = useCallback(async (options: Parameters<ApiModel["queryMetric"]>[0]) => {
    const { queryMetric } = await loadApiModel();
    const result = await queryMetric(options);
    setLastActionResult(result);
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection]);

  const handleRelationshipPreview = useCallback(async (options: RelationshipSaveOptions) => {
    const { previewWorkspaceRelationship } = await loadRelationshipWorkspaceActions();
    const result = await previewWorkspaceRelationship(activeWorkspaceId, options);
    if (!result) return;
    setSection("sources");
    return result;
  }, [activeWorkspaceId, setSection]);

  const handleRelationshipSave = useCallback(async (options: RelationshipSaveOptions) => {
    const { saveWorkspaceRelationship } = await loadRelationshipWorkspaceActions();
    const outcome = await saveWorkspaceRelationship(activeWorkspaceId, options, Boolean(options.confirm));
    if (!outcome) return;
    if (outcome.surface) {
      if (outcome.surface.status.workspace.id !== activeWorkspaceId) return;
      setStatus(outcome.surface.status);
      setWorkbench(outcome.surface.workbench);
    }
    setSection("sources");
    return outcome.result;
  }, [activeWorkspaceId, setSection, setStatus, setWorkbench]);

  const handleDashboardRelationshipSave = useCallback(async (options: RelationshipSaveOptions) => {
    const { saveWorkspaceRelationship } = await loadRelationshipWorkspaceActions();
    const outcome = await saveWorkspaceRelationship(activeWorkspaceId, options, true);
    if (!outcome?.surface) {
      return { ok: false, stale: true, workspaceId: activeWorkspaceId };
    }
    setLastActionResult(outcome.result as unknown as Record<string, unknown>);
    setStatus(outcome.surface.status);
    setWorkbench(outcome.surface.workbench);
    return outcome.result as unknown as Record<string, unknown>;
  }, [activeWorkspaceId, setLastActionResult, setStatus, setWorkbench]);

  const handleFormulaPreview = useCallback(async (options: Parameters<ApiModel["previewFormula"]>[0]) => {
    const { previewFormula } = await loadApiModel();
    setFormulaPreview(await previewFormula(options));
    setSection("sources");
  }, [setFormulaPreview, setSection]);

  const handleSaveFormula = useCallback(async (options: Parameters<ApiModel["saveFormula"]>[0]) => {
    const { saveFormula } = await loadApiModel();
    const result = await saveFormula(options);
    setLastActionResult(result as unknown as Record<string, unknown>);
    if (options.confirm) {
      setWorkbench(await refreshWorkbench());
    }
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection, setWorkbench]);

  const handleDeleteFormula = useCallback(async (options: Parameters<ApiModel["deleteFormula"]>[0]) => {
    const { deleteFormula } = await loadApiModel();
    const result = await deleteFormula(options);
    setLastActionResult(result as unknown as Record<string, unknown>);
    if (options.confirm) {
      setWorkbench(await refreshWorkbench());
    }
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection, setWorkbench]);

  const handleSourceIntelligenceRun = useCallback(async (options?: SourceIntelligenceRunOptions) => {
    const { stayOnPage = false, inputs = [], ...sourceOptions } = options ?? { inputs: [] };
    const hasInputs = inputs.length > 0;
    if (!hasInputs) {
      const result = actionErrorResult("source-intelligence", new Error("请先在数据源工作台选择本地文件或文件夹。"));
      setLastActionResult(result);
      if (!stayOnPage) setSection("sources");
      return result;
    }
    const requestId = sourceIntelligenceRequestRef.current + 1;
    sourceIntelligenceRequestRef.current = requestId;
    const request = { ...sourceOptions, async: true, inputs, workspaceId: activeWorkspaceId };
    try {
      const accepted = await runSourceIntelligence(request);
      if (!("job" in accepted)) {
        const result = accepted;
        if (sourceIntelligenceRequestRef.current !== requestId || result.workspaceId !== activeWorkspaceId) return result;
        setLastActionResult(result);
        const refreshed = await refreshStatusAndWorkbench();
        if (sourceIntelligenceRequestRef.current !== requestId || refreshed.status.workspace.id !== result.workspaceId) return result;
        setWorkbench(refreshed.workbench);
        setStatus(refreshed.status);
        if (!stayOnPage) {
          navigateTo({
            section: "dashboards",
            allowLocked: true,
            tableKey: result.tableKey ?? refreshed.workbench.tables[0]?.table_key,
            sourceRunKey: result.runKey,
          });
        }
        return result;
      }

      let job = accepted.job;
      setLastActionResult(accepted as unknown as Record<string, unknown>);
      while (!TERMINAL_JOB_STATUSES.has(job.status)) {
        await waitForJobPoll(1200);
        const payload = await fetchAnalysisJobs({ jobKey: job.jobKey });
        if (!payload.job) throw new Error(`任务状态不可用：${job.jobKey}`);
        job = payload.job;
        if (sourceIntelligenceRequestRef.current !== requestId) return accepted as unknown as Record<string, unknown>;
        setLastActionResult({ ok: true, action: "source-intelligence-job", job });
      }
      if (job.status !== "succeeded" || !job.result || typeof job.result !== "object" || Array.isArray(job.result)) {
        throw new Error(jobFailureMessage(job));
      }
      const result = job.result as Record<string, unknown> & { workspaceId?: string; tableKey?: string; runKey?: string };
      if (sourceIntelligenceRequestRef.current !== requestId || result.workspaceId !== activeWorkspaceId) return result;
      setLastActionResult(result);
      const refreshed = await refreshStatusAndWorkbench();
      if (sourceIntelligenceRequestRef.current !== requestId || refreshed.status.workspace.id !== result.workspaceId) return result;
      setWorkbench(refreshed.workbench);
      setStatus(refreshed.status);
      if (!stayOnPage) {
        navigateTo({
          section: "dashboards",
          allowLocked: true,
          tableKey: result.tableKey || refreshed.workbench.tables[0]?.table_key,
          sourceRunKey: result.runKey,
        });
      }
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || "Source Intelligence failed");
      setLastActionResult({
        ok: false,
        action: "source-intelligence",
        error: message,
      });
      if (!stayOnPage) setSection("sources");
      throw error;
    }
  }, [activeWorkspaceId, navigateTo, setLastActionResult, setSection, setStatus, setWorkbench]);

  const handleSourceDashboardDraft = useCallback(async (options: Parameters<typeof createSourceDashboardDraft>[0]) => {
    const result = await createSourceDashboardDraft(options);
    const refreshed = await refreshStatusWorkbenchDrafts();
    setLastActionResult(result);
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    setActionDrafts(refreshed.actionDrafts);
    navigateTo({
      section: "agent",
      actionKey: resultString(result, "actionKey", "action_key"),
      tableKey: resultString(result, "tableKey", "table_key"),
    });
    return result;
  }, [navigateTo, setActionDrafts, setLastActionResult, setStatus, setWorkbench]);

  return {
    handleAddMetric,
    handleCommitImport,
    handleCommitFolderImport,
    handleCopyView,
    handleDashboardRelationshipSave,
    handleDeleteFormula,
    handleDeleteSource,
    handleDeleteView,
    handleFieldUpdate,
    handleFormulaPreview,
    handleImportPolicy,
    handleInferMetrics,
    handleInferSemantics,
    handleInspectSource,
    handleNavigationOperation,
    handlePreview,
    handlePreviewFolderImport,
    handleQuery,
    handleQueryMetric,
    handleRelationshipPreview,
    handleRelationshipSave,
    handleRemoveConnector,
    handleRemoveImportJob,
    handleRenameSource,
    handleSaveConnector,
    handleSaveFormula,
    handleSaveView,
    handleSetSemantic,
    handleSourceDashboardDraft,
    handleSourceIntelligenceRun,
    handleSyncConnector,
    handleTableQuery,
  };
}
