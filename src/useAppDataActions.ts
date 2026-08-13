import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import {
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
import {
  cancelImportJob,
  createImportJob,
  fetchImportJob,
  listImportJobs,
  resumeImportJob,
  type CreateImportJobOptions,
} from "./apiImportJobs";
import type { AnalysisJob } from "./typesJobs";
import { latestUsableSourceIntelligenceRun } from "./workspaceFlowModel";
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
  workbench: WorkbenchPayload;
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

function sameAnalysisJobs(left: AnalysisJob[], right: AnalysisJob[]) {
  return left.length === right.length && left.every((job, index) => {
    const candidate = right[index];
    return candidate
      && job.jobKey === candidate.jobKey
      && job.status === candidate.status
      && job.progress === candidate.progress
      && job.stage === candidate.stage
      && job.updatedAt === candidate.updatedAt;
  });
}

export function useAppDataActions({
  activeWorkspaceId,
  workbench,
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
  const sourceIntelligenceLaunchingRef = useRef(false);
  const sourceIntelligenceRecoveryKeyRef = useRef("");
  const hydratedSourceIntelligenceJobsRef = useRef(new Set<string>());
  const [sourceIntelligenceJobs, setSourceIntelligenceJobs] = useState<AnalysisJob[]>([]);
  const setSection = useCallback((section: AppSection) => navigateTo({ section }), [navigateTo]);
  const handlePreview = useCallback(async (options: { filePath: string; table?: string; uniqueFields?: string[]; conflictRule?: string }) => {
    const result = await previewImportWithOptions(options);
    setPreview(result);
    setSection("sources");
    return result;
  }, [setPreview, setSection]);

  const handlePreviewFolderImport = useCallback(async (options: { path: string; limit?: number; recursive?: boolean; uniqueFields?: string[]; conflictRule?: string }) => {
    const result = await previewFolderImport(options);
    setSection("sources");
    return result;
  }, [setSection]);

  const requireActiveImportJob = useCallback((job: AnalysisJob | undefined, action: string) => {
    if (!job) throw new Error(`${action}: import job payload is missing`);
    if (job.workspaceId !== activeWorkspaceId) throw new Error(`${action}: import job belongs to another workspace`);
    return job;
  }, [activeWorkspaceId]);

  const handleCreateImportJob = useCallback(async (options: CreateImportJobOptions) => {
    const payload = await createImportJob(options);
    const job = requireActiveImportJob(payload.job, "create-import-job");
    setLastActionResult(payload as unknown as Record<string, unknown>);
    return job;
  }, [requireActiveImportJob, setLastActionResult]);

  const handleFetchImportJob = useCallback(async (jobKey: string) => {
    const payload = await fetchImportJob(jobKey);
    return requireActiveImportJob(payload.job, "fetch-import-job");
  }, [requireActiveImportJob]);

  const handleListImportJobs = useCallback(async () => {
    const payload = await listImportJobs(20);
    return (payload.jobs ?? []).filter((job) => job.workspaceId === activeWorkspaceId && job.kind === "import");
  }, [activeWorkspaceId]);

  const handleCancelImportJob = useCallback(async (job: AnalysisJob) => {
    requireActiveImportJob(job, "cancel-import-job");
    const payload = await cancelImportJob(job.jobKey);
    const latest = requireActiveImportJob(payload.job, "cancel-import-job");
    setLastActionResult(payload as unknown as Record<string, unknown>);
    return latest;
  }, [requireActiveImportJob, setLastActionResult]);

  const handleResumeImportJob = useCallback(async (job: AnalysisJob) => {
    requireActiveImportJob(job, "resume-import-job");
    const payload = await resumeImportJob(job.jobKey);
    const latest = requireActiveImportJob(payload.job, "resume-import-job");
    setLastActionResult(payload as unknown as Record<string, unknown>);
    return latest;
  }, [requireActiveImportJob, setLastActionResult]);

  const handleImportJobCompleted = useCallback(async (job: AnalysisJob) => {
    requireActiveImportJob(job, "complete-import-job");
    if (job.status !== "succeeded") return;
    const refreshed = await refreshStatusAndWorkbench();
    if (refreshed.status.workspace.id !== activeWorkspaceId) return;
    setLastActionResult({ ok: true, action: "import-job-completed", job });
    setStatus(refreshed.status);
    setWorkbench(refreshed.workbench);
    navigateTo({ section: "sources", tableKey: refreshed.workbench.tables[0]?.table_key });
  }, [activeWorkspaceId, navigateTo, requireActiveImportJob, setLastActionResult, setStatus, setWorkbench]);

  const handleWorkspaceRecoveryInvalidated = useCallback((keys: string[]) => {
    const requested = new Set(keys);
    if (!requested.has("workspace-status") && !requested.has("workbench")) return;
    void refreshStatusAndWorkbench().then((refreshed) => {
      if (refreshed.status.workspace.id !== activeWorkspaceId) return;
      if (requested.has("workspace-status")) setStatus(refreshed.status);
      if (requested.has("workbench")) setWorkbench(refreshed.workbench);
    }).catch((error) => {
      setLastActionResult(actionErrorResult("workspace-recovery-refresh", error));
    });
  }, [activeWorkspaceId, setLastActionResult, setStatus, setWorkbench]);

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
      throw error;
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
    sourceIntelligenceLaunchingRef.current = true;
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
      hydratedSourceIntelligenceJobsRef.current.add(job.jobKey);
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
    } finally {
      if (sourceIntelligenceRequestRef.current === requestId) sourceIntelligenceLaunchingRef.current = false;
    }
  }, [activeWorkspaceId, navigateTo, setLastActionResult, setSection, setStatus, setWorkbench]);

  useEffect(() => {
    let disposed = false;
    let timer = 0;
    let baselineLoaded = false;
    hydratedSourceIntelligenceJobsRef.current = new Set();
    setSourceIntelligenceJobs([]);

    const refreshJobs = async () => {
      let hasActive = false;
      try {
        const payload = await fetchAnalysisJobs({ limit: 20 });
        if (disposed) return;
        const jobs = (payload.jobs ?? [])
          .filter((job) => job.workspaceId === activeWorkspaceId && job.kind === "source-intelligence");
        setSourceIntelligenceJobs((current) => sameAnalysisJobs(current, jobs) ? current : jobs);
        hasActive = jobs.some((job) => !TERMINAL_JOB_STATUSES.has(job.status));
        const succeededJobs = jobs.filter((job) => job.status === "succeeded");
        if (!baselineLoaded) {
          succeededJobs.forEach((job) => hydratedSourceIntelligenceJobsRef.current.add(job.jobKey));
          baselineLoaded = true;
        } else {
          const newlyCompletedJobs = succeededJobs.filter((job) => !hydratedSourceIntelligenceJobsRef.current.has(job.jobKey));
          newlyCompletedJobs.forEach((job) => hydratedSourceIntelligenceJobsRef.current.add(job.jobKey));
          if (!newlyCompletedJobs.length) return;
          const refreshed = await refreshStatusAndWorkbench();
          if (!disposed && refreshed.status.workspace.id === activeWorkspaceId) {
            setStatus(refreshed.status);
            setWorkbench(refreshed.workbench);
          }
        }
      } catch {
        // The workspace surface remains usable if the optional background-job feed is temporarily unavailable.
      } finally {
        if (!disposed) timer = window.setTimeout(() => void refreshJobs(), hasActive ? 1500 : 8000);
      }
    };

    void refreshJobs();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
    };
  }, [activeWorkspaceId, setStatus, setWorkbench]);

  useEffect(() => {
    if (!workbench.tables.length || latestUsableSourceIntelligenceRun(workbench.sourceIntelligenceRuns)) return;
    if (sourceIntelligenceLaunchingRef.current) return;
    const inputs = Array.from(new Set(workbench.importJobs
      .filter((job) => job.status === "success" && job.source_file.trim())
      .map((job) => job.source_file.trim())));
    if (!inputs.length) return;
    const dataVersionKey = workbench.tables
      .map((table) => `${table.table_key}:${table.data_version ?? table.updated_at ?? table.row_count}`)
      .sort()
      .join("|");
    const recoveryKey = `${activeWorkspaceId}:${inputs.join("\n")}:${dataVersionKey}`;
    if (sourceIntelligenceRecoveryKeyRef.current === recoveryKey) return;
    const timer = window.setTimeout(() => {
      void (async () => {
        if (sourceIntelligenceLaunchingRef.current || sourceIntelligenceRecoveryKeyRef.current === recoveryKey) return;
        const payload = await fetchAnalysisJobs({ statuses: ["created", "queued", "running", "cancel_requested"], limit: 20 });
        const hasActiveJob = (payload.jobs ?? []).some((job) => job.workspaceId === activeWorkspaceId && job.kind === "source-intelligence");
        sourceIntelligenceRecoveryKeyRef.current = recoveryKey;
        if (hasActiveJob) return;
        await handleSourceIntelligenceRun({
          inputs,
          label: "Workspace evidence",
          stayOnPage: true,
        });
      })().catch(() => {
        // handleSourceIntelligenceRun already records the actionable failure for the journey UI.
      });
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [activeWorkspaceId, handleSourceIntelligenceRun, workbench.importJobs, workbench.sourceIntelligenceRuns, workbench.tables]);

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
    sourceIntelligenceJobs,
    handleAddMetric,
    handleCreateImportJob,
    handleFetchImportJob,
    handleListImportJobs,
    handleCancelImportJob,
    handleResumeImportJob,
    handleImportJobCompleted,
    handleWorkspaceRecoveryInvalidated,
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
