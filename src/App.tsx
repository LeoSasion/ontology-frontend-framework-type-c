import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AppSection } from "./appSections";
import { useLanguage } from "./components/Bilingual";
import { emptyAgentResult, emptyDashboardPayload, emptyFormulaPreview, emptyImportPreview, emptyQueryResult, emptyTableQuery, emptyWorkbenchPayload, emptyWorkspaceStatus } from "./emptyWorkspaceData";
import { applyThemePalette, getUserPreferences, hasStoredThemeSnapshot, resolveThemePalette } from "./theme";
import { businessSectionForStep, type BusinessPathStepKey } from "./businessPathModel";
import { actionErrorResult, connectingStatus, preferredLandingSection, type ApiMode, type LoadState } from "./appWorkspaceModel";
import { refreshStatusDashboardsWorkbenchDrafts } from "./appRefreshModel";
import { AppMainView, ModuleLoadingPanel, Sidebar, TopBar, preloadModules, sectionPreloaders } from "./appLazyModules";
import { useAppAgentActions } from "./useAppAgentActions";
import { useAppDataActions } from "./useAppDataActions";
import { useAppDashboardActions } from "./useAppDashboardActions";
import { useAppSettingsActions } from "./useAppSettingsActions";
import { useAppWorkspaceActions } from "./useAppWorkspaceActions";
import type { ActionDraft, AgentAskResult, DashboardPayload, EvidenceFocus, FormulaPreviewPayload, ImportPreview, QueryResult, TableQueryPayload, WorkbenchPayload, WorkspaceStatus } from "./types";
import { buildWorkspaceFlow, resolveSectionForFlow } from "./workspaceFlowModel";
import {
  evidenceFocusFromNavigation,
  navigationContextFromEvidence,
  navigationContextForSection,
  navigationContextFromTarget,
  mergeNavigationContext,
  readNavigationTarget,
  sameNavigationTarget,
  writeNavigationUrl,
  type AppNavigationContext,
  type AppNavigationTarget,
} from "./appNavigationModel";
import { getAppSection } from "./appSections";

export default function App() {
  const { resolvedLanguage } = useLanguage();
  const initialNavigationRef = useRef<AppNavigationTarget | null>(null);
  if (!initialNavigationRef.current) initialNavigationRef.current = readNavigationTarget(window.location.search);
  const initialNavigation = initialNavigationRef.current;
  const [section, setSection] = useState<AppSection>(initialNavigation.section);
  const explicitInitialSectionRef = useRef(new URLSearchParams(window.location.search).has("section"));
  const previousSectionRef = useRef<AppSection>(initialNavigation.section);
  const contentRef = useRef<HTMLElement | null>(null);
  const autoLandingAppliedRef = useRef(false);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [status, setStatus] = useState<WorkspaceStatus>(emptyWorkspaceStatus);
  const [preview, setPreview] = useState<ImportPreview>(emptyImportPreview);
  const [query, setQuery] = useState<QueryResult>(emptyQueryResult);
  const [tableQuery, setTableQuery] = useState<TableQueryPayload>(emptyTableQuery);
  const [workbench, setWorkbench] = useState<WorkbenchPayload>(emptyWorkbenchPayload);
  const [formulaPreview, setFormulaPreview] = useState<FormulaPreviewPayload>(emptyFormulaPreview);
  const [dashboards, setDashboards] = useState<DashboardPayload>(emptyDashboardPayload);
  const [activeDashboardKey, setActiveDashboardKey] = useState(initialNavigation.dashboardKey ?? "default");
  const [activeViewKey, setActiveViewKey] = useState(initialNavigation.viewKey ?? "");
  const [agent, setAgent] = useState<AgentAskResult>(emptyAgentResult);
  const [actionDrafts, setActionDrafts] = useState<ActionDraft[]>([]);
  const [lastActionResult, setLastActionResult] = useState<Record<string, unknown> | null>(null);
  const [navigationContext, setNavigationContext] = useState<AppNavigationContext>(() => navigationContextFromTarget(initialNavigation));
  const [evidenceFocus, setEvidenceFocus] = useState<EvidenceFocus | null>(() => evidenceFocusFromNavigation(initialNavigation));
  const workspaceActions = useAppWorkspaceActions({
    activeWorkspaceId: status.workspace.id,
    setActionDrafts,
    setActiveDashboardKey,
    setActiveViewKey,
    setAgent,
    setDashboards,
    setLastActionResult,
    setNavigationContext,
    setEvidenceFocus,
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
      setActiveDashboardKey((current) => current === "default" ? surface.dashboards.dashboards[0]?.dashboard_key ?? "default" : current);
      setActiveViewKey((current) => current || (surface.workbench.savedViews[0]?.view_key ?? ""));
      setActionDrafts(surface.actionDrafts);
      setAgent(emptyAgentResult);
      if (!explicitInitialSectionRef.current && !autoLandingAppliedRef.current) {
        setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards, surface.actionDrafts.length));
        autoLandingAppliedRef.current = true;
      }
    } catch (error) {
      setLastActionResult(actionErrorResult("initial-load", error));
      setStatus({
        ...emptyWorkspaceStatus,
        health: {
          ok: false,
          notes: [error instanceof Error ? error.message : String(error)],
        },
      });
    }
    setLoadState("ready");
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    preloadModules(sectionPreloaders[section]);
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
  const pendingDraftCount = actionDrafts.filter((draft) => draft.status === "draft").length;
  const agentHasPendingDraft = agent.requiresConfirmation === true && pendingDraftCount > 0;
  const workspaceFlow = useMemo(() => buildWorkspaceFlow({
    status: displayStatus,
    workbench,
    dashboardCount: dashboards.dashboards.length,
    pendingDraftCount,
    agentRequiresConfirmation: agentHasPendingDraft,
  }), [agentHasPendingDraft, dashboards.dashboards.length, displayStatus, pendingDraftCount, workbench]);
  const navigateTo = useCallback((target: AppNavigationTarget) => {
    const resolvedSection = target.allowLocked ? target.section : resolveSectionForFlow(target.section, workspaceFlow);
    const requestedContext = mergeNavigationContext(navigationContext, navigationContextFromTarget(target));
    const mergedContext: AppNavigationContext = {
      ...requestedContext,
      dashboardKey: target.dashboardKey ?? (activeDashboardKey !== "default" ? activeDashboardKey : navigationContext.dashboardKey),
      viewKey: target.viewKey ?? (activeViewKey || navigationContext.viewKey),
      origin: resolvedSection === "evidence" ? target.origin : undefined,
    };
    const resolvedTarget: AppNavigationTarget = {
      section: resolvedSection,
      ...navigationContextForSection(resolvedSection, mergedContext),
      evidenceFocus: target.evidenceFocus,
      allowLocked: target.allowLocked,
    };
    if (target.dashboardKey) setActiveDashboardKey(target.dashboardKey);
    if (target.viewKey) setActiveViewKey(target.viewKey);
    if (target.evidenceFocus !== undefined) setEvidenceFocus(target.evidenceFocus);
    else if (resolvedTarget.section === "evidence") setEvidenceFocus(evidenceFocusFromNavigation(resolvedTarget));
    setNavigationContext(navigationContextFromTarget(resolvedTarget));
    setSection(resolvedTarget.section);

    const currentTarget = readNavigationTarget(window.location.search);
    if (!sameNavigationTarget(currentTarget, resolvedTarget)) {
      window.history.pushState(null, "", writeNavigationUrl(window.location.href, resolvedTarget));
    }
  }, [activeDashboardKey, activeViewKey, navigationContext, workspaceFlow]);

  const openSection = useCallback((nextSection: AppSection) => {
    navigateTo({ section: nextSection });
  }, [navigateTo]);

  useEffect(() => {
    const target: AppNavigationTarget = {
      section,
      ...navigationContextForSection(section, {
        ...navigationContext,
        dashboardKey: activeDashboardKey !== "default" ? activeDashboardKey : navigationContext.dashboardKey,
        viewKey: activeViewKey || navigationContext.viewKey,
      }),
    };
    const nextUrl = writeNavigationUrl(window.location.href, target);
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (currentUrl !== nextUrl) window.history.replaceState(null, "", nextUrl);
  }, [activeDashboardKey, activeViewKey, navigationContext, section]);

  useEffect(() => {
    const handlePopState = () => {
      const target = readNavigationTarget(window.location.search);
      const resolvedSection = resolveSectionForFlow(target.section, workspaceFlow);
      setNavigationContext(navigationContextFromTarget(target));
      if (target.dashboardKey) setActiveDashboardKey(target.dashboardKey);
      if (target.viewKey) setActiveViewKey(target.viewKey);
      setEvidenceFocus(resolvedSection === "evidence" ? evidenceFocusFromNavigation(target) : null);
      setSection(resolvedSection);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [workspaceFlow]);

  useEffect(() => {
    if (loadState === "loading") return;
    const resolvedSection = resolveSectionForFlow(section, workspaceFlow);
    if (resolvedSection !== section) {
      setSection(resolvedSection);
    }
  }, [loadState, section, workspaceFlow]);

  useEffect(() => {
    const meta = getAppSection(section);
    document.title = `${resolvedLanguage === "zh" ? meta.zh : meta.en} · AIBI-C`;
    if (previousSectionRef.current !== section) {
      previousSectionRef.current = section;
      window.requestAnimationFrame(() => contentRef.current?.focus({ preventScroll: true }));
    }
  }, [resolvedLanguage, section]);

  const dataActions = useAppDataActions({
    activeWorkspaceId: status.workspace.id,
    workbench,
    setActionDrafts,
    setActiveViewKey,
    setDashboards,
    setFormulaPreview,
    setLastActionResult,
    setPreview,
    setQuery,
    navigateTo,
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
    activeWorkspaceId: status.workspace.id,
    setActionDrafts,
    setActiveDashboardKey,
    setAgent,
    setDashboards,
    setLastActionResult,
    navigateTo,
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
    navigateTo({
      section: "evidence",
      evidenceFocus: focus,
      ...navigationContextFromEvidence(focus, section),
    });
  }, [navigateTo, section]);

  const handleOpenSectionForStep = useCallback((step: BusinessPathStepKey) => {
    openSection(businessSectionForStep(step));
  }, [openSection]);

  const focusedTable = workbench.tables.find((table) => table.table_key === navigationContext.tableKey) ?? workbench.tables[0];

  return (
    <div
      className="appShell"
      data-language={resolvedLanguage}
      data-load-state={loadState}
      lang={resolvedLanguage === "zh" ? "zh-CN" : "en"}
    >
      <a className="skipLink" href="#main-content">{resolvedLanguage === "zh" ? "跳到主要内容" : "Skip to main content"}</a>
      <Suspense fallback={<aside className="workspaceSidebar" aria-hidden="true" />}>
        <Sidebar
          activeSection={section}
          actionDrafts={actionDrafts}
          onSectionChange={openSection}
          onWorkspaceCreate={workspaceActions.handleWorkspaceCreate}
          onWorkspaceDelete={workspaceActions.handleWorkspaceDelete}
          onWorkspaceRename={workspaceActions.handleWorkspaceRename}
          onWorkspaceSelect={workspaceActions.handleWorkspaceSelect}
          status={displayStatus}
          flow={workspaceFlow}
        />
      </Suspense>
      <main className="contentShell" id="main-content" ref={contentRef} tabIndex={-1}>
        <Suspense fallback={null}>
          <TopBar
            activeSection={section}
            apiMode={apiMode}
            flow={workspaceFlow}
            onOpenAgent={() => openSection("agent")}
            onRetryService={() => void refresh()}
            pendingDraftCount={pendingDraftCount}
            status={displayStatus}
          />
        </Suspense>
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
            focusedTableKey={focusedTable?.table_key ?? navigationContext.tableKey ?? ""}
            formulaPreview={formulaPreview}
            lastActionResult={lastActionResult}
            onOpenBusinessStep={handleOpenSectionForStep}
            onOpenEvidence={handleOpenEvidence}
            openSection={openSection}
            navigateTo={navigateTo}
            pendingDraftCount={pendingDraftCount}
            preview={preview}
            query={query}
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
    </div>
  );
}
