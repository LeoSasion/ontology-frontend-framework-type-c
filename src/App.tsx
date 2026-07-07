import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createWorkspace, deleteWorkspace, renameWorkspace, selectWorkspace } from "./api";
import { AgentCommandDock } from "./components/AgentCommandDock";
import { Sidebar, type AppSection } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { useLanguage } from "./components/Bilingual";
import { emptyAgentResult, emptyDashboardPayload, emptyFormulaPreview, emptyImportPreview, emptyQueryResult, emptyRelationshipPreview, emptyTableQuery, emptyWorkbenchPayload, emptyWorkspaceStatus } from "./emptyWorkspaceData";
import { applyThemePalette, getUserPreferences, hasStoredThemeSnapshot, resolveThemePalette } from "./theme";
import { isAppSection } from "./appSections";
import { businessSectionForStep, type BusinessPathStepKey } from "./businessPathModel";
import { actionErrorResult, connectingStatus, preferredLandingSection, type ApiMode, type LoadState } from "./appWorkspaceModel";
import { refreshStatusDashboardsWorkbenchDrafts } from "./appRefreshModel";
import { AgentPanel, DashboardCanvas, EvidenceView, HomeOverview, InspectorLoadingPanel, InspectorPanel, ModuleLoadingPanel, SettingsPanel, SourceWorkbench, ViewWorkspace, allSectionPreloaders, inspectorPreloader, preloadModules, scheduleIdlePreload, sectionPreloaders } from "./appLazyModules";
import { BusinessPathBar } from "./components/BusinessPathBar";
import { useAppAgentActions } from "./useAppAgentActions";
import { useAppDataActions } from "./useAppDataActions";
import { useAppDashboardActions } from "./useAppDashboardActions";
import { useAppSettingsActions } from "./useAppSettingsActions";
import type { ActionDraft, AgentAskResult, DashboardPayload, EvidenceFocus, FormulaPreviewPayload, ImportPreview, QueryResult, RelationshipPreviewPayload, TableQueryPayload, WorkbenchPayload, WorkspaceStatus } from "./types";
import { buildWorkspaceFlow, resolveSectionForFlow } from "./workspaceFlowModel";

function sectionFromUrl(): AppSection | null {
  const section = new URLSearchParams(window.location.search).get("section");
  return isAppSection(section) ? section : null;
}

function initialSection(): AppSection {
  return sectionFromUrl() ?? "home";
}

const inspectorPreferenceStorageKey = "aibiHybrid.contextDrawerPreference";

function initialInspectorPreference() {
  if (typeof window === "undefined") {
    return { expanded: false, pinned: false };
  }
  try {
    const stored = window.localStorage.getItem(inspectorPreferenceStorageKey);
    if (!stored) return { expanded: false, pinned: false };
    const parsed = JSON.parse(stored) as { expanded?: unknown; pinned?: unknown };
    return {
      expanded: parsed.expanded === true || parsed.pinned === true,
      pinned: parsed.pinned === true,
    };
  } catch {
    return { expanded: false, pinned: false };
  }
}

export default function App() {
  const { resolvedLanguage } = useLanguage();
  const [section, setSection] = useState<AppSection>(() => initialSection());
  const [inspectorPreference, setInspectorPreference] = useState(() => initialInspectorPreference());
  const explicitInitialSectionRef = useRef(sectionFromUrl() !== null);
  const autoLandingAppliedRef = useRef(false);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [status, setStatus] = useState<WorkspaceStatus>(emptyWorkspaceStatus);
  const [preview, setPreview] = useState<ImportPreview>(emptyImportPreview);
  const [query, setQuery] = useState<QueryResult>(emptyQueryResult);
  const [tableQuery, setTableQuery] = useState<TableQueryPayload>(emptyTableQuery);
  const [workbench, setWorkbench] = useState<WorkbenchPayload>(emptyWorkbenchPayload);
  const [relationshipPreview, setRelationshipPreview] = useState<RelationshipPreviewPayload>(emptyRelationshipPreview);
  const [formulaPreview, setFormulaPreview] = useState<FormulaPreviewPayload>(emptyFormulaPreview);
  const [dashboards, setDashboards] = useState<DashboardPayload>(emptyDashboardPayload);
  const [activeDashboardKey, setActiveDashboardKey] = useState("default");
  const [activeViewKey, setActiveViewKey] = useState("");
  const [agent, setAgent] = useState<AgentAskResult>(emptyAgentResult);
  const [actionDrafts, setActionDrafts] = useState<ActionDraft[]>([]);
  const [lastActionResult, setLastActionResult] = useState<Record<string, unknown> | null>(null);
  const [evidenceFocus, setEvidenceFocus] = useState<EvidenceFocus | null>(null);

  const refresh = useCallback(async () => {
    setLoadState("loading");
    try {
      const surface = await refreshStatusDashboardsWorkbenchDrafts();
      setStatus(surface.status);
      setPreview(emptyImportPreview);
      setQuery(emptyQueryResult);
      setTableQuery(emptyTableQuery);
      setWorkbench(surface.workbench);
      setDashboards(surface.dashboards);
      setActiveDashboardKey((current) => surface.dashboards.dashboards.some((dashboard) => dashboard.dashboard_key === current) ? current : surface.dashboards.dashboards[0]?.dashboard_key ?? "default");
      setActiveViewKey((current) => surface.workbench.savedViews.some((view) => view.view_key === current) ? current : surface.workbench.savedViews[0]?.view_key ?? "");
      setActionDrafts(surface.actionDrafts);
      setAgent(emptyAgentResult);
      if (!explicitInitialSectionRef.current && !autoLandingAppliedRef.current) {
        setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards));
        autoLandingAppliedRef.current = true;
      }
    } catch (error) {
      setLastActionResult(actionErrorResult("initial-load", error));
    }
    setLoadState("ready");
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    preloadModules(sectionPreloaders[section]);
  }, [section]);

  useEffect(() => scheduleIdlePreload(() => {
    preloadModules([...allSectionPreloaders, inspectorPreloader]);
  }), []);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("section") === section) {
      return;
    }
    url.searchParams.set("section", section);
    window.history.replaceState(null, "", `${url.pathname}?${url.searchParams.toString()}${url.hash}`);
  }, [section]);

  useEffect(() => {
    try {
      window.localStorage.setItem(inspectorPreferenceStorageKey, JSON.stringify(inspectorPreference));
    } catch {
      // The inspector still works when storage is unavailable.
    }
  }, [inspectorPreference]);

  const reloadWorkspaceSurface = useCallback(async () => {
    const surface = await refreshStatusDashboardsWorkbenchDrafts();
    setStatus(surface.status);
    setWorkbench(surface.workbench);
    setDashboards(surface.dashboards);
    setAgent(emptyAgentResult);
    setActionDrafts(surface.actionDrafts);
    setActiveDashboardKey(surface.dashboards.dashboards[0]?.dashboard_key ?? "default");
    setActiveViewKey(surface.workbench.savedViews[0]?.view_key ?? "");
    return surface;
  }, []);

  const handleWorkspaceCreate = useCallback(async (name: string) => {
    const previewResult = await createWorkspace(name, false);
    if (previewResult.requiresConfirmation !== true) {
      setLastActionResult(previewResult);
      return previewResult;
    }
    const result = await createWorkspace(name, true);
    setLastActionResult(result);
    if (result.ok !== false) {
      const surface = await reloadWorkspaceSurface();
      if (surface) setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards));
    }
    return result;
  }, [reloadWorkspaceSurface]);

  const handleWorkspaceSelect = useCallback(async (workspaceId: string) => {
    if (!workspaceId || workspaceId === status.workspace.id) return;
    const result = await selectWorkspace(workspaceId, true);
    setLastActionResult(result);
    if (result.ok !== false) {
      const surface = await reloadWorkspaceSurface();
      if (surface) setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards));
    }
  }, [reloadWorkspaceSurface, status.workspace.id]);

  const handleWorkspaceDelete = useCallback(async (workspaceId: string) => {
    if (!workspaceId || workspaceId === "default" || workspaceId === status.workspace.id) return;
    const previewResult = await deleteWorkspace(workspaceId, false);
    if (previewResult.requiresConfirmation !== true) {
      setLastActionResult(previewResult);
      return previewResult;
    }
    const result = await deleteWorkspace(workspaceId, true);
    setLastActionResult(result);
    if (result.ok !== false) {
      const surface = await reloadWorkspaceSurface();
      if (surface) setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards));
    }
    return result;
  }, [reloadWorkspaceSurface, status.workspace.id]);

  const handleWorkspaceRename = useCallback(async (workspaceId: string, name: string) => {
    const nextName = name.trim();
    if (!workspaceId || !nextName) return;
    const previewResult = await renameWorkspace(workspaceId, nextName, false);
    if (previewResult.requiresConfirmation !== true) {
      setLastActionResult(previewResult);
      return previewResult;
    }
    const result = await renameWorkspace(workspaceId, nextName, true);
    setLastActionResult(result);
    if (result.ok !== false) {
      await reloadWorkspaceSurface();
    }
    return result;
  }, [reloadWorkspaceSurface]);

  useEffect(() => {
    if (!status.database && hasStoredThemeSnapshot()) {
      return;
    }
    const preferences = getUserPreferences(workbench);
    applyThemePalette(resolveThemePalette(workbench, preferences));
  }, [status.database, workbench]);

  const apiMode = useMemo<ApiMode>(() => {
    if (status.database) return "live";
    return loadState === "loading" ? "loading" : "fallback";
  }, [loadState, status.database]);
  const displayStatus = apiMode === "loading" ? connectingStatus : status;
  const pendingDraftCount = agent.requiresConfirmation ? Math.max(1, actionDrafts.length) : actionDrafts.length;
  const workspaceFlow = useMemo(() => buildWorkspaceFlow({
    status: displayStatus,
    workbench,
    dashboardCount: dashboards.dashboards.length,
    pendingDraftCount,
    agentRequiresConfirmation: agent.requiresConfirmation === true,
  }), [agent.requiresConfirmation, dashboards.dashboards.length, displayStatus, pendingDraftCount, workbench]);
  const openSection = useCallback((nextSection: AppSection) => {
    setSection(resolveSectionForFlow(nextSection, workspaceFlow));
  }, [workspaceFlow]);

  useEffect(() => {
    if (loadState === "loading") return;
    const resolvedSection = resolveSectionForFlow(section, workspaceFlow);
    if (resolvedSection !== section) {
      setSection(resolvedSection);
    }
  }, [loadState, section, workspaceFlow]);

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
    handleSourceDashboardDraft,
    handleSourceIntelligenceRun,
    handleSyncConnector,
    handleTableQuery,
  } = useAppDataActions({
    setActionDrafts,
    setActiveViewKey,
    setDashboards,
    setFormulaPreview,
    setLastActionResult,
    setPreview,
    setQuery,
    setRelationshipPreview,
    setSection,
    setStatus,
    setTableQuery,
    setWorkbench,
  });

  const {
    handleBusinessDashboardOperation,
    handleDashboardFilterOperation,
    handleDashboardModulesSave,
    handleDashboardOperation,
    handleDashboardWidgetOperation,
  } = useAppDashboardActions({
    setActiveDashboardKey,
    setDashboards,
    setLastActionResult,
    setStatus,
    setWorkbench,
  });

  const {
    handleAgentCommandAsk,
    handleAsk,
    handleAskReadOnly,
    handleConfirmAction,
    handleConfirmDryRun,
    handleDraftDashboard,
    handleHomeAsk,
    handleRejectAction,
  } = useAppAgentActions({
    setActionDrafts,
    setActiveDashboardKey,
    setAgent,
    setDashboards,
    setLastActionResult,
    setSection,
    setStatus,
    setWorkbench,
  });

  const handleAgentPanelAsk = useCallback(async (prompt: string) => {
    await handleAsk(prompt);
  }, [handleAsk]);

  const {
    handleApplyConfig,
    handleExportConfig,
    handleSavePreferences,
    handleSaveThemePalette,
    handleValidateConfig,
  } = useAppSettingsActions({
    setDashboards,
    setLastActionResult,
    setSection,
    setStatus,
    setWorkbench,
  });

  const handleOpenEvidence = useCallback((focus: EvidenceFocus) => {
    setEvidenceFocus(focus);
    openSection("evidence");
  }, [openSection]);

  const handleOpenBusinessStep = useCallback((step: BusinessPathStepKey) => {
    openSection(businessSectionForStep(step));
  }, [openSection]);

  const mainView = useMemo(() => {
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
          onOpenBusinessStep={handleOpenBusinessStep}
          onOpenSection={openSection}
        />
      );
    }
    if (section === "dashboards") {
      return (
        <DashboardCanvas
          dashboards={dashboards}
          query={query}
          workbench={workbench}
          activeDashboardKey={activeDashboardKey}
          onDashboardSelect={setActiveDashboardKey}
          onAgentDraft={handleDraftDashboard}
          onAsk={handleAgentCommandAsk}
          onOpenEvidence={handleOpenEvidence}
          onDashboardFilterOperation={handleDashboardFilterOperation}
          onDashboardOperation={handleDashboardOperation}
          onDashboardModulesSave={handleDashboardModulesSave}
          onBusinessDashboardOperation={handleBusinessDashboardOperation}
          onRelationshipSave={handleDashboardRelationshipSave}
          onDashboardWidgetOperation={handleDashboardWidgetOperation}
          onOpenBusinessStep={handleOpenBusinessStep}
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
          onAsk={handleAgentPanelAsk}
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
          dashboardCount={dashboards.dashboards.length}
          focus={evidenceFocus}
          lastActionResult={lastActionResult}
          pendingDraftCount={pendingDraftCount}
          onSetSemantic={handleSetSemantic}
          onSourceIntelligenceRun={handleSourceIntelligenceRun}
          onOpenBusinessStep={handleOpenBusinessStep}
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
          onOpenEvidence={handleOpenEvidence}
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
          onOpenBusinessStep={handleOpenBusinessStep}
          onOpenDashboard={() => openSection("dashboards")}
        />
      );
  }, [activeDashboardKey, activeViewKey, actionDrafts, agent, dashboards, evidenceFocus, formulaPreview, handleAddMetric, handleAgentCommandAsk, handleAgentPanelAsk, handleApplyConfig, handleAskReadOnly, handleBusinessDashboardOperation, handleCommitFolderImport, handleCommitImport, handleConfirmAction, handleConfirmDryRun, handleCopyView, handleDashboardFilterOperation, handleDashboardOperation, handleDashboardRelationshipSave, handleDashboardWidgetOperation, handleDeleteFormula, handleDeleteSource, handleDeleteView, handleDraftDashboard, handleExportConfig, handleFieldUpdate, handleFormulaPreview, handleHomeAsk, handleImportPolicy, handleInferMetrics, handleInferSemantics, handleInspectSource, handleNavigationOperation, handleOpenBusinessStep, handleOpenEvidence, handlePreview, handlePreviewFolderImport, handleQuery, handleQueryMetric, handleRejectAction, handleRelationshipPreview, handleRelationshipSave, handleRemoveConnector, handleRemoveImportJob, handleRenameSource, handleSaveConnector, handleSaveFormula, handleSavePreferences, handleSaveThemePalette, handleSaveView, handleSetSemantic, handleSourceDashboardDraft, handleSourceIntelligenceRun, handleSyncConnector, handleTableQuery, handleValidateConfig, lastActionResult, openSection, preview, query, relationshipPreview, resolvedLanguage, section, status, tableQuery, workbench]);
  const activeDashboardName = dashboards.dashboards.find((dashboard) => dashboard.dashboard_key === activeDashboardKey)?.name ?? activeDashboardKey;
  const activeViewName = workbench.savedViews.find((view) => view.view_key === activeViewKey)?.name ?? activeViewKey;
  const activeTableName = workbench.tables[0]?.display_name ?? status.sourceRuns[0]?.name ?? "";
  const inspectorExpanded = inspectorPreference.expanded || inspectorPreference.pinned;

  const handleInspectorExpand = useCallback(() => {
    setInspectorPreference((current) => ({ ...current, expanded: true }));
  }, []);

  const handleInspectorCollapse = useCallback(() => {
    setInspectorPreference((current) => ({ ...current, expanded: false, pinned: false }));
  }, []);

  const handleInspectorPinToggle = useCallback(() => {
    setInspectorPreference((current) => {
      const pinned = !current.pinned;
      return { expanded: pinned ? true : current.expanded, pinned };
    });
  }, []);

  const handleInspectorOpenAgent = useCallback(() => {
    setInspectorPreference((current) => ({ ...current, expanded: true }));
    openSection("agent");
  }, [openSection]);

  const handleInspectorOpenEvidence = useCallback(() => {
    setInspectorPreference((current) => ({ ...current, expanded: true }));
    openSection("evidence");
  }, [openSection]);

  const handleInspectorOpenSection = useCallback((nextSection: AppSection) => {
    setInspectorPreference((current) => ({ ...current, expanded: true }));
    openSection(nextSection);
  }, [openSection]);

  return (
    <div
      className="appShell"
      data-inspector-state={inspectorExpanded ? "expanded" : "collapsed"}
      data-inspector-pinned={inspectorPreference.pinned ? "true" : "false"}
      data-language={resolvedLanguage}
      data-load-state={loadState}
      lang={resolvedLanguage === "zh" ? "zh-CN" : "en"}
    >
      <Sidebar
        activeDashboardKey={activeDashboardKey}
        activeSection={section}
        actionDrafts={actionDrafts}
        agent={agent}
        dashboards={dashboards}
        onDashboardSelect={setActiveDashboardKey}
        onSectionChange={openSection}
        onSourceIntelligenceRun={handleSourceIntelligenceRun}
        onWorkspaceCreate={handleWorkspaceCreate}
        onWorkspaceDelete={handleWorkspaceDelete}
        onWorkspaceRename={handleWorkspaceRename}
        onWorkspaceSelect={handleWorkspaceSelect}
        status={displayStatus}
        workbench={workbench}
        flow={workspaceFlow}
      />
      <main className="contentShell">
        <TopBar activeSection={section} status={displayStatus} apiMode={apiMode} />
        <BusinessPathBar
          activeSection={section}
          flow={workspaceFlow}
          onOpenStep={handleOpenBusinessStep}
        />
        <Suspense fallback={<ModuleLoadingPanel section={section} language={resolvedLanguage} />}>
          {mainView}
        </Suspense>
      </main>
      <AgentCommandDock
        activeSection={section}
        actionDrafts={actionDrafts}
        agent={agent}
        onAsk={handleAgentCommandAsk}
        onOpenAgent={() => openSection("agent")}
        onOpenSection={openSection}
        status={displayStatus}
      />
      <Suspense fallback={<InspectorLoadingPanel language={resolvedLanguage} />}>
        <InspectorPanel
          activeSection={section}
          status={displayStatus}
          preview={preview}
          agent={agent}
          actionDrafts={actionDrafts}
          evidenceFocus={evidenceFocus}
          activeDashboardName={activeDashboardName}
          activeViewName={activeViewName}
          activeTableName={activeTableName}
          lastActionResult={lastActionResult}
          actionQueueDisabled={loadState === "loading" || apiMode !== "live"}
          inspectorCollapsed={!inspectorExpanded}
          inspectorPinned={inspectorPreference.pinned}
          onConfirmDryRun={handleConfirmDryRun}
          onConfirmAction={handleConfirmAction}
          onRejectAction={handleRejectAction}
          onCollapseInspector={handleInspectorCollapse}
          onExpandInspector={handleInspectorExpand}
          onPinInspectorToggle={handleInspectorPinToggle}
          onOpenAgent={handleInspectorOpenAgent}
          onOpenEvidence={handleInspectorOpenEvidence}
          onOpenSection={handleInspectorOpenSection}
        />
      </Suspense>
    </div>
  );
}
