import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { captureScreenshot, check, click, evaluate, finishReceipt, launchChrome, navigate, waitFor } from "./ui-verify-chrome.mjs";
import { apiBaseUrl, fetchJson, postJson, withTemporaryWorkspace } from "./ui-verify-workspace.mjs";

const baseUrl = process.env.AIBI_UI_BASE_URL ?? apiBaseUrl;
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-semantic-execution-"));
const itemsFile = join(screenshotDir, "items.csv");
const refundsFile = join(screenshotDir, "refunds-by-item.csv");
writeFileSync(itemsFile, "order_id,item_id\nO-1002,I2\nO-1006,I6\nO-1009,I9\n", "utf8");
writeFileSync(refundsFile, "item_id,channel,status,resolution_hours\nI2,Tmall,success,18\nI6,Douyin,success,26\nI9,Tmall,pending,40\n", "utf8");
const checks = [];
let browserIssues = [];

const run = await withTemporaryWorkspace("codex_semantic_execution", async ({ temporaryWorkspaceId }) => {
  await postJson("/api/import/commit", { filePath: resolve("validation-inputs/orders.csv"), table: "orders", name: "订单表", mode: "create", confirm: true });
  await postJson("/api/import/commit", { filePath: itemsFile, table: "items", name: "订单明细表", mode: "create", confirm: true });
  await postJson("/api/import/commit", { filePath: refundsFile, table: "refunds", name: "退款表", mode: "create", confirm: true });
  const firstSaved = await postJson("/api/relationships/save", {
    leftTable: "orders",
    rightTable: "items",
    leftField: "order_id",
    rightField: "order_id",
    fieldMappings: [{ leftField: "order_id", rightField: "order_id" }],
    joinType: "left",
    confirm: true,
  });
  const secondSaved = await postJson("/api/relationships/save", {
    leftTable: "items",
    rightTable: "refunds",
    leftField: "item_id",
    rightField: "item_id",
    fieldMappings: [{ leftField: "item_id", rightField: "item_id" }],
    joinType: "left",
    confirm: true,
  });
  const prompt = "按订单表的 channel 看退款表的 resolution_hours";
  const directQuery = await postJson("/api/semantic-query", { prompt, table: "orders", limit: 20 });
  const apiAnswer = await postJson("/api/agent/explain", { prompt, workspaceId: temporaryWorkspaceId });
  const unitVerification = await postJson("/api/analysis-units/verify", { unitKey: apiAnswer.analysisUnit?.unitKey });
  const unitDetail = await fetchJson(`/api/analysis-units?unit=${encodeURIComponent(apiAnswer.analysisUnit?.unitKey ?? "")}`);
  const adaptedChart = await postJson("/api/chart-adapt", { unitKey: apiAnswer.analysisUnit?.unitKey, preferredChart: "bar" });
  const exportPath = join(screenshotDir, "analysis-export.zip");
  const analysisExport = await postJson("/api/exports/analysis", {
    queryReceiptKey: apiAnswer.queryPlanReceipt?.receiptKey,
    unitKey: apiAnswer.analysisUnit?.unitKey,
    output: exportPath,
  });
  const exportCreated = existsSync(exportPath);
  rmSync(exportPath, { force: true });
  checks.push(
    check("semantic-ui-fixture-relationships-validated", firstSaved.saved?.validation?.status === "validated" && secondSaved.saved?.validation?.status === "validated", { first: firstSaved.saved?.validation, second: secondSaved.saved?.validation }),
    check("semantic-ui-api-executes-two-hop", apiAnswer.answerCard?.kind === "semantic-relationship-analysis" && apiAnswer.executionPlan?.status === "ready" && apiAnswer.executionPlan?.relationships?.length === 2 && apiAnswer.queryPlanReceipt?.status === "executed", { answerKind: apiAnswer.answerCard?.kind, executionPlan: apiAnswer.executionPlan }),
    check("semantic-ui-direct-api-and-agent-share-plan", directQuery.executed === true && directQuery.executionPlan?.planHash === apiAnswer.executionPlan?.planHash && directQuery.query?.runtime?.executionPlanHash === apiAnswer.queryPlanReceipt?.runtime?.executionPlanHash, { directPlanHash: directQuery.executionPlan?.planHash, agentPlanHash: apiAnswer.executionPlan?.planHash }),
    check("semantic-ui-agent-creates-verifiable-analysis-unit", apiAnswer.analysisUnit?.status === "ready" && apiAnswer.analysisUnit?.queryReceiptKey === apiAnswer.queryPlanReceipt?.receiptKey && apiAnswer.chartAdapter?.status === "ready" && unitVerification.rowsFingerprintMatches === true && unitVerification.calculationMatches === true, { analysisUnit: apiAnswer.analysisUnit, chartAdapter: apiAnswer.chartAdapter, unitVerification }),
    check("semantic-ui-analysis-unit-api-preserves-scalar-projection", unitDetail.analysisUnit?.unitKey === apiAnswer.analysisUnit?.unitKey && unitDetail.analysisUnit?.shape?.columns?.join(",") === "label,value" && unitDetail.analysisUnit?.rows?.every((row) => !("raw" in row)) && adaptedChart.chartAdapter?.status === "ready" && adaptedChart.chartAdapter?.chartType === "bar", { unitDetail: unitDetail.analysisUnit, adaptedChart: adaptedChart.chartAdapter }),
    check("semantic-ui-analysis-export-api-is-artifact-only", exportCreated && analysisExport.analysisExport?.receiptKey === apiAnswer.queryPlanReceipt?.receiptKey && analysisExport.analysisExport?.unitKey === apiAnswer.analysisUnit?.unitKey && analysisExport.analysisExport?.manifest?.sideEffects?.requery === false && analysisExport.analysisExport?.manifest?.sideEffects?.businessDatabaseWrite === false, { analysisExport: analysisExport.analysisExport }),
  );

  let browser = null;
  try {
    browser = await launchChrome();
    await navigate(browser.client, `${baseUrl}/?section=agent&workspace=${encodeURIComponent(temporaryWorkspaceId)}`);
    const ready = await waitFor(browser.client, (expectedWorkspace) => {
      const text = document.body?.innerText ?? "";
      const hasShell = Boolean(document.querySelector(".appShell"));
      const hasComposer = Boolean(document.querySelector('[data-testid="agent-prompt-composer"]'));
      const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复");
      const hasFrameworkOverlay = Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay"));
      const workspace = document.querySelector('select[aria-label="选择工作区"]')?.value ?? "";
      return {
        ok: hasShell && hasComposer && workspace === expectedWorkspace && !hasErrorBoundary && !hasFrameworkOverlay,
        title: document.title,
        url: location.href,
        hasShell,
        hasComposer,
        hasErrorBoundary,
        hasFrameworkOverlay,
        workspace,
        expectedWorkspace,
      };
    }, temporaryWorkspaceId, { timeoutMs: 25000, intervalMs: 250 });
    checks.push(check("semantic-ui-agent-page-ready", ready.ok, ready));
    const filled = await evaluate(browser.client, (value) => {
      const input = document.querySelector('[data-testid="agent-prompt-composer"] textarea');
      if (!(input instanceof HTMLTextAreaElement)) return false;
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
      setter?.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }, prompt);
    const submitted = await click(browser.client, '[data-testid="agent-prompt-composer"] button');
    const rendered = await waitFor(browser.client, () => {
      const execution = document.querySelector('[data-testid="agent-semantic-execution-plan"]');
      const answer = document.querySelector('[data-testid="agent-answer-card"]');
      const unit = document.querySelector('[data-testid="agent-analysis-unit-strip"]');
      return {
        ok: Boolean(execution && answer && unit),
        answerText: answer?.textContent ?? "",
        executionText: execution?.textContent ?? "",
        unitText: unit?.textContent ?? "",
      };
    }, null, { timeoutMs: 25000, intervalMs: 250 });
    if (rendered.ok) await click(browser.client, '[data-testid="agent-semantic-plan"] > summary');
    const visibleState = await evaluate(browser.client, () => ({
      answer: document.querySelector('[data-testid="agent-answer-card"]')?.textContent ?? "",
      execution: document.querySelector('[data-testid="agent-semantic-execution-plan"]')?.textContent ?? "",
      unit: document.querySelector('[data-testid="agent-analysis-unit-strip"]')?.textContent ?? "",
      exportButton: document.querySelector('[data-testid="agent-analysis-export"]')?.textContent ?? "",
      hasError: Boolean(document.querySelector(".appFallback, .fallbackPanel, vite-error-overlay")),
    }));
    checks.push(
      check("semantic-ui-agent-question-submitted", filled && submitted.ok, { filled, submitted }),
      check("semantic-ui-execution-plan-rendered", rendered.ok && /计划哈希|Plan hash/.test(visibleState.execution) && /最终粒度|Final grain/.test(visibleState.execution), visibleState),
      check("semantic-ui-business-answer-rendered", /受控跨表分析|Controlled cross-table analysis/.test(visibleState.answer) && /执行引擎: sqlite|Engine: sqlite/.test(visibleState.answer) && !visibleState.answer.includes("[object Object]") && !visibleState.hasError, visibleState),
      check("semantic-ui-analysis-unit-rationale-visible", /可复算分析单元|Recomputable analysis unit/.test(visibleState.unit) && /比较|comparison/.test(visibleState.unit) && /柱状图|bar chart/.test(visibleState.unit), visibleState),
      check("semantic-ui-analysis-export-action-visible", /导出 Excel \+ 报告|Export Excel \+ report/.test(visibleState.exportButton), visibleState),
    );

    const ambiguityPrompt = "看 channel 和 status";
    const ambiguityFormIdle = await waitFor(browser.client, () => {
      const button = document.querySelector('[data-testid="agent-prompt-composer"] button');
      const input = document.querySelector('[data-testid="agent-prompt-composer"] textarea');
      return { ok: button instanceof HTMLButtonElement && input instanceof HTMLTextAreaElement && !input.disabled };
    }, null, { timeoutMs: 25000, intervalMs: 150 });
    const ambiguityFilled = ambiguityFormIdle.ok;
    const ambiguitySubmitReady = await waitFor(browser.client, (targetValue) => {
      const button = document.querySelector('[data-testid="agent-prompt-composer"] button');
      const input = document.querySelector('[data-testid="agent-prompt-composer"] textarea');
      if (!(button instanceof HTMLButtonElement) || !(input instanceof HTMLTextAreaElement)) {
        return { ok: false, value: "", buttonDisabled: null, inputDisabled: null };
      }
      if (input.value !== targetValue && !input.disabled) {
        const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
        const previous = input.value;
        setter?.call(input, targetValue);
        input._valueTracker?.setValue(previous);
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return { ok: !button.disabled && !input.disabled && input.value === targetValue, value: input.value, buttonDisabled: button.disabled, inputDisabled: input.disabled };
    }, ambiguityPrompt, { timeoutMs: 15000, intervalMs: 150 });
    const ambiguitySubmitted = ambiguitySubmitReady.ok
      ? await click(browser.client, '[data-testid="agent-prompt-composer"] button')
      : { ok: false, error: "form-not-ready" };
    const ambiguityBundle = await waitFor(browser.client, () => ({
      ok: Boolean(document.querySelector('[data-testid="agent-semantic-clarification-bundle"]')),
      candidates: document.querySelectorAll('[data-testid="agent-semantic-candidate"]').length,
      groups: document.querySelectorAll('[data-testid="agent-semantic-clarification-bundle"] .agentSemanticChips').length,
    }), null, { timeoutMs: 60000, intervalMs: 250 });
    const candidatesSelected = await evaluate(browser.client, () => {
      const buttons = Array.from(document.querySelectorAll('[data-testid="agent-semantic-candidate"]'));
      const ordersChannel = buttons.find((button) => button.textContent?.includes("订单表.channel"));
      const refundsStatus = buttons.find((button) => button.textContent?.includes("退款表.status"));
      if (!(ordersChannel instanceof HTMLButtonElement) || !(refundsStatus instanceof HTMLButtonElement)) return false;
      ordersChannel.click();
      refundsStatus.click();
      return true;
    });
    const clarificationReady = await waitFor(browser.client, () => {
      const button = document.querySelector('[data-testid="agent-semantic-confirm-candidates"]');
      return { ok: button instanceof HTMLButtonElement && !button.disabled };
    }, null, { timeoutMs: 5000, intervalMs: 100 });
    const clarificationConfirmed = await click(browser.client, '[data-testid="agent-semantic-confirm-candidates"]');
    const clarificationResolved = await waitFor(browser.client, () => ({
      ok: !document.querySelector('[data-testid="agent-semantic-clarification-bundle"]') && Boolean(document.querySelector('[data-testid="agent-answer-card"]')),
      answer: document.querySelector('[data-testid="agent-answer-card"]')?.textContent ?? "",
    }), null, { timeoutMs: 60000, intervalMs: 250 });
    checks.push(
      check("semantic-ui-multiple-ambiguities-use-one-bundle", ambiguityFormIdle.ok && ambiguityFilled && ambiguitySubmitReady.ok && ambiguitySubmitted.ok && ambiguityBundle.ok && ambiguityBundle.groups === 2 && ambiguityBundle.candidates >= 4, { ambiguityFormIdle, ambiguityFilled, ambiguitySubmitReady, ambiguitySubmitted, ambiguityBundle }),
      check("semantic-ui-bundle-requires-all-selections", candidatesSelected && clarificationReady.ok && clarificationConfirmed.ok, { candidatesSelected, clarificationReady, clarificationConfirmed }),
      check("semantic-ui-combined-selection-resolves-field-ambiguity", clarificationResolved.ok && !/需要选择字段所属表|Choose the field's table/.test(clarificationResolved.answer), clarificationResolved),
    );
    await captureScreenshot(browser.client, join(screenshotDir, "semantic-execution-agent.png"));
    browserIssues = browser.client.consoleIssues();
  } finally {
    if (browser) await browser.close();
  }
  checks.push(check("semantic-ui-browser-console-clean", browserIssues.length === 0, browserIssues));
  return { apiAnswer: { executionPlan: apiAnswer.executionPlan, queryPlanReceipt: apiAnswer.queryPlanReceipt, analysisUnit: apiAnswer.analysisUnit, chartAdapter: apiAnswer.chartAdapter }, screenshotDir };
});

const receipt = finishReceipt({
  ok: false,
  generatedBy: "scripts/verify-ui-semantic-execution.mjs",
  baseUrl,
  screenshotDir,
  lifecycle: run.lifecycle,
  browserIssues,
  checks,
});
console.log(JSON.stringify(receipt, null, 2));
process.exit(receipt.ok ? 0 : 1);
