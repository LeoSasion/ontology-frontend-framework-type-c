import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  captureScreenshot,
  check,
  click,
  evaluate,
  finishReceipt,
  launchChrome,
  navigate,
  setViewport,
  waitFor,
} from "./ui-verify-chrome.mjs";

const apiBaseUrl = process.env.AIBI_API_BASE_URL ?? "http://127.0.0.1:8787";
const baseUrl = process.env.AIBI_UI_BASE_URL ?? apiBaseUrl;
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-flow-"));
const viewport = { key: "desktop", label: "desktop", width: 1280, height: 900 };

async function fetchJson(path) {
  let lastError = null;
  const attempts = 8;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(`${apiBaseUrl}${path}`);
      const payload = await response.json();
      if (!response.ok || payload?.ok === false) throw new Error(`${path}: ${payload?.error ?? `${response.status} ${response.statusText}`}`);
      return payload;
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) {
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 250 * (attempt + 1)));
      }
    }
  }
  throw lastError;
}

function assertPageState() {
  const text = document.body?.innerText || "";
  const get = (testId) => document.querySelector(`[data-testid="${testId}"]`);
  const isVisible = (element) => {
    if (!(element instanceof HTMLElement)) {
      return false;
    }
    if (element.closest("details:not([open])")) {
      return false;
    }
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden";
  };
  const visible = (testId) => isVisible(get(testId));
  const visibleCount = (selector) => Array.from(document.querySelectorAll(selector)).filter(isVisible).length;
  const disabled = (testId) => Boolean(get(testId)?.disabled);
  const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复");
  return {
    title: document.title,
    url: location.href,
    connected: Boolean(document.querySelector(".appShell")) && !get("service-diagnostics"),
    hasErrorBoundary,
    errorDetail: document.querySelector(".appFallback pre, .fallbackPanel pre")?.textContent?.trim() || "",
    hasFrameworkOverlay: Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay")),
    noSampleCopy: !/样例|示例|demo data|test data|fallback source|mock data|lorem/i.test(text),
    chrome: {
      singleSidebar: Boolean(document.querySelector(".workspaceSidebar")),
      noGlobalBusinessPath: !get("global-business-path"),
      noGlobalAgentDock: !get("agent-command-dock"),
      noGlobalInspector: !document.querySelector(".inspector"),
    },
    home: {
      primaryTask: visible("workspace-primary-task"),
      journey: visible("workspace-journey"),
      connectData: visible("workspace-connect-data"),
      prepareEvidence: visible("workspace-prepare-evidence"),
      questionForm: visible("workspace-question-form"),
      reviewDraft: visible("workspace-review-draft"),
      openBoard: visible("workspace-open-board"),
    },
    sources: {
      entry: visible("source-intelligence-folder-entry"),
      importPreview: visible("source-import-preview-button"),
      coverageItems: visibleCount('[data-testid="source-coverage-item"]'),
      analysisNextAction: visible("source-next-analysis") || visible("beginner-plan-refresh-profile"),
      sourceError: visible("source-intelligence-error"),
    },
    dashboards: {
      taskStrip: Boolean(get("dashboard-business-task-strip")),
      chartPrompt: Boolean(get("dashboard-ai-chart-prompt")),
      createOneChart: Boolean(get("dashboard-task-explain")),
      evidenceJump: Boolean(get("dashboard-more-evidence")),
      secondaryCollapsed: Boolean(get("dashboard-more-details")) && !get("dashboard-more-details").open,
    },
    evidence: {
      businessSummary: Boolean(get("evidence-business-summary")),
      sourceSummary: Boolean(get("evidence-source-intelligence-summary")),
      receiptsCollapsed: Boolean(get("evidence-receipts-details")) && !get("evidence-receipts-details").open,
    },
    agent: {
      taskPacket: Boolean(get("agent-task-packet")),
      draftQueue: Boolean(get("agent-draft-queue")),
      emptyDraftQueue: Boolean(get("agent-draft-queue-empty")),
      noDataRoute: Boolean(get("agent-no-data-route")),
    },
  };
}

async function readCurrentSection(client, testId) {
  const ready = await waitFor(client, (expectedTestId) => {
    const text = document.body?.innerText || "";
    const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复");
    return {
      ok: Boolean(document.querySelector(".appShell")) &&
        Boolean(document.querySelector(`[data-testid="${expectedTestId}"]`)) &&
        !document.querySelector('[data-testid="service-diagnostics"]') &&
        !hasErrorBoundary,
      title: document.title,
      url: location.href,
      hasShell: Boolean(document.querySelector(".appShell")),
      hasSection: Boolean(document.querySelector(`[data-testid="${expectedTestId}"]`)),
      hasServiceDiagnostics: Boolean(document.querySelector('[data-testid="service-diagnostics"]')),
      hasErrorBoundary,
      hasFrameworkOverlay: Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay")),
    };
  }, testId, { timeoutMs: 25000, intervalMs: 250 });
  const state = await evaluate(client, assertPageState, null, 10000);
  return { ready, state };
}

async function waitForSection(client, section, testId) {
  let result = null;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const retry = attempt ? `&retry=${Date.now()}-${attempt}` : "";
    await navigate(client, `${baseUrl}/?section=${section}${retry}`);
    result = await readCurrentSection(client, testId);
    if (result.ready.ok) return result;
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250 * (attempt + 1)));
  }
  return result;
}

const checks = [];
const steps = [];
let browser = null;
let status = null;
let workbench = null;
let dashboards = null;
let drafts = null;
let browserIssues = [];

try {
  [status, workbench, dashboards, drafts] = await Promise.all([
    fetchJson("/api/status"),
    fetchJson("/api/workbench"),
    fetchJson("/api/dashboards"),
    fetchJson("/api/actions?limit=12"),
  ]);
  const counts = status.counts ?? {};
  const hasData = Number(counts.tables ?? 0) > 0;
  const hasSourceIntelligence = Number(counts.sourceIntelligenceRuns ?? 0) > 0;
  const latestUsableSourceIntelligenceRun = Array.isArray(workbench.sourceIntelligenceRuns)
    ? workbench.sourceIntelligenceRuns.find((run) => run.freshness?.usableForPlanning !== false)
    : null;
  const hasCurrentEvidence = Boolean(latestUsableSourceIntelligenceRun);
  const dashboardList = Array.isArray(dashboards.dashboards) ? dashboards.dashboards : [];
  const dashboardCount = Number(counts.dashboards ?? dashboardList.length);
  const hasPendingDraft = Number(drafts.pendingCount ?? drafts.actionDrafts?.length ?? 0) > 0;
  checks.push(
    check("api-live-status", status.ok === true && Boolean(status.database), { workspace: status.workspace, counts }),
    check("api-workspace-data-state-supported", hasData || Number(counts.tables ?? 0) === 0, { mode: hasData ? "data" : "empty", tables: counts.tables }),
    check("api-source-intelligence-state-supported", hasData ? hasSourceIntelligence : Number(counts.sourceIntelligenceRuns ?? 0) === 0, { mode: hasData ? "data" : "empty", sourceIntelligenceRuns: counts.sourceIntelligenceRuns }),
    check("api-dashboard-state-supported", Array.isArray(dashboards.dashboards) && dashboardCount >= 0, { mode: hasData ? "data" : "empty", dashboards: dashboardCount, savedDashboards: dashboardList.length }),
    check("api-action-drafts-readable", Array.isArray(drafts.actionDrafts), { pendingCount: drafts.pendingCount ?? drafts.actionDrafts?.length ?? 0 }),
  );

  browser = await launchChrome();
  await setViewport(browser.client, viewport);

  if (!hasData) {
    const sourcesPage = await waitForSection(browser.client, "sources", "source-import-preview-button");
    checks.push(
      check("ui-empty-sources-ready", sourcesPage.ready.ok, { ready: sourcesPage.ready }),
      check("ui-empty-sources-import-only", sourcesPage.state.sources.importPreview && !sourcesPage.state.sources.entry),
      check("ui-empty-sources-no-inline-source-error", !sourcesPage.state.sources.sourceError),
      check("ui-empty-sources-no-error", !sourcesPage.state.hasErrorBoundary && !sourcesPage.state.hasFrameworkOverlay),
      check("ui-empty-sources-no-sample-copy", sourcesPage.state.noSampleCopy),
    );
    steps.push({ section: "empty-sources", state: sourcesPage.state });

    const dashboardLocked = await waitForSection(browser.client, "dashboards", "source-import-preview-button");
    checks.push(
      check("ui-empty-dashboard-routes-to-import", dashboardLocked.ready.ok && dashboardLocked.state.sources.importPreview && !dashboardLocked.state.sources.entry, { ready: dashboardLocked.ready, url: dashboardLocked.state.url }),
      check("ui-empty-dashboard-no-error", !dashboardLocked.state.hasErrorBoundary && !dashboardLocked.state.hasFrameworkOverlay),
    );
    steps.push({ section: "empty-dashboard-locked", state: dashboardLocked.state });

    const evidenceLocked = await waitForSection(browser.client, "evidence", "source-import-preview-button");
    checks.push(
      check("ui-empty-evidence-routes-to-import", evidenceLocked.ready.ok && evidenceLocked.state.sources.importPreview && !evidenceLocked.state.sources.entry, { ready: evidenceLocked.ready, url: evidenceLocked.state.url }),
      check("ui-empty-evidence-no-error", !evidenceLocked.state.hasErrorBoundary && !evidenceLocked.state.hasFrameworkOverlay),
    );
    steps.push({ section: "empty-evidence-locked", state: evidenceLocked.state });

    const agentPage = await waitForSection(browser.client, "agent", "agent-no-data-route");
    checks.push(
      check("ui-empty-agent-ready", agentPage.ready.ok, { ready: agentPage.ready }),
      check("ui-empty-agent-no-data-route-visible", agentPage.state.agent.noDataRoute),
      check("ui-empty-agent-no-error", !agentPage.state.hasErrorBoundary && !agentPage.state.hasFrameworkOverlay),
      check("ui-empty-agent-no-sample-copy", agentPage.state.noSampleCopy),
    );
    steps.push({ section: "empty-agent", state: agentPage.state });

    const screenshot = await captureScreenshot(browser.client, join(screenshotDir, "ui-flow-empty-agent-ready.png"));
    steps.push({ section: "empty-agent-screenshot", screenshot });
  } else {
    const home = await waitForSection(browser.client, "home", "workspace-primary-task");
    checks.push(
      check("ui-home-ready", home.ready.ok, { ready: home.ready }),
      check("ui-home-single-primary-task-visible", home.state.home.primaryTask),
      check("ui-home-four-step-journey-visible", home.state.home.journey),
      check(
        "ui-home-primary-task-matches-evidence-state",
        hasPendingDraft
          ? home.state.home.reviewDraft && !home.state.home.questionForm
          : hasCurrentEvidence
          ? home.state.home.questionForm && !home.state.home.prepareEvidence
          : home.state.home.prepareEvidence && !home.state.home.questionForm,
        { hasCurrentEvidence, hasPendingDraft, home: home.state.home },
      ),
      check("ui-home-board-hidden-while-evidence-stale", hasCurrentEvidence || !home.state.home.openBoard, { hasCurrentEvidence, openBoard: home.state.home.openBoard }),
      check("ui-shell-redundant-global-chrome-retired", home.state.chrome.singleSidebar && home.state.chrome.noGlobalBusinessPath && home.state.chrome.noGlobalAgentDock && home.state.chrome.noGlobalInspector, home.state.chrome),
      check("ui-home-no-error", !home.state.hasErrorBoundary && !home.state.hasFrameworkOverlay),
      check("ui-home-no-sample-copy", home.state.noSampleCopy),
    );
    steps.push({ section: "home", state: home.state });

    if (hasCurrentEvidence && dashboardCount > 0) {
      const boardClick = await click(browser.client, '[data-testid="workspace-open-board"]');
      checks.push(check("ui-home-board-click-fired", boardClick.ok, boardClick));
      const dashboardsPage = await readCurrentSection(browser.client, "dashboard-business-task-strip");
      checks.push(
        check("ui-home-to-dashboard-jump", dashboardsPage.ready.ok && dashboardsPage.state.url.includes("section=dashboards"), { ready: dashboardsPage.ready, url: dashboardsPage.state.url }),
        check("ui-dashboard-single-chart-prompt-visible", dashboardsPage.state.dashboards.chartPrompt && dashboardsPage.state.dashboards.createOneChart),
        check("ui-dashboard-evidence-jump-visible", dashboardsPage.state.dashboards.evidenceJump),
        check("ui-dashboard-secondary-settings-collapsed", dashboardsPage.state.dashboards.secondaryCollapsed),
        check("ui-dashboard-no-error", !dashboardsPage.state.hasErrorBoundary && !dashboardsPage.state.hasFrameworkOverlay),
      );
      steps.push({ section: "dashboards", state: dashboardsPage.state });

      const moreClick = await click(browser.client, '[data-testid="dashboard-more-details"] > summary');
      checks.push(check("ui-dashboard-more-opened", moreClick.ok, moreClick));
      const evidenceClick = await click(browser.client, '[data-testid="dashboard-more-evidence"]');
      checks.push(check("ui-dashboard-evidence-click-fired", evidenceClick.ok, evidenceClick));
      const evidencePage = await readCurrentSection(browser.client, "evidence-next-action");
      checks.push(
        check("ui-dashboard-to-evidence-jump", evidencePage.ready.ok && evidencePage.state.url.includes("section=evidence"), { ready: evidencePage.ready, url: evidencePage.state.url }),
        check("ui-evidence-source-summary-visible", evidencePage.state.evidence.sourceSummary),
        check("ui-evidence-raw-receipts-collapsed", evidencePage.state.evidence.receiptsCollapsed),
        check("ui-evidence-no-error", !evidencePage.state.hasErrorBoundary && !evidencePage.state.hasFrameworkOverlay),
      );
      steps.push({ section: "evidence", state: evidencePage.state });
    }

    const sourcesPage = await waitForSection(browser.client, "sources", "beginner-import-plan");
    checks.push(
      check("ui-sources-ready", sourcesPage.ready.ok, { ready: sourcesPage.ready }),
      check("ui-sources-profile-entry-hidden-after-profile", !sourcesPage.state.sources.entry),
      check("ui-sources-raw-coverage-hidden-after-profile", sourcesPage.state.sources.coverageItems === 0, { coverageItems: sourcesPage.state.sources.coverageItems }),
      check("ui-sources-analysis-next-action-visible", sourcesPage.state.sources.analysisNextAction),
      check("ui-sources-no-inline-source-error", !sourcesPage.state.sources.sourceError),
      check("ui-sources-no-error", !sourcesPage.state.hasErrorBoundary && !sourcesPage.state.hasFrameworkOverlay),
    );
    steps.push({ section: "sources", state: sourcesPage.state });

    const expertClick = await click(browser.client, '[data-testid="source-expert-toggle"]');
    const relationshipSafetyReady = await waitFor(browser.client, () => ({
      ok: Boolean(document.querySelector('[data-testid="relationship-safety-controls"]')),
      loading: Boolean(document.querySelector('[data-testid="source-advanced-loading"]')),
    }), null, { timeoutMs: 12000, intervalMs: 250 });
    const relationshipSafetyOpen = await click(browser.client, '[data-testid="relationship-safety-controls"] > summary');
    const relationshipSafetyState = await evaluate(browser.client, () => {
      const panel = document.querySelector('[data-testid="relationship-safety-controls"]');
      return {
        open: panel instanceof HTMLDetailsElement && panel.open,
        selectCount: panel?.querySelectorAll("select").length ?? 0,
        inputCount: panel?.querySelectorAll("input").length ?? 0,
      };
    });
    const relationshipSafetyEdit = await evaluate(browser.client, () => {
      const panel = document.querySelector('[data-testid="relationship-safety-controls"]');
      const selects = panel?.querySelectorAll("select") ?? [];
      const filterField = selects[0];
      const preaggregationMeasure = selects[2];
      const unavailable = document.querySelector('[data-testid="relationship-modeling-unavailable"]');
      const available = filterField instanceof HTMLSelectElement
        && preaggregationMeasure instanceof HTMLSelectElement
        && !filterField.disabled
        && !preaggregationMeasure.disabled;
      const setFirstBusinessOption = (select) => {
        if (!(select instanceof HTMLSelectElement) || select.options.length < 2) return false;
        select.value = select.options[1].value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      };
      return {
        available,
        unavailable: Boolean(unavailable),
        filterChanged: available && setFirstBusinessOption(filterField),
        preaggregationChanged: available && setFirstBusinessOption(preaggregationMeasure),
      };
    });
    const relationshipSafetyApplied = await waitFor(browser.client, () => {
      const panel = document.querySelector('[data-testid="relationship-safety-controls"]');
      const selects = panel?.querySelectorAll("select") ?? [];
      const input = panel?.querySelector("input");
      const unavailable = document.querySelector('[data-testid="relationship-modeling-unavailable"]');
      const unavailableState = Boolean(
        unavailable
        && selects[0] instanceof HTMLSelectElement
        && selects[0].disabled
        && selects[2] instanceof HTMLSelectElement
        && selects[2].disabled,
      );
      const editableState = Boolean(input && !input.disabled && selects[3] instanceof HTMLSelectElement && !selects[3].disabled);
      return {
        ok: unavailableState || editableState,
        unavailable: unavailableState,
        editable: editableState,
        filterValue: selects[0] instanceof HTMLSelectElement ? selects[0].value : "",
        measureValue: selects[2] instanceof HTMLSelectElement ? selects[2].value : "",
      };
    }, null, { timeoutMs: 4000, intervalMs: 100 });
    checks.push(
      check("ui-source-expert-controls-open", expertClick.ok && relationshipSafetyReady.ok, { expertClick, relationshipSafetyReady }),
      check("ui-relationship-safety-controls-lazy-load", relationshipSafetyReady.ok && !relationshipSafetyReady.loading, relationshipSafetyReady),
      check("ui-relationship-safety-controls-interactive", relationshipSafetyOpen.ok && relationshipSafetyState.open && relationshipSafetyState.selectCount >= 4 && relationshipSafetyState.inputCount >= 1, relationshipSafetyState),
      check(
        "ui-relationship-safety-policy-editable",
        relationshipSafetyApplied.ok && (
          relationshipSafetyEdit.available
            ? relationshipSafetyEdit.filterChanged && relationshipSafetyEdit.preaggregationChanged && relationshipSafetyApplied.editable
            : relationshipSafetyEdit.unavailable && relationshipSafetyApplied.unavailable
        ),
        { relationshipSafetyEdit, relationshipSafetyApplied },
      ),
    );
    steps.push({ section: "sources-relationship-safety", state: relationshipSafetyState });

    const agentPage = await waitForSection(browser.client, "agent", "agent-task-packet");
    checks.push(
      check("ui-agent-ready", agentPage.ready.ok, { ready: agentPage.ready }),
      check("ui-agent-task-packet-visible", agentPage.state.agent.taskPacket),
      check(
        "ui-agent-draft-boundary-matches-pending-state",
        Number(drafts.pendingCount ?? drafts.actionDrafts?.length ?? 0) > 0
          ? agentPage.state.agent.draftQueue
          : !agentPage.state.agent.draftQueue && !agentPage.state.agent.emptyDraftQueue,
      ),
      check("ui-agent-not-no-data-route-with-real-data", !agentPage.state.agent.noDataRoute),
      check("ui-agent-no-error", !agentPage.state.hasErrorBoundary && !agentPage.state.hasFrameworkOverlay),
    );
    steps.push({ section: "agent", state: agentPage.state });

    const screenshot = await captureScreenshot(browser.client, join(screenshotDir, "ui-flow-agent-ready.png"));
    steps.push({ section: "agent-screenshot", screenshot });
  }
} catch (error) {
  checks.push(check("ui-flow-runtime", false, { error: error instanceof Error ? error.message : String(error) }));
} finally {
  if (browser) {
    browserIssues = browser.client.consoleIssues();
    await browser.close();
  }
}

const receipt = finishReceipt({
  ok: false,
  generatedBy: "scripts/verify-ui-flow.mjs",
  baseUrl,
  apiBaseUrl,
  screenshotDir,
  workspace: status?.workspace,
  counts: status?.counts,
  tables: workbench?.tables?.map((table) => ({ table_key: table.table_key, display_name: table.display_name, row_count: table.row_count })).slice(0, 8),
  dashboards: dashboards?.dashboards?.map((dashboard) => ({ dashboard_key: dashboard.dashboard_key, name: dashboard.name, widgetCount: dashboard.widgets?.length ?? 0 })).slice(0, 8),
  browserIssues,
  steps,
  checks,
});

console.log(JSON.stringify(receipt, null, 2));
process.exit(receipt.ok ? 0 : 1);
