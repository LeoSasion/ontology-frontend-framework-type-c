import { useEffect, useRef, useState } from "react";
import type { ImportPolicy } from "./types";
import type { SourceWorkbenchProps } from "./sourceWorkbenchContracts";
import type { AnalysisJob } from "./typesJobs";
import { buildImportOptions, buildImportPolicyOptions } from "./sourceWorkbenchCommandModel";
import { buildImportPreviewSummary } from "./sourceWorkbenchModel";
import {
  buildDurableImportQueuedReceipt,
  buildImportPolicyReceipt,
  buildImportPreviewReceipt,
  type WorkbenchOperationReceipt,
} from "./sourceWorkbenchReceiptModel";
import { startImportCompletionRefresh } from "./importCompletionRefresh";
import { biText } from "./components/Bilingual";

type ImportControllerOptions = Pick<
  SourceWorkbenchProps,
  "preview" | "onPreview" | "onPreviewFolderImport" | "onImportPolicy"
  | "onCreateImportJob" | "onFetchImportJob" | "onCancelImportJob" | "onResumeImportJob" | "onImportJobCompleted"
  | "onListImportJobs"
> & {
  workspaceId: string;
  importPolicies: ImportPolicy[];
  onCommittedInputs?: (inputs: string[]) => Promise<void>;
};

export function useSourceWorkbenchImportController({
  preview,
  importPolicies,
  onPreview,
  onPreviewFolderImport,
  onImportPolicy,
  onCreateImportJob,
  onFetchImportJob,
  onListImportJobs,
  onCancelImportJob,
  onResumeImportJob,
  onImportJobCompleted,
  workspaceId,
  onCommittedInputs,
}: ImportControllerOptions) {
  const [filePath, setFilePath] = useState("");
  const [targetTable, setTargetTable] = useState("");
  const [targetName, setTargetName] = useState("");
  const [importMode, setImportMode] = useState("merge");
  const [uniqueFields, setUniqueFields] = useState("");
  const [conflictRule, setConflictRule] = useState("overwrite");
  const [folderImportPlan, setFolderImportPlan] = useState<Awaited<ReturnType<typeof onPreviewFolderImport>> | null>(null);
  const [singleImportBinding, setSingleImportBinding] = useState<{ filePath: string; planFingerprint: string } | null>(null);
  const [importOperationReceipt, setImportOperationReceipt] = useState<WorkbenchOperationReceipt | null>(null);
  const [activeImportJob, setActiveImportJob] = useState<AnalysisJob | null>(null);
  const completedJobKeysRef = useRef(new Set<string>());
  const importJobCompletedRef = useRef(onImportJobCompleted);
  importJobCompletedRef.current = onImportJobCompleted;
  const importRequestRef = useRef<{ fingerprint: string; requestKey: string } | null>(null);
  const createInFlightRef = useRef<Promise<AnalysisJob> | null>(null);
  const workspaceRef = useRef(workspaceId);
  workspaceRef.current = workspaceId;
  const activeImportPolicy = importPolicies.find((policy) => policy.table_key === targetTable);
  const previewReadable = Boolean(preview.ok && preview.profile.rowCount > 0 && preview.profile.columnCount > 0);
  const previewSummary = buildImportPreviewSummary({ preview, previewReadable, targetName });
  const previewCommitOptions = preview.commitOptions;
  const normalizedUniqueFields = uniqueFields.split(",").map((field) => field.trim()).filter(Boolean);
  const singleImportPlanReady = Boolean(
    singleImportBinding?.planFingerprint
    && singleImportBinding.filePath === filePath.trim()
    && previewCommitOptions
    && targetTable.trim() === previewCommitOptions.table
    && importMode === previewCommitOptions.mode
    && conflictRule === previewCommitOptions.conflictRule
    && normalizedUniqueFields.join("\u0000") === previewCommitOptions.uniqueFields.join("\u0000"),
  );
  const importJobActive = Boolean(activeImportJob && !["succeeded", "failed", "canceled", "needs_attention"].includes(activeImportJob.status));

  useEffect(() => {
    setActiveImportJob(null);
    completedJobKeysRef.current = new Set();
    importRequestRef.current = null;
    createInFlightRef.current = null;
    const storageKey = `aibi-c:import-job:${workspaceId}`;
    let persistedJobKey = "";
    try {
      persistedJobKey = window.localStorage.getItem(storageKey) ?? "";
    } catch {
      // Private browsing/storage policy must not prevent durable server reattachment.
    }
    let disposed = false;
    let timer = 0;
    let attempt = 0;
    const reattach = () => {
      const selectJob = (jobs: AnalysisJob[]) => (
        jobs.find((job) => !["canceled", "succeeded", "failed"].includes(job.status)) ?? jobs[0] ?? null
      );
      const discover = persistedJobKey
        ? onFetchImportJob(persistedJobKey).catch(() => onListImportJobs().then(selectJob))
        : onListImportJobs().then(selectJob);
      void discover.then((job) => {
        if (!job) return;
        if (disposed || workspaceRef.current !== workspaceId || job.workspaceId !== workspaceId) return;
        setActiveImportJob(job);
      }).catch(() => {
        if (disposed || workspaceRef.current !== workspaceId) return;
        attempt += 1;
        timer = window.setTimeout(reattach, Math.min(5_000, 500 * (2 ** Math.min(attempt, 3))));
      });
    };
    reattach();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
    };
  }, [onFetchImportJob, onListImportJobs, workspaceId]);

  useEffect(() => {
    const storageKey = `aibi-c:import-job:${workspaceId}`;
    if (activeImportJob?.workspaceId === workspaceId) {
      try {
        window.localStorage.setItem(storageKey, activeImportJob.jobKey);
      } catch {
        // Server-side history remains authoritative when local storage is unavailable.
      }
    }
  }, [activeImportJob?.jobKey, activeImportJob?.workspaceId, workspaceId]);

  useEffect(() => {
    const job = activeImportJob;
    if (!job || job.workspaceId !== workspaceId) return;
    if (["succeeded", "failed", "canceled", "needs_attention"].includes(job.status)) {
      if (job.status === "succeeded" && !completedJobKeysRef.current.has(job.jobKey)) {
        return startImportCompletionRefresh({
          complete: () => importJobCompletedRef.current(job),
          onCompleted: () => {
            if (workspaceRef.current !== workspaceId) return;
            completedJobKeysRef.current.add(job.jobKey);
            setImportOperationReceipt({
              tone: "ok",
              title: biText("导入完成，界面已更新", "Import completed; interface updated"),
              detail: biText("工作区中的数据表与字段已经重新载入。", "Workspace tables and fields have been reloaded."),
              nextStep: biText("继续生成证据摘要或开始分析。", "Continue by preparing evidence or starting analysis."),
              technical: `job=${job.jobKey}`,
            });
          },
          onRetry: (error, attempt, delayMs) => {
            if (workspaceRef.current !== workspaceId) return;
            setImportOperationReceipt({
              tone: "warn",
              title: biText("导入已完成，正在重试界面刷新", "Import completed; retrying interface refresh"),
              detail: error instanceof Error ? error.message : String(error),
              nextStep: biText("无需重复导入；界面会自动读取已提交结果。", "Do not import again; the interface will automatically reload the committed result."),
              technical: `job=${job.jobKey}; retry=${attempt}; delayMs=${delayMs}`,
            });
          },
          schedule: (task, delayMs) => {
            const timer = window.setTimeout(task, delayMs);
            return () => window.clearTimeout(timer);
          },
        });
      }
      return;
    }
    let disposed = false;
    let timer = 0;
    let attempt = 0;
    const poll = () => {
      void onFetchImportJob(job.jobKey).then((latest) => {
        if (disposed || workspaceRef.current !== workspaceId || latest.workspaceId !== workspaceId) return;
        setActiveImportJob(latest);
      }).catch((error) => {
        if (disposed || workspaceRef.current !== workspaceId) return;
        setImportOperationReceipt({
          tone: "warn",
          title: biText("暂时无法读取导入进度", "Import progress is temporarily unavailable"),
          detail: error instanceof Error ? error.message : String(error),
          nextStep: biText("任务会在后台继续；稍后重新打开数据源页。", "The job continues in the background; reopen Sources shortly."),
          technical: `job=${job.jobKey}`,
        });
        attempt += 1;
        timer = window.setTimeout(poll, Math.min(5_000, 600 * (2 ** Math.min(attempt, 3))));
      });
    };
    timer = window.setTimeout(poll, 1200);
    return () => {
      disposed = true;
      window.clearTimeout(timer);
    };
  }, [activeImportJob?.jobKey, activeImportJob?.status, activeImportJob?.updatedAt, onFetchImportJob, workspaceId]);

  function requestKey() {
    return globalThis.crypto?.randomUUID
      ? `import:${globalThis.crypto.randomUUID()}`
      : `import:${Date.now()}:${Math.random().toString(36).slice(2)}`;
  }

  function stableRequestKey(fingerprint: string) {
    if (importRequestRef.current?.fingerprint !== fingerprint) {
      importRequestRef.current = { fingerprint, requestKey: requestKey() };
    }
    return importRequestRef.current.requestKey;
  }

  function createImportJobOnce(input: Parameters<typeof onCreateImportJob>[0]) {
    if (!createInFlightRef.current) {
      createInFlightRef.current = onCreateImportJob(input).finally(() => {
        createInFlightRef.current = null;
      });
    }
    return createInFlightRef.current;
  }

  function importOptions(confirm = false) {
    const options = buildImportOptions({
      filePath,
      targetTable,
      targetName,
      importMode,
      uniqueFields,
      conflictRule,
      confirm,
    });
    return {
      ...options,
      expectedPlan: confirm && singleImportBinding?.filePath === filePath.trim()
        ? singleImportBinding.planFingerprint
        : undefined,
    };
  }

  async function runImportPreviewAction() {
    const result = await onPreview(importOptions(false));
    importRequestRef.current = null;
    setSingleImportBinding(result.planFingerprint ? { filePath: filePath.trim(), planFingerprint: result.planFingerprint } : null);
    setFolderImportPlan(null);
    let receiptTargetTable = targetTable;
    let receiptImportMode = importMode;
    let receiptUniqueFields = uniqueFields;
    if (result.ok && result.matchedTable) {
      receiptTargetTable = result.matchedTable.table_key;
      receiptImportMode = "merge";
      setTargetTable(result.matchedTable.table_key);
      setTargetName(result.matchedTable.display_name);
      setImportMode("merge");
    } else if (result.ok) {
      const suggestedTable = String(result.suggestedTableKey || "").trim();
      const suggestedName = String(result.suggestedDisplayName || suggestedTable).trim();
      if (suggestedTable) {
        setTargetTable(suggestedTable);
        receiptTargetTable = suggestedTable;
      }
      if (suggestedName) setTargetName(suggestedName);
      setImportMode("create");
      receiptImportMode = "create";
    }
    if (result.ok) {
      const suggestedUniqueFields = result.mergePolicyPreview.uniqueFields;
      if (!uniqueFields.trim() && suggestedUniqueFields.length) {
        receiptUniqueFields = suggestedUniqueFields.join(", ");
        setUniqueFields(receiptUniqueFields);
      }
    }
    setImportOperationReceipt(buildImportPreviewReceipt({
      filePath,
      targetTable: receiptTargetTable,
      importMode: receiptImportMode,
      uniqueFields: receiptUniqueFields,
      conflictRule,
    }));
  }

  async function runImportCommitAction(confirm: boolean) {
    if (!confirm) {
      await runImportPreviewAction();
      return;
    }
    if (!singleImportBinding?.planFingerprint) throw new Error(biText("请先重新检查来源。", "Check the source again first."));
    const options = importOptions(true);
    const requestFingerprint = `single:${workspaceId}:${singleImportBinding.planFingerprint}:${options.filePath}:${options.table}:${options.mode}:${(options.uniqueFields ?? []).join("\u0000")}:${options.conflictRule}`;
    const job = await createImportJobOnce({
      requestKey: stableRequestKey(requestFingerprint),
      expectedPlan: singleImportBinding.planFingerprint,
      importKind: "single",
      path: options.filePath,
      table: options.table,
      name: options.name,
      mode: options.mode,
      uniqueFields: options.uniqueFields,
      conflictRule: options.conflictRule,
    });
    if (job.workspaceId !== workspaceId) throw new Error(biText("导入任务与当前工作区不一致。", "Import job does not match the active workspace."));
    setActiveImportJob(job);
    importRequestRef.current = null;
    setFolderImportPlan(null);
    setImportOperationReceipt(buildDurableImportQueuedReceipt({
      jobKey: job.jobKey,
      planFingerprint: singleImportBinding.planFingerprint,
      importKind: "single",
    }));
  }

  async function runFolderImportPreviewAction() {
    const selectedUniqueFields = uniqueFields.split(",").map((field) => field.trim()).filter(Boolean);
    const result = await onPreviewFolderImport({
      path: filePath,
      limit: 200,
      recursive: true,
      uniqueFields: selectedUniqueFields,
      conflictRule,
    });
    importRequestRef.current = null;
    setFolderImportPlan(result);
    setSingleImportBinding(null);
    const firstGroup = result.groups[0];
    if (firstGroup) {
      setTargetTable(firstGroup.tableKey);
      setTargetName(firstGroup.displayName);
      setImportMode(firstGroup.willMerge ? "merge" : "create");
      setUniqueFields(firstGroup.uniqueFields.join(", "));
    }
    setImportOperationReceipt({
      tone: result.readyToCommit ? "ok" : "warn",
      title: result.fileCount > 0
        ? biText(`发现 ${result.fileCount} 个可导入文件`, `${result.fileCount} importable files found`)
        : biText("没有发现可导入文件", "No importable files found"),
      detail: result.fileCount > 0
        ? biText(`将归并为 ${result.tableCount} 张业务表。`, `They will be grouped into ${result.tableCount} business tables.`)
        : biText("请选择包含 CSV 或 Excel 的文件夹。", "Choose a folder with CSV or Excel files."),
      nextStep: result.fileCount > 0
        ? result.readyToCommit
          ? biText("确认后按同类表原子导入，导入前不会写入。", "Confirm the atomic grouped import. Nothing writes before confirmation.")
          : biText("先确认唯一键并重新预检；阻断未解除前不能提交。", "Confirm the unique key and preview again; blocked plans cannot commit.")
        : biText("粘贴文件夹路径后重新检查。", "Paste a folder path and check again."),
      technical: [...(result.blockers ?? []), result.planFingerprint ? `plan=${result.planFingerprint}` : ""].filter(Boolean).join("; ") || result.path,
    });
  }

  async function runFolderImportCommitAction(confirm: boolean) {
    if (confirm) {
      if (!folderImportPlan?.planFingerprint) throw new Error(biText("请先重新检查文件夹。", "Check the folder again first."));
      const folderUniqueFields = uniqueFields.split(",").map((field) => field.trim()).filter(Boolean);
      const requestFingerprint = `folder:${workspaceId}:${folderImportPlan.planFingerprint}:${filePath.trim()}:${folderUniqueFields.join("\u0000")}:${conflictRule}`;
      const job = await createImportJobOnce({
        requestKey: stableRequestKey(requestFingerprint),
        expectedPlan: folderImportPlan.planFingerprint,
        importKind: "folder",
        path: filePath,
        uniqueFields: folderUniqueFields,
        conflictRule,
        recursive: true,
        limit: 200,
      });
      if (job.workspaceId !== workspaceId) throw new Error(biText("导入任务与当前工作区不一致。", "Import job does not match the active workspace."));
      setActiveImportJob(job);
      importRequestRef.current = null;
      setImportOperationReceipt(buildDurableImportQueuedReceipt({
        jobKey: job.jobKey,
        planFingerprint: folderImportPlan.planFingerprint,
        importKind: "folder",
        fileCount: folderImportPlan.fileCount,
        tableCount: folderImportPlan.tableCount,
      }));
      return;
    }
    await runFolderImportPreviewAction();
  }

  async function cancelActiveImportJob(job: AnalysisJob) {
    const latest = await onCancelImportJob(job);
    if (latest.workspaceId === workspaceId) setActiveImportJob(latest);
  }

  async function resumeActiveImportJob(job: AnalysisJob) {
    const latest = await onResumeImportJob(job);
    if (latest.workspaceId === workspaceId) setActiveImportJob(latest);
  }

  async function runImportPolicyAction(confirm: boolean) {
    await onImportPolicy(buildImportPolicyOptions({ targetTable, uniqueFields, conflictRule, confirm }));
    setImportOperationReceipt(buildImportPolicyReceipt({ confirm, targetTable, uniqueFields, conflictRule }));
  }

  return {
    preview,
    filePath,
    targetTable,
    targetName,
    importMode,
    uniqueFields,
    conflictRule,
    activeImportPolicy,
    previewReadable,
    ...previewSummary,
    importOperationReceipt,
    folderImportPlan,
    singleImportPlanReady,
    activeImportJob,
    importJobActive,
    setFilePath,
    setTargetTable,
    setTargetName,
    setImportMode,
    setUniqueFields,
    setConflictRule,
    runImportPreviewAction,
    runImportCommitAction,
    runFolderImportPreviewAction,
    runFolderImportCommitAction,
    cancelActiveImportJob,
    resumeActiveImportJob,
    runImportPolicyAction,
  };
}
