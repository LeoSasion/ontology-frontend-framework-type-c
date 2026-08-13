import type {
  FieldConfig,
  FormulaDefinition,
  ImportPreview,
  MetricDefinition,
  QueryResult,
  RelationshipRecord,
  WorkbenchPayload,
  WorkbenchTable,
  WorkspaceStatus,
} from "./types";
import { biText } from "./components/Bilingual";
import { numberValue } from "./safeValue";

export { numberValue };

export function confidencePercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function queryIntentLabel(value: string) {
  if (value === "whitelist aggregate query; no user SQL accepted") {
    return biText("白名单聚合查询；不接受用户 SQL", "Whitelist aggregate query; no user SQL accepted");
  }
  return value;
}

export function splitCsv(value: string) {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

export function splitInputPaths(value: string) {
  return value.split(/\r?\n|[,，]/).map((item) => item.trim()).filter(Boolean);
}

export function metricValue(metrics: Record<string, number>, key: string) {
  const value = metrics[key];
  return typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : "0";
}

export function runtimeLabel(engine?: string) {
  if (engine === "duckdb") {
    return "DuckDB";
  }
  if (engine === "sqlite") return biText("已阻断的旧引擎", "Blocked legacy engine");
  return biText("待检测", "Unknown");
}

export function actionResultSummary(result: Record<string, unknown> | null) {
  if (!result) return "";
  if (typeof result.proposed === "number") return biText(`已生成 ${result.proposed} 条建议`, `${result.proposed} suggestions generated`);
  if (typeof result.saved === "number") return biText(`已保存 ${result.saved} 条配置`, `${result.saved} configs saved`);
  if (typeof result.count === "number") return biText(`共 ${result.count} 条记录`, `${result.count} records`);
  if (Array.isArray(result.rows)) return biText(`返回 ${result.rows.length} 行结果`, `${result.rows.length} rows returned`);
  if (result.confirmed === true) return biText("已确认保存", "Saved");
  if (result.requiresConfirmation === true) return biText("这是预演结果，确认后才写入", "Preview only, confirm to write");
  return biText("操作已完成", "Action completed");
}

export function resultRows(result: Record<string, unknown> | null) {
  if (!result) return [];
  const directRows = result.rows;
  if (Array.isArray(directRows)) return directRows as Array<Record<string, unknown>>;
  const tableQuery = result.tableQuery;
  if (tableQuery && typeof tableQuery === "object" && Array.isArray((tableQuery as { rows?: unknown[] }).rows)) {
    return (tableQuery as { rows: Array<Record<string, unknown>> }).rows;
  }
  return [];
}

export function resultManifest(result: Record<string, unknown> | null) {
  const manifest = result?.manifest;
  return manifest && typeof manifest === "object" ? manifest as Record<string, unknown> : null;
}

export function recordNumber(record: Record<string, unknown> | null | undefined, key: string) {
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function countText(value: number) {
  return value.toLocaleString();
}

export function sourceProfileSummary(result: Record<string, unknown> | null) {
  const manifest = resultManifest(result);
  if (!manifest) return actionResultSummary(result);
  return [
    `${numberValue(manifest.sourceCount)} ${biText("个文件", "files")}`,
    `${numberValue(manifest.tableCount)} ${biText("张表", "tables")}`,
    `${numberValue(manifest.relationshipCount)} ${biText("条业务连接", "business links")}`,
    `${numberValue(manifest.metricSqlExecutableCount)}/${numberValue(manifest.metricSqlPlanCount)} ${biText("个可用问题", "answerable questions")}`,
  ].join(" · ");
}

export function sourceProfileBusinessStatus(result: Record<string, unknown> | null) {
  const manifest = resultManifest(result);
  if (!manifest) {
    return {
      title: actionResultSummary(result) || biText("证据摘要已返回", "Evidence summary returned"),
      impact: biText("先查看下面的摘要，再决定是否让 Agent 生成看板草案。", "Review the summary first, then decide whether Agent should draft a dashboard."),
      nextStep: biText("如果摘要看起来不完整，重新选择文件夹生成。", "If the summary looks incomplete, choose the folder again and regenerate."),
    };
  }
  const sourceCount = numberValue(manifest.sourceCount);
  const tableCount = numberValue(manifest.tableCount);
  const relationshipCount = numberValue(manifest.relationshipCount);
  const executableMetricCount = numberValue(manifest.metricSqlExecutableCount);
  const metricPlanCount = numberValue(manifest.metricSqlPlanCount);
  const ready = sourceCount > 0 && tableCount > 0 && executableMetricCount > 0;
  return {
    title: ready
      ? biText("证据摘要可用于分析", "Evidence summary is ready for analysis")
      : biText("证据摘要已生成，但还不够可用", "Evidence summary was created but needs review"),
    impact: ready
      ? biText(
        `已识别 ${sourceCount} 个文件、${tableCount} 张表、${relationshipCount} 条业务连接，并验证 ${executableMetricCount}/${metricPlanCount} 个可回答问题。`,
        `${sourceCount} files, ${tableCount} tables, ${relationshipCount} business links, and ${executableMetricCount}/${metricPlanCount} answerable questions are ready.`,
      )
      : biText(
        `已识别 ${sourceCount} 个文件、${tableCount} 张表，但可回答问题不足；先检查表格列名和来源覆盖。`,
        `${sourceCount} files and ${tableCount} tables were found, but answerable questions are limited. Check headers and source coverage first.`,
      ),
    nextStep: ready
      ? biText("下一步可以生成看板候选，或直接让 Agent 解释这些证据。", "Next, create a dashboard candidate or ask Agent to explain the evidence.")
      : biText("先换一个更完整的目录重试，或让 Agent 根据回执指出缺口。", "Retry with a more complete folder, or ask Agent to identify the gaps from the receipt."),
  };
}

export function sourceProfileErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return String(error || biText("证据摘要生成失败", "Evidence summary failed"));
}

export function sourceProfileRecovery(error: string, inputs: string) {
  const normalized = error.toLowerCase();
  const inputCount = splitInputPaths(inputs).length;
  if (!inputCount) {
    return {
      title: biText("还没有可扫描的路径", "No path to scan yet"),
      summary: biText("先粘贴一个本地文件或文件夹路径；系统只读扫描，不会改动源目录。", "Paste a local file or folder path first. The scan is read-only and will not modify source folders."),
      steps: [
        biText("从资源管理器复制文件夹地址，粘贴到上方输入框。", "Copy a folder path from Explorer and paste it above."),
        biText("确认目录里有 CSV、XLS 或 XLSX 表格文件。", "Confirm the folder contains CSV, XLS, or XLSX table files."),
        biText("先从一个小目录开始，确认摘要可读后再扩大范围。", "Start with one small folder, then expand after the summary is readable."),
      ],
    };
  }
  if (normalized.includes("not found") || normalized.includes("no such") || normalized.includes("does not exist") || normalized.includes("找不到")) {
    return {
      title: biText("路径没有找到", "Path was not found"),
      summary: biText("通常是路径少了一层、目录名写错，或把文件名和文件夹名混在了一起。", "This usually means a missing folder level, a mistyped folder name, or a file/folder path mix-up."),
      steps: [
        biText("确认路径能在资源管理器里直接打开。", "Confirm the path opens directly in Explorer."),
        biText("一行放一个路径；多个路径不要夹杂说明文字。", "Put one path per line and avoid extra notes in the input."),
        biText("先缩小到一个确定存在的文件或文件夹，再重新生成摘要。", "Narrow to one file or folder that definitely exists, then regenerate the summary."),
      ],
    };
  }
  if (normalized.includes("permission") || normalized.includes("access") || normalized.includes("denied") || normalized.includes("权限")) {
    return {
      title: biText("系统没有读取权限", "Read permission is blocked"),
      summary: biText("生成证据摘要只需要读取文件；如果目录受保护，请换到可读副本或调整本地权限。", "Creating an evidence summary only needs read access. Use a readable copy or adjust local permissions for protected folders."),
      steps: [
        biText("把文件复制到当前用户可读的位置。", "Copy the files to a location this user can read."),
        biText("不要把凭据、日志或生产库一起放进扫描目录。", "Do not include credentials, logs, or production databases in the scan folder."),
        biText("重新生成摘要，确认仍不写回外部源目录。", "Create the summary again; external source folders remain untouched."),
      ],
    };
  }
  if (normalized.includes("empty") || normalized.includes("unsupported") || normalized.includes("no files") || normalized.includes("没有文件")) {
    return {
      title: biText("没有找到可分析表格", "No analyzable spreadsheet found"),
      summary: biText("证据摘要需要 CSV、XLS、XLSX 或可解析的表格文件。", "Evidence summaries need CSV, XLS, XLSX, or another parseable table file."),
      steps: [
        biText("确认目录里有可分析表格，而不只是压缩包或说明文档。", "Confirm the folder contains analyzable spreadsheets, not only archives or notes."),
        biText("先保留原始列名，不要手工合并表头。", "Keep original column names first; do not manually merge headers."),
        biText("如果文件很多，先扫描一个小目录确认结果。", "If there are many files, scan one small folder first."),
      ],
    };
  }
  return {
    title: biText("证据摘要没有完成", "Evidence summary did not finish"),
    summary: biText("数据没有被写坏；这一步只是生成证据回执。先按下面路径缩小问题。", "No data was damaged; this step only creates evidence receipts. Use the steps below to narrow the issue."),
    steps: [
      biText("先确认路径、权限和文件格式，再重新运行。", "Check path, permissions, and file format, then run again."),
      biText("只放一个本地文件夹重试，避免一次扫描太多来源。", "Retry with one local folder to avoid scanning too many sources at once."),
      biText("让 Agent 根据错误和当前工作区给出下一步，不要创建草案。", "Ask Agent for next steps from the error and workspace context, without creating drafts."),
    ],
  };
}

export function semanticFieldNames(fields: FieldConfig[]) {
  return fields.slice(0, 4).map((field) => field.field_name);
}

export function buildFieldSemanticReadiness(fields: FieldConfig[]) {
  const relationshipFields = fields.filter((field) => field.role === "identity_key" || field.usage === "joinable");
  const readyFields = fields.filter((field) => {
    const dashboardReady = field.role === "measure" || field.role === "dimension" || field.role === "status" || field.usage === "aggregatable" || field.usage === "groupable" || field.usage === "filterable";
    return dashboardReady && field.confidence >= 0.82;
  });
  const reviewFields = fields.filter((field) => {
    const missingPurpose = !field.role || !field.usage;
    const lowConfidence = field.confidence < 0.82;
    const ambiguousNumericId = field.role === "measure" && /(^|[_\s-])(id|key|code|uuid|编号|编码)([_\s-]|$)/i.test(field.field_name);
    return missingPurpose || lowConfidence || ambiguousNumericId;
  });
  return {
    readyFields,
    relationshipFields,
    reviewFields,
    readyNames: semanticFieldNames(readyFields),
    relationshipNames: semanticFieldNames(relationshipFields),
    reviewNames: semanticFieldNames(reviewFields),
  };
}

export type SourceWorkbenchCollections = {
  tables: WorkbenchTable[];
  fields: FieldConfig[];
  metrics: MetricDefinition[];
  relationships: RelationshipRecord[];
  relationshipRecommendations: NonNullable<WorkbenchPayload["relationshipRecommendations"]>;
  importJobs: WorkbenchPayload["importJobs"];
  importPolicies: NonNullable<WorkbenchPayload["importPolicies"]>;
  connectors: NonNullable<WorkbenchPayload["connectors"]>;
  connectorAdapters: NonNullable<WorkbenchPayload["connectorAdapters"]>;
  rowFormulas: FormulaDefinition[];
  navigationModules: NonNullable<WorkbenchPayload["navigation"]>;
  sourceIntelligenceRuns: WorkbenchPayload["sourceIntelligenceRuns"];
  fieldRoles: string[];
  fieldUsages: string[];
  safeAggregations: string[];
  sourceRuns: WorkspaceStatus["sourceRuns"];
  queryRows: QueryResult["rows"];
  firstTableKey: string;
};

export function buildSourceWorkbenchCollections(
  workbench: WorkbenchPayload,
  status: WorkspaceStatus,
  query: QueryResult,
): SourceWorkbenchCollections {
  const tables = Array.isArray(workbench.tables) ? workbench.tables : [];
  const fields = Array.isArray(workbench.fields) ? workbench.fields : [];
  const metrics = Array.isArray(workbench.metrics) ? workbench.metrics : [];
  const relationships = Array.isArray(workbench.relationships) ? workbench.relationships : [];
  const relationshipRecommendations = Array.isArray(workbench.relationshipRecommendations) ? workbench.relationshipRecommendations : [];
  const importJobs = Array.isArray(workbench.importJobs) ? workbench.importJobs : [];
  const importPolicies = Array.isArray(workbench.importPolicies) ? workbench.importPolicies : [];
  const connectors = Array.isArray(workbench.connectors) ? workbench.connectors : [];
  const connectorAdapters = Array.isArray(workbench.connectorAdapters) ? workbench.connectorAdapters : [];
  const rowFormulas = Array.isArray(workbench.formulas) ? workbench.formulas : [];
  const navigationModules = Array.isArray(workbench.navigation) ? workbench.navigation : [];
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const fieldRoles = Array.isArray(workbench.fieldRoles) ? workbench.fieldRoles : [];
  const fieldUsages = Array.isArray(workbench.fieldUsages) ? workbench.fieldUsages : [];
  const safeAggregations = Array.isArray(workbench.safeAggregations) ? workbench.safeAggregations : [];
  const sourceRuns = Array.isArray(status.sourceRuns) ? status.sourceRuns : [];
  const queryRows = Array.isArray(query.rows) ? query.rows : [];
  const firstTableKey = tables[0]?.table_key ?? "";

  return {
    tables,
    fields,
    metrics,
    relationships,
    relationshipRecommendations,
    importJobs,
    importPolicies,
    connectors,
    connectorAdapters,
    rowFormulas,
    navigationModules,
    sourceIntelligenceRuns,
    fieldRoles,
    fieldUsages,
    safeAggregations,
    sourceRuns,
    queryRows,
    firstTableKey,
  };
}

export type SourceWorkbenchSelection = {
  selectedTableKey: string;
  selectedFields: FieldConfig[];
  selectedMetrics: MetricDefinition[];
  measureFields: FieldConfig[];
  groupFields: FieldConfig[];
  indexCandidateName: string;
  selectedFormulaAssets: Array<FormulaDefinition | MetricDefinition>;
};

export function buildSourceWorkbenchSelection(options: {
  tables: WorkbenchTable[];
  fields: FieldConfig[];
  metrics: MetricDefinition[];
  rowFormulas: FormulaDefinition[];
  activeTableKey: string;
  firstTableKey: string;
}): SourceWorkbenchSelection {
  const { tables, fields, metrics, rowFormulas, activeTableKey, firstTableKey } = options;
  const selectedTableKey = tables.some((table) => table.table_key === activeTableKey) ? activeTableKey : firstTableKey;
  const selectedFields = fields.filter((field) => field.table_key === selectedTableKey);
  const selectedMetrics = metrics.filter((metric) => metric.table_key === selectedTableKey);
  const selectedRowFormulas = rowFormulas.filter((formula) => {
    const tableKey = String(formula.table_key ?? formula.tableKey ?? "");
    const mode = String(formula.mode ?? "row");
    return tableKey === selectedTableKey && mode === "row";
  });
  const calculatedMeasureFields: FieldConfig[] = selectedRowFormulas.map((formula) => ({
    table_key: selectedTableKey,
    field_name: String(formula.name ?? formula.field_key ?? formula.fieldKey ?? ""),
    role: "measure",
    usage: "aggregatable",
    confidence: 0.96,
    source: "calculated-field",
    note: String(formula.formula_text ?? formula.formulaText ?? ""),
  })).filter((field) => field.field_name);
  const analysisFields = [
    ...selectedFields,
    ...calculatedMeasureFields.filter((formula) => !selectedFields.some((field) => field.field_name === formula.field_name)),
  ];
  const measureFields = analysisFields.filter((field) => field.role === "measure" || field.usage === "aggregatable");
  const groupFields = analysisFields.filter((field) => field.role === "dimension" || field.role === "status" || field.usage === "groupable");
  const indexCandidateField = groupFields.find((field) => ["filterable", "groupable"].includes(field.usage) || ["dimension", "status", "identity_key"].includes(field.role)) ?? groupFields[0] ?? selectedFields[0];
  const selectedFormulaAssets = [
    ...rowFormulas.filter((formula) => (formula.table_key ?? formula.tableKey) === selectedTableKey),
    ...selectedMetrics.filter((metric) => metric.metric_type === "formula" || metric.metricType === "formula" || metric.formula_text || metric.formulaText),
  ];

  return {
    selectedTableKey,
    selectedFields,
    selectedMetrics,
    measureFields,
    groupFields,
    indexCandidateName: indexCandidateField?.field_name ?? "",
    selectedFormulaAssets,
  };
}

export type SourceWorkbenchRuntimeSummary = {
  runtimeStatus: WorkbenchPayload["queryRuntime"] | WorkspaceStatus["queryRuntime"];
  queryInfo: QueryResult["query"];
  queryRuntime: QueryResult["query"]["runtime"];
};

export function buildSourceWorkbenchRuntimeSummary(
  workbench: WorkbenchPayload,
  status: WorkspaceStatus,
  query: QueryResult,
): SourceWorkbenchRuntimeSummary {
  const queryInfo = query.query ?? { sqlIntent: "", runtime: undefined, fallbackReason: undefined };
  return {
    runtimeStatus: workbench.queryRuntime ?? status.queryRuntime,
    queryInfo,
    queryRuntime: queryInfo.runtime,
  };
}

export type ImportPreviewSummary = {
  matchedTableName: string;
  importInsertRows: number;
  importUpdateRows: number;
  importSkipRows: number;
  importDuplicateRows: number;
  importEmptyKeyRows: number;
  importAfterRows: number;
  importKeyHealthy: boolean;
};

export function buildImportPreviewSummary(options: {
  preview: ImportPreview;
  previewReadable: boolean;
  targetName: string;
}): ImportPreviewSummary {
  const { preview, previewReadable, targetName } = options;
  const mergePlan = preview.mergePolicyPreview.mergePlan ?? null;
  const uniqueKeyQuality = preview.uniqueKeyQuality ?? null;
  const matchedTableName = preview.matchedTable?.display_name ?? targetName;
  const importInsertRows = recordNumber(mergePlan, "insertRows");
  const importUpdateRows = recordNumber(mergePlan, "updateRows");
  const importSkipRows = recordNumber(mergePlan, "skipRows");
  const importDuplicateRows = recordNumber(uniqueKeyQuality, "duplicateRowsInFile");
  const importEmptyKeyRows = recordNumber(uniqueKeyQuality, "emptyKeyRows");
  const importAfterRows = mergePlan ? recordNumber(mergePlan, "afterRowsEstimate") : preview.profile.rowCount;
  const importKeyHealthy = previewReadable && importDuplicateRows === 0 && importEmptyKeyRows === 0;

  return {
    matchedTableName,
    importInsertRows,
    importUpdateRows,
    importSkipRows,
    importDuplicateRows,
    importEmptyKeyRows,
    importAfterRows,
    importKeyHealthy,
  };
}
