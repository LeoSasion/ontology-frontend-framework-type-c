import type { useSourceWorkbenchImportController } from "../useSourceWorkbenchImportController";
import { countText } from "../sourceWorkbenchModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type SourceWorkbenchImportPanelProps = ReturnType<typeof useSourceWorkbenchImportController> & {
  busy: string | null;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
};

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
  setFilePath,
  setTargetTable,
  setTargetName,
  setImportMode,
  setUniqueFields,
  setConflictRule,
  runBusy,
  runImportPreviewAction,
  runImportCommitAction,
  runFolderImportPreviewAction,
  runFolderImportCommitAction,
  runImportPolicyAction,
}: SourceWorkbenchImportPanelProps) {
  const createTargetLabel = preview.suggestedDisplayName || targetName || preview.suggestedTableKey || targetTable;
  const sourceLooksLikeFile = /\.(?:csv|tsv|xlsx?|xlsm)$/i.test(filePath.trim());
  const sourceCheckBusy = busy === "preview" || busy === "folder-preview";

  function checkSource() {
    if (sourceLooksLikeFile) {
      return runBusy("preview", runImportPreviewAction);
    }
    return runBusy("folder-preview", runFolderImportPreviewAction);
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
        </label>
        <div className="buttonRow tight importCheckActions">
          <button
            className="primaryButton compactAction"
            data-testid="source-import-preview-button"
            disabled={sourceCheckBusy || !filePath.trim()}
            onClick={() => void checkSource()}
            type="button"
          >
            <Icon name="source" />
            {sourceCheckBusy ? biText("正在检查…", "Checking…") : biText("检查来源", "Check source")}
          </button>
          <span className="importSourceHint">
            {sourceLooksLikeFile
              ? biText("已识别为文件", "Detected as a file")
              : biText("自动按文件夹检查；文件路径请保留扩展名", "Checking as a folder; keep the extension for file paths")}
          </span>
        </div>
      </div>
      <details className="advancedDetails compactAdvanced">
        <summary>{biText("导入去重规则", "Import deduplication rules")}</summary>
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
              <option value="merge">{biText("合并", "Merge")}</option>
              <option value="create">{biText("新建/替换", "Create/replace")}</option>
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
              onClick={() => runBusy("import-policy-dry", () => runImportPolicyAction(false))}
              type="button"
            >
              {biText("预演策略", "Preview policy")}
            </button>
            <button
              className="miniButton"
              data-testid="import-policy-confirm-button"
              disabled={busy === "import-policy"}
              onClick={() => runBusy("import-policy", () => runImportPolicyAction(true))}
              type="button"
            >
              {biText("保存策略", "Save policy")}
            </button>
          </div>
        </div>
      </details>
      {importOperationReceipt ? (
        <div aria-live="polite" className={`operationReceipt ${importOperationReceipt.tone}`} data-testid="import-operation-receipt" role="status">
          <div>
            <strong>{importOperationReceipt.title}</strong>
            <span>{importOperationReceipt.detail}</span>
            <small>{importOperationReceipt.nextStep}</small>
          </div>
          <details data-testid="import-operation-technical-details">
            <summary>{biText("查看导入策略和回执", "View import policy and receipt")}</summary>
            <span>{biText("策略", "Policy")}: {preview.mergePolicyPreview.uniqueFields.join(", ") || biText("自动", "auto")} · {preview.mergePolicyPreview.conflictRule}</span>
            <span>{importOperationReceipt.technical}</span>
          </details>
        </div>
      ) : null}
      {folderImportPlan && folderImportPlan.fileCount > 0 ? (
        <div className="folderImportPlan" data-testid="folder-import-plan">
          <div className="folderImportPlanHeader">
            <div>
              <span className="statusBadge ok">{biText("文件夹计划", "Folder plan")}</span>
              <h4>{biText(`导入 ${folderImportPlan.fileCount} 个文件`, `Import ${folderImportPlan.fileCount} files`)}</h4>
              <p>{biText(`按文件名归并为 ${folderImportPlan.tableCount} 张业务表。`, `Grouped into ${folderImportPlan.tableCount} business tables by file name.`)}</p>
            </div>
            <button
              className="primaryButton compactAction"
              data-testid="folder-import-confirm-button"
              disabled={busy === "folder-confirm"}
              onClick={() => runBusy("folder-confirm", () => runFolderImportCommitAction(true))}
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
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {previewReadable ? (
        <>
          <div className="importConfirmationSummary" data-testid="import-confirmation-summary">
            <div>
              <span className="statusBadge ok">{biText("预检通过", "Preflight passed")}</span>
              <h4>{preview.matchedTable ? biText(`合并到 ${matchedTableName}`, `Merge into ${matchedTableName}`) : biText(`新建 ${createTargetLabel}`, `Create ${createTargetLabel}`)}</h4>
              <p>{biText("确认前不会写入；你可以先看影响，再决定是否导入。", "Nothing writes before confirmation. Review the impact before importing.")}</p>
            </div>
            <div className="importImpactGrid" data-testid="import-confirmation-impact">
              <div>
                <strong>{countText(importInsertRows)}</strong>
                <span>{biText("新增", "insert")}</span>
              </div>
              <div>
                <strong>{countText(importUpdateRows)}</strong>
                <span>{biText("更新", "update")}</span>
              </div>
              <div>
                <strong>{countText(importSkipRows)}</strong>
                <span>{biText("跳过", "skip")}</span>
              </div>
              <div>
                <strong>{countText(importAfterRows)}</strong>
                <span>{biText("导入后行数", "rows after")}</span>
              </div>
            </div>
            <div className="importSafetyStrip" data-testid="import-confirmation-safety">
              <span className={importKeyHealthy ? "ok" : "warn"}>
                {importKeyHealthy
                  ? biText("唯一键可用，无重复/空键", "Unique key is usable, no duplicate or empty keys")
                  : biText(`需复核：${importDuplicateRows} 重复行，${importEmptyKeyRows} 空键`, `Review needed: ${importDuplicateRows} duplicate rows, ${importEmptyKeyRows} empty keys`)}
              </span>
              <span>{preview.mergePolicyPreview.willWrite ? biText("确认后才写入工作区", "Writes only after confirmation") : biText("当前只做检查，不写入", "Current state is preview")}</span>
              <span>{preview.matchedTable ? biText("会合并到已有表", "Merges into an existing table") : biText("会新建工作区表", "Creates a workspace table")}</span>
            </div>
            <div className="buttonRow tight">
              <button
                className="primaryButton compactAction"
                data-testid="import-confirmation-confirm"
                disabled={busy === "import-confirm"}
                onClick={() => runBusy("import-confirm", () => runImportCommitAction(true))}
                type="button"
              >
                <Icon name="lock" />
                <Bilingual zh="确认导入" en="Confirm import" />
              </button>
            </div>
          </div>
          <div className="policyStrip">
            <div>
              <strong>{preview.profile.rowCount.toLocaleString()}</strong>
              <span>{biText("预检行", "preview rows")}</span>
            </div>
            <div>
              <strong>{preview.profile.columnCount}</strong>
              <span>{biText("字段", "fields")}</span>
            </div>
            <div>
              <strong>{preview.mergePolicyPreview.mergePlan ? String(preview.mergePolicyPreview.mergePlan.afterRowsEstimate ?? "-") : "-"}</strong>
              <span>{biText("预计行数", "estimated rows")}</span>
            </div>
            <div>
              <strong>{preview.mergePolicyPreview.willWrite ? biText("会写入", "writes") : biText("不写入", "preview")}</strong>
              <span>{biText("安全边界", "safety")}</span>
            </div>
          </div>
        </>
      ) : null}
    </article>
  );
}
