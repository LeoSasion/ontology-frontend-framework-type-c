import { useState, type Dispatch, type SetStateAction } from "react";
import type { SourceRunSummary, WorkbenchTable } from "../types";
import { Bilingual, biText, translateName } from "./Bilingual";
import { Icon } from "./Icons";

type SourceWorkbenchDataManagementPanelProps = {
  busy: string | null;
  sourceRuns: SourceRunSummary[];
  tables: WorkbenchTable[];
  selectedManagedSourceKey: string;
  sourceRenameName: string;
  setSourceRenameName: Dispatch<SetStateAction<string>>;
  selectManagedSource: (tableKey: string) => void;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  onInspectSource: (table: string) => Promise<void>;
  onRenameSource: (options: { source: string; name: string; confirm?: boolean }) => Promise<void>;
  onDeleteSource: (options: { source: string; confirm?: boolean }) => Promise<void>;
};

type SourceListItem = {
  key: string;
  name: string;
  sourceFile: string;
  rowCount: number;
  columnCount: number;
};

function buildSourceList(sourceRuns: SourceRunSummary[], tables: WorkbenchTable[]): SourceListItem[] {
  if (tables.length) {
    return tables.map((table) => ({
      key: table.table_key,
      name: table.display_name,
      sourceFile: table.source_file,
      rowCount: table.row_count,
      columnCount: table.column_count,
    }));
  }
  const seen = new Set<string>();
  return sourceRuns.flatMap((run) => {
    if (seen.has(run.table_key)) return [];
    seen.add(run.table_key);
    return [{
      key: run.table_key,
      name: run.name,
      sourceFile: run.source_file,
      rowCount: run.row_count,
      columnCount: run.column_count,
    }];
  });
}

export function SourceWorkbenchDataManagementPanel({
  busy,
  sourceRuns,
  tables,
  selectedManagedSourceKey,
  sourceRenameName,
  setSourceRenameName,
  selectManagedSource,
  runBusy,
  onInspectSource,
  onRenameSource,
  onDeleteSource,
}: SourceWorkbenchDataManagementPanelProps) {
  const [clearNotice, setClearNotice] = useState("");
  const sourceList = buildSourceList(sourceRuns, tables);
  const selectedTable = tables.find((table) => table.table_key === selectedManagedSourceKey) ?? tables[0];
  const selectedLabel = selectedTable?.display_name ?? selectedManagedSourceKey;
  const tableKeys = tables.map((table) => table.table_key).filter(Boolean);

  async function runClearSandbox(confirm: boolean) {
    setClearNotice("");
    for (const tableKey of tableKeys) {
      await onDeleteSource({ source: tableKey, confirm });
    }
    setClearNotice(confirm
      ? biText(`已请求清空 ${tableKeys.length} 张表`, `Requested clearing ${tableKeys.length} tables`)
      : biText(`已预演 ${tableKeys.length} 张表的删除影响`, `Previewed delete impact for ${tableKeys.length} tables`));
  }

  if (!tables.length) {
    return null;
  }

  return (
    <article className="workbenchPanel sourceLifecyclePanel" data-testid="source-data-management-panel">
      <div className="tileHeader">
        <div>
          <h3><Bilingual zh="已接入数据" en="Connected data" /></h3>
          <p className="quietText">
            <Bilingual
              zh="这里管理当前工作区的数据表。删除会先走受控命令，并同步清理相关字段、视图、关系和看板引用。"
              en="Manage the current workspace tables here. Deletion uses the controlled command and clears related fields, views, links, and dashboard references."
            />
          </p>
        </div>
        <span>{tables.length}</span>
      </div>

      <div className="sourceLifecycleList" data-testid="source-lifecycle-list">
        {sourceList.map((source) => (
          <article className={source.key === selectedManagedSourceKey ? "runRow selected" : "runRow"} key={source.key}>
            <div>
              <strong><Bilingual {...translateName(source.name)} /></strong>
              <span>{source.sourceFile || source.key}</span>
              <div className="inlineActions">
                <button className="miniButton" data-testid={`source-inspect-${source.key}`} disabled={busy === `source-inspect-${source.key}`} onClick={() => runBusy(`source-inspect-${source.key}`, () => onInspectSource(source.key))} type="button">
                  <Icon name="evidence" />
                  {biText("检查", "Inspect")}
                </button>
                <button className="miniButton" data-testid={`source-select-${source.key}`} onClick={() => selectManagedSource(source.key)} type="button">
                  {source.key === selectedManagedSourceKey ? biText("当前", "Current") : biText("管理", "Manage")}
                </button>
              </div>
            </div>
            <dl>
              <div>
                <dt>{biText("行", "Rows")}</dt>
                <dd>{source.rowCount}</dd>
              </div>
              <div>
                <dt>{biText("列", "Cols")}</dt>
                <dd>{source.columnCount}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>

      <div className="sourceManagement">
        <div className="formGrid twoCol">
          <label>
            <span>{biText("当前管理的数据源", "Managed source")}</span>
            <select value={selectedManagedSourceKey} onChange={(event) => selectManagedSource(event.target.value)}>
              {tables.map((table) => <option key={table.table_key} value={table.table_key}>{table.display_name}</option>)}
            </select>
          </label>
          <label>
            <span>{biText("显示名称", "Display name")}</span>
            <input value={sourceRenameName} onChange={(event) => setSourceRenameName(event.target.value)} />
          </label>
        </div>
        <div className="buttonRow tight">
          <button className="miniButton" data-testid="source-rename-dry-run-button" disabled={busy === "source-rename-dry"} onClick={() => runBusy("source-rename-dry", () => onRenameSource({ source: selectedManagedSourceKey, name: sourceRenameName, confirm: false }))} type="button">
            {biText("预演改名", "Preview rename")}
          </button>
          <button className="miniButton" data-testid="source-rename-button" disabled={busy === "source-rename"} onClick={() => runBusy("source-rename", () => onRenameSource({ source: selectedManagedSourceKey, name: sourceRenameName, confirm: true }))} type="button">
            {biText("确认改名", "Confirm rename")}
          </button>
        </div>
      </div>

      <details className="advancedDetails compactAdvanced sourceDangerZone" data-testid="source-danger-zone">
        <summary>{biText("删除或清空沙盒", "Delete or clear sandbox")}</summary>
        <p>
          {biText(
            `当前选择：${selectedLabel}。删除会移除依赖它的明细、关系、导入任务和看板组件。`,
            `Selected: ${selectedLabel}. Deletion removes details, links, import jobs, and dashboard widgets that depend on it.`,
          )}
        </p>
        <div className="buttonRow tight">
          <button className="miniButton dangerButton" data-testid="source-delete-dry-run-button" disabled={busy === "source-delete-dry"} onClick={() => runBusy("source-delete-dry", () => onDeleteSource({ source: selectedManagedSourceKey, confirm: false }))} type="button">
            {biText("预演删除影响", "Preview delete impact")}
          </button>
          <button className="miniButton dangerButton" data-testid="source-delete-button" disabled={busy === "source-delete"} onClick={() => runBusy("source-delete", () => onDeleteSource({ source: selectedManagedSourceKey, confirm: true }))} type="button">
            {biText("确认删除当前数据源", "Delete current source")}
          </button>
        </div>
        <div className="buttonRow tight">
          <button className="miniButton dangerButton ghostDangerButton" data-testid="source-clear-dry-run-button" disabled={busy === "source-clear-dry"} onClick={() => runBusy("source-clear-dry", () => runClearSandbox(false))} type="button">
            {biText("预演清空沙盒", "Preview clear sandbox")}
          </button>
          <button className="miniButton dangerButton" data-testid="source-clear-button" disabled={busy === "source-clear"} onClick={() => runBusy("source-clear", () => runClearSandbox(true))} type="button">
            {biText(`确认清空 ${tables.length} 张表`, `Clear ${tables.length} tables`)}
          </button>
        </div>
        {clearNotice ? <p className="sourceManagerNotice">{clearNotice}</p> : null}
      </details>
    </article>
  );
}
