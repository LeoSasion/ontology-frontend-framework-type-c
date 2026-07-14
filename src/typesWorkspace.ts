import type { WorkspaceDomainPackRuntime } from "./typesDomain";

export type SelectionConfidence = "explicit" | "recommended" | "fallback" | "missing" | "none";

export interface WorkspaceStatus {
  ok: boolean;
  workspace: WorkspaceRecord;
  workspaces?: WorkspaceRecord[];
  database?: string;
  queryRuntime?: QueryRuntimeStatus;
  domainPacks?: WorkspaceDomainPackRuntime;
  counts: {
    tables: number;
    sourceRuns: number;
    fields: number;
    metrics: number;
    relationships: number;
    dashboards: number;
    actionDrafts: number;
    sourceIntelligenceRuns?: number;
    connectors?: number;
  };
  sourceRuns: SourceRunSummary[];
  health: {
    ok: boolean;
    notes: string[];
  };
}

export interface WorkspaceRecord {
  id: string;
  name: string;
  current_source_run_id?: string | null;
  created_at?: string;
  isActive?: boolean;
}

export interface QueryRuntimeStatus {
  engine: string;
  available: boolean;
  database: string;
  fallbackEngine?: string | null;
  error?: string | null;
}

export interface SourceRunSummary {
  id: string;
  table_key: string;
  name: string;
  status: string;
  row_count: number;
  column_count: number;
  source_file: string;
}
