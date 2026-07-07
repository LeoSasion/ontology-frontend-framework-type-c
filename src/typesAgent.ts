import type { DomainPackRuntime, SourcePipelineContract } from "./typesSource";
import type { SelectionConfidence } from "./typesWorkspace";

export interface AgentAskResult {
  ok: boolean;
  llm: {
    configured: boolean;
    mode: "provider" | "deterministic-fallback" | string;
    audit?: {
      provider?: string;
      configured?: boolean;
      mode?: string;
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
    clarification?: {
      kind: string;
      widgetType?: string;
      tableKey?: string;
      dashboardKey?: string;
      candidateMeasures?: string[];
      candidateDimensions?: string[];
    };
    evidenceRefs: Array<Record<string, unknown>>;
    nextActions: Array<{ zh: string; en: string }>;
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
  domainPackRuntime: DomainPackRuntime;
  sourcePipelineContract: SourcePipelineContract;
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
