import type { ConnectorAdapterContract, DataConnectorConfig, ImportJob } from "../types";
import type { useSourceWorkbenchConnectorController } from "../useSourceWorkbenchConnectorController";
import { Bilingual, biText } from "./Bilingual";
import { OperationReceipt } from "./OperationReceipt";

type SourceWorkbenchConnectorPanelProps = ReturnType<typeof useSourceWorkbenchConnectorController> & {
  showAdvanced: boolean;
  busy: string | null;
  connectors: DataConnectorConfig[];
  connectorAdapters: ConnectorAdapterContract[];
  importJobs: ImportJob[];
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  onRemoveImportJob: (options: { jobKey: string; confirm?: boolean }) => Promise<void>;
};

export function SourceWorkbenchConnectorPanel({
  showAdvanced,
  busy,
  connectors,
  connectorAdapters,
  importJobs,
  connectorEditingKey,
  connectorName,
  connectorType,
  connectorProvider,
  connectorStatus,
  connectorEndpoint,
  connectorResource,
  connectorImportMode,
  connectorTargetTable,
  connectorUniqueFields,
  connectorConflictRule,
  connectorNotes,
  connectorOperationReceipt,
  setConnectorName,
  setConnectorType,
  setConnectorProvider,
  setConnectorStatus,
  setConnectorEndpoint,
  setConnectorResource,
  setConnectorImportMode,
  setConnectorTargetTable,
  setConnectorUniqueFields,
  setConnectorConflictRule,
  setConnectorNotes,
  resetConnectorDraft,
  loadConnector,
  runBusy,
  runConnectorSaveAction,
  runConnectorSyncAction,
  runConnectorRemoveAction,
  onRemoveImportJob,
}: SourceWorkbenchConnectorPanelProps) {
  const panelClassName = showAdvanced ? "workbenchPanel advancedPanel" : "workbenchPanel advancedPanel collapsed";
  const availableAdapters = connectorAdapters.filter((adapter) => adapter.available);
  const selectedAdapter = connectorAdapters.find((adapter) => adapter.connectorType === connectorType);
  const selectedAdapterAvailable = selectedAdapter?.available === true;
  const selectedUnavailableAdapter = selectedAdapter && !selectedAdapter.available ? selectedAdapter : null;

  function connectorTypeLabel(connectorTypeValue: string) {
    if (connectorTypeValue === "file") return biText("文件", "File");
    if (connectorTypeValue === "database") return biText("数据库", "Database");
    return connectorTypeValue.toUpperCase();
  }

  function adapterAvailableFor(connector: DataConnectorConfig) {
    return connectorAdapters.some((adapter) => adapter.connectorType === connector.type && adapter.available);
  }

  return (
    <>
      <article className={panelClassName}>
        <div className="tileHeader">
          <h3><Bilingual zh="保存数据连接" en="Save data connection" /></h3>
          <span>{connectors.length} · {availableAdapters.length} {biText("个可用 Adapter", "available Adapters")}</span>
        </div>
        <div className="connectorBusinessLead" data-testid="connector-business-lead">
          <strong>{connectorEditingKey ? biText("正在编辑已有连接", "Editing an existing connection") : biText("把常用文件或系统保存成可复用入口", "Save a common file or system as a reusable entry")}</strong>
          <span>{biText("保存只记录连接配置；同步前先由只读 Adapter 检查来源，写入仍需单独确认。", "Saving only records the connection setup. A read-only Adapter checks the source before sync, and writes still need separate confirmation.")}</span>
        </div>
        <div className="formGrid connectorPrimaryForm">
          <label>
            <span>{biText("连接名称", "Connection name")}</span>
            <input value={connectorName} onChange={(event) => setConnectorName(event.target.value)} />
          </label>
          <label className="wideField">
            <span>{biText("文件路径或接口地址", "File path or endpoint")}</span>
            <input value={connectorEndpoint} onChange={(event) => setConnectorEndpoint(event.target.value)} />
          </label>
          <label>
            <span>{biText("生成的数据表", "Result table")}</span>
            <input value={connectorTargetTable} onChange={(event) => setConnectorTargetTable(event.target.value)} />
          </label>
        </div>
        <details className="advancedDetails compactAdvanced connectorTechnicalDetails" data-testid="connector-technical-details">
          <summary>{biText("连接规则和写入策略", "Connection rules and write policy")}</summary>
          <div className="formGrid">
            <label>
              <span>{biText("类型", "Type")}</span>
              <select value={connectorType} onChange={(event) => setConnectorType(event.target.value)}>
                {availableAdapters.map((adapter) => (
                  <option key={adapter.adapterId} value={adapter.connectorType}>{connectorTypeLabel(adapter.connectorType)}</option>
                ))}
                {selectedUnavailableAdapter ? (
                  <option disabled value={selectedUnavailableAdapter.connectorType}>
                    {connectorTypeLabel(selectedUnavailableAdapter.connectorType)} · {biText("未安装 Adapter", "Adapter not installed")}
                  </option>
                ) : null}
              </select>
            </label>
            <label>
              <span>{connectorType === "file" ? biText("提供方", "Provider") : biText("只读资源", "Read-only resource")}</span>
              <input
                value={connectorType === "file" ? connectorProvider : connectorResource}
                onChange={(event) => connectorType === "file" ? setConnectorProvider(event.target.value) : setConnectorResource(event.target.value)}
              />
            </label>
            <label>
              <span>{biText("状态", "Status")}</span>
              <select value={connectorStatus} onChange={(event) => setConnectorStatus(event.target.value)}>
                <option value="draft">{biText("草稿", "Draft")}</option>
                <option value="active">{biText("启用", "Active")}</option>
                <option value="paused">{biText("暂停", "Paused")}</option>
              </select>
            </label>
            <label>
              <span>{biText("同步模式", "Sync mode")}</span>
              <select value={connectorImportMode} onChange={(event) => setConnectorImportMode(event.target.value)}>
                <option value="auto">{biText("自动", "Auto")}</option>
                <option value="create">{biText("新建/替换", "Create/replace")}</option>
                <option value="merge">{biText("合并", "Merge")}</option>
              </select>
            </label>
            <label>
              <span>{biText("唯一键", "Unique key")}</span>
              <input value={connectorUniqueFields} onChange={(event) => setConnectorUniqueFields(event.target.value)} />
            </label>
            <label>
              <span>{biText("冲突规则", "Conflict rule")}</span>
              <select value={connectorConflictRule} onChange={(event) => setConnectorConflictRule(event.target.value)}>
                <option value="overwrite">{biText("覆盖", "Overwrite")}</option>
                <option value="fill-empty">{biText("只填空值", "Fill empty")}</option>
                <option value="skip-existing">{biText("跳过已有", "Skip existing")}</option>
              </select>
            </label>
            <label className="wideField">
              <span>{biText("备注", "Notes")}</span>
              <input value={connectorNotes} onChange={(event) => setConnectorNotes(event.target.value)} />
            </label>
          </div>
        </details>
        {!selectedAdapterAvailable ? (
          <p className="quietText" data-testid="connector-adapter-unavailable">
            {biText("未安装该类型的 Adapter。", "No Adapter is installed for this type.")}
          </p>
        ) : null}
        <div className="buttonRow">
          <button className="secondaryButton" data-testid="connector-save-dry-run-button" disabled={!selectedAdapterAvailable || busy === "connector-save-dry"} onClick={() => runBusy("connector-save-dry", () => runConnectorSaveAction(false))} type="button">
            {biText("预演保存", "Preview save")}
          </button>
          <button className="primaryButton" data-testid="connector-save-button" disabled={!selectedAdapterAvailable || busy === "connector-save"} onClick={() => runBusy("connector-save", () => runConnectorSaveAction(true))} type="button">
            {biText("保存数据连接", "Save data connection")}
          </button>
          <button className="secondaryButton" onClick={resetConnectorDraft} type="button">
            {biText("新建连接", "New connection")}
          </button>
        </div>
        {connectorOperationReceipt ? (
          <OperationReceipt
            receipt={connectorOperationReceipt}
            summary={biText("查看连接回执", "View connection receipt")}
            technical={<span>{connectorOperationReceipt.technical}</span>}
            technicalTestId="connector-operation-technical-details"
            testId="connector-operation-receipt"
          />
        ) : null}
        <ul className="metricList connectorList">
          {connectors.slice(0, 6).map((connector) => (
            <li key={connector.connectorKey}>
              <div>
                <strong>{connector.name}</strong>
                <span>{connector.provider || connector.type || "-"} · {connector.config?.targetTableKey ?? "-"} · {connector.lastSyncStatus ?? biText("还未同步", "Not synced yet")}</span>
              </div>
              <div className="jobActions">
                <button className="miniButton" data-testid={`connector-load-${connector.connectorKey}`} onClick={() => loadConnector(connector)} type="button">
                  {biText("编辑", "Edit")}
                </button>
                <button className="miniButton" data-testid={`connector-sync-dry-${connector.connectorKey}`} disabled={!adapterAvailableFor(connector) || busy === `connector-sync-dry-${connector.connectorKey}`} onClick={() => runBusy(`connector-sync-dry-${connector.connectorKey}`, () => runConnectorSyncAction(connector, false))} type="button">
                  {biText("预演同步", "Preview sync")}
                </button>
                <button className="miniButton" data-testid={`connector-sync-${connector.connectorKey}`} disabled={!adapterAvailableFor(connector) || busy === `connector-sync-${connector.connectorKey}`} onClick={() => runBusy(`connector-sync-${connector.connectorKey}`, () => runConnectorSyncAction(connector, true))} type="button">
                  {biText("确认同步", "Confirm sync")}
                </button>
                <button className="miniButton dangerButton" data-testid={`connector-remove-${connector.connectorKey}`} disabled={busy === `connector-remove-${connector.connectorKey}`} onClick={() => runBusy(`connector-remove-${connector.connectorKey}`, () => runConnectorRemoveAction(connector))} type="button">
                  {biText("删除", "Delete")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      </article>

      <article className={panelClassName}>
        <div className="tileHeader">
          <h3><Bilingual zh="清理导入记录" en="Clean import records" /></h3>
          <span>{importJobs.length}</span>
        </div>
        <p className="quietText">
          {biText("这里管理的是导入回执和记录，不是源业务文件；删除前可以先预览影响。", "This manages import receipts and records, not source business files. Preview the impact before deleting.")}
        </p>
        <ul className="metricList">
          {importJobs.slice(0, 6).map((job) => (
            <li key={job.job_key}>
              <div>
                <strong>{job.table_key ?? "-"}</strong>
                <span>{job.row_count.toLocaleString()} {biText("行", "rows")} · {job.status} · {job.mode}</span>
              </div>
              <div className="jobActions">
                <button
                  className="miniButton"
                  data-testid={`import-job-dry-remove-${job.job_key}`}
                  disabled={busy === `job-dry-${job.job_key}`}
                  onClick={() => runBusy(`job-dry-${job.job_key}`, () => onRemoveImportJob({ jobKey: job.job_key, confirm: false }))}
                  type="button"
                >
                  {biText("预览清理", "Preview cleanup")}
                </button>
                <button
                  className="miniButton dangerButton"
                  data-testid={`import-job-remove-${job.job_key}`}
                  disabled={busy === `job-remove-${job.job_key}`}
                  onClick={() => runBusy(`job-remove-${job.job_key}`, () => onRemoveImportJob({ jobKey: job.job_key, confirm: true }))}
                  type="button"
                >
                  {biText("确认清理", "Confirm cleanup")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      </article>
    </>
  );
}
