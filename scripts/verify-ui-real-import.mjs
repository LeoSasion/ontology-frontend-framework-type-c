import { existsSync, mkdtempSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
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

const baseUrl = process.env.AIBI_UI_BASE_URL ?? apiBaseUrl;
const knownRealDataFolders = [
  "C:\\Users\\Administrator\\Documents\\财务报表\\真实数据",
  "C:\\Users\\Administrator\\Documents\\财务报表_bak\\真实数据",
];
const fallbackFolder = knownRealDataFolders.find((folder) => existsSync(folder)) ?? knownRealDataFolders[0];
const configuredPath = process.env.AIBI_REAL_IMPORT_PATH ?? process.env.AIBI_REAL_IMPORT_FILE ?? process.env.AIBI_REAL_IMPORT_FOLDER ?? fallbackFolder;
const configuredMode = process.env.AIBI_REAL_IMPORT_MODE;
const detectedMode = existsSync(configuredPath) && statSync(configuredPath).isDirectory() ? "folder" : "file";
const importTarget = { mode: configuredMode === "folder" || configuredMode === "file" ? configuredMode : detectedMode, path: configuredPath };
const importFolder = importTarget.mode === "folder" ? importTarget.path : dirname(importTarget.path);
const importFile = importTarget.mode === "file" ? importTarget.path : join(importFolder, "源数据-05月", "保单明细-5月.csv");
const datasetLabel = process.env.AIBI_REAL_IMPORT_LABEL ?? basename(importTarget.path).replace(/\.[^.]+$/, "") ?? "真实数据";
const datasetDomain = process.env.AIBI_REAL_IMPORT_DOMAIN ?? (knownRealDataFolders.some((folder) => resolve(folder) === resolve(importTarget.path)) ? "financial-commerce" : "unspecified-real-domain");
const minimumFolderGroups = Math.max(1, Number(process.env.AIBI_REAL_IMPORT_MIN_GROUPS ?? 1));
const knownFinancialBaseline = importTarget.mode === "folder" && knownRealDataFolders.some((folder) => resolve(folder) === resolve(importTarget.path));
const nonProductionPathPattern = /[\\/](fixtures|testdata|validation-inputs)[\\/]/i;
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-import-"));
const viewport = { key: "desktop", label: "desktop", width: 1280, height: 900 };
const evidenceViewports = [
  { key: "compact-landscape", width: 1280, height: 720 },
  { key: "landscape", width: 1440, height: 900 },
  { key: "portrait-pc", width: 900, height: 1440 },
  { key: "square", width: 1100, height: 1100 },
];

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
      evidenceJump: Boolean(get("dashboard-more-evidence") || get("dashboard-task-evidence")),
      secondaryCollapsed: Boolean(get("dashboard-more-details")) && !get("dashboard-more-details").open,
    },
    evidence: {
      businessSummary: isVisible("evidence-business-summary"),
      sourceSummary: isVisible("evidence-source-intelligence-summary"),
      receiptsCollapsed: Boolean(get("evidence-receipts-details")) && !get("evidence-receipts-details").open,
      trustActions: isVisible("evidence-trust-actions"),
    },
    agent: {
      taskPacketDetails: isVisible("agent-task-packet-details"),
      taskPacket: isVisible("agent-task-packet"),
      draftQueue: isVisible("agent-draft-queue"),
      emptyDraftQueue: isVisible("agent-draft-queue-empty"),
      noDataRoute: isVisible("agent-no-data-route"),
      trustAnalysisCollapsed: Boolean(get("agent-trust-analysis-details")) && !get("agent-trust-analysis-details").open,
    },
    settings: {
      trustContextCollapsed: Boolean(get("settings-trust-context-details")) && !get("settings-trust-context-details").open,
      trustContextVisible: isVisible("trust-context-settings"),
    },
  };
}

async function setNativeValue(client, selector, value) {
  return evaluate(client, ({ targetSelector, nextValue }) => {
    const element = document.querySelector(targetSelector);
    if (!element) return { ok: false, error: `missing ${targetSelector}` };
    const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    descriptor?.set?.call(element, nextValue);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, value: element.value };
  }, { targetSelector: selector, nextValue: value });
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

async function navigateUntil(client, targetUrl, label, predicate, timeoutMs = 30000) {
  let state = null;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const separator = targetUrl.includes("?") ? "&" : "?";
    const retryUrl = attempt ? `${targetUrl}${separator}retry=${Date.now()}-${attempt}` : targetUrl;
    await navigate(client, retryUrl);
    state = await waitFor(client, predicate, null, { timeoutMs, intervalMs: 500 });
    if (state.ok) return state;
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 500 * (attempt + 1)));
  }
  throw new Error(`${label} did not become ready: ${JSON.stringify(state)}`);
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
    check("real-import-uses-production-data", !nonProductionPathPattern.test(importTarget.path), { importTarget, datasetDomain }),
    check("real-import-domain-declared", datasetDomain !== "unspecified-real-domain", { datasetDomain, datasetLabel }),
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

      const waitForImportControls = () => waitFor(browser.client, () => {
        const text = document.body?.innerText || "";
        const importInput = document.querySelector(".sourceImportPanel input");
        const importButton = document.querySelector('[data-testid="import-preview-button"]');
        const folderButton = document.querySelector('[data-testid="folder-import-preview-button"]');
        const sourceEntry = document.querySelector('[data-testid="source-intelligence-folder-entry"]');
        const error = document.querySelector(".appFallback, .fallbackPanel, [data-testid='source-intelligence-error']");
        return {
          ok: Boolean(importInput && importButton && folderButton) && !sourceEntry && !error,
          hasImportInput: Boolean(importInput),
          hasImportButton: Boolean(importButton),
          hasFolderButton: Boolean(folderButton),
          hasSourceEntry: Boolean(sourceEntry),
          hasError: Boolean(error),
          text: text.slice(0, 700),
        };
      }, null, { timeoutMs: 45000, intervalMs: 500 });
      let importControlsReady = null;
      for (let attempt = 0; attempt < 4; attempt += 1) {
        const retry = attempt ? `&retry=${Date.now()}-${attempt}` : "";
        await navigate(browser.client, `${baseUrl}/?section=sources${retry}`);
        importControlsReady = await waitForImportControls();
        if (importControlsReady.ok) break;
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 250 * (attempt + 1)));
      }
      if (!importControlsReady?.ok) {
        throw new Error(`source import controls did not become ready: ${JSON.stringify(importControlsReady)}`);
      }
      checks.push(check("ui-import-controls-mounted", importControlsReady.ok, importControlsReady));
      const sourcesReady = await pageState(browser.client);
      checks.push(
        check("ui-import-sources-ready", sourcesReady.ready.ok, { ready: sourcesReady.ready }),
        check("ui-import-sources-import-only", !sourcesReady.state.sources.sourceEntry && sourcesReady.state.sources.importPreviewButton && sourcesReady.state.sources.folderPreviewButton, { sources: sourcesReady.state.sources }),
        check("ui-import-sources-no-error-before", !sourcesReady.state.hasErrorBoundary && !sourcesReady.state.hasFrameworkOverlay && !sourcesReady.state.sources.sourceError),
      );
      steps.push({ step: "sources-open", state: sourcesReady.state });

      const setImportPath = await setNativeValue(browser.client, ".sourceImportPanel input", importTarget.path);
      checks.push(check("ui-import-path-filled", setImportPath.ok && setImportPath.value === importTarget.path, setImportPath));
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));

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
            ok: Boolean(plan && confirm) && groups.length > 0 && !error,
            hasPlan: Boolean(plan),
            groupCount: groups.length,
            hasConfirm: Boolean(confirm),
            hasError: Boolean(error),
            text: text.slice(0, 700),
          };
        }, 60000);
        checks.push(
          check("ui-folder-import-plan-visible", previewReady.ok, previewReady),
          check("ui-folder-import-groups-readable", Number(previewReady.groupCount ?? 0) >= minimumFolderGroups, { ...previewReady, minimumFolderGroups }),
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
        return { ok: tableCount > 0, status };
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
        check("api-known-financial-folder-deduplicated", !knownFinancialBaseline || (
          rowCountsByName["保单明细"] === 426 &&
          rowCountsByName["售后单"] === 1393 &&
          rowCountsByName["订单"] === 2351 &&
          rowCountsByName["资金"] === 1376
        ), { importTarget, rowCountsByName, importedTables: importedTables.map((table) => ({ table_key: table.table_key, display_name: table.display_name, row_count: table.row_count })) }),
      );

      let importResultReady = null;
      for (let attempt = 0; attempt < 4; attempt += 1) {
        const retry = attempt ? `&retry=${Date.now()}-${attempt}` : "";
        await navigate(browser.client, `${baseUrl}/?section=sources${retry}`);
        importResultReady = await waitFor(browser.client, () => {
          const result = document.querySelector('[data-testid="import-success-next-step"]');
          const error = document.querySelector(".appFallback, .fallbackPanel, vite-error-overlay, .vite-error-overlay");
          return { ok: Boolean(result) && !error, hasResult: Boolean(result), hasError: Boolean(error) };
        }, null, { timeoutMs: 30000, intervalMs: 500 });
        if (importResultReady.ok) break;
        await new Promise((resolveDelay) => setTimeout(resolveDelay, 500 * (attempt + 1)));
      }
      const afterImportState = await evaluate(browser.client, realFlowState, null, 10000);
      const importNextStepText = await evaluate(browser.client, () => document.querySelector('[data-testid="import-success-next-step"]')?.textContent ?? "", null, 10000);
      const expectedConnectedRows = importedTables.reduce((total, table) => total + Number(table.row_count ?? 0), 0);
      const expectedConnectedFields = importedTables.reduce((total, table) => total + Number(table.column_count ?? 0), 0);
      checks.push(
        check("ui-import-result-page-ready", Boolean(importResultReady?.ok), importResultReady),
        check("ui-import-success-next-step-visible", afterImportState.sources.importSuccessNextStep, { sources: afterImportState.sources }),
        check("ui-import-next-step-receipt-visible", afterImportState.sources.importReceipt || afterImportState.sources.importSuccessNextStep, { sources: afterImportState.sources }),
        check("ui-import-next-step-uses-workspace-totals", importNextStepText.includes(expectedConnectedRows.toLocaleString()) && importNextStepText.includes(expectedConnectedFields.toLocaleString()), { importNextStepText, expectedConnectedRows, expectedConnectedFields }),
        check("ui-import-no-error-after-confirm", !afterImportState.hasErrorBoundary && !afterImportState.hasFrameworkOverlay && !afterImportState.sources.sourceError),
        check("ui-import-no-seeded-copy", !afterImportState.hasSeededSampleCopy),
      );
      steps.push({ step: "import-confirmed", state: afterImportState });

      for (const viewViewport of evidenceViewports) {
        await setViewport(browser.client, viewViewport);
        const viewWorkspaceReady = await navigateUntil(browser.client, `${baseUrl}/?section=views`, `view empty state ${viewViewport.key}`, () => {
          const emptyState = document.querySelector('[data-testid="view-empty-state"]');
          const aiDraft = document.querySelector('[data-testid="view-empty-ai-draft"]');
          const workspaceGrid = document.querySelector(".viewWorkspaceGrid");
          const queryPanel = document.querySelector(".viewQueryPanel");
          const rect = emptyState?.getBoundingClientRect();
          return {
            ok: Boolean(emptyState && aiDraft && rect && rect.width > 280 && rect.right <= window.innerWidth && !workspaceGrid && !queryPanel),
            emptyRect: rect ? { left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width) } : null,
            viewport: { width: window.innerWidth, height: window.innerHeight },
            hasWorkspaceGrid: Boolean(workspaceGrid),
            hasQueryPanel: Boolean(queryPanel),
            hasAiDraft: Boolean(aiDraft),
            documentOverflowX: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
          };
        }, 30000);
        const screenshot = await captureScreenshot(browser.client, join(screenshotDir, `real-import-views-${viewViewport.key}.png`));
        checks.push(
          check(`ui-view-empty-${viewViewport.key}-responsive`, viewWorkspaceReady.ok, viewWorkspaceReady),
          check(`ui-view-empty-${viewViewport.key}-no-x-overflow`, viewWorkspaceReady.documentOverflowX === 0, viewWorkspaceReady),
        );
        steps.push({ step: `views-empty-${viewViewport.key}`, viewport: viewViewport, state: viewWorkspaceReady, screenshot });
      }
      await setViewport(browser.client, viewport);

      await navigateUntil(browser.client, `${baseUrl}/?section=sources`, "source profile recovery", () => {
        const shell = document.querySelector(".appShell");
        const error = document.querySelector(".appFallback, .fallbackPanel, vite-error-overlay, .vite-error-overlay");
        return { ok: Boolean(shell) && !error, hasShell: Boolean(shell), hasError: Boolean(error) };
      });
      const profileStatus = await waitForApi(async () => {
        const status = await getStatus();
        return { ok: Number(status.counts?.sourceIntelligenceRuns ?? 0) > 0, status };
      }, { timeoutMs: 120000, intervalMs: 1000, label: "automatic source intelligence count" });
      counts = profileStatus.status.counts;
      const automaticProfileState = await navigateUntil(browser.client, `${baseUrl}/?section=sources`, "automatic evidence ready", () => {
        const entry = document.querySelector('[data-testid="source-intelligence-folder-entry"]');
        const details = entry?.closest("details");
        const error = document.querySelector('[data-testid="source-intelligence-error"], .appFallback, .fallbackPanel');
        const nextDashboard = document.querySelector('[data-testid="source-next-dashboard"]');
        return {
          ok: Boolean(nextDashboard) && !error,
          manualEntryVisible: Boolean(entry && (!details || details.open)),
          hasNextDashboard: Boolean(nextDashboard),
          hasError: Boolean(error),
        };
      }, 30000);
      checks.push(
        check("api-source-intelligence-recorded-automatically", Number(counts.sourceIntelligenceRuns ?? 0) > 0, { counts }),
        check("ui-import-continues-to-evidence-automatically", automaticProfileState.ok, automaticProfileState),
        check("ui-manual-evidence-path-is-secondary", !automaticProfileState.manualEntryVisible, automaticProfileState),
      );

      const sourceAdvancedClick = await click(browser.client, '[data-testid="source-expert-toggle"]');
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

      const firstChartEntry = await navigateUntil(browser.client, `${baseUrl}/?section=dashboards`, "first chart entry", () => {
        const text = document.body?.innerText || "";
        const strip = document.querySelector('[data-testid="dashboard-business-task-strip"]');
        const prompt = document.querySelector('[data-testid="dashboard-ai-chart-prompt"]');
        const chartButton = document.querySelector('[data-testid="dashboard-task-explain"]');
        const beta = document.querySelector('[data-testid="dashboard-beta-details"]');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        return {
          ok: Boolean(strip && prompt && chartButton) && text.includes("codex_import_") && !error,
          hasStrip: Boolean(strip),
          hasPrompt: Boolean(prompt),
          promptValue: prompt?.value ?? "",
          hasChartButton: Boolean(chartButton),
          chartDisabled: Boolean(chartButton?.disabled),
          betaCollapsed: Boolean(beta && !beta.open),
          workspaceSynced: text.includes("codex_import_"),
          hasError: Boolean(error),
        };
      }, 45000);
      checks.push(
        check("ui-first-chart-entry-visible", firstChartEntry.ok, firstChartEntry),
        check("ui-first-chart-prompt-is-empty-by-default", firstChartEntry.promptValue === "", firstChartEntry),
        check("ui-first-chart-prompt-does-not-expose-internal-template", firstChartEntry.promptValue === "" && !firstChartEntry.promptValue.includes("source_"), firstChartEntry),
        check("ui-full-dashboard-beta-collapsed", firstChartEntry.betaCollapsed, firstChartEntry),
      );

      const chartPromptValue = await setNativeValue(browser.client, '[data-testid="dashboard-ai-chart-prompt"]', "看支付保费总额");
      const chartPromptReady = await waitForUi(browser.client, "chart prompt ready", () => {
        const prompt = document.querySelector('[data-testid="dashboard-ai-chart-prompt"]');
        const chartButton = document.querySelector('[data-testid="dashboard-task-explain"]');
        return {
          ok: Boolean(prompt && chartButton) && prompt.value === "看支付保费总额" && !chartButton.disabled,
          promptValue: prompt?.value ?? "",
          chartDisabled: Boolean(chartButton?.disabled),
        };
      }, 10000);
      checks.push(
        check("ui-first-chart-prompt-filled-by-user", chartPromptValue.ok && chartPromptReady.ok, { chartPromptValue, chartPromptReady }),
      );

      const chartClick = await click(browser.client, '[data-testid="dashboard-task-explain"]');
      checks.push(check("ui-dashboard-single-chart-click-fired", chartClick.ok, chartClick));
      const chartAgentState = await waitForUi(browser.client, "single chart confirmation", () => {
        const taskDetails = document.querySelector('[data-testid="agent-task-packet-details"]');
        const confirm = document.querySelector('[data-testid="agent-current-draft-confirm"]');
        const widgets = Array.from(document.querySelectorAll('[data-testid="agent-dashboard-draft-widget"]'));
        const trustAnalysis = document.querySelector('[data-testid="agent-trust-analysis-details"]');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        const confirmButtons = Array.from(document.querySelectorAll('[data-testid^="agent-current-draft-confirm"], [data-testid^="agent-draft-confirm-"]')).filter((button) => {
          const details = button.closest("details");
          return !details || details.open;
        });
        return {
          ok: Boolean(taskDetails && confirm && trustAnalysis && !trustAnalysis.open) && widgets.length === 1 && confirmButtons.length === 1 && !error,
          url: location.href,
          hasTaskDetails: Boolean(taskDetails),
          hasConfirm: Boolean(confirm),
          previewWidgetCount: widgets.length,
          confirmButtonCount: confirmButtons.length,
          trustAnalysisCollapsed: Boolean(trustAnalysis && !trustAnalysis.open),
          hasError: Boolean(error),
        };
      }, 90000);
      actions = await getActions(12);
      const singleChartDraft = actions.actionDrafts?.find((draft) => draft.kind === "dashboard.create");
      checks.push(
        check("ui-dashboard-single-chart-draft-visible", chartAgentState.ok, chartAgentState),
        check("ui-agent-query-plan-secondary-collapsed", chartAgentState.trustAnalysisCollapsed, chartAgentState),
        check("api-single-chart-draft-is-one-widget", Boolean(singleChartDraft) &&
          singleChartDraft.label === "生成单图表草案" &&
          singleChartDraft.payload?.dashboardDraft?.source === "single-chart" &&
          singleChartDraft.payload?.dashboardDraft?.widgetCount === 1 &&
          singleChartDraft.payload?.dashboardDraft?.widgets?.length === 1 &&
          ["metric", "line", "bar", "pie", "table"].includes(singleChartDraft.payload.dashboardDraft.widgets[0]?.type), { singleChartDraft }),
      );
      for (const reviewViewport of evidenceViewports) {
        await setViewport(browser.client, reviewViewport);
        const reviewLayout = await evaluate(browser.client, () => {
          const visible = (element) => {
            const details = element.closest("details");
            if (details && !details.open && element !== details.querySelector("summary")) return false;
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 1 && rect.height > 1 && style.display !== "none" && style.visibility !== "hidden";
          };
          const narrowLongText = Array.from(document.querySelectorAll("button,strong,span,p,small"))
            .filter(visible)
            .filter((element) => (element.textContent || "").trim().length > 6 && element.getBoundingClientRect().width < 48)
            .map((element) => (element.textContent || "").trim().slice(0, 40));
          const confirmCount = Array.from(document.querySelectorAll('[data-testid^="agent-current-draft-confirm"], [data-testid^="agent-draft-confirm-"]')).filter(visible).length;
          return {
            documentOverflowX: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
            confirmCount,
            narrowLongText,
          };
        });
        const screenshot = await captureScreenshot(browser.client, join(screenshotDir, `real-import-draft-${reviewViewport.key}.png`));
        checks.push(
          check(`ui-draft-${reviewViewport.key}-no-x-overflow`, reviewLayout.documentOverflowX === 0, reviewLayout),
          check(`ui-draft-${reviewViewport.key}-single-confirm`, reviewLayout.confirmCount === 1, reviewLayout),
          check(`ui-draft-${reviewViewport.key}-no-vertical-text`, reviewLayout.narrowLongText.length === 0, reviewLayout),
        );
        steps.push({ step: `draft-${reviewViewport.key}`, viewport: reviewViewport, state: reviewLayout, screenshot });
      }
      await setViewport(browser.client, viewport);
      const draftScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "real-import-single-chart-draft.png"));
      steps.push({ step: "single-chart-draft", state: chartAgentState, actions: { pendingCount: actions.pendingCount ?? actions.actionDrafts?.length ?? 0 }, screenshot: draftScreenshot });

      const chartConfirmClick = await click(browser.client, '[data-testid="agent-current-draft-confirm"]');
      checks.push(check("ui-dashboard-single-chart-confirm-click-fired", chartConfirmClick.ok, chartConfirmClick));
      const dashboardStatus = await waitForApi(async () => {
        const status = await getStatus();
        const nextDashboards = await getDashboards();
        const createdDashboard = nextDashboards.dashboards?.[0];
        return {
          ok: Number(status.counts?.dashboards ?? 0) === 1 && createdDashboard?.widgets?.length === 1,
          status,
          dashboards: nextDashboards,
        };
      }, { timeoutMs: 45000, intervalMs: 1000, label: "single chart dashboard confirmation" });
      counts = dashboardStatus.status.counts;
      dashboards = dashboardStatus.dashboards;
      actions = await getActions(12);
      const confirmedQueryResponse = await fetch(`${apiBaseUrl}/api/confirmed-queries?status=candidate&limit=10`);
      const confirmedQueryPayload = await confirmedQueryResponse.json();
      const firstChartCandidate = confirmedQueryPayload.confirmedQueries?.find((item) => item.originating_action_key === singleChartDraft?.action_key);
      checks.push(
        check("api-single-chart-dashboard-created", dashboardStatus.ok, { counts, dashboards: dashboards.dashboards }),
        check("api-single-chart-draft-cleared-after-confirm", !actions.actionDrafts?.some((draft) => draft.action_key === singleChartDraft?.action_key), { pendingCount: actions.pendingCount ?? actions.actionDrafts?.length ?? 0 }),
        check("api-first-chart-creates-confirmed-query-candidate", confirmedQueryResponse.ok && firstChartCandidate?.status === "candidate", { firstChartCandidate }),
      );

      const dashboardPage = await waitForUi(browser.client, "confirmed single chart dashboard", () => {
        const strip = document.querySelector('[data-testid="dashboard-business-task-strip"]');
        const widget = document.querySelector('.bDashboardKit');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        const stripRect = strip?.getBoundingClientRect();
        const widgetRect = widget?.getBoundingClientRect();
        return {
          ok: Boolean(strip && widget && strip.classList.contains("compact") && widgetRect && stripRect && widgetRect.top < stripRect.top) && !error,
          hasStrip: Boolean(strip),
          hasWidget: Boolean(widget),
          compactCreate: Boolean(strip?.classList.contains("compact")),
          resultBeforeCreate: Boolean(widgetRect && stripRect && widgetRect.top < stripRect.top),
          hasError: Boolean(error),
        };
      }, 30000);
      const deferredPanelsBeforeOpen = await evaluate(browser.client, () => ({
        guided: Boolean(document.querySelector('[data-testid="dashboard-beginner-editor"]')),
        advanced: Boolean(document.querySelector('[data-testid="dashboard-advanced-widget-workbench"]')),
        contract: Boolean(document.querySelector('[data-testid="dashboard-contract-boundary-panel"]')),
      }));
      const dashboardDataReady = await waitForUi(browser.client, "confirmed single chart live data", () => {
        const metricCard = document.querySelector('[data-testid="b-widget-metric"]');
        const metricValue = metricCard?.querySelector(".bMetricValue")?.textContent?.trim() ?? "";
        const loading = metricCard?.querySelector('[data-testid="b-widget-data-loading"]');
        const unavailable = metricCard?.querySelector('[data-testid="b-widget-data-error"]');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        const nonZero = metricValue !== "" && !/^0(?:[.,]0+)?$/.test(metricValue);
        return {
          ok: Boolean(metricCard && metricValue && !loading && !unavailable && nonZero && !error),
          metricValue,
          hasMetricCard: Boolean(metricCard),
          loading: Boolean(loading),
          unavailable: Boolean(unavailable),
          hasError: Boolean(error),
        };
      }, 30000);
      checks.push(
        check("ui-confirmed-single-chart-dashboard-visible", dashboardPage.ok, dashboardPage),
        check("ui-dashboard-deferred-panels-not-mounted-before-open", !deferredPanelsBeforeOpen.guided && !deferredPanelsBeforeOpen.advanced && !deferredPanelsBeforeOpen.contract, deferredPanelsBeforeOpen),
        check("ui-dashboard-widget-live-data-visible", dashboardDataReady.ok, dashboardDataReady),
      );
      for (const resultViewport of evidenceViewports) {
        await setViewport(browser.client, resultViewport);
        const resultLayout = await evaluate(browser.client, () => {
          const strip = document.querySelector('[data-testid="dashboard-business-task-strip"]');
          const widget = document.querySelector('.bDashboardKit');
          const stripRect = strip?.getBoundingClientRect();
          const widgetRect = widget?.getBoundingClientRect();
          return {
            documentOverflowX: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
            resultBeforeCreate: Boolean(widgetRect && stripRect && widgetRect.top < stripRect.top),
            compactCreate: Boolean(strip?.classList.contains("compact")),
          };
        });
        const screenshot = await captureScreenshot(browser.client, join(screenshotDir, `real-import-result-${resultViewport.key}.png`));
        checks.push(
          check(`ui-result-${resultViewport.key}-no-x-overflow`, resultLayout.documentOverflowX === 0, resultLayout),
          check(`ui-result-${resultViewport.key}-result-first`, resultLayout.resultBeforeCreate && resultLayout.compactCreate, resultLayout),
        );
        steps.push({ step: `result-${resultViewport.key}`, viewport: resultViewport, state: resultLayout, screenshot });
      }
      await setViewport(browser.client, viewport);
      const dashboardScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "real-import-dashboard.png"));
      steps.push({ step: "single-chart-confirmed", state: dashboardPage, liveData: dashboardDataReady, deferredPanelsBeforeOpen, screenshot: dashboardScreenshot });

      const dashboardMoreOpen = await openDetails(browser.client, '[data-testid="dashboard-more-details"]');
      checks.push(check("ui-dashboard-more-opens-for-evidence", dashboardMoreOpen.ok, dashboardMoreOpen));
      const evidenceClick = await click(browser.client, '[data-testid="dashboard-more-evidence"]');
      checks.push(check("ui-dashboard-evidence-click-fired", evidenceClick.ok, evidenceClick));
      const evidenceReady = await waitForUi(browser.client, "evidence summary", () => {
        const business = document.querySelector('[data-testid="evidence-business-summary"]');
        const source = document.querySelector('[data-testid="evidence-source-intelligence-summary"]');
        const receipts = document.querySelector('[data-testid="evidence-receipts-details"]');
        const trustActions = document.querySelector('[data-testid="evidence-trust-actions"]');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        return {
          ok: Boolean(business && source && receipts && trustActions) && !error,
          url: location.href,
          hasBusiness: Boolean(business),
          hasSource: Boolean(source),
          receiptsCollapsed: Boolean(receipts && !receipts.open),
          hasTrustActions: Boolean(trustActions),
          hasError: Boolean(error),
        };
      }, 30000);
      checks.push(
        check("ui-evidence-business-summary-visible", evidenceReady.ok && evidenceReady.hasBusiness, evidenceReady),
        check("ui-evidence-source-summary-visible", evidenceReady.ok && evidenceReady.hasSource, evidenceReady),
        check("ui-evidence-receipts-collapsed", evidenceReady.receiptsCollapsed, evidenceReady),
        check("ui-evidence-export-and-reuse-visible", evidenceReady.hasTrustActions, evidenceReady),
      );
      const evidenceExplanationOpen = await openDetails(browser.client, '[data-testid="evidence-explanation-details"]');
      checks.push(check("ui-evidence-explanation-opens-for-layout-check", evidenceExplanationOpen.ok, evidenceExplanationOpen));
      const evidenceRatioResults = [];
      for (const evidenceViewport of evidenceViewports) {
        await setViewport(browser.client, evidenceViewport);
        const ratioState = await waitFor(browser.client, () => {
          const main = document.querySelector(".mainPanel");
          const business = document.querySelector('[data-testid="evidence-business-summary"]');
          const narrative = document.querySelector(".evidenceNarrativeSteps");
          const trust = document.querySelector(".evidenceTrustChecks");
          const gapStats = document.querySelector(".evidenceGapStats");
          const gapItems = document.querySelector(".evidenceGapItems");
          const columnCount = (element) => {
            if (!element) return 0;
            const columns = getComputedStyle(element).gridTemplateColumns.trim();
            return !columns || columns === "none" ? 0 : columns.split(/\s+/).length;
          };
          const mainWidth = main?.getBoundingClientRect().width ?? 0;
          const state = {
            ok: Boolean(main && business && narrative && trust && gapStats && gapItems),
            mainWidth,
            documentXOverflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
            mainXOverflow: main ? Math.max(0, main.scrollWidth - main.clientWidth) : 0,
            narrativeColumns: columnCount(narrative),
            trustColumns: columnCount(trust),
            gapStatsColumns: columnCount(gapStats),
            gapItemsColumns: columnCount(gapItems),
          };
          return state;
        }, null, { timeoutMs: 10000, intervalMs: 150 });
        const expectedMaxColumns = ratioState.mainWidth <= 520 ? 1 : ratioState.mainWidth <= 760 ? 2 : 99;
        const narrowGridCollapsed = [
          ratioState.narrativeColumns,
          ratioState.trustColumns,
          ratioState.gapStatsColumns,
          ratioState.gapItemsColumns,
        ].every((columnCount) => columnCount > 0 && columnCount <= expectedMaxColumns);
        const ratioScreenshot = await captureScreenshot(browser.client, join(screenshotDir, `real-import-evidence-${evidenceViewport.key}.png`));
        const ratioResult = { viewport: evidenceViewport, state: ratioState, expectedMaxColumns, screenshot: ratioScreenshot };
        evidenceRatioResults.push(ratioResult);
        checks.push(
          check(`ui-evidence-${evidenceViewport.key}-layout-ready`, ratioState.ok, ratioResult),
          check(`ui-evidence-${evidenceViewport.key}-no-x-overflow`, ratioState.documentXOverflow === 0 && ratioState.mainXOverflow === 0, ratioResult),
          check(`ui-evidence-${evidenceViewport.key}-narrow-grid-collapses`, narrowGridCollapsed, ratioResult),
        );
      }
      await setViewport(browser.client, viewport);
      const evidenceScreenshot = await captureScreenshot(browser.client, join(screenshotDir, "real-import-evidence.png"));
      steps.push({ step: "evidence-ready", screenshot: evidenceScreenshot, ratios: evidenceRatioResults });

      const settingsReady = await navigateUntil(browser.client, `${baseUrl}/?section=settings`, "trusted context settings", () => {
        const details = document.querySelector('[data-testid="settings-trust-context-details"]');
        const error = document.querySelector(".appFallback, .fallbackPanel");
        return { ok: Boolean(details && !details.open) && !error, collapsed: Boolean(details && !details.open), hasError: Boolean(error) };
      }, 30000);
      checks.push(check("ui-settings-trusted-context-collapsed", settingsReady.ok && settingsReady.collapsed, settingsReady));
      const settingsContextOpen = await openDetails(browser.client, '[data-testid="settings-trust-context-details"]');
      const settingsContextReady = await waitForUi(browser.client, "trusted context panel", () => ({
        ok: Boolean(document.querySelector('[data-testid="trust-context-settings"]')),
      }), 10000);
      checks.push(
        check("ui-settings-trusted-context-opens", settingsContextOpen.ok && settingsContextReady.ok, { settingsContextOpen, settingsContextReady }),
      );

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
  datasetLabel,
  datasetDomain,
  importFile,
  importFolder,
  importTarget,
  minimumFolderGroups,
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
