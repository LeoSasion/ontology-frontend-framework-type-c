import { fetchJson } from "./apiClient";

export { askAgent, askAgentReadOnly, confirmAction, getActionDrafts } from "./apiAgent";
export {
  businessDashboardOperation,
  dashboardFilterOperation,
  dashboardOperation,
  dashboardWidgetOperation,
  getBCostMonitorValidation,
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
  previewRelationship,
  queryMetric,
  queryRelationship,
  recommendIndexes,
  recommendRelationships,
  saveFormula,
  saveRelationship,
  setSemantic,
  updateFieldConfig,
} from "./apiModel";
export { applyConfig, exportConfig, savePreferences, saveThemePalette, validateConfig } from "./apiSettings";
export {
  commitImport,
  commitFolderImport,
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
export { copyView, deleteView, runQuery, runTableQuery, saveView } from "./apiViews";
export { createWorkspace, deleteWorkspace, getDashboards, getWorkbenchData, getWorkspaceStatus, renameWorkspace, selectWorkspace } from "./apiWorkspace";

export function getQualityDoctor() {
  return fetchJson<Record<string, unknown>>("/api/quality/doctor", { ok: false });
}

export function getBBiCliCapabilities() {
  return fetchJson<Record<string, unknown>>("/api/b-cli/capabilities", { ok: false });
}
