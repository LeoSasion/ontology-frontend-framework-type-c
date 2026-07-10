import type { AppSection } from "./appSections";
import type { BusinessPathStepKey } from "./businessPathModel";
import type { WorkbenchPayload, WorkspaceStatus } from "./types";

export type WorkspaceFlowStage = "connect" | "profile" | "chart" | "evidence" | "confirm";

export type WorkspaceFlowCounts = {
  tableCount: number;
  fieldCount: number;
  metricCount: number;
  relationshipCount: number;
  sourceRunCount: number;
  sourceProfileCount: number;
  dashboardCount: number;
  pendingDraftCount: number;
};

export type WorkspaceFlowModel = {
  hasData: boolean;
  hasProfile: boolean;
  hasDashboard: boolean;
  hasEvidence: boolean;
  hasPendingDraft: boolean;
  activeStage: WorkspaceFlowStage;
  nextStep: BusinessPathStepKey;
  completedCount: number;
  totalCount: number;
  counts: WorkspaceFlowCounts;
};

export type WorkspaceFlowOptions = {
  status?: WorkspaceStatus;
  workbench: WorkbenchPayload;
  dashboardCount?: number;
  pendingDraftCount?: number;
  agentRequiresConfirmation?: boolean;
};

function positiveCount(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function buildWorkspaceFlow({
  status,
  workbench,
  dashboardCount,
  pendingDraftCount,
  agentRequiresConfirmation = false,
}: WorkspaceFlowOptions): WorkspaceFlowModel {
  const tables = Array.isArray(workbench.tables) ? workbench.tables : [];
  const fields = Array.isArray(workbench.fields) ? workbench.fields : [];
  const metrics = Array.isArray(workbench.metrics) ? workbench.metrics : [];
  const relationships = Array.isArray(workbench.relationships) ? workbench.relationships : [];
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const sourceRuns = Array.isArray(status?.sourceRuns) ? status.sourceRuns : [];

  const tableCount = positiveCount(status?.counts.tables, tables.length);
  const fieldCount = positiveCount(status?.counts.fields, fields.length);
  const metricCount = positiveCount(status?.counts.metrics, metrics.length);
  const relationshipCount = positiveCount(status?.counts.relationships, relationships.length);
  const sourceRunCount = positiveCount(status?.counts.sourceRuns, sourceRuns.length);
  const sourceProfileCount = positiveCount(status?.counts.sourceIntelligenceRuns, sourceIntelligenceRuns.length);
  const resolvedDashboardCount = positiveCount(dashboardCount ?? status?.counts.dashboards, 0);
  const resolvedDraftCount = positiveCount(pendingDraftCount ?? status?.counts.actionDrafts, agentRequiresConfirmation ? 1 : 0);

  const hasData = tableCount > 0 || tables.length > 0;
  const hasProfile = sourceProfileCount > 0;
  const hasEvidence = hasProfile;
  const hasDashboard = resolvedDashboardCount > 0;
  const hasPendingDraft = resolvedDraftCount > 0 || agentRequiresConfirmation;
  const activeStage: WorkspaceFlowStage = hasPendingDraft
    ? "confirm"
    : !hasData
      ? "connect"
      : !hasProfile
        ? "profile"
        : !hasDashboard
          ? "chart"
          : "evidence";
  const nextStep: BusinessPathStepKey = activeStage === "connect" || activeStage === "profile"
    ? "data"
    : activeStage === "chart"
      ? "chart"
      : activeStage === "evidence"
        ? "evidence"
        : "confirm";

  const completedCount = [hasData, hasProfile, hasDashboard].filter(Boolean).length;

  return {
    hasData,
    hasProfile,
    hasDashboard,
    hasEvidence,
    hasPendingDraft,
    activeStage,
    nextStep,
    completedCount,
    totalCount: 3,
    counts: {
      tableCount,
      fieldCount,
      metricCount,
      relationshipCount,
      sourceRunCount,
      sourceProfileCount,
      dashboardCount: resolvedDashboardCount,
      pendingDraftCount: resolvedDraftCount,
    },
  };
}

export function isBusinessStepLockedByFlow(step: BusinessPathStepKey, flow: WorkspaceFlowModel) {
  if (step === "data") return false;
  if (step === "chart") return !flow.hasProfile;
  if (step === "evidence") return !flow.hasEvidence;
  if (step === "confirm") return !flow.hasPendingDraft;
  return false;
}

export function isSectionLockedByFlow(section: AppSection, flow: WorkspaceFlowModel) {
  if (section === "views") return !flow.hasData;
  if (section === "dashboards") return !flow.hasProfile;
  if (section === "evidence") return !flow.hasEvidence;
  return false;
}

export function resolveSectionForFlow(section: AppSection, flow: WorkspaceFlowModel): AppSection {
  return isSectionLockedByFlow(section, flow) ? "sources" : section;
}
