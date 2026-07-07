import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  captureScreenshot,
  check,
  evaluate,
  finishReceipt,
  launchChrome,
  navigate,
  setViewport,
  waitForAppReady,
} from "./ui-verify-chrome.mjs";
import {
  apiBaseUrl,
  getActions,
  getDashboards,
  getStatus,
  getWorkbench,
  withTemporaryWorkspace,
  zeroCounts,
} from "./ui-verify-workspace.mjs";

const baseUrl = process.env.AIBI_UI_BASE_URL ?? "http://127.0.0.1:8686";
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-empty-"));
const viewport = { key: "desktop", label: "desktop", width: 1280, height: 900 };

function emptyWorkspaceState() {
  const text = document.body?.innerText || "";
  const insideClosedDetails = (element) => {
    const details = element.closest("details");
    return Boolean(details && !details.open && element !== details.querySelector("summary") && !element.closest("summary"));
  };
  const visible = (element) => {
    if (!element || insideClosedDetails(element)) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity || "1") > 0.01 &&
      rect.width > 1 &&
      rect.height > 1;
  };
  const get = (testId) => document.querySelector(`[data-testid="${testId}"]`);
  const isVisible = (testId) => visible(get(testId));
  const disabled = (testId) => Boolean(get(testId)?.disabled);
  const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复");
  const seededSamplePattern = /样例订单|示例订单|demo|test|fallback source|临时看板|mock data|lorem|orders|refunds/i;
  return {
    title: document.title,
    url: location.href,
    textSample: text.slice(0, 1000),
    connected: text.includes("数据服务已连接") || text.includes("Data service connected"),
    hasShell: Boolean(document.querySelector(".appShell")),
    hasErrorBoundary,
    hasFrameworkOverlay: Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay")),
    hasSeededSampleCopy: seededSamplePattern.test(text),
    importGuidanceText: /导入|接入数据|检查文件|本地文件|还没有可分析的数据表|暂无证据|先接入数据/.test(text),
    home: {
      actionDock: isVisible("home-action-dock"),
      importAction: isVisible("home-action-import"),
      chartActionVisible: isVisible("home-action-cost-monitor"),
      chartActionDisabled: disabled("home-action-cost-monitor"),
    },
    sources: {
      importEntry: isVisible("source-intelligence-folder-entry"),
      importPreviewButton: isVisible("import-preview-button"),
      coverageItems: Array.from(document.querySelectorAll('[data-testid="source-coverage-item"]')).filter(visible).length,
      dashboardNextVisible: isVisible("source-dashboard-next-action"),
      guideDetailsOpen: Boolean(get("source-guide-details")?.open),
      sourceError: isVisible("source-intelligence-error"),
    },
    dashboards: {
      taskStripVisible: isVisible("dashboard-business-task-strip"),
      widgetCards: Array.from(document.querySelectorAll(".dashboardWidgetCard, .dashboardCanvasWidget")).filter(visible).length,
    },
    evidence: {
      businessSummaryVisible: isVisible("evidence-business-summary"),
      receiptsVisible: isVisible("evidence-receipts-details"),
    },
    agent: {
      noDataRoute: isVisible("agent-no-data-route"),
      taskPacketVisible: isVisible("agent-task-packet"),
      draftQueueVisible: isVisible("agent-draft-queue"),
    },
  };
}

async function openSection(client, section) {
  await navigate(client, `${baseUrl}/?section=${section}`);
  const ready = await waitForAppReady(client, null, 25000);
  const state = await evaluate(client, emptyWorkspaceState, null, 10000);
  return { section, ready, state };
}

const checks = [];
const steps = [];
let lifecycle = null;
let browserInfo = null;
let browserIssues = [];
let workspace = null;
let counts = null;

try {
  const run = await withTemporaryWorkspace("codex_empty", async ({ lifecycle: activeLifecycle }) => {
    lifecycle = activeLifecycle;
    const status = await getStatus();
    const workbench = await getWorkbench();
    const dashboards = await getDashboards();
    const actions = await getActions(12);
    workspace = status.workspace;
    counts = status.counts;

    checks.push(
      check("api-temporary-workspace-active", status.workspace?.id === activeLifecycle.temporaryWorkspace.id, { workspace: status.workspace }),
      check("api-empty-counts", zeroCounts(status.counts), { counts: status.counts }),
      check("api-empty-workbench", (workbench.tables?.length ?? 0) === 0 && (workbench.sourceIntelligenceRuns?.length ?? 0) === 0, {
        tables: workbench.tables?.length ?? 0,
        sourceIntelligenceRuns: workbench.sourceIntelligenceRuns?.length ?? 0,
      }),
      check("api-empty-dashboards", (dashboards.dashboards?.length ?? 0) === 0, { dashboards: dashboards.dashboards?.length ?? 0 }),
      check("api-empty-actions", (actions.actionDrafts?.length ?? 0) === 0, { actionDrafts: actions.actionDrafts?.length ?? 0 }),
    );

    let browser = null;
    try {
      browser = await launchChrome();
      browserInfo = { chromePath: browser.chromePath, chromeName: browser.chromeName };
      await setViewport(browser.client, viewport);

      const home = await openSection(browser.client, "home");
      checks.push(
        check("ui-empty-home-ready", home.ready.ok, { ready: home.ready }),
        check("ui-empty-home-guides-to-import", home.state.home.importAction || home.state.importGuidanceText, { home: home.state.home, importGuidanceText: home.state.importGuidanceText }),
        check("ui-empty-home-chart-not-active", !home.state.home.chartActionVisible || home.state.home.chartActionDisabled, { home: home.state.home }),
        check("ui-empty-home-no-error", !home.state.hasErrorBoundary && !home.state.hasFrameworkOverlay),
        check("ui-empty-home-no-seeded-copy", !home.state.hasSeededSampleCopy),
      );
      steps.push(home);

      const sources = await openSection(browser.client, "sources");
      checks.push(
        check("ui-empty-sources-ready", sources.ready.ok, { ready: sources.ready }),
        check("ui-empty-sources-import-entry-visible", sources.state.sources.importEntry && sources.state.sources.importPreviewButton),
        check("ui-empty-sources-no-coverage-list", sources.state.sources.coverageItems === 0, { sources: sources.state.sources }),
        check("ui-empty-sources-next-action-collapsed", !sources.state.sources.dashboardNextVisible && !sources.state.sources.guideDetailsOpen, { sources: sources.state.sources }),
        check("ui-empty-sources-no-error", !sources.state.hasErrorBoundary && !sources.state.hasFrameworkOverlay && !sources.state.sources.sourceError),
        check("ui-empty-sources-no-seeded-copy", !sources.state.hasSeededSampleCopy),
      );
      steps.push(sources);

      const dashboardsPage = await openSection(browser.client, "dashboards");
      checks.push(
        check("ui-empty-dashboards-ready", dashboardsPage.ready.ok, { ready: dashboardsPage.ready }),
        check("ui-empty-dashboards-route-guides-to-data", dashboardsPage.state.sources.importEntry || dashboardsPage.state.importGuidanceText, { state: dashboardsPage.state }),
        check("ui-empty-dashboards-no-chart-workbench", !dashboardsPage.state.dashboards.taskStripVisible && dashboardsPage.state.dashboards.widgetCards === 0, { dashboards: dashboardsPage.state.dashboards }),
        check("ui-empty-dashboards-no-error", !dashboardsPage.state.hasErrorBoundary && !dashboardsPage.state.hasFrameworkOverlay),
        check("ui-empty-dashboards-no-seeded-copy", !dashboardsPage.state.hasSeededSampleCopy),
      );
      steps.push(dashboardsPage);

      const evidencePage = await openSection(browser.client, "evidence");
      checks.push(
        check("ui-empty-evidence-ready", evidencePage.ready.ok, { ready: evidencePage.ready }),
        check("ui-empty-evidence-route-guides-to-data", evidencePage.state.sources.importEntry || evidencePage.state.importGuidanceText, { state: evidencePage.state }),
        check("ui-empty-evidence-no-proof-panels", !evidencePage.state.evidence.businessSummaryVisible, { evidence: evidencePage.state.evidence }),
        check("ui-empty-evidence-no-error", !evidencePage.state.hasErrorBoundary && !evidencePage.state.hasFrameworkOverlay),
        check("ui-empty-evidence-no-seeded-copy", !evidencePage.state.hasSeededSampleCopy),
      );
      steps.push(evidencePage);

      const agent = await openSection(browser.client, "agent");
      checks.push(
        check("ui-empty-agent-ready", agent.ready.ok, { ready: agent.ready }),
        check("ui-empty-agent-no-data-route-visible", agent.state.agent.noDataRoute || agent.state.importGuidanceText, { agent: agent.state.agent }),
        check("ui-empty-agent-no-analysis-task-packet", !agent.state.agent.taskPacketVisible, { agent: agent.state.agent }),
        check("ui-empty-agent-no-error", !agent.state.hasErrorBoundary && !agent.state.hasFrameworkOverlay),
        check("ui-empty-agent-no-seeded-copy", !agent.state.hasSeededSampleCopy),
      );
      steps.push(agent);

      const homeScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "empty-home.png"));
      steps.push({ section: "home-screenshot", screenshot: homeScreenshot });
      await navigate(browser.client, `${baseUrl}/?section=sources`);
      await waitForAppReady(browser.client, null, 25000);
      const sourcesScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "empty-sources.png"));
      steps.push({ section: "sources-screenshot", screenshot: sourcesScreenshot });
    } finally {
      if (browser) {
        browserIssues = browser.client.consoleIssues();
        await browser.close();
      }
    }

    return {};
  });
  lifecycle = run.lifecycle;
} catch (error) {
  lifecycle = error?.lifecycle ?? lifecycle;
  checks.push(check("ui-empty-workspace-runtime", false, { error: error instanceof Error ? error.message : String(error) }));
}

const receipt = finishReceipt({
  ok: false,
  generatedBy: "scripts/verify-ui-empty-workspace.mjs",
  baseUrl,
  apiBaseUrl,
  viewport,
  screenshotDir,
  browser: browserInfo,
  browserIssues,
  workspace,
  counts,
  lifecycle,
  steps: steps.map((step) => ({
    section: step.section,
    ready: step.ready,
    state: step.state ? {
      url: step.state.url,
      connected: step.state.connected,
      importGuidanceText: step.state.importGuidanceText,
      hasSeededSampleCopy: step.state.hasSeededSampleCopy,
      home: step.state.home,
      sources: step.state.sources,
      dashboards: step.state.dashboards,
      evidence: step.state.evidence,
      agent: step.state.agent,
    } : undefined,
    screenshot: step.screenshot,
  })),
  checks,
});

console.log(JSON.stringify(receipt, null, 2));
process.exit(receipt.ok ? 0 : 1);
