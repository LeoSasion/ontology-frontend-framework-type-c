import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { captureScreenshot, check, click, evaluate, finishReceipt, launchChrome, navigate, waitFor, waitForAppReady } from "./ui-verify-chrome.mjs";
import { apiBaseUrl, fetchJson, postJson, withTemporaryWorkspace } from "./ui-verify-workspace.mjs";

const baseUrl = process.env.AIBI_UI_BASE_URL ?? apiBaseUrl;
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-connector-adapter-"));
const checks = [];
let browserIssues = [];

const run = await withTemporaryWorkspace("codex_connector_adapter", async ({ temporaryWorkspaceId }) => {
  await postJson("/api/import/commit", {
    filePath: resolve("validation-inputs/orders.csv"),
    table: "orders",
    name: "订单表",
    mode: "create",
    confirm: true,
  });
  const saved = await postJson("/api/connectors", {
    name: `M11 UI ${temporaryWorkspaceId}`,
    type: "file",
    provider: "local-tabular",
    status: "active",
    endpoint: resolve("validation-inputs/orders.csv"),
    targetTable: "orders_adapter_copy",
    confirm: true,
  });
  const connectorKey = saved.savedConnector;

  try {
    const adapters = await fetchJson("/api/connector-adapters");
    const preview = await postJson("/api/connectors/preview", { connector: connectorKey, limit: 2 });
    const plan = await postJson("/api/connectors/sync-plan", { connector: connectorKey });
    checks.push(
      check("connector-adapter-http-contract-visible", adapters.schema === "aibi-connector-adapter/v1" && adapters.adapters?.[0]?.adapterId === "local-tabular/v1" && adapters.adapters?.[0]?.permissions?.network === "none", adapters),
      check("connector-adapter-http-preview-is-read-only", preview.operation === "bounded-preview" && preview.preview?.returnedRows === 2 && preview.sideEffects?.businessDatabaseWrite === false, preview),
      check("connector-adapter-http-plan-requires-confirmation", plan.operation === "sync-plan" && plan.requiresConfirmation === true && plan.syncPlan?.writeBoundary?.requiresConfirmation === true, plan),
    );

    let browser = null;
    try {
      browser = await launchChrome();
      await navigate(browser.client, `${baseUrl}/?section=sources&workspace=${encodeURIComponent(temporaryWorkspaceId)}&table=orders`);
      const ready = await waitForAppReady(browser.client, "source-expert-toggle", 25000);
      checks.push(check("connector-adapter-source-page-ready", ready.ok, ready));
      await click(browser.client, '[data-testid="source-expert-toggle"]');
      await click(browser.client, '[data-testid="source-evidence-details"] > summary');
      const connectorPanel = await waitFor(browser.client, () => {
        const lead = document.querySelector('[data-testid="connector-business-lead"]');
        const text = lead?.textContent ?? "";
        return { ok: Boolean(lead) && /只读 Adapter|read-only Adapter/.test(text), text };
      }, null, { timeoutMs: 15000, intervalMs: 200 });
      const adapterOptions = await evaluate(browser.client, () => {
        const select = document.querySelector('[data-testid="connector-technical-details"] select');
        return select instanceof HTMLSelectElement
          ? Array.from(select.options).map((option) => ({ value: option.value, disabled: option.disabled }))
          : [];
      });
      const clicked = await click(browser.client, `[data-testid="connector-sync-dry-${connectorKey}"]`);
      const receipt = await waitFor(browser.client, () => {
        const node = document.querySelector('[data-testid="connector-operation-receipt"]');
        const text = node?.textContent ?? "";
        return { ok: /只读 Adapter|read-only Adapter/.test(text) && /不会写入|Nothing writes/.test(text), text };
      }, null, { timeoutMs: 20000, intervalMs: 200 });
      const visibleState = await evaluate(browser.client, () => ({
        hasFallback: Boolean(document.querySelector(".appFallback, .fallbackPanel, vite-error-overlay")),
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      }));
      checks.push(
        check("connector-adapter-boundary-copy-visible", connectorPanel.ok, connectorPanel),
        check(
          "only-available-adapters-are-presented-as-operable",
          adapterOptions.length === 3 &&
            ["file", "api", "database"].every((value, index) => adapterOptions[index]?.value === value && adapterOptions[index]?.disabled === false) &&
            !adapterOptions.some((option) => option.value === "erp"),
          adapterOptions,
        ),
        check("connector-adapter-preview-receipt-visible", clicked.ok && receipt.ok, { clicked, receipt }),
        check("connector-adapter-browser-layout-stable", !visibleState.hasFallback && !visibleState.horizontalOverflow, visibleState),
      );
      await captureScreenshot(browser.client, join(screenshotDir, "connector-adapter-preview.png"));
      browserIssues = browser.client.consoleIssues();
    } finally {
      if (browser) await browser.close();
    }
    checks.push(check("connector-adapter-browser-console-clean", browserIssues.length === 0, browserIssues));
    return { connectorKey, screenshotDir };
  } finally {
    if (connectorKey) await postJson("/api/connectors/remove", { connector: connectorKey, confirm: true });
  }
});

const receipt = finishReceipt({
  ok: false,
  generatedBy: "scripts/verify-ui-connector-adapter.mjs",
  baseUrl,
  screenshotDir,
  lifecycle: run.lifecycle,
  browserIssues,
  checks,
});
console.log(JSON.stringify(receipt, null, 2));
process.exit(receipt.ok ? 0 : 1);
