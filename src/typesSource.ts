import type { NavigationModule } from "./typesDashboard";
import type { SourcePipelineContract, WorkspaceDomainPackRuntime } from "./typesDomain";
import type { SourceIntelligenceRunSummary } from "./typesSourceIntelligence";
import type { QueryRuntimeStatus } from "./typesWorkspace";

export type {
  CoreActionHint,
  CoreFunctionHint,
  CoreLinkHint,
  CoreSemanticHint,
  CoreSemanticRuntime,
  DomainPackManifest,
  DomainPackReference,
  AnalyticalSkillReference,
  WorkspaceAnalyticalSkillRuntime,
  WorkspaceDomainPackRuntime,
  SourcePipelineContract,
  SourcePipelineStageContract,
} from "./typesDomain";
export type { EvidenceFocus, SourceIntelligenceDashboardCandidate, SourceIntelligenceRunSummary } from "./typesSourceIntelligence";

export interface SourceFieldProfile {
  field: string;
  role: "measure" | "dimension" | "event_time" | "identity_key" | "status" | string;
  usage: string;
  confidence: number;
  nonEmpty: number;
  uniqueCount: number;
  sampleValues: string[];
}

export interface ImportPreview {
  ok: boolean;
  dryRun: boolean;
  file: string;
  suggestedTableKey: string;
  suggestedDisplayName?: string;
  matchedTable?: {
    table_key: string;
    display_name: string;
    row_count: number;
  } | null;
  profile: {
    rowCount: number;
    columnCount: number;
    fields: SourceFieldProfile[];
    measures: string[];
    dimensions: string[];
    identityKeys: string[];
    warnings: string[];
  };
  matches?: Array<Record<string, unknown>>;
  uniqueKeyQuality?: Record<string, unknown> | null;
  mergePolicyPreview: {
    mode: string;
    uniqueFields: string[];
    conflictRule: string;
    mergePlan?: Record<string, unknown> | null;
    willWrite: boolean;
  };
  sourcePipelineContract: SourcePipelineContract;
}

export interface FolderImportPlanItem {
  file: string;
  absolutePath: string;
  tableKey: string;
  displayName: string;
  mode: string;
  rowCount: number;
  columnCount: number;
  uniqueFields: string[];
}

export interface FolderImportPlanGroup {
  tableKey: string;
  displayName: string;
  fileCount: number;
  rowCount: number;
  columnCount: number;
  uniqueFields: string[];
  modes: string[];
  files: string[];
  willMerge: boolean;
}

export interface FolderImportPlan {
  ok: boolean;
  dryRun?: boolean;
  requiresConfirmation?: boolean;
  committed?: boolean;
  path: string;
  fileCount: number;
  tableCount: number;
  willWrite?: boolean;
  items: FolderImportPlanItem[];
  groups: FolderImportPlanGroup[];
  results?: Array<Record<string, unknown>>;
}

export interface WorkbenchTable {
  table_key: string;
  workspace_id?: string;
  display_name: string;
  source_file: string;
  row_count: number;
  column_count: number;
  created_at?: string;
  data_version?: number;
  updated_at?: string;
}

export interface FieldConfig {
  workspace_id?: string;
  table_key: string;
  field_name: string;
  role: string;
  usage: string;
  confidence: number;
  tags_json?: string;
  usage_json?: string;
  source?: string;
  note?: string;
  updated_at?: string;
}

export interface MetricDefinition {
  metric_key: string;
  workspace_id?: string;
  label: string;
  table_key: string;
  measure: string;
  aggregation: string;
  dimension?: string | null;
  time_field?: string | null;
  value_format: string;
  filters_json?: string;
  description?: string;
  source?: string;
  enabled?: number;
  formula_text?: string;
  formula_ast_json?: string;
  dependencies_json?: string;
  metric_type?: string;
  formulaText?: string;
  formulaAst?: Record<string, unknown>;
  dependencies?: string[];
  metricType?: string;
  updated_at?: string;
  created_at?: string;
}

export interface FormulaDefinition {
  workspace_id?: string;
  field_key?: string;
  fieldKey?: string;
  metric_key?: string;
  metricKey?: string;
  table_key?: string;
  tableKey?: string;
  tableName?: string;
  name?: string;
  label?: string;
  mode?: string;
  metricType?: string;
  formula_text?: string;
  formulaText?: string;
  formulaAst?: Record<string, unknown>;
  dependencies?: string[];
  value_format?: string;
  valueFormat?: string;
  description?: string;
  source?: string;
  enabled?: boolean | number;
  createdAt?: string;
  updatedAt?: string;
}

export interface RelationshipRecord {
  relation_key: string;
  workspace_id?: string;
  name: string;
  left_table_key: string;
  right_table_key: string;
  left_field: string;
  right_field: string;
  fieldMappings?: Array<{ leftField: string; rightField: string }>;
  filters?: Array<{ phase?: "pre" | "post"; side?: string; field: string; operator: string; value?: unknown; enabled?: boolean }>;
  preaggregation?: { side?: "right"; groupFields?: string[]; measures?: Array<{ field: string; aggregation: string }> };
  join_type: string;
  confidence: number;
  validation?: {
    schema?: string;
    status?: string;
    blockers?: string[];
    metrics?: Record<string, number | string | boolean | null>;
    warnings?: string[];
    filters?: Array<Record<string, unknown>>;
    preaggregation?: Record<string, unknown>;
    dataVersions?: Record<string, number>;
    revalidatedAfterImport?: string;
    staleReason?: string;
    validatedAt?: string;
  };
  created_at?: string;
  updated_at?: string;
}

export interface RelationshipRecommendation {
  leftTableKey: string;
  leftTableName: string;
  rightTableKey: string;
  rightTableName: string;
  fieldMappings: Array<{ leftField: string; rightField: string }>;
  joinType: string;
  score: number;
  confidence: number;
  overlapRatio: number;
  existing: boolean;
  reasons: string[];
  previewMetrics?: Record<string, number | string | boolean | null>;
  previewCommand?: string;
  saveCommand?: string;
  source?: string;
}

export interface ImportJob {
  job_key: string;
  source_file: string;
  table_key?: string | null;
  mode: string;
  status: string;
  row_count: number;
  created_at: string;
  result?: Record<string, unknown>;
}

export interface ImportPolicy {
  table_key: string;
  conflict_rule: string;
  updated_at: string;
  uniqueFields: string[];
}

export interface DataConnectorConfig {
  connectorKey: string;
  name: string;
  type: "file" | "api" | "erp" | "database" | string;
  provider: string;
  status: "draft" | "active" | "paused" | string;
  config: {
    endpoint?: string;
    resource?: string;
    credentialConfigured?: boolean;
    importMode?: "auto" | "create" | "replace" | "merge" | string;
    targetTableKey?: string;
    uniqueFields?: string[];
    conflictRule?: string;
    notes?: string;
  };
  schedule: {
    mode?: string;
  };
  createdAt: string;
  updatedAt: string;
  lastSyncAt?: string | null;
  lastSyncStatus?: string | null;
  lastSyncResult?: Record<string, unknown> | null;
}

export interface ConnectorAdapterContract {
  schema: "aibi-connector-adapter/v1" | string;
  adapterId: string;
  connectorType: string;
  available: boolean;
  operations: string[];
  permissions?: Record<string, unknown>;
  limits?: Record<string, unknown>;
  credentials?: Record<string, unknown>;
  persistence?: Record<string, unknown>;
  reason?: string;
}

export interface SavedView {
  view_key: string;
  name: string;
  tag_name: string;
  table_key: string;
  table_name?: string;
  config: Record<string, unknown>;
  is_default: boolean;
  sort_order: number;
  created_by: string;
  agent_managed: boolean;
  created_at: string;
  updated_at: string;
  columnCount?: number;
  filterCount?: number;
  sortCount?: number;
  search?: string;
}

export interface TableQueryPayload {
  ok: boolean;
  tableQuery: {
    mode: "detail" | "aggregate" | string;
    tableKey: string;
    tableName?: string;
    viewKey?: string;
    viewName?: string;
    columns: string[];
    rows: Array<Record<string, string | number | boolean | null>>;
    totalRows: number;
    filteredRows: number;
    limit: number;
    offset?: number;
    page?: number;
    pageCount?: number;
    filters?: Array<Record<string, unknown>>;
    sort?: Array<Record<string, string>>;
    search?: string;
    sqlIntent?: string;
    runtime?: {
      engine: string;
      compiledSql: string;
      params?: unknown[];
    };
  };
}

export interface UserPreferencesConfig {
  requireDeleteNameConfirmation: boolean;
  autoSaveDashboardOnSwitch: boolean;
  agentCanManageGeneratedAssets: boolean;
  agentCanManageManualAssets: boolean;
  themeKey: string;
}

export interface ThemePaletteConfig {
  themeKey: string;
  name: string;
  mode: "light" | "dark" | string;
  tokens: Record<string, string>;
  enabled: boolean;
  sortOrder: number;
  createdBy: "system" | "user" | string;
  createdAt?: string;
  updatedAt?: string;
}

export interface WorkbenchPayload {
  ok: boolean;
  navigation?: NavigationModule[];
  tables: WorkbenchTable[];
  fields: FieldConfig[];
  metrics: MetricDefinition[];
  formulas?: FormulaDefinition[];
  relationships: RelationshipRecord[];
  relationshipRecommendations?: RelationshipRecommendation[];
  importJobs: ImportJob[];
  importPolicies?: ImportPolicy[];
  connectors?: DataConnectorConfig[];
  connectorAdapters?: ConnectorAdapterContract[];
  preferences?: UserPreferencesConfig;
  themePalettes?: ThemePaletteConfig[];
  savedViews: SavedView[];
  sourceIntelligenceRuns: SourceIntelligenceRunSummary[];
  domainPacks?: WorkspaceDomainPackRuntime;
  fieldRoles: string[];
  fieldUsages: string[];
  safeAggregations: string[];
  queryRuntime?: QueryRuntimeStatus;
  formulaDsl: {
    allowedFunctions: string[];
    fieldReference: string;
    acceptsSql: boolean;
  };
}

export interface RelationshipPreviewPayload {
  ok: boolean;
  workspaceId?: string;
  dryRun: boolean;
  requiresConfirmation?: boolean;
  relationship: Record<string, unknown>;
  relationshipPreview: {
    joinType: string;
    mappings: Array<Record<string, string>>;
    filters?: Array<Record<string, unknown>>;
    preaggregation?: Record<string, unknown> | null;
    metrics: Record<string, number>;
    warnings: string[];
    rows: Array<Record<string, unknown>>;
  };
}

export interface FormulaPreviewPayload {
  ok: boolean;
  dryRun: boolean;
  expression: string;
  formulaDsl: {
    mode: string;
    allowedFunctions: string[];
    fieldReference: string;
    acceptsSql: boolean;
  };
  dependencies: string[];
  formulaAst: Record<string, unknown> | null;
  compiledSql: string;
  errors: string[];
}

export interface FormulaMutationPayload {
  ok: boolean;
  dryRun?: boolean;
  confirmed?: boolean;
  requiresConfirmation?: boolean;
  blockedByReferences?: boolean;
  references?: Array<{
    kind: string;
    key: string;
    label: string;
    reason: string;
  }>;
  proposedFormula?: FormulaDefinition & {
    formulaKey?: string;
    compiledSql?: string;
  };
  savedFormula?: FormulaDefinition;
  targetFormula?: FormulaDefinition;
  deletedFormula?: FormulaDefinition;
  error?: string;
}
