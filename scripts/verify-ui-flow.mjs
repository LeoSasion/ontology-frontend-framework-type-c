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
  waitForAppReady,
} from "./ui-verify-chrome.mjs";

const baseUrl = process.env.AIBI_UI_BASE_URL ?? "http://127.0.0.1:8686";
const apiBaseUrl = process.env.AIBI_API_BASE_URL ?? "http://127.0.0.1:8787";
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-flow-"));
const viewport = { key: "desktop", label: "desktop", width: 1280, height: 900 };

async function fetchJson(path) {
  const response = await fetch(`${apiBaseUrl}${path}`);
  const payload = await response.json();
  if (!response.ok || payload?.ok === false) {
    throw new Error(`${path}: ${payload?.error ?? `${response.status} ${response.statusText}`}`);
  }
  return payload;
}

function assertPageState() {
  const text = document.body?.innerText || "";
  const get = (testId) => document.querySelector(`[data-testid="${testId}"]`);
  const disabled = (testId) => Boolean(get(testId)?.disabled);
  const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复");
  return {
    title: document.title,
    url: location.href,
    connected: text.includes("数据服务已连接") || text.includes("Data service connected"),
    hasErrorBoundary,
    errorDetail: document.querySelector(".appFallback pre, .fallbackPanel pre")?.textContent?.trim() || "",
    hasFrameworkOverlay: Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay")),
    noSampleCopy: !/样例|示例|demo data|test data|fallback source|mock data|lorem/i.test(text),
    home: {
      actionDock: Boolean(get("home-action-dock")),
      importAction: Boolean(get("home-action-import")),
      chartActionEnabled: Boolean(get("home-action-cost-monitor")) && !disabled("home-action-cost-monitor"),
    },
    sources: {
      entry: Boolean(get("source-intelligence-folder-entry")),
      coverageItems: document.querySelectorAll('[data-testid="source-coverage-item"]').length,
      dashboardNextAction: Boolean(get("source-dashboard-next-action")),
      sourceError: Boolean(get("source-intelligence-error")),
    },
    dashboards: {
      taskStrip: Boolean(get("dashboard-business-task-strip")),
      chartPrompt: Boolean(get("dashboard-ai-chart-prompt")),
      createOneChart: Boolean(get("dashboard-task-explain")),
      evidenceJump: Boolean(get("dashboard-task-evidence")),
      betaCollapsed: Boolean(get("dashboard-beta-details")) && !get("dashboard-beta-details").open,
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
  const ready = await waitForAppReady(client, testId, 25000);
  const state = await evaluate(client, assertPageState, null, 10000);
  return { ready, state };
}

async function waitForSection(client, section, testId) {
  await navigate(client, `${baseUrl}/?section=${section}`);
  return readCurrentSection(client, testId);
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
  const hasDashboard = Number(counts.dashboards ?? 0) > 0 || dashboards.dashboards?.length > 0;
  checks.push(
    check("api-live-status", status.ok === true && Boolean(status.database), { workspace: status.workspace, counts }),
    check("api-workspace-data-state-supported", hasData || Number(counts.tables ?? 0) === 0, { mode: hasData ? "data" : "empty", tables: counts.tables }),
    check("api-source-intelligence-state-supported", hasData ? hasSourceIntelligence : Number(counts.sourceIntelligenceRuns ?? 0) === 0, { mode: hasData ? "data" : "empty", sourceIntelligenceRuns: counts.sourceIntelligenceRuns }),
    check("api-dashboard-state-supported", hasData ? hasDashboard : Number(counts.dashboards ?? 0) === 0, { mode: hasData ? "data" : "empty", dashboards: counts.dashboards ?? dashboards.dashboards?.length }),
    check("api-action-drafts-readable", Array.isArray(drafts.actionDrafts), { pendingCount: drafts.pendingCount ?? drafts.actionDrafts?.length ?? 0 }),
  );

  browser = await launchChrome();
  await setViewport(browser.client, viewport);

  if (!hasData) {
    const sourcesPage = await waitForSection(browser.client, "sources", "source-intelligence-folder-entry");
    checks.push(
      check("ui-empty-sources-ready", sourcesPage.ready.ok, { ready: sourcesPage.ready }),
      check("ui-empty-sources-import-entry-visible", sourcesPage.state.sources.entry),
      check("ui-empty-sources-no-inline-source-error", !sourcesPage.state.sources.sourceError),
      check("ui-empty-sources-no-error", !sourcesPage.state.hasErrorBoundary && !sourcesPage.state.hasFrameworkOverlay),
      check("ui-empty-sources-no-sample-copy", sourcesPage.state.noSampleCopy),
    );
    steps.push({ section: "empty-sources", state: sourcesPage.state });

    const dashboardLocked = await waitForSection(browser.client, "dashboards", "source-intelligence-folder-entry");
    checks.push(
      check("ui-empty-dashboard-routes-to-import", dashboardLocked.ready.ok && dashboardLocked.state.sources.entry, { ready: dashboardLocked.ready, url: dashboardLocked.state.url }),
      check("ui-empty-dashboard-no-error", !dashboardLocked.state.hasErrorBoundary && !dashboardLocked.state.hasFrameworkOverlay),
    );
    steps.push({ section: "empty-dashboard-locked", state: dashboardLocked.state });

    const evidenceLocked = await waitForSection(browser.client, "evidence", "source-intelligence-folder-entry");
    checks.push(
      check("ui-empty-evidence-routes-to-import", evidenceLocked.ready.ok && evidenceLocked.state.sources.entry, { ready: evidenceLocked.ready, url: evidenceLocked.state.url }),
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
    const home = await waitForSection(browser.client, "home", "home-action-dock");
    checks.push(
      check("ui-home-ready", home.ready.ok, { ready: home.ready }),
      check("ui-home-primary-import-visible", home.state.home.importAction),
      check("ui-home-chart-action-enabled-with-data", home.state.home.chartActionEnabled),
      check("ui-home-no-error", !home.state.hasErrorBoundary && !home.state.hasFrameworkOverlay),
      check("ui-home-no-sample-copy", home.state.noSampleCopy),
    );
    steps.push({ section: "home", state: home.state });

    const dashboardClick = await click(browser.client, '[data-testid="home-action-cost-monitor"]');
    checks.push(check("ui-home-dashboard-click-fired", dashboardClick.ok, dashboardClick));
    const dashboardAfterClick = await waitFor(browser.client, () => {
      const text = document.body?.innerText || "";
      return {
        ok: location.search.includes("section=dashboards") && Boolean(document.querySelector('[data-testid="dashboard-business-task-strip"]')),
        url: location.href,
        connected: text.includes("数据服务已连接"),
      };
    }, null, { timeoutMs: 12000, intervalMs: 250 });
    checks.push(check("ui-home-to-dashboard-jump", dashboardAfterClick.ok, { state: dashboardAfterClick }));

    const dashboardsPage = dashboardAfterClick.ok
      ? await readCurrentSection(browser.client, "dashboard-business-task-strip")
      : await waitForSection(browser.client, "dashboards", "dashboard-business-task-strip");
    checks.push(
      check("ui-dashboard-ready", dashboardsPage.ready.ok, { ready: dashboardsPage.ready }),
      check("ui-dashboard-single-chart-prompt-visible", dashboardsPage.state.dashboards.chartPrompt && dashboardsPage.state.dashboards.createOneChart),
      check("ui-dashboard-evidence-jump-visible", dashboardsPage.state.dashboards.evidenceJump),
      check("ui-dashboard-beta-secondary-collapsed", dashboardsPage.state.dashboards.betaCollapsed),
      check("ui-dashboard-no-error", !dashboardsPage.state.hasErrorBoundary && !dashboardsPage.state.hasFrameworkOverlay),
      check("ui-dashboard-no-sample-copy", dashboardsPage.state.noSampleCopy),
    );
    steps.push({ section: "dashboards", state: dashboardsPage.state });

    const evidenceClick = await click(browser.client, '[data-testid="dashboard-task-evidence"]');
    checks.push(check("ui-dashboard-evidence-click-fired", evidenceClick.ok, evidenceClick));
    const evidenceAfterClick = await waitFor(browser.client, () => ({
      ok: location.search.includes("section=evidence") && Boolean(document.querySelector('[data-testid="evidence-business-summary"]')),
      url: location.href,
    }), null, { timeoutMs: 12000, intervalMs: 250 });
    checks.push(check("ui-dashboard-to-evidence-jump", evidenceAfterClick.ok, { state: evidenceAfterClick }));

    const evidencePage = evidenceAfterClick.ok
      ? await readCurrentSection(browser.client, "evidence-business-summary")
      : await waitForSection(browser.client, "evidence", "evidence-business-summary");
    checks.push(
      check("ui-evidence-ready", evidencePage.ready.ok, { ready: evidencePage.ready }),
      check("ui-evidence-business-summary-visible", evidencePage.state.evidence.businessSummary),
      check("ui-evidence-source-summary-visible", evidencePage.state.evidence.sourceSummary),
      check("ui-evidence-raw-receipts-collapsed", evidencePage.state.evidence.receiptsCollapsed),
      check("ui-evidence-no-error", !evidencePage.state.hasErrorBoundary && !evidencePage.state.hasFrameworkOverlay),
      check("ui-evidence-no-sample-copy", evidencePage.state.noSampleCopy),
    );
    steps.push({ section: "evidence", state: evidencePage.state });

    const sourcesPage = await waitForSection(browser.client, "sources", "source-intelligence-folder-entry");
    checks.push(
      check("ui-sources-ready", sourcesPage.ready.ok, { ready: sourcesPage.ready }),
      check("ui-sources-evidence-entry-visible", sourcesPage.state.sources.entry),
      check("ui-sources-real-coverage-listed", sourcesPage.state.sources.coverageItems > 0, { coverageItems: sourcesPage.state.sources.coverageItems }),
      check("ui-sources-dashboard-next-action-visible", sourcesPage.state.sources.dashboardNextAction),
      check("ui-sources-no-inline-source-error", !sourcesPage.state.sources.sourceError),
      check("ui-sources-no-error", !sourcesPage.state.hasErrorBoundary && !sourcesPage.state.hasFrameworkOverlay),
    );
    steps.push({ section: "sources", state: sourcesPage.state });

    const agentPage = await waitForSection(browser.client, "agent", "agent-task-packet");
    checks.push(
      check("ui-agent-ready", agentPage.ready.ok, { ready: agentPage.ready }),
      check("ui-agent-task-packet-visible", agentPage.state.agent.taskPacket),
      check("ui-agent-draft-boundary-visible", agentPage.state.agent.draftQueue || agentPage.state.agent.emptyDraftQueue),
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
