import { useState } from "react";
import type { ImportPolicy } from "./types";
import type { SourceWorkbenchProps } from "./sourceWorkbenchContracts";
import { buildImportOptions, buildImportPolicyOptions } from "./sourceWorkbenchCommandModel";
import { buildImportPreviewSummary } from "./sourceWorkbenchModel";
import {
  buildImportCommitReceipt,
  buildImportPolicyReceipt,
  buildImportPreviewReceipt,
  type WorkbenchOperationReceipt,
} from "./sourceWorkbenchReceiptModel";
import { biText } from "./components/Bilingual";

type ImportControllerOptions = Pick<
  SourceWorkbenchProps,
  "preview" | "onPreview" | "onCommitImport" | "onPreviewFolderImport" | "onCommitFolderImport" | "onImportPolicy"
> & {
  importPolicies: ImportPolicy[];
  onCommittedInputs?: (inputs: string[]) => Promise<void>;
};

export function useSourceWorkbenchImportController({
  preview,
  importPolicies,
  onPreview,
  onCommitImport,
  onPreviewFolderImport,
  onCommitFolderImport,
  onImportPolicy,
  onCommittedInputs,
}: ImportControllerOptions) {
  const [filePath, setFilePath] = useState("");
  const [targetTable, setTargetTable] = useState("");
  const [targetName, setTargetName] = useState("");
  const [importMode, setImportMode] = useState("merge");
  const [uniqueFields, setUniqueFields] = useState("");
  const [conflictRule, setConflictRule] = useState("overwrite");
  const [folderImportPlan, setFolderImportPlan] = useState<Awaited<ReturnType<typeof onPreviewFolderImport>> | null>(null);
  const [importOperationReceipt, setImportOperationReceipt] = useState<WorkbenchOperationReceipt | null>(null);
  const activeImportPolicy = importPolicies.find((policy) => policy.table_key === targetTable);
  const previewReadable = Boolean(preview.ok && preview.profile.rowCount > 0 && preview.profile.columnCount > 0);
  const previewSummary = buildImportPreviewSummary({ preview, previewReadable, targetName });

  function importOptions(confirm = false) {
    return buildImportOptions({
      filePath,
      targetTable,
      targetName,
      importMode,
      uniqueFields,
      conflictRule,
      confirm,
    });
  }

  async function runImportPreviewAction() {
    const result = await onPreview(importOptions(false));
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
    await onCommitImport(importOptions(confirm));
    setFolderImportPlan(null);
    setImportOperationReceipt(buildImportCommitReceipt({
      confirm,
      preview,
      matchedTableName: previewSummary.matchedTableName,
      targetTable,
      importInsertRows: previewSummary.importInsertRows,
      importUpdateRows: previewSummary.importUpdateRows,
      importSkipRows: previewSummary.importSkipRows,
      importAfterRows: previewSummary.importAfterRows,
    }));
    if (confirm && filePath.trim()) await onCommittedInputs?.([filePath.trim()]);
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
    setFolderImportPlan(result);
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
    const result = await onCommitFolderImport({
      path: filePath,
      limit: 200,
      recursive: true,
      uniqueFields: uniqueFields.split(",").map((field) => field.trim()).filter(Boolean),
      conflictRule,
      expectedPlan: folderImportPlan?.planFingerprint,
      confirm,
    });
    setFolderImportPlan(result);
    setImportOperationReceipt({
      tone: result.committed ? "ok" : "warn",
      title: result.committed
        ? biText("文件夹导入已完成", "Folder import completed")
        : biText("文件夹导入待确认", "Folder import needs confirmation"),
      detail: biText(`已处理 ${result.fileCount} 个文件，归并为 ${result.tableCount} 张业务表。`, `${result.fileCount} files grouped into ${result.tableCount} business tables.`),
      nextStep: result.committed
        ? biText("下一步可以让 Agent 生成单图或看板草案。", "Next, ask Agent to create a chart or dashboard draft.")
        : biText("确认后才会写入工作区。", "Confirm before writing to the workspace."),
      technical: result.sourceRunId
        ? `sourceRun=${result.sourceRunId}; plan=${result.planFingerprint ?? "-"}`
        : [...(result.blockers ?? []), result.planFingerprint ? `plan=${result.planFingerprint}` : ""].filter(Boolean).join("; ") || result.path,
    });
    if (confirm && result.committed && filePath.trim()) await onCommittedInputs?.([filePath.trim()]);
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
    runImportPolicyAction,
  };
}
