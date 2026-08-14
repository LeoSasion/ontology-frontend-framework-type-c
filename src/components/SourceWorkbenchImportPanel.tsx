import { Suspense, useEffect, useState } from "react";
import { lazyWithRetry } from "../lazyWithRetry";
import type { useSourceWorkbenchImportController } from "../useSourceWorkbenchImportController";
import { countText } from "../sourceWorkbenchModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import { OperationReceipt } from "./OperationReceipt";
import { ImportJobStatusCard } from "./ImportJobStatusCard";

const ImportSchemaChangeReport = lazyWithRetry(() => import("./ImportSchemaChangeReport"));

type SourceWorkbenchImportPanelProps = ReturnType<typeof useSourceWorkbenchImportController> & {
  busy: string | null;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
};

type ImportPanelActionError = {
  receipt: {
    detail: string;
    nextStep: string;
    title: string;
    tone: "warn";
    technical: string;
  };
  retry: () => Promise<void>;
  retryLabel: string;
};

function failureCategory(error: unknown) {
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  if (/(fetch|network|timeout|unavailable|econn|service|连接|超时|服务)/.test(message)) return "service-unavailable";
  if (/(file|folder|path|format|read|文件|路径|格式|读取)/.test(message)) return "source-unreadable";
  if (/(schema|field|plan|merge|fingerprint|字段|计划|合并|预演)/.test(message)) return "plan-changed";
  return "operation-incomplete";
}

function buildImportActionError(action: string, error: unknown) {
  const category = failureCategory(error);
  const isConfirm = action === "import-confirm" || action === "folder-confirm";
  const isPreview = action === "preview" || action === "folder-preview";
  const isPolicy = action.startsWith("import-policy");
  const isJobControl = action === "import-cancel" || action === "import-resume";
  const detail = isConfirm
    ? biText("任务请求没有返回明确结果；系统不会把未知状态当作成功。", "The job request did not return a definitive result; an unknown state is never treated as success.")
    : category === "service-unavailable"
      ? biText("本地服务暂时不可用，当前输入和预演仍保留在页面中。", "The local service is temporarily unavailable. Your current inputs and preview remain on this page.")
      : category === "source-unreadable"
        ? biText("来源路径、文件格式或读取权限需要检查。", "Check the source path, file format, or read permission.")
      : category === "plan-changed"
          ? biText("来源或导入规则与刚才的预演不再一致。", "The source or import rules no longer match the last preview.")
          : isPreview
            ? biText("系统没有读取到可预演的来源；请检查路径是否存在，且文件是 CSV 或 Excel。", "No previewable source was read. Check that the path exists and the file is CSV or Excel.")
            : biText("本次操作没有完成，页面没有把它标记为成功。", "This operation did not complete, and the page has not marked it as successful.");
  const title = isConfirm
    ? biText("导入结果尚未确认", "Import result is not yet confirmed")
    : isPolicy
      ? biText("导入规则操作未完成", "Import rule action did not complete")
      : isJobControl
        ? biText("任务状态操作未完成", "Job status action did not complete")
        : biText("来源检查未完成", "Source check did not complete");
  const nextStep = isConfirm
    ? biText("保留当前来源和规则并重试；系统会复用同一请求边界，避免重复创建任务。", "Keep the current source and rules, then retry. The same request boundary is reused to avoid duplicate jobs.")
    : isPolicy
      ? biText("核对目标表和规则后重试；保存前不会更改默认策略。", "Review the target table and rules, then retry. Defaults do not change before save succeeds.")
      : isJobControl
        ? biText("重新读取任务状态后重试；不要重复创建导入任务。", "Reload the job status and retry. Do not create another import job.")
        : biText("修正来源或等待服务恢复后重试；检查阶段不会创建导入任务。", "Correct the source or wait for the service to recover, then retry. Checking does not create an import job.");
  return {
    detail,
    nextStep,
    title,
    tone: "warn" as const,
    technical: `action=${action}; category=${category}; captured=${error instanceof Error ? "exception" : "unknown"}`,
  };
}

function retryLabel(action: string) {
  if (action === "import-confirm" || action === "folder-confirm") return biText("重试创建导入任务", "Retry import job creation");
  if (action === "import-cancel") return biText("重试取消任务", "Retry canceling job");
  if (action === "import-resume") return biText("重试恢复任务", "Retry resuming job");
  if (action.startsWith("import-policy")) return biText("重试导入规则操作", "Retry import rule action");
  return biText("重新检查来源", "Check source again");
}

function pathLeaf(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() || path;
}

export function SourceWorkbenchImportPanel({
  preview,
  busy,
  filePath,
  targetTable,
  targetName,
  importMode,
  uniqueFields,
  conflictRule,
  activeImportPolicy,
  previewReadable,
  matchedTableName,
  importInsertRows,
  importUpdateRows,
  importSkipRows,
  importAfterRows,
  importDuplicateRows,
  importEmptyKeyRows,
  importKeyHealthy,
  importOperationReceipt,
  folderImportPlan,
  singleImportPlanReady,
  schemaChangeAcknowledged,
  schemaChangeConfirmationRequired,
  activeImportJob,
  importJobActive,
  recentImportPaths,
  setFilePath,
  setTargetTable,
  setTargetName,
  setImportMode,
  setUniqueFields,
  setConflictRule,
  setSchemaChangeAcknowledged,
  runBusy,
  runImportPreviewAction,
  runImportCommitAction,
  runFolderImportPreviewAction,
  runFolderImportCommitAction,
  cancelActiveImportJob,
  resumeActiveImportJob,
  runImportPolicyAction,
}: SourceWorkbenchImportPanelProps) {
  const [importActionError, setImportActionError] = useState<ImportPanelActionError | null>(null);
  const [rulesOpen, setRulesOpen] = useState(false);
  const createTargetLabel = preview.suggestedDisplayName || targetName || preview.suggestedTableKey || targetTable;
  const sourceLooksLikeFile = /\.(?:csv|tsv|xlsx?|xlsm)$/i.test(filePath.trim());
  const sourceCheckBusy = busy === "preview" || busy === "folder-preview";
  const plannedMode = String(preview.commitOptions?.mode || preview.mergePolicyPreview.mode || importMode);
  const replacingTable = previewReadable && plannedMode === "replace" && Boolean(preview.matchedTable);
  const previewBlocked = preview.readyToCommit === false;
  const mergeSchemaBlocked = preview.blockers?.includes("merge-schema-mismatch") === true;
  const sourceChecked = previewReadable || folderImportPlan !== null;

  useEffect(() => {
    setImportActionError(null);
  }, [conflictRule, filePath, importMode, targetName, targetTable, uniqueFields]);

  useEffect(() => {
    if (mergeSchemaBlocked) setRulesOpen(true);
  }, [mergeSchemaBlocked]);

  async function runImportAction(label: string, action: () => Promise<void>) {
    setImportActionError(null);
    try {
      await runBusy(label, action);
    } catch (error) {
      setImportActionError({
        receipt: buildImportActionError(label, error),
        retry: () => runImportAction(label, action),
        retryLabel: retryLabel(label),
      });
    }
  }

  function checkSource() {
    if (sourceLooksLikeFile) {
      return runImportAction("preview", runImportPreviewAction);
    }
    return runImportAction("folder-preview", runFolderImportPreviewAction);
  }

  function switchToReplaceAndRecheck() {
    setImportMode("replace");
    return runImportAction("preview", () => runImportPreviewAction("replace"));
  }

  return (
    <article className="workbenchPanel widePanel sourceImportPanel">
      <div className="tileHeader">
        <h3><Bilingual zh="导入前检查" en="Pre-import check" /></h3>
        <span>
          {preview.mergePolicyPreview.willWrite
            ? biText("确认后写入", "Writes after confirmation")
            : biText("只检查，不写入", "Check only")}
        </span>
      </div>
      <div className="formGrid oneCol">
        <label>
          <span>{biText("文件或文件夹路径", "File or folder path")}</span>
          <input
            value={filePath}
            onChange={(event) => setFilePath(event.target.value)}
            placeholder={biText("粘贴本地文件或文件夹路径", "Paste a local file or folder path")}
          />
          <small className="importPathExample">{biText("支持 CSV、XLSX、XLSM；也可粘贴包含这些文件的文件夹", "Supports CSV, XLSX, and XLSM, or a folder containing those files")}</small>
        </label>
        {recentImportPaths.length ? (
          <div className="recentImportPaths" data-testid="recent-import-paths">
            <span>{biText("最近检查", "Recently checked")}</span>
            <div>
              {recentImportPaths.map((path) => (
                <button className="miniButton" key={path} onClick={() => setFilePath(path)} title={path} type="button">
                  {pathLeaf(path)}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        <div className="buttonRow tight importCheckActions">
          <button
            className={`${sourceChecked ? "secondaryButton" : "primaryButton"} compactAction`}
            data-testid="source-import-preview-button"
            disabled={sourceCheckBusy || importJobActive || !filePath.trim()}
            onClick={() => void checkSource()}
            type="button"
          >
            <Icon name="source" />
            {sourceCheckBusy
              ? biText("正在检查…", "Checking…")
              : sourceChecked
                ? biText("重新检查来源", "Check source again")
                : biText("检查来源", "Check source")}
          </button>
          <span className="importSourceHint">
            {sourceLooksLikeFile
              ? biText("已识别为文件", "Detected as a file")
              : biText("自动按文件夹检查；文件路径请保留扩展名", "Checking as a folder; keep the extension for file paths")}
          </span>
        </div>
      </div>
      {importActionError ? (
        <OperationReceipt
          actions={(
            <button className="secondaryButton compactAction" disabled={busy !== null} onClick={() => void importActionError.retry()} type="button">
              {importActionError.retryLabel}
            </button>
          )}
          className="operationReceipt importInlineError"
          receipt={importActionError.receipt}
          role="alert"
          summary={biText("查看失败阶段", "View failure stage")}
          technical={<span>{importActionError.receipt.technical}</span>}
          technicalTestId="import-action-error-technical"
          testId="import-action-error"
        />
      ) : null}
      <details
        className="advancedDetails compactAdvanced"
        data-testid="import-target-write-rules"
        onToggle={(event) => setRulesOpen(event.currentTarget.open)}
        open={rulesOpen}
      >
        <summary>{biText("目标表与写入规则", "Target table and write rules")}</summary>
        <div className="formGrid">
          <label>
            <span>{biText("目标表", "Target table")}</span>
            <input value={targetTable} onChange={(event) => setTargetTable(event.target.value)} />
          </label>
          <label>
            <span>{biText("显示名", "Display name")}</span>
            <input value={targetName} onChange={(event) => setTargetName(event.target.value)} />
          </label>
          <label>
            <span>{biText("写入模式", "Write mode")}</span>
            <select value={importMode} onChange={(event) => setImportMode(event.target.value)}>
              <option value="merge">{biText("合并更新", "Merge updates")}</option>
              <option value="create">{biText("新建数据表", "Create table")}</option>
              <option value="replace">{biText("替换整表", "Replace table")}</option>
            </select>
          </label>
          <label>
            <span>{biText("唯一键", "Unique key")}</span>
            <input value={uniqueFields} onChange={(event) => setUniqueFields(event.target.value)} />
          </label>
          <label>
            <span>{biText("冲突规则", "Conflict rule")}</span>
            <select value={conflictRule} onChange={(event) => setConflictRule(event.target.value)}>
              <option value="overwrite">{biText("覆盖", "Overwrite")}</option>
              <option value="fill-empty">{biText("只填空值", "Fill empty")}</option>
              <option value="skip-existing">{biText("跳过已有", "Skip existing")}</option>
            </select>
          </label>
        </div>
        <div className="policyActionStrip">
          <div>
            <strong>{biText("当前导入策略", "Current import policy")}</strong>
            <span>
              {activeImportPolicy
                ? `${activeImportPolicy.uniqueFields.join(", ")} · ${activeImportPolicy.conflict_rule}`
                : biText("尚未保存，使用自动识别", "Not saved yet, using auto-detection")}
            </span>
          </div>
          <div className="buttonRow tight">
            <button
              className="miniButton"
              data-testid="import-policy-dry-run-button"
              disabled={busy === "import-policy-dry"}
              onClick={() => void runImportAction("import-policy-dry", () => runImportPolicyAction(false))}
              type="button"
            >
              {biText("预演策略", "Preview policy")}
            </button>
            <button
              className="miniButton"
              data-testid="import-policy-confirm-button"
              disabled={busy === "import-policy"}
              onClick={() => void runImportAction("import-policy", () => runImportPolicyAction(true))}
              type="button"
            >
              {biText("保存策略", "Save policy")}
            </button>
          </div>
        </div>
      </details>
      {importOperationReceipt ? (
        <OperationReceipt
          receipt={importOperationReceipt}
          role="status"
          summary={biText("查看导入策略和回执", "View import policy and receipt")}
          technical={<>
            <span>{biText("策略", "Policy")}: {preview.mergePolicyPreview.uniqueFields.join(", ") || biText("自动", "auto")} · {preview.mergePolicyPreview.conflictRule}</span>
            <span>{importOperationReceipt.technical}</span>
          </>}
          technicalTestId="import-operation-technical-details"
          testId="import-operation-receipt"
        />
      ) : null}
      {activeImportJob ? (
        <ImportJobStatusCard
          busy={busy !== null}
          job={activeImportJob}
          onCancel={(job) => runImportAction("import-cancel", () => cancelActiveImportJob(job))}
          onResume={(job) => runImportAction("import-resume", () => resumeActiveImportJob(job))}
        />
      ) : null}
      {folderImportPlan && folderImportPlan.fileCount > 0 ? (
        <div className="folderImportPlan" data-testid="folder-import-plan">
          <div className="folderImportPlanHeader">
            <div>
              <span className={`statusBadge ${folderImportPlan.readyToCommit ? "ok" : "warn"}`}>
                {folderImportPlan.readyToCommit ? biText("原子计划可提交", "Atomic plan ready") : biText("计划已阻断", "Plan blocked")}
              </span>
              <h4>{biText(`导入 ${folderImportPlan.fileCount} 个文件`, `Import ${folderImportPlan.fileCount} files`)}</h4>
              <p>{biText(`按文件名归并为 ${folderImportPlan.tableCount} 张业务表。`, `Grouped into ${folderImportPlan.tableCount} business tables by file name.`)}</p>
            </div>
            <button
              className="primaryButton compactAction"
              data-testid="folder-import-confirm-button"
              disabled={busy === "folder-confirm" || importJobActive || folderImportPlan.readyToCommit !== true}
              onClick={() => void runImportAction("folder-confirm", () => runFolderImportCommitAction(true))}
              type="button"
            >
              <Icon name="lock" />
              <Bilingual zh="确认导入文件夹" en="Confirm folder import" />
            </button>
          </div>
          <div className="folderImportGroups">
            {folderImportPlan.groups.map((group) => (
              <div className="folderImportGroup" key={group.tableKey}>
                <strong>{group.displayName}</strong>
                <span>{biText(`${group.fileCount} 个文件 · ${group.rowCount.toLocaleString()} 行`, `${group.fileCount} files · ${group.rowCount.toLocaleString()} rows`)}</span>
                <small>{group.uniqueFields.length ? group.uniqueFields.join(", ") : biText("自动唯一键", "Auto unique key")}</small>
                <small>{group.keyDecision?.authority === "owner_confirmed" ? biText("唯一键已由业务方确认", "Owner-confirmed key") : biText("唯一键仍是候选", "Key is still a candidate")}</small>
                {group.blockers?.length ? <small className="folderImportBlocker">{group.blockers.join(" · ")}</small> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {previewReadable ? (
        <>
          {preview.schemaChange?.confirmationRequired ? (
            <Suspense fallback={<p className="folderImportBlocker" role="status">{biText("正在整理字段影响…", "Preparing schema impact…")}</p>}>
              <ImportSchemaChangeReport
                acknowledged={schemaChangeAcknowledged}
                change={preview.schemaChange}
                onAcknowledgedChange={setSchemaChangeAcknowledged}
              />
            </Suspense>
          ) : null}
          <div className="importConfirmationSummary" data-testid="import-confirmation-summary">
            <div>
              <span className={`statusBadge ${previewBlocked ? "warn" : "ok"}`}>{previewBlocked ? biText("计划已阻断", "Plan blocked") : biText("预检通过", "Preflight passed")}</span>
              <h4>{mergeSchemaBlocked
                ? biText("字段结构不同，不能直接合并", "Schemas differ; direct merge is blocked")
                : replacingTable
                  ? biText(`替换 ${matchedTableName}`, `Replace ${matchedTableName}`)
                  : preview.matchedTable
                    ? biText(`合并到 ${matchedTableName}`, `Merge into ${matchedTableName}`)
                    : biText(`新建 ${createTargetLabel}`, `Create ${createTargetLabel}`)}</h4>
              <p>{mergeSchemaBlocked
                ? biText("请选择“替换整表”并重新检查来源；确认前不会写入。", "Choose Replace table and check the source again; nothing writes before confirmation.")
                : biText("确认前不会写入；你可以先看影响，再决定是否导入。", "Nothing writes before confirmation. Review the impact before importing.")}</p>
              {mergeSchemaBlocked ? (
                <button
                  className="secondaryButton compactAction importReplaceRecovery"
                  data-testid="import-switch-replace-and-recheck"
                  disabled={sourceCheckBusy || importJobActive}
                  onClick={() => void switchToReplaceAndRecheck()}
                  type="button"
                >
                  {biText("改为替换整表并重新检查", "Switch to replace and check again")}
                </button>
              ) : null}
            </div>
            <div className="importImpactGrid" data-testid="import-confirmation-impact">
              {replacingTable ? <>
                <div><strong>{countText(preview.profile.rowCount)}</strong><span>{biText("新文件行数", "incoming rows")}</span></div>
                <div><strong>{countText(preview.matchedTable?.row_count ?? 0)}</strong><span>{biText("现有行数", "current rows")}</span></div>
                <div><strong>{countText(preview.profile.rowCount)}</strong><span>{biText("替换后行数", "rows after replace")}</span></div>
                <div><strong>{countText(preview.profile.columnCount)}</strong><span>{biText("新文件字段", "incoming fields")}</span></div>
              </> : <>
                <div><strong>{countText(importInsertRows)}</strong><span>{biText("新增", "insert")}</span></div>
                <div><strong>{countText(importUpdateRows)}</strong><span>{biText("更新", "update")}</span></div>
                <div><strong>{countText(importSkipRows)}</strong><span>{biText("跳过", "skip")}</span></div>
                <div><strong>{countText(importAfterRows)}</strong><span>{biText("导入后行数", "rows after")}</span></div>
              </>}
            </div>
            {preview.importStage?.sealed ? (
              <div className="importStageSeal" data-testid="import-stage-seal" role="status">
                <Icon name="lock" />
                <div>
                  <strong>{biText("来源已密封，只解析一次", "Source sealed after one parse")}</strong>
                  <span>
                    {biText(
                      `${countText(preview.importStage.rowCount)} 行已绑定到本次确认；源文件后续变化不会改写这次导入。`,
                      `${countText(preview.importStage.rowCount)} rows are bound to this confirmation; later source changes cannot alter this import.`,
                    )}
                  </span>
                </div>
              </div>
            ) : null}
            <div className="importSafetyStrip" data-testid="import-confirmation-safety">
              <span className={replacingTable ? "warn" : importKeyHealthy ? "ok" : "warn"}>
                {replacingTable
                  ? biText("整表替换，不按唯一键合并", "Full replacement; unique-key merge is not used")
                  : importKeyHealthy
                  ? biText("唯一键可用，无重复/空键", "Unique key is usable, no duplicate or empty keys")
                  : biText(`需复核：${importDuplicateRows} 重复行，${importEmptyKeyRows} 空键`, `Review needed: ${importDuplicateRows} duplicate rows, ${importEmptyKeyRows} empty keys`)}
              </span>
              <span>{preview.mergePolicyPreview.willWrite ? biText("确认后才写入工作区", "Writes only after confirmation") : biText("当前只做检查，不写入", "Current state is preview")}</span>
              <span>{replacingTable ? biText("会替换已有表", "Replaces the existing table") : preview.matchedTable ? biText("会合并到已有表", "Merges into an existing table") : biText("会新建工作区表", "Creates a workspace table")}</span>
            </div>
            <div className="buttonRow tight">
              <button
                className="primaryButton compactAction"
                data-testid="import-confirmation-confirm"
                disabled={busy === "import-confirm" || importJobActive || !singleImportPlanReady || (schemaChangeConfirmationRequired && !schemaChangeAcknowledged)}
                onClick={() => void runImportAction("import-confirm", () => runImportCommitAction(true))}
                type="button"
              >
                <Icon name="lock" />
                <Bilingual zh="确认导入" en="Confirm import" />
              </button>
              {!singleImportPlanReady ? (
                <span className="folderImportBlocker" role="status">
                  {mergeSchemaBlocked
                    ? biText("字段不同，不能合并；切换为替换整表后重新检查。", "Schemas differ; choose Replace table and check again.")
                    : biText("来源或导入规则已变化，请重新检查来源。", "The source or import rules changed. Check the source again.")}
                </span>
              ) : null}
              {schemaChangeConfirmationRequired && !schemaChangeAcknowledged ? (
                <span className="folderImportBlocker" role="status">{biText("请先核对并勾选字段变化确认。", "Review and acknowledge the schema change first.")}</span>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </article>
  );
}
