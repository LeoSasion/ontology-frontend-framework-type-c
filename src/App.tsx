import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { InspectorLoadingPanel, InspectorPanel, ModuleLoadingPanel, allSectionPreloaders, inspectorPreloader, preloadModules, scheduleIdlePreload, sectionPreloaders } from "./appLazyModules";
import { BusinessPathBar } from "./components/BusinessPathBar";
import { AppMainView } from "./components/AppMainView";
import { useAppAgentActions } from "./useAppAgentActions";
import { useAppDataActions } from "./useAppDataActions";
import { useAppDashboardActions } from "./useAppDashboardActions";
import { useAppSettingsActions } from "./useAppSettingsActions";
import { useAppWorkspaceActions } from "./useAppWorkspaceActions";
import { useInspectorController } from "./useInspectorController";
import type { ActionDraft, AgentAskResult, DashboardPayload, EvidenceFocus, FormulaPreviewPayload, ImportPreview, QueryResult, RelationshipPreviewPayload, TableQueryPayload, WorkbenchPayload, WorkspaceStatus } from "./types";
import { buildWorkspaceFlow, resolveSectionForFlow } from "./workspaceFlowModel";

function sectionFromUrl(): AppSection | null {
  const section = new URLSearchParams(window.location.search).get("section");
  return isAppSection(section) ? section : null;
}

function initialSection(): AppSection {
  return sectionFromUrl() ?? "home";
}

export default function App() {
  const { resolvedLanguage } = useLanguage();
  const [section, setSection] = useState<AppSection>(() => initialSection());
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
  const workspaceActions = useAppWorkspaceActions({
    activeWorkspaceId: status.workspace.id,
    setActionDrafts,
    setActiveDashboardKey,
    setActiveViewKey,
    setAgent,
    setDashboards,
    setLastActionResult,
    setSection,
    setStatus,
    setWorkbench,
  });

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

  const dataActions = useAppDataActions({
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

  const dashboardActions = useAppDashboardActions({
    setActiveDashboardKey,
    setDashboards,
    setLastActionResult,
    setStatus,
    setWorkbench,
  });

  const agentActions = useAppAgentActions({
    setActionDrafts,
    setActiveDashboardKey,
    setAgent,
    setDashboards,
    setLastActionResult,
    setSection,
    setStatus,
    setWorkbench,
  });

  const settingsActions = useAppSettingsActions({
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

  const activeDashboardName = dashboards.dashboards.find((dashboard) => dashboard.dashboard_key === activeDashboardKey)?.name ?? activeDashboardKey;
  const activeViewName = workbench.savedViews.find((view) => view.view_key === activeViewKey)?.name ?? activeViewKey;
  const activeTableName = workbench.tables[0]?.display_name ?? status.sourceRuns[0]?.name ?? "";
  const inspector = useInspectorController(openSection);

  return (
    <div
      className="appShell"
      data-inspector-state={inspector.expanded ? "expanded" : "collapsed"}
      data-inspector-pinned={inspector.pinned ? "true" : "false"}
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
        onSourceIntelligenceRun={dataActions.handleSourceIntelligenceRun}
        onWorkspaceCreate={workspaceActions.handleWorkspaceCreate}
        onWorkspaceDelete={workspaceActions.handleWorkspaceDelete}
        onWorkspaceRename={workspaceActions.handleWorkspaceRename}
        onWorkspaceSelect={workspaceActions.handleWorkspaceSelect}
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
          <AppMainView
            actionDrafts={actionDrafts}
            activeDashboardKey={activeDashboardKey}
            activeViewKey={activeViewKey}
            agent={agent}
            agentActions={agentActions}
            dashboards={dashboards}
            dashboardActions={dashboardActions}
            dataActions={dataActions}
            evidenceFocus={evidenceFocus}
            formulaPreview={formulaPreview}
            lastActionResult={lastActionResult}
            onOpenBusinessStep={handleOpenBusinessStep}
            onOpenEvidence={handleOpenEvidence}
            openSection={openSection}
            pendingDraftCount={pendingDraftCount}
            preview={preview}
            query={query}
            relationshipPreview={relationshipPreview}
            section={section}
            setActiveDashboardKey={setActiveDashboardKey}
            setActiveViewKey={setActiveViewKey}
            settingsActions={settingsActions}
            status={status}
            tableQuery={tableQuery}
            workbench={workbench}
          />
        </Suspense>
      </main>
      <AgentCommandDock
        activeSection={section}
        actionDrafts={actionDrafts}
        agent={agent}
        onAsk={agentActions.handleAgentCommandAsk}
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
          inspectorCollapsed={!inspector.expanded}
          inspectorPinned={inspector.pinned}
          onConfirmDryRun={agentActions.handleConfirmDryRun}
          onConfirmAction={agentActions.handleConfirmAction}
          onRejectAction={agentActions.handleRejectAction}
          onCollapseInspector={inspector.collapse}
          onExpandInspector={inspector.expand}
          onPinInspectorToggle={inspector.togglePinned}
          onOpenAgent={inspector.openAgent}
          onOpenEvidence={inspector.openEvidence}
          onOpenSection={inspector.openAndExpand}
        />
      </Suspense>
    </div>
  );
}
