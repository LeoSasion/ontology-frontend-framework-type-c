import type { Dispatch, SetStateAction } from "react";
import { AgentPanel, DashboardCanvas, EvidenceView, HomeOverview, SettingsPanel, SourceWorkbench, ViewWorkspace } from "../appLazyModules";
import type { BusinessPathStepKey } from "../businessPathModel";
import type { AppNavigationTarget } from "../appNavigationModel";
import type { AppSection } from "./Sidebar";
import type { useAppAgentActions } from "../useAppAgentActions";
import type { useAppDataActions } from "../useAppDataActions";
import type { useAppDashboardActions } from "../useAppDashboardActions";
import type { useAppSettingsActions } from "../useAppSettingsActions";
import type {
  ActionDraft,
  AgentAskResult,
  DashboardPayload,
  EvidenceFocus,
  FormulaPreviewPayload,
  ImportPreview,
  QueryResult,
  RelationshipPreviewPayload,
  TableQueryPayload,
  WorkbenchPayload,
  WorkspaceStatus,
} from "../types";

type AppMainViewProps = {
  actionDrafts: ActionDraft[];
  activeDashboardKey: string;
  activeViewKey: string;
  agent: AgentAskResult;
  agentActions: ReturnType<typeof useAppAgentActions>;
  dashboards: DashboardPayload;
  dashboardActions: ReturnType<typeof useAppDashboardActions>;
  dataActions: ReturnType<typeof useAppDataActions>;
  evidenceFocus: EvidenceFocus | null;
  focusedTableKey: string;
  formulaPreview: FormulaPreviewPayload;
  lastActionResult: Record<string, unknown> | null;
  onOpenBusinessStep: (step: BusinessPathStepKey) => void;
  onOpenEvidence: (focus: EvidenceFocus) => void;
  openSection: (section: AppSection) => void;
  navigateTo: (target: AppNavigationTarget) => void;
  pendingDraftCount: number;
  preview: ImportPreview;
  query: QueryResult;
  relationshipPreview: RelationshipPreviewPayload;
  section: AppSection;
  setActiveDashboardKey: Dispatch<SetStateAction<string>>;
  setActiveViewKey: Dispatch<SetStateAction<string>>;
  settingsActions: ReturnType<typeof useAppSettingsActions>;
  status: WorkspaceStatus;
  tableQuery: TableQueryPayload;
  workbench: WorkbenchPayload;
};

export function AppMainView({
  actionDrafts,
  activeDashboardKey,
  activeViewKey,
  agent,
  agentActions,
  dashboards,
  dashboardActions,
  dataActions,
  evidenceFocus,
  focusedTableKey,
  formulaPreview,
  lastActionResult,
  onOpenBusinessStep,
  onOpenEvidence,
  openSection,
  navigateTo,
  pendingDraftCount,
  preview,
  query,
  relationshipPreview,
  section,
  setActiveDashboardKey,
  setActiveViewKey,
  settingsActions,
  status,
  tableQuery,
  workbench,
}: AppMainViewProps) {
  const {
    handleAddMetric,
    handleCommitFolderImport,
    handleCommitImport,
    handleCopyView,
    handleDashboardRelationshipSave,
    handleDeleteFormula,
    handleDeleteSource,
    handleDeleteView,
    handleFieldUpdate,
    handleFormulaPreview,
    handleImportPolicy,
    handleInferMetrics,
    handleInferSemantics,
    handleInspectSource,
    handleNavigationOperation,
    handlePreview,
    handlePreviewFolderImport,
    handleQuery,
    handleQueryMetric,
    handleRelationshipPreview,
    handleRelationshipSave,
    handleRemoveConnector,
    handleRemoveImportJob,
    handleRenameSource,
    handleSaveConnector,
    handleSaveFormula,
    handleSaveView,
    handleSetSemantic,
    handleSourceIntelligenceRun,
    handleSyncConnector,
    handleTableQuery,
  } = dataActions;
  const {
    handleBusinessDashboardOperation,
    handleDashboardFilterOperation,
    handleDashboardModulesSave,
    handleDashboardOperation,
    handleDashboardWidgetOperation,
  } = dashboardActions;
  const {
    handleAgentCommandAsk,
    handleAsk,
    handleAskBranch,
    handleConfirmAction,
    handleConfirmDryRun,
    handleDraftDashboard,
    handleHomeAsk,
    handleRejectAction,
  } = agentActions;
  const {
    handleApplyConfig,
    handleExportConfig,
    handleSavePreferences,
    handleSaveThemePalette,
    handleValidateConfig,
  } = settingsActions;

  if (section === "home") {
    return (
      <HomeOverview
        status={status}
        workbench={workbench}
        query={query}
        agent={agent}
        onAsk={handleHomeAsk}
        onQuery={async () => {
          await handleQuery();
          openSection("dashboards");
        }}
        onSourceIntelligenceRun={handleSourceIntelligenceRun}
        onBusinessDashboardOperation={handleBusinessDashboardOperation}
        onSetSemantic={handleSetSemantic}
        onOpenBusinessStep={onOpenBusinessStep}
        onOpenSection={openSection}
      />
    );
  }
  if (section === "dashboards") {
    return (
      <DashboardCanvas
        dashboards={dashboards}
        focusedTableKey={focusedTableKey}
        query={query}
        workbench={workbench}
        activeDashboardKey={activeDashboardKey}
        onDashboardSelect={setActiveDashboardKey}
        onAgentDraft={handleDraftDashboard}
        onAsk={handleAgentCommandAsk}
        onOpenEvidence={onOpenEvidence}
        onDashboardFilterOperation={handleDashboardFilterOperation}
        onDashboardOperation={handleDashboardOperation}
        onDashboardModulesSave={handleDashboardModulesSave}
        onBusinessDashboardOperation={handleBusinessDashboardOperation}
        onRelationshipSave={handleDashboardRelationshipSave}
        onDashboardWidgetOperation={handleDashboardWidgetOperation}
        onOpenBusinessStep={onOpenBusinessStep}
      />
    );
  }
  if (section === "agent") {
    return (
      <AgentPanel
        result={agent}
        actionDrafts={actionDrafts}
        workbench={workbench}
        lastActionResult={lastActionResult}
        onAsk={async (prompt) => {
          await handleAsk(prompt);
        }}
        onAskBranch={async (prompt, parentRunKey, branchLabel) => {
          await handleAskBranch(prompt, parentRunKey, branchLabel);
        }}
        onConfirmDryRun={handleConfirmDryRun}
        onConfirmAction={handleConfirmAction}
        onRejectAction={handleRejectAction}
        onOpenSources={() => openSection("sources")}
      />
    );
  }
  if (section === "evidence") {
    return (
      <EvidenceView
        agent={agent}
        focus={evidenceFocus}
        lastActionResult={lastActionResult}
        pendingDraftCount={pendingDraftCount}
        onSetSemantic={handleSetSemantic}
        onSourceIntelligenceRun={handleSourceIntelligenceRun}
        onOpenBusinessStep={onOpenBusinessStep}
        onOpenAgent={() => navigateTo({ section: "agent", tableKey: evidenceFocus?.tableKey ?? focusedTableKey, dashboardKey: evidenceFocus?.dashboardKey })}
        onOpenDashboard={(dashboardKey) => navigateTo({ section: "dashboards", dashboardKey, tableKey: evidenceFocus?.tableKey ?? focusedTableKey })}
        workbench={workbench}
      />
    );
  }
  if (section === "views") {
    return (
      <ViewWorkspace
        activeViewKey={activeViewKey}
        onCopyView={handleCopyView}
        onDeleteView={handleDeleteView}
        onOpenEvidence={onOpenEvidence}
        onOpenSources={() => openSection("sources")}
        onAsk={handleAgentCommandAsk}
        onRunTableQuery={handleTableQuery}
        onSaveView={handleSaveView}
        onSelectView={setActiveViewKey}
        tableQuery={tableQuery}
        workbench={workbench}
      />
    );
  }
  if (section === "settings") {
    return (
      <SettingsPanel
        onApplyConfig={handleApplyConfig}
        onExportConfig={handleExportConfig}
        onSavePreferences={handleSavePreferences}
        onSaveThemePalette={handleSaveThemePalette}
        onValidateConfig={handleValidateConfig}
        workbench={workbench}
      />
    );
  }
  return (
    <SourceWorkbench
      status={status}
      preview={preview}
      query={query}
      workbench={workbench}
      relationshipPreview={relationshipPreview}
      formulaPreview={formulaPreview}
      focusedTableKey={focusedTableKey}
      onPreview={handlePreview}
      onCommitImport={handleCommitImport}
      onPreviewFolderImport={handlePreviewFolderImport}
      onCommitFolderImport={handleCommitFolderImport}
      onImportPolicy={handleImportPolicy}
      onRemoveImportJob={handleRemoveImportJob}
      onInspectSource={handleInspectSource}
      onRenameSource={handleRenameSource}
      onDeleteSource={handleDeleteSource}
      onNavigationOperation={handleNavigationOperation}
      onSaveConnector={handleSaveConnector}
      onSyncConnector={handleSyncConnector}
      onRemoveConnector={handleRemoveConnector}
      onQuery={handleQuery}
      onFieldUpdate={handleFieldUpdate}
      onInferSemantics={handleInferSemantics}
      onSetSemantic={handleSetSemantic}
      onInferMetrics={handleInferMetrics}
      onAddMetric={handleAddMetric}
      onQueryMetric={handleQueryMetric}
      onRelationshipPreview={handleRelationshipPreview}
      onRelationshipSave={handleRelationshipSave}
      onFormulaPreview={handleFormulaPreview}
      onFormulaSave={handleSaveFormula}
      onFormulaDelete={handleDeleteFormula}
      onSourceIntelligenceRun={handleSourceIntelligenceRun}
      onBusinessDashboardOperation={handleBusinessDashboardOperation}
      onAsk={handleAgentCommandAsk}
      onOpenBusinessStep={onOpenBusinessStep}
      onOpenDashboard={() => navigateTo({ section: "dashboards", tableKey: focusedTableKey })}
    />
  );
}
