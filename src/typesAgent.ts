import type { CoreSemanticRuntime, SourcePipelineContract } from "./typesSource";
import type { SelectionConfidence } from "./typesWorkspace";

export interface BusinessIntentFrame {
  schema: "aibi-agent-intent-frame/v1" | string;
  taskType: "overview" | "comparison" | "trend" | "composition" | "ranking" | "anomaly" | "reconciliation" | "diagnosis" | string;
  decisionGoal?: string | null;
  measureConcepts: Array<{ concept: string; field: string; tableKey: string; role: string; source: string; confidence: number }>;
  dimensionConcepts: Array<{ concept: string; field: string; tableKey: string; role: string; source: string; confidence: number }>;
  otherConcepts: Array<{ concept: string; field: string; tableKey: string; role: string; source: string; confidence: number }>;
  timeScope?: { expression: string; parts: Record<string, string> } | null;
  filters: Array<{ fieldExpression: string; operator: string; value: string }>;
  comparisons: string[];
  requestedOutput: string;
  grainExpectation: { fields: string[]; description: string };
  constraints: Record<string, unknown>;
  unresolved: Array<{ kind: string; mention: string; reason: string; candidateCount: number }>;
  evidenceRefs: Array<Record<string, unknown>>;
  confidence: Record<string, number>;
  resolution: { taskTypeReason: string; providerRequired: boolean; silentDisambiguation: boolean };
}

export interface AgentClarification {
  schema: "aibi-agent-clarification/v1" | string;
  status: "required" | "not-required" | string;
  required: boolean;
  taskType: string;
  items: Array<{ kind: string; mention: string; question: string; reason: string; candidates: SemanticFieldCandidate[] }>;
  combined: boolean;
  message?: string | null;
}

export interface SemanticContextBundle {
  schema: "aibi-semantic-context-bundle/v1" | string;
  workspaceId: string;
  retrievalPolicy: { strategy: string; reranker: string; ambiguityGatePreserved: boolean };
  sources: Record<string, unknown>;
  missingSlots: Array<Record<string, unknown>>;
  stale: boolean;
  fingerprint: string;
}

export interface AgentAskResult {
  ok: boolean;
  workspaceId: string;
  llm: {
    configured: boolean;
    mode: "provider" | "deterministic-fallback" | string;
    response?: {
      summary: string;
      rationale: string[];
      clarification: string | null;
      nextActions: string[];
      citedEvidence: string[];
      certainty: "grounded" | "needs_clarification" | string;
    } | null;
    audit?: {
      provider?: string;
      model?: string;
      configured?: boolean;
      enabled?: boolean;
      mode?: string;
      status?: string;
      runId?: string;
      attempts?: number;
      durationMs?: number;
      requestHash?: string;
      usage?: {
        promptTokens?: number | null;
        completionTokens?: number | null;
        totalTokens?: number | null;
      } | null;
      serverSideOnly?: boolean;
      secretExposed?: boolean;
      contextBoundary?: string;
      fallbackReason?: string | null;
      regressionStatus?: string;
    };
  };
  matched: {
    table?: {
      table_key: string;
      display_name: string;
    } | null;
    tableSelectionConfidence: SelectionConfidence;
    dashboard?: {
      dashboard_key: string;
      name: string;
      default_table_key?: string;
    } | null;
    dashboardSelectionConfidence: SelectionConfidence;
    widget?: Record<string, unknown> | null;
    widgetSelectionConfidence?: SelectionConfidence;
    dashboardFilter?: Record<string, unknown> | null;
    dashboardFilterSelectionConfidence?: SelectionConfidence;
    dashboardOperation?: Record<string, unknown> | null;
    dashboardOperationSelectionConfidence?: SelectionConfidence;
    metric?: Record<string, unknown> | null;
    metricSelectionConfidence?: SelectionConfidence;
    semantic?: Record<string, unknown> | null;
    semanticSelectionConfidence?: SelectionConfidence;
    view?: Record<string, unknown> | null;
    viewSelectionConfidence?: SelectionConfidence;
    formula?: Record<string, unknown> | null;
    formulaSelectionConfidence?: SelectionConfidence;
    relationship?: Record<string, unknown> | null;
    relationshipSelectionConfidence?: SelectionConfidence;
    importFile?: string | null;
    importFileSelectionConfidence?: SelectionConfidence;
    indexField?: string | null;
    indexFieldSelectionConfidence?: SelectionConfidence;
  };
  plan: string[];
  queryPlanReceipt?: QueryPlanReceipt;
  semanticPlan?: SemanticQueryPlan;
  executionPlan?: SemanticQueryExecutionPlan | null;
  analysisRun?: AnalysisRun;
  intentFrame?: BusinessIntentFrame;
  semanticContext?: SemanticContextBundle;
  clarification?: AgentClarification;
  analysisUnit?: AnalysisUnit;
  chartAdapter?: ChartAdapter;
  context?: {
    matchedTermCount: number;
    matchedRuleCount: number;
    terms: Array<{ termKey: string; name: string; definition: string }>;
    rules: Array<{ ruleKey: string; title: string; statement: string }>;
    confirmedQueries: Array<{ queryKey: string; question: string; matchScore: number }>;
    knowledgeRules?: Array<{ packId: string; ruleId: string; title: string; grain: string }>;
  };
  answerCard?: {
    kind: string;
    title: { zh: string; en: string };
    summary: { zh: string; en: string };
    confidence: string;
    metrics: Array<{
      label: { zh: string; en: string };
      value: string;
      rawValue?: number | string | null;
      unit?: string;
    }>;
    rows: Array<Record<string, unknown>>;
    query?: Record<string, unknown>;
    executionPlan?: SemanticQueryExecutionPlan | null;
    clarification?: {
      kind: string;
      widgetType?: string;
      tableKey?: string;
      dashboardKey?: string;
      candidateMeasures?: string[];
      candidateDimensions?: string[];
      status?: string;
      bindings?: SemanticFieldBinding[];
    };
    evidenceRefs: Array<Record<string, unknown>>;
    nextActions: Array<{ zh: string; en: string }>;
    queryPlanReceipt?: QueryPlanReceipt;
    analysisUnitRef?: Pick<AnalysisUnit, "unitKey" | "kind" | "status" | "resultFingerprint">;
    chartAdapter?: ChartAdapter;
  };
  recommendedCommands: string[];
  requiresConfirmation: boolean;
  actionDraft: {
    actionKey: string;
    kind: string;
    status: string;
  };
  ontology: {
    version: 1;
    objects: Array<Record<string, unknown>>;
    functions: Array<Record<string, unknown>>;
    links: Array<Record<string, unknown>>;
    actions: string[];
    evidenceFiles: string[];
  };
  coreSemanticRuntime: CoreSemanticRuntime;
  sourcePipelineContract: SourcePipelineContract;
}

export interface ChartAdapter {
  schema: "aibi-chart-adapter/v1" | string;
  status: "ready" | "blocked" | string;
  unitKey: string;
  queryReceiptKey: string;
  chartType?: "metric" | "bar" | "line" | "pie" | "table" | null;
  allowedChartTypes: string[];
  config: Record<string, unknown>;
  rationale: string[];
  blockers: string[];
  inputFingerprint: string;
}

export interface AnalysisUnit {
  schema: "aibi-analysis-unit/v1" | string;
  unitKey: string;
  workspaceId: string;
  queryReceiptKey: string;
  kind: "metric" | "comparison" | "trend" | "composition" | "ranking" | "anomaly" | string;
  status: "ready" | "blocked" | string;
  title: string;
  definitionFingerprint: string;
  resultFingerprint: string;
  grain: Record<string, unknown>;
  shape: Record<string, unknown>;
  rows: Array<Record<string, unknown>>;
  calculation: Record<string, unknown>;
  validation: { status: string; blockers: string[]; warnings: string[]; checks: Record<string, boolean> };
  chartAdapter: ChartAdapter;
  createdAt: string;
  updatedAt: string;
}

export interface QueryPlanReceipt {
  schema: "aibi-query-plan-receipt/v1" | string;
  receiptKey: string;
  request: string;
  status: "executed" | "blocked" | string;
  source: {
    workspaceId: string;
    tableKey?: string | null;
    schemaFingerprint: string;
    dataFingerprint: string;
  };
  selection: {
    group?: string | null;
    measure?: string | null;
    aggregation?: string | null;
    filters: Array<Record<string, unknown>>;
    joins: Array<Record<string, unknown>>;
    semanticPlan?: SemanticQueryPlan | null;
    executionPlan?: SemanticQueryExecutionPlan | null;
  };
  runtime: {
    engine?: string | null;
    database?: string | null;
    compiledSql?: string | null;
    executionPlanHash?: string | null;
    sqlIntent: string;
  };
  validation: Record<string, boolean>;
  resultBinding?: {
    resultFingerprint: string;
    rowCount: number;
    columns: string[];
    projection?: "scalar-result-fields-only" | string;
    snapshotStored: boolean;
  } | null;
  contextRefs: Array<Record<string, unknown>>;
  domainPacks?: Array<{ packId: string; version: string; fingerprint: string; capabilities?: string[] }>;
  domainPackFingerprint?: string;
  evidenceRefs: Array<Record<string, unknown>>;
  unresolved: unknown[];
  actionKey?: string | null;
  createdAt: string;
}

export interface SemanticFieldCandidate {
  id: string;
  tableKey: string;
  tableName: string;
  field: string;
  role: string;
  aggregation?: string;
  confidence: number;
  source: string;
  matchedAlias: string;
}

export interface SemanticFieldBinding {
  mention: string;
  status: "resolved" | "ambiguous" | string;
  selected?: SemanticFieldCandidate | null;
  candidates: SemanticFieldCandidate[];
  reason: string;
}

export interface SemanticRelationshipPath {
  tables: string[];
  safeForPlanning: boolean;
  risks: string[];
  hops: Array<{
    relationKey: string;
    relationshipLeftTable?: string;
    relationshipRightTable?: string;
    fromTable: string;
    toTable: string;
    direction: string;
    joinType: string;
    fieldMappings: Array<{ leftField: string; rightField: string }>;
    filters?: Array<Record<string, unknown>>;
    preaggregation?: Record<string, unknown>;
    validationStatus?: string;
    dataVersions?: Record<string, number>;
    currentDataVersions?: Record<string, number>;
    relationshipUpdatedAt?: string;
    risk: {
      safeForPlanning: boolean;
      risks: string[];
      confidence: number;
      requiresCurrentPreview: boolean;
      composite: boolean;
    };
  }>;
}

export interface SemanticQueryPlan {
  schema: "aibi-semantic-query-plan/v1" | string;
  status: "not-applicable" | "ready" | "needs-clarification" | "needs-relationship" | "needs-validation" | string;
  autoExecutable: false;
  fieldResolution: {
    status: string;
    bindings: SemanticFieldBinding[];
    selected: SemanticFieldCandidate[];
    unresolved: SemanticFieldBinding[];
  };
  grain: {
    dimensions: SemanticFieldCandidate[];
    measures: SemanticFieldCandidate[];
    otherFields: SemanticFieldCandidate[];
    tables: string[];
  };
  joinPlan: {
    rootTable: string;
    requiredTables: string[];
    targets: Array<{
      targetTable: string;
      paths: SemanticRelationshipPath[];
      selectedPath?: SemanticRelationshipPath | null;
    }>;
    maxHops: number;
  };
  executionBoundary: string;
}

export interface SemanticQueryExecutionPlan {
  schema: "aibi-semantic-query-execution-plan/v1" | string;
  status: "ready" | "blocked" | string;
  autoExecutable: boolean;
  blockers: string[];
  semanticPlanStatus: string;
  rootTable?: string | null;
  planHash: string;
  relationships?: Array<NonNullable<SemanticQueryExecutionPlan["relationship"]>>;
  relationship?: {
    relationKey: string;
    leftTable: string;
    rightTable: string;
    joinType: string;
    direction: string;
    fieldMappings: Array<{ leftField: string; rightField: string }>;
    filters: Array<Record<string, unknown>>;
    preaggregation: Record<string, unknown>;
    dataVersions: Record<string, number>;
    updatedAt: string;
  };
  groups?: Array<{ side: "left" | "right"; tableKey: string; field: string }>;
  measure?: { side: "left" | "right"; tableKey: string; field: string; aggregation: string };
  finalGrain?: string[];
}

export interface AnalysisRun {
  run_key: string;
  workspace_id: string;
  parent_run_key?: string | null;
  branch_label: string;
  question: string;
  status: "pending_confirmation" | "confirmed" | "executed" | "blocked" | "rejected" | string;
  query_receipt_key: string;
  action_key?: string | null;
  result: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ActionDraft {
  action_key: string;
  workspace_id?: string;
  kind: string;
  label: string;
  status: "draft" | "confirmed" | string;
  payload: Record<string, unknown>;
  evidence: string[];
  created_at: string;
  confirmed_at?: string | null;
}

export interface ActionDraftPayload {
  ok: boolean;
  actionDrafts: ActionDraft[];
}
