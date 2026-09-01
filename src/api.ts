import { fetchJson } from "./apiClient";

export { askAgent, askAgentReadOnly, confirmAction, getActionDrafts } from "./apiAgent";
export { getDomainPacks, setDomainPack } from "./apiDomainPacks";
export {
  businessDashboardOperation,
  dashboardFilterOperation,
  dashboardOperation,
  dashboardWidgetOperation,
  getDashboardWidgetCatalog,
  recommendDashboardWidgets,
  saveDashboardModules,
} from "./apiDashboard";
export {
  addMetric,
  createIndex,
  deleteFormula,
  inferMetrics,
  inferSemantics,
  previewFormula,
  queryMetric,
  queryRelationship,
  runSemanticQuery,
  recommendIndexes,
  recommendRelationships,
  saveFormula,
  setSemantic,
  updateFieldConfig,
} from "./apiModel";
export { previewRelationship, saveRelationship } from "./apiRelationship";
export { applyConfig, exportConfig, savePreferences, saveThemePalette, validateConfig } from "./apiSettings";
export {
  createSourceDashboardDraft,
  deleteSource,
  inspectSource,
  listConnectors,
  listImportJobs,
  listSources,
  navigationOperation,
  previewImport,
  previewFolderImport,
  previewImportWithOptions,
  removeConnector,
  removeImportJob,
  renameSource,
  runSourceIntelligence,
  saveConnector,
  setImportPolicy,
  syncConnector,
} from "./apiSource";
export { copyView, deleteView, runQuery, runTableQuery, runTableQueryBatch, saveView } from "./apiViews";
export { createWorkspace, deleteWorkspace, getDashboards, getWorkbenchData, getWorkspaceStatus, renameWorkspace, selectWorkspace } from "./apiWorkspace";

export function getQualityDoctor() {
  return fetchJson<Record<string, unknown>>("/api/quality/doctor", { ok: false });
}

export function getCliCapabilities() {
  return fetchJson<Record<string, unknown>>("/api/cli/capabilities", { ok: false });
}
