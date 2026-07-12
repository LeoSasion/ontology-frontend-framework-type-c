import { useCallback, useRef, type Dispatch, type SetStateAction } from "react";
import {
  addMetric,
  commitImport,
  commitFolderImport,
  copyView,
  createSourceDashboardDraft,
  deleteFormula,
  deleteSource,
  deleteView,
  inferMetrics,
  inferSemantics,
  inspectSource,
  navigationOperation,
  previewFormula,
  previewFolderImport,
  previewImportWithOptions,
  previewRelationship,
  queryMetric,
  removeConnector,
  removeImportJob,
  renameSource,
  runQuery,
  runSourceIntelligence,
  runTableQuery,
  saveConnector,
  saveFormula,
  saveRelationship,
  saveView,
  setImportPolicy,
  setSemantic,
  syncConnector,
  updateFieldConfig,
} from "./api";
import type { AppNavigationTarget } from "./appNavigationModel";
import type { AppSection } from "./appSections";
import { actionErrorResult, normalizeQuery } from "./appWorkspaceModel";
import {
  refreshStatusAndWorkbench,
  refreshStatusWorkbenchDashboards,
  refreshStatusWorkbenchDrafts,
  refreshWorkbench,
} from "./appRefreshModel";
import type { SourceIntelligenceRunOptions } from "./sourceIntelligenceRunModel";
import type {
  ActionDraft,
  DashboardPayload,
  FormulaPreviewPayload,
  ImportPreview,
  QueryResult,
  RelationshipPreviewPayload,
  TableQueryPayload,
  WorkbenchPayload,
  WorkspaceStatus,
} from "./types";

type AppDataActionsOptions = {
  activeWorkspaceId: string;
  setActionDrafts: Dispatch<SetStateAction<ActionDraft[]>>;
  setActiveViewKey: Dispatch<SetStateAction<string>>;
  setDashboards: Dispatch<SetStateAction<DashboardPayload>>;
  setFormulaPreview: Dispatch<SetStateAction<FormulaPreviewPayload>>;
  setLastActionResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  setPreview: Dispatch<SetStateAction<ImportPreview>>;
  setQuery: Dispatch<SetStateAction<QueryResult>>;
  setRelationshipPreview: Dispatch<SetStateAction<RelationshipPreviewPayload>>;
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

export function useAppDataActions({
  activeWorkspaceId,
  setActionDrafts,
  setActiveViewKey,
  setDashboards,
  setFormulaPreview,
  setLastActionResult,
  setPreview,
  setQuery,
  setRelationshipPreview,
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

  const handlePreviewFolderImport = useCallback(async (options: { path: string; limit?: number; recursive?: boolean }) => {
    const result = await previewFolderImport(options);
    setSection("sources");
    return result;
  }, [setSection]);

  const handleCommitFolderImport = useCallback(async (options: { path: string; limit?: number; recursive?: boolean; confirm?: boolean }) => {
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

  const handleFieldUpdate = useCallback(async (options: { table: string; field: string; role: string; usage: string; confidence?: number; confirm?: boolean }) => {
    const result = await updateFieldConfig(options);
    setLastActionResult(result);
    if (options.confirm) {
      setWorkbench(await refreshWorkbench());
    }
  }, [setLastActionResult, setWorkbench]);

  const handleInferSemantics = useCallback(async (options: Parameters<typeof inferSemantics>[0]) => {
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

  const handleSetSemantic = useCallback(async (options: Parameters<typeof setSemantic>[0] & { stayOnPage?: boolean }) => {
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

  const handleInferMetrics = useCallback(async (options: Parameters<typeof inferMetrics>[0]) => {
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

  const handleAddMetric = useCallback(async (options: Parameters<typeof addMetric>[0]) => {
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

  const handleQueryMetric = useCallback(async (options: Parameters<typeof queryMetric>[0]) => {
    const result = await queryMetric(options);
    setLastActionResult(result);
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection]);

  const handleRelationshipPreview = useCallback(async (options: { leftTable: string; rightTable: string; leftField: string; rightField: string; joinType?: string; limit?: number }) => {
    setRelationshipPreview(await previewRelationship(options));
    setSection("sources");
  }, [setRelationshipPreview, setSection]);

  const handleRelationshipSave = useCallback(async (options: { leftTable: string; rightTable: string; leftField: string; rightField: string; joinType?: string; limit?: number; confirm?: boolean }) => {
    const result = await saveRelationship(options);
    setRelationshipPreview(result);
    if (options.confirm) {
      setWorkbench(await refreshWorkbench());
    }
    setSection("sources");
  }, [setRelationshipPreview, setSection, setWorkbench]);

  const handleDashboardRelationshipSave = useCallback(async (options: Parameters<typeof saveRelationship>[0]) => {
    const result = await saveRelationship(options);
    setRelationshipPreview(result);
    setLastActionResult(result as unknown as Record<string, unknown>);
    setWorkbench(await refreshWorkbench());
    return result as unknown as Record<string, unknown>;
  }, [setLastActionResult, setRelationshipPreview, setWorkbench]);

  const handleFormulaPreview = useCallback(async (options: { expression: string; table?: string; mode?: string }) => {
    setFormulaPreview(await previewFormula(options));
    setSection("sources");
  }, [setFormulaPreview, setSection]);

  const handleSaveFormula = useCallback(async (options: Parameters<typeof saveFormula>[0]) => {
    const result = await saveFormula(options);
    setLastActionResult(result as unknown as Record<string, unknown>);
    if (options.confirm) {
      setWorkbench(await refreshWorkbench());
    }
    setSection("sources");
    return result;
  }, [setLastActionResult, setSection, setWorkbench]);

  const handleDeleteFormula = useCallback(async (options: Parameters<typeof deleteFormula>[0]) => {
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
    const request = { ...sourceOptions, inputs, workspaceId: activeWorkspaceId };
    try {
      const result = await runSourceIntelligence(request);
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
