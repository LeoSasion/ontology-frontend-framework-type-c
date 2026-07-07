import type { Dispatch, SetStateAction } from "react";
import type { FieldConfig, FormulaDefinition, FormulaMutationPayload, FormulaPreviewPayload, MetricDefinition, QueryResult, QueryRuntimeStatus, WorkbenchTable } from "../types";
import { queryIntentLabel, runtimeLabel } from "../sourceWorkbenchModel";
import { Bilingual, biText } from "./Bilingual";

type QueryOptions = {
  table?: string;
  group?: string;
  measure?: string;
  aggregation?: string;
  limit?: number;
};

type FormulaSaveOptions = {
  id?: string;
  name: string;
  table: string;
  expression: string;
  mode?: string;
  dimension?: string;
  timeField?: string;
  valueFormat?: string;
  description?: string;
  confirm?: boolean;
};

type FormulaAsset = FormulaDefinition | MetricDefinition;

type SourceWorkbenchQueryFormulaPanelProps = {
  showAdvanced: boolean;
  busy: string | null;
  tables: WorkbenchTable[];
  selectedTableKey: string;
  groupFields: FieldConfig[];
  measureFields: FieldConfig[];
  safeAggregations: string[];
  queryForm: QueryOptions;
  queryRows: QueryResult["rows"];
  queryInfo: QueryResult["query"];
  queryRuntime?: QueryResult["query"]["runtime"];
  runtimeStatus?: QueryRuntimeStatus;
  formulaName: string;
  formulaExpression: string;
  formulaMode: string;
  formulaPreview: FormulaPreviewPayload;
  formulaMutation: FormulaMutationPayload | null;
  selectedFormulaAssets: FormulaAsset[];
  setQueryForm: Dispatch<SetStateAction<QueryOptions>>;
  setFormulaName: Dispatch<SetStateAction<string>>;
  setFormulaExpression: Dispatch<SetStateAction<string>>;
  setFormulaMode: Dispatch<SetStateAction<string>>;
  setFormulaMutation: Dispatch<SetStateAction<FormulaMutationPayload | null>>;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  onQuery: (options?: QueryOptions) => Promise<void>;
  onFormulaPreview: (options: { expression: string; table?: string; mode?: string }) => Promise<void>;
  onFormulaSave: (options: FormulaSaveOptions) => Promise<FormulaMutationPayload>;
  onFormulaDelete: (options: { formula: string; confirm?: boolean }) => Promise<FormulaMutationPayload>;
};

function formulaAssetKey(asset: FormulaAsset) {
  const raw = asset as Partial<FormulaDefinition & MetricDefinition>;
  return String(raw.field_key ?? raw.fieldKey ?? raw.metric_key ?? raw.metricKey ?? raw.name ?? raw.label ?? "");
}

function formulaAssetName(asset: FormulaAsset) {
  const raw = asset as Partial<FormulaDefinition & MetricDefinition>;
  return String(raw.name ?? raw.label ?? raw.field_key ?? raw.metric_key ?? "");
}

function formulaAssetExpression(asset: FormulaAsset) {
  const raw = asset as Partial<FormulaDefinition & MetricDefinition>;
  return String(raw.formula_text ?? raw.formulaText ?? "");
}

export function SourceWorkbenchQueryFormulaPanel({
  showAdvanced,
  busy,
  tables,
  selectedTableKey,
  groupFields,
  measureFields,
  safeAggregations,
  queryForm,
  queryRows,
  queryInfo,
  queryRuntime,
  runtimeStatus,
  formulaName,
  formulaExpression,
  formulaMode,
  formulaPreview,
  formulaMutation,
  selectedFormulaAssets,
  setQueryForm,
  setFormulaName,
  setFormulaExpression,
  setFormulaMode,
  setFormulaMutation,
  runBusy,
  onQuery,
  onFormulaPreview,
  onFormulaSave,
  onFormulaDelete,
}: SourceWorkbenchQueryFormulaPanelProps) {
  function formulaOptions(confirm = false): FormulaSaveOptions {
    return {
      name: formulaName,
      table: selectedTableKey,
      expression: formulaExpression,
      mode: formulaMode,
      dimension: groupFields[0]?.field_name,
      valueFormat: formulaMode === "aggregate" ? "compact" : "auto",
      description: formulaMode === "aggregate" ? "Formula metric saved from BI workbench." : "Calculated field saved from BI workbench.",
      confirm,
    };
  }

  async function saveFormulaDraft(confirm = false) {
    const result = await onFormulaSave(formulaOptions(confirm));
    setFormulaMutation(result);
  }

  async function deleteFormulaDraft(formula: string, confirm = false) {
    const result = await onFormulaDelete({ formula, confirm });
    setFormulaMutation(result);
  }

  const maxQueryValue = Math.max(...queryRows.map((item) => Number(item.value) || 0), 1);

  return (
    <>
      <article className="workbenchPanel widePanel">
        <div className="tileHeader">
          <h3><Bilingual zh="快速结果" en="Quick result" /></h3>
          <div className="buttonRow tight">
            <span className={runtimeStatus?.available ? "statusBadge ok" : "statusBadge warn"}>
              {runtimeStatus?.available ? biText("结果可刷新", "Results ready") : biText("等待连接", "Waiting")}
            </span>
            <button className="miniButton" data-testid="query-run-button" disabled={busy === "query"} onClick={() => runBusy("query", () => onQuery(queryForm))} type="button">
              {biText("刷新", "Refresh")}
            </button>
          </div>
        </div>
        <p className="quietText">{biText("系统按当前推荐指标刷新结果；需要手动换表、换分组时再展开高级查询。", "The system refreshes the recommended result. Open advanced query only when you need table, grouping, or measure changes.")}</p>
        <div className="barList">
          {queryRows.map((row) => {
            const value = Number(row.value) || 0;
            return (
              <div className="barRow" key={String(row.label ?? "value")}>
                <span>{row.label ?? "value"}</span>
                <div className="barTrack">
                  <div className="barFill" style={{ width: `${Math.max(8, (value / maxQueryValue) * 100)}%` }} />
                </div>
                <strong>{value.toLocaleString()}</strong>
              </div>
            );
          })}
        </div>
        <details className="advancedDetails compactAdvanced">
          <summary>{biText("高级查询设置", "Advanced query setup")}</summary>
          <div className="formGrid queryForm">
            <label>
              <span>{biText("表", "Table")}</span>
              <select value={queryForm.table ?? selectedTableKey} onChange={(event) => setQueryForm((current) => ({ ...current, table: event.target.value }))}>
                {tables.map((table) => <option key={table.table_key} value={table.table_key}>{table.display_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("分组", "Group")}</span>
              <select value={queryForm.group ?? ""} onChange={(event) => setQueryForm((current) => ({ ...current, group: event.target.value || undefined }))}>
                <option value="">{biText("不分组", "No group")}</option>
                {groupFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("度量", "Measure")}</span>
              <select value={queryForm.measure ?? "*"} onChange={(event) => setQueryForm((current) => ({ ...current, measure: event.target.value }))}>
                <option value="*">*</option>
                {measureFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("聚合", "Agg.")}</span>
              <select value={queryForm.aggregation ?? "sum"} onChange={(event) => setQueryForm((current) => ({ ...current, aggregation: event.target.value }))}>
                {safeAggregations.map((agg) => <option key={agg} value={agg}>{agg}</option>)}
              </select>
            </label>
          </div>
          <details className="advancedDetails compactAdvanced" data-testid="source-query-runtime-technical">
            <summary>{biText("查看取数诊断", "View query diagnostics")}</summary>
            <p className="quietText">{queryIntentLabel(queryInfo.sqlIntent)}</p>
            <div className="formulaMeta">
              <span>{biText("执行引擎", "Runtime")}: {runtimeLabel(queryRuntime?.engine ?? runtimeStatus?.engine)}</span>
              <span>{biText("同步行", "Synced rows")}: {queryRuntime?.syncedRows ?? "-"}</span>
              {queryInfo.fallbackReason ? <strong>{biText("已切换到备用查询", "Using fallback query")}</strong> : null}
            </div>
            {queryRuntime?.compiledSql ? <pre className="compactCode">{queryRuntime.compiledSql}</pre> : null}
          </details>
        </details>
      </article>

      <article className={showAdvanced ? "workbenchPanel advancedPanel" : "workbenchPanel advancedPanel collapsed"}>
        <div className="tileHeader">
          <h3><Bilingual zh="计算字段和指标" en="Calculated fields and metrics" /></h3>
          <div className="buttonRow tight">
            <button className="miniButton" data-testid="formula-preview-button" disabled={busy === "formula"} onClick={() => runBusy("formula", () => onFormulaPreview({ expression: formulaExpression, table: selectedTableKey, mode: formulaMode }))} type="button">
              {biText("预览", "Preview")}
            </button>
            <button className="miniButton" data-testid="formula-save-dry-run-button" disabled={busy === "formula-dry"} onClick={() => runBusy("formula-dry", () => saveFormulaDraft(false))} type="button">
              {biText("预演保存", "Preview save")}
            </button>
            <button className="primaryButton compactAction" data-testid="formula-save-confirm-button" disabled={busy === "formula-save"} onClick={() => runBusy("formula-save", () => saveFormulaDraft(true))} type="button">
              {biText("确认保存", "Confirm save")}
            </button>
          </div>
        </div>
        <label className="formulaNameField">
          <span>{biText("公式名称", "Formula name")}</span>
          <input value={formulaName} onChange={(event) => setFormulaName(event.target.value)} />
        </label>
        <textarea className="formulaInput" value={formulaExpression} onChange={(event) => setFormulaExpression(event.target.value)} aria-label={biText("公式表达式", "Formula expression")} />
        <div className="buttonRow tight">
          <select value={formulaMode} onChange={(event) => setFormulaMode(event.target.value)}>
            <option value="aggregate">{biText("聚合指标", "Aggregate metric")}</option>
            <option value="row">{biText("行级字段", "Row field")}</option>
          </select>
          <span className={formulaPreview.ok ? "statusBadge ok" : "statusBadge warn"}>{formulaPreview.ok ? biText("可编译", "Compiles") : biText("有错误", "Errors")}</span>
        </div>
        <div className="formulaMeta">
          <span>{biText("依赖字段", "Depends on")}: {formulaPreview.dependencies.join(", ") || "-"}</span>
          {formulaPreview.errors.map((error) => <strong key={error}>{error}</strong>)}
          {formulaMutation?.requiresConfirmation ? <strong>{biText("保存预演已生成", "Save preview ready")}</strong> : null}
          {formulaMutation?.confirmed ? <strong>{biText("公式已保存", "Formula saved")}</strong> : null}
          {formulaMutation?.blockedByReferences ? <strong>{biText("已有资产引用，不能直接删除", "Referenced by assets, cannot delete directly")}</strong> : null}
        </div>
        {formulaMutation?.references?.length ? (
          <div className="referenceList" data-testid="formula-reference-list">
            {formulaMutation.references.slice(0, 5).map((reference) => (
              <span key={`${reference.kind}-${reference.key}-${reference.reason}`}>
                {reference.kind}: {reference.label} · {reference.reason}
              </span>
            ))}
          </div>
        ) : null}
        <details className="advancedDetails compactAdvanced formulaTechnicalDetails" data-testid="formula-technical-details">
          <summary>{biText("查看编译后的查询", "View compiled query")}</summary>
          <pre className="compactCode">{formulaPreview.compiledSql}</pre>
        </details>
        <div className="formulaAssetList" data-testid="formula-asset-list">
          <strong>{biText("已保存公式", "Saved formulas")}</strong>
          {selectedFormulaAssets.length ? selectedFormulaAssets.map((asset) => {
            const rawAsset = asset as Partial<FormulaDefinition & MetricDefinition>;
            const key = formulaAssetKey(asset);
            return (
              <div className="formulaAssetRow" key={key}>
                <button className="textButton" type="button" onClick={() => {
                  setFormulaName(formulaAssetName(asset));
                  setFormulaExpression(formulaAssetExpression(asset));
                  setFormulaMode(String(rawAsset.mode ?? (String(rawAsset.metric_type ?? rawAsset.metricType) === "formula" ? "aggregate" : "row")));
                }}>
                  {formulaAssetName(asset)}
                </button>
                <span>{String(rawAsset.mode ?? rawAsset.aggregation ?? "formula")}</span>
                <button className="miniButton" data-testid={`formula-delete-dry-run-${key}`} type="button" onClick={() => runBusy(`formula-delete-dry-${key}`, () => deleteFormulaDraft(key, false))}>
                  {biText("删除预演", "Preview delete")}
                </button>
                <button className="miniButton danger" data-testid={`formula-delete-confirm-${key}`} type="button" onClick={() => runBusy(`formula-delete-${key}`, () => deleteFormulaDraft(key, true))}>
                  {biText("确认删除", "Delete")}
                </button>
              </div>
            );
          }) : <p className="quietText">{biText("当前表还没有保存公式。", "No saved formulas for this table yet.")}</p>}
        </div>
      </article>
    </>
  );
}
