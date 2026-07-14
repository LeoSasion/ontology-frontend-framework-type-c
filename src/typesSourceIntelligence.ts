export interface SourceIntelligenceRunSummary {
  run_key: string;
  workspace_id?: string;
  label: string;
  status: string;
  output_dir: string;
  source_count: number;
  table_count: number;
  field_candidate_count: number;
  relationship_count: number;
  metric_sql_plan_count: number;
  metric_sql_executable_count: number;
  created_at: string;
  inputRoots: string[];
  sourceFingerprint?: string;
  enabledDomainPacks?: Array<{ packId: string; version: string; fingerprint: string; capabilities?: string[] }>;
  freshness?: {
    status: "current" | "stale" | "unknown" | string;
    usableForPlanning: boolean;
    missingFingerprints: string[];
    mismatches: string[];
  };
  isInternal?: boolean;
  fileCoverage?: {
    sourceProfilePath: string;
    sourceFiles: string[];
    sourceFileCount: number;
    manifestSourceCount: number;
    filesBySourceGroup: Array<{ group: string; count: number }>;
    skippedTableCount: number;
    skippedTables: Array<Record<string, unknown>>;
    complete: boolean;
    dashboardCandidate?: SourceIntelligenceDashboardCandidate;
  };
}

export interface SourceIntelligenceDashboardCandidate {
  status: string;
  title: string;
  source: string;
  analysisCount: number;
  executableMetricCount: number;
  plannedMetricCount: number;
  sourceCount: number;
  tableCount: number;
  analyses: Array<{
    analysisId: string;
    label: string;
    status: string;
    sourceMode: string;
    rowCount: number;
    chartType: string;
    requiredSemantics: string[];
    sample: Record<string, unknown>;
  }>;
  widgets: Array<{
    type: string;
    title: string;
    analysisId: string;
    sourceMode: string;
  }>;
  evidenceFiles: string[];
}

export interface EvidenceFocus {
  source: "dashboard-widget" | "agent-answer" | "source-intelligence" | string;
  title: string;
  subtitle?: string;
  refs: string[];
  dashboardKey?: string;
  viewKey?: string;
  tableKey?: string;
  widgetType?: string;
  detail?: Record<string, unknown>;
}
