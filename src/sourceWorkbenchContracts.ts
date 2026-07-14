import type { FolderImportPlan, FormulaMutationPayload, FormulaPreviewPayload, ImportPreview, QueryResult, RelationshipPreviewPayload, WorkbenchPayload, WorkspaceStatus } from "./types";
import type { BusinessPathStepKey } from "./businessPathModel";
import type { BusinessDashboardOptions, RelationshipSaveOptions } from "./dashboardCanvasContracts";
import type { ConnectorOptions, ImportOptions, ImportPolicyOptions, MetricMutationOptions, SourceIntelligenceRunOptions } from "./sourceWorkbenchCommandModel";
import type { NavigationOperationOptions } from "./sourceWorkbenchDraftModel";

export type QueryOptions = {
  table?: string;
  group?: string;
  measure?: string;
  aggregation?: string;
  limit?: number;
};

export type FieldUpdateOptions = {
  table: string;
  field: string;
  role: string;
  usage: string;
  confidence?: number;
  confirm?: boolean;
};

export type SemanticInferOptions = {
  table?: string;
  overwriteManual?: boolean;
  confirm?: boolean;
};

export type SemanticSetOptions = {
  table: string;
  field: string;
  role: string;
  tags?: string[];
  usage?: string[];
  confidence?: number;
  note?: string;
  confirm?: boolean;
};

export type MetricQueryOptions = {
  metric: string;
  group?: string[];
  filters?: Array<{ field: string; operator: string; value?: string }>;
  sort?: string;
  limit?: number;
};

export type SourceWorkbenchProps = {
  focusedTableKey?: string;
  status: WorkspaceStatus;
  preview: ImportPreview;
  query: QueryResult;
  workbench: WorkbenchPayload;
  relationshipPreview: RelationshipPreviewPayload;
  formulaPreview: FormulaPreviewPayload;
  onPreview: (options: ImportOptions) => Promise<ImportPreview>;
  onCommitImport: (options: ImportOptions) => Promise<void>;
  onPreviewFolderImport: (options: { path: string; limit?: number; recursive?: boolean }) => Promise<FolderImportPlan>;
  onCommitFolderImport: (options: { path: string; limit?: number; recursive?: boolean; confirm?: boolean }) => Promise<FolderImportPlan>;
  onImportPolicy: (options: ImportPolicyOptions) => Promise<void>;
  onRemoveImportJob: (options: { jobKey: string; confirm?: boolean }) => Promise<void>;
  onInspectSource: (table: string) => Promise<void>;
  onRenameSource: (options: { source: string; name: string; confirm?: boolean }) => Promise<void>;
  onDeleteSource: (options: { source: string; confirm?: boolean }) => Promise<void>;
  onNavigationOperation: (options: NavigationOperationOptions) => Promise<Record<string, unknown>>;
  onSaveConnector: (options: ConnectorOptions) => Promise<void>;
  onSyncConnector: (options: { connector: string; allowPaused?: boolean; confirm?: boolean }) => Promise<Record<string, unknown>>;
  onRemoveConnector: (options: { connector: string; confirm?: boolean }) => Promise<void>;
  onQuery: (options?: QueryOptions) => Promise<void>;
  onFieldUpdate: (options: FieldUpdateOptions) => Promise<void>;
  onInferSemantics: (options: SemanticInferOptions) => Promise<Record<string, unknown>>;
  onSetSemantic: (options: SemanticSetOptions) => Promise<Record<string, unknown>>;
  onInferMetrics: (options: SemanticInferOptions) => Promise<Record<string, unknown>>;
  onAddMetric: (options: MetricMutationOptions) => Promise<Record<string, unknown>>;
  onQueryMetric: (options: MetricQueryOptions) => Promise<Record<string, unknown>>;
  onRelationshipPreview: (options: RelationshipSaveOptions) => Promise<void>;
  onRelationshipSave: (options: RelationshipSaveOptions) => Promise<void>;
  onFormulaPreview: (options: { expression: string; table?: string; mode?: string }) => Promise<void>;
  onFormulaSave: (options: { id?: string; name: string; table: string; expression: string; mode?: string; dimension?: string; timeField?: string; valueFormat?: string; description?: string; confirm?: boolean }) => Promise<FormulaMutationPayload>;
  onFormulaDelete: (options: { formula: string; confirm?: boolean }) => Promise<FormulaMutationPayload>;
  onSourceIntelligenceRun: (options?: SourceIntelligenceRunOptions) => Promise<Record<string, unknown> | void>;
  onBusinessDashboardOperation: (options: BusinessDashboardOptions) => Promise<Record<string, unknown>>;
  onAsk: (prompt: string) => Promise<void>;
  onOpenBusinessStep: (step: BusinessPathStepKey) => void;
  onOpenDashboard: () => void;
};
