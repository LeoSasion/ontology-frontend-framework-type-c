import { emptyDashboardPayload, emptyQueryResult, emptyWorkspaceStatus, emptyWorkbenchPayload } from "./emptyWorkspaceData";
import { actionRecoveryFromError, buildActionRecovery } from "./actionRecoveryModel";
import type { AppSection } from "./components/Sidebar";
import type { DashboardPayload, QueryResult, WorkbenchPayload, WorkspaceStatus } from "./types";

export type LoadState = "loading" | "ready";
export type ApiMode = "loading" | "live" | "fallback";

export function preferredLandingSection(status: WorkspaceStatus, workbench: WorkbenchPayload, dashboards: DashboardPayload): AppSection {
  const dashboardCount = status.counts?.dashboards ?? 0;
  const tableCount = status.counts?.tables ?? 0;
  const sourceRunCount = status.sourceRuns?.length ?? 0;
  const hasDashboard = dashboardCount > 0 || dashboards.dashboards.length > 0;
  const hasSource = tableCount > 0 || sourceRunCount > 0 || workbench.tables.length > 0;
  if (hasDashboard) return "dashboards";
  if (hasSource) return "sources";
  return "home";
}

export function normalizeStatus(payload: WorkspaceStatus): WorkspaceStatus {
  const source = payload && typeof payload === "object" ? payload : emptyWorkspaceStatus;
  return {
    ...emptyWorkspaceStatus,
    ...source,
    workspace: { ...emptyWorkspaceStatus.workspace, ...(source.workspace ?? {}) },
    workspaces: Array.isArray(source.workspaces) ? source.workspaces : (source.workspace ? [source.workspace] : emptyWorkspaceStatus.workspaces),
    counts: { ...emptyWorkspaceStatus.counts, ...(source.counts ?? {}) },
    sourceRuns: Array.isArray(source.sourceRuns) ? source.sourceRuns : [],
    health: {
      ...emptyWorkspaceStatus.health,
      ...(source.health ?? {}),
      notes: Array.isArray(source.health?.notes) ? source.health.notes : [],
    },
  };
}

export const connectingStatus: WorkspaceStatus = {
  ...emptyWorkspaceStatus,
  workspace: {
    id: "default",
    name: "AIBI 工作区",
    current_source_run_id: null,
  },
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
    ok: false,
    notes: ["Connecting to local data service..."],
  },
};

export function normalizeQuery(payload: QueryResult): QueryResult {
  const source = payload && typeof payload === "object" ? payload : emptyQueryResult;
  return {
    ...emptyQueryResult,
    ...source,
    query: { ...emptyQueryResult.query, ...(source.query ?? {}) },
    rows: Array.isArray(source.rows) ? source.rows : [],
  };
}

export function normalizeWorkbench(payload: WorkbenchPayload): WorkbenchPayload {
  const source = payload && typeof payload === "object" ? payload : emptyWorkbenchPayload;
  return {
    ...emptyWorkbenchPayload,
    ...source,
    navigation: Array.isArray(source.navigation) ? source.navigation : emptyWorkbenchPayload.navigation,
    tables: Array.isArray(source.tables) ? source.tables : [],
    fields: Array.isArray(source.fields) ? source.fields : [],
    metrics: Array.isArray(source.metrics) ? source.metrics : [],
    formulas: Array.isArray(source.formulas) ? source.formulas : [],
    relationships: Array.isArray(source.relationships) ? source.relationships : [],
    relationshipRecommendations: Array.isArray(source.relationshipRecommendations) ? source.relationshipRecommendations : [],
    importJobs: Array.isArray(source.importJobs) ? source.importJobs : [],
    importPolicies: Array.isArray(source.importPolicies) ? source.importPolicies : [],
    connectors: Array.isArray(source.connectors) ? source.connectors : [],
    preferences: source.preferences ?? emptyWorkbenchPayload.preferences,
    themePalettes: Array.isArray(source.themePalettes) ? source.themePalettes : emptyWorkbenchPayload.themePalettes,
    savedViews: Array.isArray(source.savedViews) ? source.savedViews : [],
    sourceIntelligenceRuns: Array.isArray(source.sourceIntelligenceRuns) ? source.sourceIntelligenceRuns : [],
    fieldRoles: Array.isArray(source.fieldRoles) ? source.fieldRoles : emptyWorkbenchPayload.fieldRoles,
    fieldUsages: Array.isArray(source.fieldUsages) ? source.fieldUsages : emptyWorkbenchPayload.fieldUsages,
    safeAggregations: Array.isArray(source.safeAggregations) ? source.safeAggregations : emptyWorkbenchPayload.safeAggregations,
    formulaDsl: source.formulaDsl ?? emptyWorkbenchPayload.formulaDsl,
  };
}

export function normalizeDashboards(payload: DashboardPayload): DashboardPayload {
  const source = payload && typeof payload === "object" ? payload : emptyDashboardPayload;
  return {
    ...emptyDashboardPayload,
    ...source,
    dashboards: Array.isArray(source.dashboards) ? source.dashboards : [],
  };
}

export function actionErrorResult(action: string, error: unknown): Record<string, unknown> {
  const recovery = actionRecoveryFromError(error) ?? buildActionRecovery(action, error);
  return {
    ok: false,
    action,
    error: recovery.technical,
    category: recovery.category,
    targetSection: recovery.targetSection,
    safeState: recovery.safeState.zh,
    evidence: recovery.evidence,
    next: recovery.next.zh,
    recovery,
  };
}
