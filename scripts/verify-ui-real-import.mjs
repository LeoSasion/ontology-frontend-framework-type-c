import { existsSync, mkdtempSync } from "node:fs";
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
import {
  apiBaseUrl,
  getActions,
  getDashboards,
  getStatus,
  getWorkbench,
  waitForApi,
  withTemporaryWorkspace,
} from "./ui-verify-workspace.mjs";

const baseUrl = process.env.AIBI_UI_BASE_URL ?? "http://127.0.0.1:8686";
const importFile = process.env.AIBI_REAL_IMPORT_FILE ?? "C:\\Users\\Administrator\\Documents\\财务报表\\真实数据\\源数据-05月\\保单明细-5月.csv";
const importFolder = process.env.AIBI_REAL_IMPORT_FOLDER ?? "C:\\Users\\Administrator\\Documents\\财务报表\\真实数据";
const importTarget = existsSync(importFolder)
  ? { mode: "folder", path: importFolder }
  : { mode: "file", path: importFile };
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-import-"));
const viewport = { key: "desktop", label: "desktop", width: 1280, height: 900 };

function realFlowState() {
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
  const seededSamplePattern = /样例订单|示例订单|demo|test|fallback source|临时看板|mock data|lorem/i;
  const assetPanel = document.querySelector(".assetPanel");
  return {
    title: document.title,
    url: location.href,
    connected: text.includes("数据服务已连接") || text.includes("Data service connected"),
    hasShell: Boolean(document.querySelector(".appShell")),
    hasErrorBoundary,
    errorDetail: document.querySelector(".appFallback pre, .fallbackPanel pre")?.textContent?.trim() || "",
    hasFrameworkOverlay: Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay")),
    hasSeededSampleCopy: seededSamplePattern.test(text),
    layout: {
      assetPanelXOverflow: assetPanel ? Math.max(0, assetPanel.scrollWidth - assetPanel.clientWidth) : 0,
    },
    sources: {
      importInputValue: document.querySelector(".sourceImportPanel input")?.value ?? "",
      importPreviewButton: isVisible("import-preview-button"),
      importPreviewDisabled: disabled("import-preview-button"),
      folderPreviewButton: isVisible("folder-import-preview-button"),
      folderPreviewDisabled: disabled("folder-import-preview-button"),
      folderPlan: isVisible("folder-import-plan"),
      folderConfirm: isVisible("folder-import-confirm-button"),
      folderConfirmDisabled: disabled("folder-import-confirm-button"),
      folderGroupCount: Array.from(document.querySelectorAll(".folderImportGroup")).filter(visible).length,
      importSummary: isVisible("import-confirmation-summary"),
      importConfirm: isVisible("import-confirmation-confirm"),
      importConfirmDisabled: disabled("import-confirmation-confirm"),
      importReceipt: isVisible("import-operation-receipt"),
      importSuccessNextStep: isVisible("import-success-next-step"),
      sourceEntry: isVisible("source-intelligence-folder-entry"),
      sourceResult: isVisible("source-intelligence-result"),
      sourceProgress: isVisible("source-intelligence-progress"),
      sourceError: isVisible("source-intelligence-error"),
      coverageItems: Array.from(document.querySelectorAll('[data-testid="source-coverage-item"]')).filter(visible).length,
      guideDetailsOpen: Boolean(get("source-guide-details")?.open),
      dashboardCreateVisible: isVisible("source-business-dashboard-create"),
      dashboardCreateDisabled: disabled("source-business-dashboard-create"),
      dashboardResult: isVisible("source-business-dashboard-result"),
    },
    dashboards: {
      taskStrip: isVisible("dashboard-business-task-strip"),
      chartPrompt: isVisible("dashboard-ai-chart-prompt"),
      createOneChart: isVisible("dashboard-task-explain"),
      createOneChartDisabled: disabled("dashboard-task-explain"),
      evidenceJump: isVisible("dashboard-task-evidence"),
      betaCollapsed: Boolean(get("dashboard-beta-details")) && !get("dashboard-beta-details").open,
    },
    evidence: {
      businessSummary: isVisible("evidence-business-summary"),
      sourceSummary: isVisible("evidence-source-intelligence-summary"),
      receiptsCollapsed: Boolean(get("evidence-receipts-details")) && !get("evidence-receipts-details").open,
    },
    agent: {
      taskPacketDetails: isVisible("agent-task-packet-details"),
      taskPacket: isVisible("agent-task-packet"),
      draftQueue: isVisible("agent-draft-queue"),
      emptyDraftQueue: isVisible("agent-draft-queue-empty"),
      noDataRoute: isVisible("agent-no-data-route"),
    },
  };
}

async function setNativeValue(client, selector, value) {
  return evaluate(client, ({ selector: targetSelector, value: nextValue }) => {
    const element = document.querySelector(targetSelector);
    if (!element) return { ok: false, error: `missing ${targetSelector}` };
    const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    descriptor?.set?.call(element, nextValue);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, value: element.value };
  }, { selector, value });
}

async function openDetails(client, selector) {
  return evaluate(client, (targetSelector) => {
    const details = document.querySelector(targetSelector);
    if (!details) return { ok: false, error: `missing ${targetSelector}` };
    if (!details.open) {
      const summary = details.querySelector("summary");
      if (summary) summary.click();
      else details.open = true;
    }
    return { ok: Boolean(details.open) };
  }, selector);
}

async function pageState(client) {
  const ready = await waitForAppReady(client, null, 25000);
  const state = await evaluate(client, realFlowState, null, 10000);
  return { ready, state };
}

async function waitForUi(client, label, predicate, timeoutMs = 30000) {
  const state = await waitFor(client, predicate, null, { timeoutMs, intervalMs: 500 });
  if (!state.ok) {
    throw new Error(`${label} did not become ready: ${JSON.stringify(state)}`);
  }
  return state;
}

const checks = [];
const steps = [];
let lifecycle = null;
let browserInfo = null;
let browserIssues = [];
let workspace = null;
let counts = null;
let importedTable = null;
let importedTables = [];
let dashboards = null;
let actions = null;

try {
  checks.push(
    check("real-import-target-exists", existsSync(importTarget.path), { importTarget, importFile, importFolder }),
    check("real-import-folder-or-file-mode", importTarget.mode === "folder" || existsSync(importFile), { importTarget, importFile, importFolder }),
  );
  if (!existsSync(importTarget.path)) {
    throw new Error(`Import target was not found: ${importTarget.path}`);
  }

  const run = await withTemporaryWorkspace("codex_import", async ({ lifecycle: activeLifecycle }) => {
    lifecycle = activeLifecycle;
    let browser = null;
    try {
      browser = await launchChrome();
      browserInfo = { chromePath: browser.chromePath, chromeName: browser.chromeName };
      await setViewport(browser.client, viewport);

      await navigate(browser.client, `${baseUrl}/?section=sources`);
      const importControlsReady = await waitForUi(browser.client, "source import controls", () => {
        const text = document.body?.innerText || "";
        const importInput = document.querySelector(".sourceImportPanel input");
        const importButton = document.querySelector('[data-testid="import-preview-button"]');
        const folderButton = document.querySelector('[data-testid="folder-import-preview-button"]');
        const sourceEntry = document.querySelector('[data-testid="source-intelligence-folder-entry"]');
        const error = document.querySelector(".appFallback, .fallbackPanel, [data-testid='source-intelligence-error']");
        return {
          ok: Boolean(importInput && importButton && folderButton && sourceEntry) && !error,
          hasImportInput: Boolean(importInput),
          hasImportButton: Boolean(importButton),
          hasFolderButton: Boolean(folderButton),
          hasSourceEntry: Boolean(sourceEntry),
          hasError: Boolean(error),
          text: text.slice(0, 700),
        };
      }, 45000);
      checks.push(check("ui-import-controls-mounted", importControlsReady.ok, importControlsReady));
      const sourcesReady = await pageState(browser.client);
      checks.push(
        check("ui-import-sources-ready", sourcesReady.ready.ok, { ready: sourcesReady.ready }),
        check("ui-import-sources-entry-visible", sourcesReady.state.sources.sourceEntry && sourcesReady.state.sources.importPreviewButton && sourcesReady.state.sources.folderPreviewButton, { sources: sourcesReady.state.sources }),
        check("ui-import-sources-no-error-before", !sourcesReady.state.hasErrorBoundary && !sourcesReady.state.hasFrameworkOverlay && !sourcesReady.state.sources.sourceError),
      );
      steps.push({ step: "sources-open", state: sourcesReady.state });

      const setImportPath = await setNativeValue(browser.client, ".sourceImportPanel input", importTarget.path);
      checks.push(check("ui-import-path-filled", setImportPath.ok && setImportPath.value === importTarget.path, setImportPath));

      if (importTarget.mode === "folder") {
        const previewClick = await click(browser.client, '[data-testid="folder-import-preview-button"]');
        checks.push(check("ui-folder-import-preview-click-fired", previewClick.ok, previewClick));
        const previewReady = await waitForUi(browser.client, "folder import preview", () => {
          const text = document.body?.innerText || "";
          const plan = document.querySelector('[data-testid="folder-import-plan"]');
          const groups = Array.from(document.querySelectorAll(".folderImportGroup"));
          const confirm = document.querySelector('[data-testid="folder-import-confirm-button"]');
          const error = document.querySelector(".appFallback, .fallbackPanel, [data-testid='source-intelligence-error']");
          return {
            ok: Boolean(plan && confirm) && groups.length >= 2 && !error,
            hasPlan: Boolean(plan),
            groupCount: groups.length,
            hasConfirm: Boolean(confirm),
            hasError: Boolean(error),
            text: text.slice(0, 700),
          };
        }, 60000);
        checks.push(
          check("ui-folder-import-plan-visible", previewReady.ok, previewReady),
          check("ui-folder-import-groups-readable", Number(previewReady.groupCount ?? 0) >= 2, previewReady),
        );

        const confirmClick = await click(browser.client, '[data-testid="folder-import-confirm-button"]');
        checks.push(check("ui-folder-import-confirm-click-fired", confirmClick.ok, confirmClick));
      } else {
        const previewClick = await click(browser.client, '[data-testid="import-preview-button"]');
        checks.push(check("ui-import-preview-click-fired", previewClick.ok, previewClick));
        const previewReady = await waitForUi(browser.client, "import preview", () => {
          const text = document.body?.innerText || "";
          const summary = document.querySelector('[data-testid="import-confirmation-summary"]');
          const error = document.querySelector(".appFallback, .fallbackPanel, [data-testid='source-intelligence-error']");
          return {
            ok: Boolean(summary) && !error,
            hasSummary: Boolean(summary),
            hasError: Boolean(error),
            text: text.slice(0, 500),
          };
        }, 45000);
        checks.push(check("ui-import-preview-summary-visible", previewReady.ok, previewReady));

        const confirmClick = await click(browser.client, '[data-testid="import-confirmation-confirm"]');
        checks.push(check("ui-import-confirm-click-fired", confirmClick.ok, confirmClick));
      }

      const importStatus = await waitForApi(async () => {
        const status = await getStatus();
        const tableCount = Number(status.counts?.tables ?? 0);
        return { ok: importTarget.mode === "folder" ? tableCount >= 4 : tableCount > 0, status };
      }, { timeoutMs: 45000, intervalMs: 1000, label: "imported table count" });
      workspace = importStatus.status.workspace;
      counts = importStatus.status.counts;
      const workbenchAfterImport = await getWorkbench();
      importedTables = workbenchAfterImport.tables ?? [];
      importedTable = workbenchAfterImport.tables?.[0] ?? null;
      const rowCountsByName = Object.fromEntries(importedTables.map((table) => [table.display_name, table.row_count]));
      checks.push(
        check("api-import-created-table", Number(importStatus.status.counts?.tables ?? 0) > 0, { counts: importStatus.status.counts }),
        check("api-import-workbench-table-readable", Boolean(importedTable?.table_key), { importedTable }),
        check("api-import-table-name-not-numeric", Boolean(importedTable?.display_name) && !/^\d+$/.test(String(importedTable?.display_name ?? "")), { importedTable }),
        check("api-import-table-key-not-numeric", Boolean(importedTable?.table_key) && !/^\d+$/.test(String(importedTable?.table_key ?? "")), { importedTable }),
        check("api-folder-import-real-tables-merged", importTarget.mode !== "folder" || (
          rowCountsByName["保单明细"] === 426 &&
          rowCountsByName["售后单"] === 1393 &&
          rowCountsByName["订单"] === 2351 &&
          rowCountsByName["资金"] === 1376
        ), { importTarget, rowCountsByName, importedTables: importedTables.map((table) => ({ table_key: table.table_key, display_name: table.display_name, row_count: table.row_count })) }),
      );

      await navigate(browser.client, `${baseUrl}/?section=sources`);
      await waitForAppReady(browser.client, null, 25000);
      const afterImportState = await evaluate(browser.client, realFlowState, null, 10000);
      checks.push(
        check("ui-import-success-next-step-visible", afterImportState.sources.importSuccessNextStep, { sources: afterImportState.sources }),
        check("ui-import-receipt-visible", afterImportState.sources.importReceipt || afterImportState.sources.importSuccessNextStep, { sources: afterImportState.sources }),
        check("ui-import-no-error-after-confirm", !afterImportState.hasErrorBoundary && !afterImportState.hasFrameworkOverlay && !afterImportState.sources.sourceError),
        check("ui-import-no-seeded-copy", !afterImportState.hasSeededSampleCopy),
      );
      steps.push({ step: "import-confirmed", state: afterImportState });

      await navigate(browser.client, `${baseUrl}/?section=views`);
      const viewWorkspaceReady = await waitForUi(browser.client, "view workspace styles", () => {
        const workspaceGrid = document.querySelector(".viewWorkspaceGrid");
        const queryPanel = document.querySelector(".viewQueryPanel");
        const agentStrip = document.querySelector('[data-testid="view-agent-task-strip"]');
        const displays = [workspaceGrid, queryPanel, agentStrip].map((element) => element ? getComputedStyle(element).display : "missing");
        return {
          ok: displays.every((display) => display === "grid"),
          displays,
          hasWorkspaceGrid: Boolean(workspaceGrid),
          hasQueryPanel: Boolean(queryPanel),
          hasAgentStrip: Boolean(agentStrip),
        };
      }, 30000);
      checks.push(check("ui-view-workspace-styles-load-with-route", viewWorkspaceReady.ok, viewWorkspaceReady));

      await navigate(browser.client, `${baseUrl}/?section=sources`);
      await waitForAppReady(browser.client, null, 25000);

      const setSourcePath = await setNativeValue(browser.client, '[data-testid="source-intelligence-folder-entry"] textarea', importTarget.path);
      const setSourceLabel = await setNativeValue(browser.client, '[data-testid="source-intelligence-folder-entry"] input', importTarget.mode === "folder" ? "真实文件夹导入回归" : "真实导入回归");
      checks.push(
        check("ui-source-intelligence-path-filled", setSourcePath.ok && setSourcePath.value === importTarget.path, setSourcePath),
        check("ui-source-intelligence-label-filled", setSourceLabel.ok, setSourceLabel),
      );
      const sourceRunClick = await click(browser.client, '[data-testid="source-intelligence-custom-run-button"]');
      checks.push(check("ui-source-intelligence-click-fired", sourceRunClick.ok, sourceRunClick));
      const sourceProfileReady = await waitForUi(browser.client, "source intelligence result", () => {
        const result = document.querySelector('[data-testid="source-intelligence-result"]');
        const progress = document.querySelector('[data-testid="source-intelligence-progress"]');
        const error = document.querySelector('[data-testid="source-intelligence-error"], .appFallback, .fallbackPanel');
        return {
          ok: Boolean(result) && !error,
          hasResult: Boolean(result),
          hasProgress: Boolean(progress),
          hasError: Boolean(error),
          errorText: error?.textContent?.slice(0, 500) ?? "",
        };
      }, 120000);
      checks.push(check("ui-source-intelligence-result-visible", sourceProfileReady.ok, sourceProfileReady));
      const profileStatus = await waitForApi(async () => {
        const status = await getStatus();
        return { ok: Number(status.counts?.sourceIntelligenceRuns ?? 0) > 0, status };
      }, { timeoutMs: 30000, intervalMs: 1000, label: "source intelligence count" });
      counts = profileStatus.status.counts;
      checks.push(check("api-source-intelligence-recorded", Number(counts.sourceIntelligenceRuns ?? 0) > 0, { counts }));

      const sourceExpertDetails = await openDetails(browser.client, '[data-testid="source-expert-details"]');
      checks.push(check("ui-source-advanced-entry-opens", sourceExpertDetails.ok, sourceExpertDetails));
      const sourceAdvancedClick = await click(browser.client, '[data-testid="source-expert-details"] button');
      checks.push(check("ui-source-advanced-workbench-click-fired", sourceAdvancedClick.ok, sourceAdvancedClick));
      const sourceAdvancedReady = await waitForUi(browser.client, "source advanced workbench", () => {
        const navigation = document.querySelector('[data-testid="navigation-action-grid"]');
        const semantics = document.querySelector('[data-testid="field-semantic-readiness"]');
        const connector = document.querySelector('[data-testid="connector-business-lead"]');
        const relationship = document.querySelector('[data-testid="relationship-auto-graph"]');
        const displays = [navigation, semantics, connector, relationship].map((element) => element ? getComputedStyle(element).display : "missing");
        return {
          ok: displays.every((display) => display === "grid"),
          displays,
          hasNavigation: Boolean(navigation),
          hasSemantics: Boolean(semantics),
          hasConnector: Boolean(connector),
          hasRelationship: Boolean(relationship),
        };
      }, 30000);
      checks.push(check("ui-source-advanced-styles-load-on-open", sourceAdvancedReady.ok, sourceAdvancedReady));

      await openDetails(browser.client, '[data-testid="source-guide-details"]');
      const dashboardCreateReady = await waitForUi(browser.client, "source dashboard create", () => {
        const details = document.querySelector('[data-testid="source-guide-details"]');
        if (details && !details.open) details.open = true;
        const button = document.querySelector('[data-testid="source-business-dashboard-create"]');
        const stateText = document.querySelector('[data-testid="source-dashboard-recipe"]')?.textContent ?? "";
        return {
          ok: Boolean(button) && !button.disabled,
          buttonExists: Boolean(button),
          disabled: Boolean(button?.disabled),
          stateText: stateText.slice(0, 600),
        };
      }, 45000);
      checks.push(check("ui-source-dashboard-create-ready", dashboardCreateReady.ok, dashboardCreateReady));
      const createDashboardClick = await click(browser.client, '[data-testid="source-business-dashboard-create"]');
      checks.push(check("ui-source-dashboard-create-click-fired", createDashboardClick.ok, createDashboardClick));
      const dashboardStatus = await waitForApi(async () => {
        const status = await getStatus();
        const nextDashboards = await getDashboards();
        return {
          ok: Number(status.counts?.dashboards ?? 0) > 0 || (nextDashboards.dashboards?.length ?? 0) > 0,
          status,
          dashboards: nextDashboards,
        };
      }, { timeoutMs: 45000, intervalMs: 1000, label: "dashboard count" });
      counts = dashboardStatus.status.counts;
      dashboards = dashboardStatus.dashboards;
      checks.push(check("api-dashboard-created", Number(counts.dashboards ?? 0) > 0 || (dashboards.dashboards?.length ?? 0) > 0, { counts, dashboards: dashboards.dashboards?.length ?? 0 }));

      await navigate(browser.client, `${baseUrl}/?section=dashboards`);
      const dashboardPage = await waitForUi(browser.client, "dashboard single-chart strip", () => {
        const strip = document.querySelector('[data-testid="dashboard-business-task-strip"]');
        const prompt = document.querySelector('[data-testid="dashboard-ai-chart-prompt"]');
        const chartButton = document.querySelector('[data-testid="dashboard-task-explain"]');
        const evidenceButton = document.querySelector('[data-testid="dashboard-task-evidence"]');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        return {
          ok: Boolean(strip && prompt && chartButton && evidenceButton) && !error,
          hasStrip: Boolean(strip),
          hasPrompt: Boolean(prompt),
          hasChartButton: Boolean(chartButton),
          chartDisabled: Boolean(chartButton?.disabled),
          hasEvidenceButton: Boolean(evidenceButton),
          hasError: Boolean(error),
        };
      }, 45000);
      checks.push(check("ui-dashboard-single-chart-strip-visible", dashboardPage.ok, dashboardPage));

      const deferredPanelsBeforeOpen = await evaluate(browser.client, () => ({
        guided: Boolean(document.querySelector('[data-testid="dashboard-beginner-editor"]')),
        advanced: Boolean(document.querySelector('[data-testid="dashboard-advanced-widget-workbench"]')),
        contract: Boolean(document.querySelector('[data-testid="dashboard-contract-boundary-panel"]')),
      }));
      checks.push(check(
        "ui-dashboard-deferred-panels-not-mounted-before-open",
        !deferredPanelsBeforeOpen.guided && !deferredPanelsBeforeOpen.advanced && !deferredPanelsBeforeOpen.contract,
        deferredPanelsBeforeOpen,
      ));

      await openDetails(browser.client, '[data-testid="dashboard-guided-edit-details"]');
      const guidedEditorReady = await waitForUi(browser.client, "guided dashboard editor", () => ({
        ok: Boolean(document.querySelector('[data-testid="dashboard-beginner-editor"]')),
      }), 30000);
      checks.push(check("ui-dashboard-guided-editor-loads-on-open", guidedEditorReady.ok, guidedEditorReady));

      await openDetails(browser.client, '[data-testid="dashboard-advanced-edit-details"]');
      const advancedEditorReady = await waitForUi(browser.client, "advanced dashboard editor", () => ({
        ok: Boolean(document.querySelector('[data-testid="dashboard-advanced-widget-workbench"]')) &&
          Boolean(document.querySelector('[data-testid="dashboard-page-admin-panel"]')),
      }), 30000);
      checks.push(check("ui-dashboard-advanced-editor-loads-on-open", advancedEditorReady.ok, advancedEditorReady));

      await openDetails(browser.client, '[data-testid="dashboard-contract-details"]');
      const contractPanelReady = await waitForUi(browser.client, "dashboard contract panel", () => ({
        ok: Boolean(document.querySelector('[data-testid="dashboard-contract-boundary-panel"]')),
      }), 30000);
      checks.push(check("ui-dashboard-contract-panel-loads-on-open", contractPanelReady.ok, contractPanelReady));

      const dashboardScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "real-import-dashboard.png"));
      steps.push({
        step: "dashboard-ready",
        deferredPanelsBeforeOpen,
        guidedEditorReady,
        advancedEditorReady,
        contractPanelReady,
        screenshot: dashboardScreenshot,
      });

      const chartClick = await click(browser.client, '[data-testid="dashboard-task-explain"]');
      checks.push(check("ui-dashboard-single-chart-click-fired", chartClick.ok, chartClick));
      const chartAgentState = await waitFor(browser.client, () => {
        const taskDetails = document.querySelector('[data-testid="agent-task-packet-details"]');
        const dashboardStrip = document.querySelector('[data-testid="dashboard-business-task-strip"]');
        const chartButton = document.querySelector('[data-testid="dashboard-task-explain"]');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        return {
          ok: Boolean(taskDetails) || (Boolean(dashboardStrip) && !chartButton?.disabled && !error),
          url: location.href,
          hasTaskDetails: Boolean(taskDetails),
          hasDashboardStrip: Boolean(dashboardStrip),
          chartDisabled: Boolean(chartButton?.disabled),
          hasError: Boolean(error),
        };
      }, null, { timeoutMs: 90000, intervalMs: 1000 });
      actions = await getActions(12);
      checks.push(
        check("ui-dashboard-single-chart-agent-returned", chartAgentState.ok, chartAgentState),
        check("api-actions-readable-after-chart-request", Array.isArray(actions.actionDrafts), { pendingCount: actions.pendingCount ?? actions.actionDrafts?.length ?? 0 }),
      );
      steps.push({ step: "single-chart-request", state: chartAgentState, actions: { pendingCount: actions.pendingCount ?? actions.actionDrafts?.length ?? 0 } });

      await navigate(browser.client, `${baseUrl}/?section=dashboards`);
      await waitForAppReady(browser.client, null, 25000);
      const evidenceClick = await click(browser.client, '[data-testid="dashboard-task-evidence"]');
      checks.push(check("ui-dashboard-evidence-click-fired", evidenceClick.ok, evidenceClick));
      const evidenceReady = await waitForUi(browser.client, "evidence summary", () => {
        const business = document.querySelector('[data-testid="evidence-business-summary"]');
        const source = document.querySelector('[data-testid="evidence-source-intelligence-summary"]');
        const receipts = document.querySelector('[data-testid="evidence-receipts-details"]');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        return {
          ok: Boolean(business && source && receipts) && !error,
          url: location.href,
          hasBusiness: Boolean(business),
          hasSource: Boolean(source),
          receiptsCollapsed: Boolean(receipts && !receipts.open),
          hasError: Boolean(error),
        };
      }, 30000);
      checks.push(
        check("ui-evidence-business-summary-visible", evidenceReady.ok && evidenceReady.hasBusiness, evidenceReady),
        check("ui-evidence-source-summary-visible", evidenceReady.ok && evidenceReady.hasSource, evidenceReady),
        check("ui-evidence-receipts-collapsed", evidenceReady.receiptsCollapsed, evidenceReady),
      );
      const evidenceScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "real-import-evidence.png"));
      steps.push({ step: "evidence-ready", screenshot: evidenceScreenshot });

      const finalState = await evaluate(browser.client, realFlowState, null, 10000);
      checks.push(
        check("ui-real-import-no-error-final", !finalState.hasErrorBoundary && !finalState.hasFrameworkOverlay),
        check("ui-real-import-no-seeded-copy-final", !finalState.hasSeededSampleCopy),
        check("ui-real-import-no-asset-panel-x-overflow", finalState.layout.assetPanelXOverflow === 0, finalState.layout),
      );
      steps.push({ step: "final", state: finalState });
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
  checks.push(check("ui-real-import-runtime", false, { error: error instanceof Error ? error.message : String(error) }));
}

const receipt = finishReceipt({
  ok: false,
  generatedBy: "scripts/verify-ui-real-import.mjs",
  baseUrl,
  apiBaseUrl,
  importFile,
  importFolder,
  importTarget,
  viewport,
  screenshotDir,
  browser: browserInfo,
  browserIssues,
  workspace,
  counts,
  importedTable,
  importedTables: importedTables.map((table) => ({ table_key: table.table_key, display_name: table.display_name, row_count: table.row_count })).slice(0, 8),
  dashboards: dashboards?.dashboards?.map((dashboard) => ({ dashboard_key: dashboard.dashboard_key, name: dashboard.name, widgetCount: dashboard.widgets?.length ?? 0 })).slice(0, 6),
  actions: actions ? { pendingCount: actions.pendingCount ?? actions.actionDrafts?.length ?? 0 } : null,
  lifecycle,
  steps: steps.map((step) => ({
    step: step.step,
    screenshot: step.screenshot,
    state: step.state ? {
      url: step.state.url,
      connected: step.state.connected,
      hasSeededSampleCopy: step.state.hasSeededSampleCopy,
      sources: step.state.sources,
      dashboards: step.state.dashboards,
      evidence: step.state.evidence,
      agent: step.state.agent,
    } : undefined,
    actions: step.actions,
  })),
  checks,
});

console.log(JSON.stringify(receipt, null, 2));
process.exit(receipt.ok ? 0 : 1);
