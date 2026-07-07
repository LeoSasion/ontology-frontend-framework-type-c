import { domainPackRuntime, sourcePipelineContract } from "./contracts";
import { defaultThemePalettes, defaultUserPreferences } from "./defaultThemeData";
import type {
  ActionDraftPayload,
  AgentAskResult,
  DashboardPayload,
  FormulaPreviewPayload,
  ImportPreview,
  QueryResult,
  RelationshipPreviewPayload,
  TableQueryPayload,
  WorkbenchPayload,
  WorkspaceStatus,
} from "./types";

export const emptyWorkspaceStatus: WorkspaceStatus = {
  ok: true,
  workspace: {
    id: "default",
    name: "AIBI 工作区",
    current_source_run_id: null,
    isActive: true,
  },
  workspaces: [
    {
      id: "default",
      name: "AIBI 工作区",
      current_source_run_id: null,
      isActive: true,
    },
  ],
  counts: {
    tables: 0,
    sourceRuns: 0,
    fields: 0,
    metrics: 0,
    relationships: 0,
    dashboards: 0,
    actionDrafts: 0,
    sourceIntelligenceRuns: 0,
    connectors: 0,
  },
  sourceRuns: [],
  health: {
    ok: true,
    notes: ["工作区已就绪，请接入数据源。"],
  },
};

export const emptyImportPreview: ImportPreview = {
  ok: true,
  dryRun: true,
  file: "",
  suggestedTableKey: "",
  matchedTable: null,
  profile: {
    rowCount: 0,
    columnCount: 0,
    fields: [],
    measures: [],
    dimensions: [],
    identityKeys: [],
    warnings: [],
  },
  matches: [],
  uniqueKeyQuality: null,
  mergePolicyPreview: {
    mode: "preview",
    uniqueFields: [],
    conflictRule: "skip",
    willWrite: false,
  },
  sourcePipelineContract,
};

export const emptyQueryResult: QueryResult = {
  ok: true,
  query: {
    table: "",
    mode: "idle",
    measure: "",
    aggregation: "count",
    sqlIntent: "No query has run yet.",
  },
  rows: [],
};

export const emptyTableQuery: TableQueryPayload = {
  ok: true,
  tableQuery: {
    mode: "detail",
    tableKey: "",
    tableName: "",
    columns: [],
    rows: [],
    totalRows: 0,
    filteredRows: 0,
    limit: 50,
    offset: 0,
    page: 1,
    pageCount: 0,
    filters: [],
    sort: [],
    search: "",
    sqlIntent: "No table query has run yet.",
  },
};

export const emptyWorkbenchPayload: WorkbenchPayload = {
  ok: true,
  navigation: [],
  tables: [],
  fields: [],
  metrics: [],
  formulas: [],
  relationships: [],
  relationshipRecommendations: [],
  importJobs: [],
  importPolicies: [],
  connectors: [],
  preferences: defaultUserPreferences,
  themePalettes: defaultThemePalettes,
  savedViews: [],
  sourceIntelligenceRuns: [],
  fieldRoles: ["measure", "dimension", "event_time", "identity_key", "status"],
  fieldUsages: ["aggregatable", "groupable", "filterable", "joinable", "display"],
  safeAggregations: ["sum", "count", "avg", "min", "max"],
  formulaDsl: {
    allowedFunctions: ["sum", "count", "avg", "min", "max", "coalesce", "case_when"],
    fieldReference: "${field_name}",
    acceptsSql: false,
  },
};

export const emptyDashboardPayload: DashboardPayload = {
  ok: true,
  dashboards: [],
};

export const emptyRelationshipPreview: RelationshipPreviewPayload = {
  ok: true,
  dryRun: true,
  relationship: {},
  relationshipPreview: {
    joinType: "left",
    mappings: [],
    metrics: {},
    warnings: [],
    rows: [],
  },
};

export const emptyFormulaPreview: FormulaPreviewPayload = {
  ok: true,
  dryRun: true,
  expression: "",
  formulaDsl: {
    mode: "field-expression",
    allowedFunctions: emptyWorkbenchPayload.formulaDsl.allowedFunctions,
    fieldReference: emptyWorkbenchPayload.formulaDsl.fieldReference,
    acceptsSql: false,
  },
  dependencies: [],
  formulaAst: null,
  compiledSql: "",
  errors: [],
};

export const emptyAgentResult: AgentAskResult = {
  ok: true,
  llm: {
    configured: false,
    mode: "deterministic-fallback",
  },
  matched: {
    table: null,
    tableSelectionConfidence: "none",
    dashboard: null,
    dashboardSelectionConfidence: "none",
  },
  plan: [
    "先接入一个文件或文件夹。 / Connect a file or folder first.",
    "生成证据摘要后再创建图表。 / Create an evidence summary before drafting charts.",
  ],
  recommendedCommands: ["python tools/bi_cli.py --json status"],
  requiresConfirmation: false,
  actionDraft: {
    actionKey: "",
    kind: "",
    status: "",
  },
  ontology: {
    version: 1,
    objects: [],
    functions: [],
    links: [],
    actions: ["import.commit", "dashboard.create", "relationship.save", "formula.save", "view.save", "semantic.set"],
    evidenceFiles: [],
  },
  domainPackRuntime,
  sourcePipelineContract,
};

export const emptyActionDrafts: ActionDraftPayload = {
  ok: true,
  actionDrafts: [],
};
