import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { captureScreenshot, check, click, evaluate, finishReceipt, launchChrome, navigate, setViewport, waitFor } from "./ui-verify-chrome.mjs";
import { apiBaseUrl, fetchJson, postJson, withTemporaryWorkspace } from "./ui-verify-workspace.mjs";

const baseUrl = process.env.AIBI_UI_BASE_URL ?? apiBaseUrl;
const screenshotDir = mkdtempSync(join(tmpdir(), "aibi-ui-semantic-execution-"));
const sitesFile = join(screenshotDir, "sites.csv");
const assetsFile = join(screenshotDir, "assets.csv");
const observationsFile = join(screenshotDir, "observations.csv");
writeFileSync(sitesFile, "site_id,region,status\nS1,North,active\nS2,South,active\nS3,North,inactive\n", "utf8");
writeFileSync(assetsFile, "asset_id,site_id,status\nA1,S1,available\nA2,S2,maintenance\nA3,S3,available\n", "utf8");
writeFileSync(observationsFile, "asset_id,status,reading_value,observed_at\nA1,valid,18,2026-07-01\nA2,valid,26,2026-07-02\nA3,pending,40,2026-07-03\n", "utf8");
const checks = [];
let browserIssues = [];

const run = await withTemporaryWorkspace("codex_semantic_execution", async ({ temporaryWorkspaceId }) => {
  await postJson("/api/import/commit", { filePath: sitesFile, table: "sites", name: "站点表", mode: "create", confirm: true });
  await postJson("/api/import/commit", { filePath: assetsFile, table: "assets", name: "资产表", mode: "create", confirm: true });
  await postJson("/api/import/commit", { filePath: observationsFile, table: "observations", name: "观测表", mode: "create", confirm: true });
  const firstSaved = await postJson("/api/relationships/save", {
    leftTable: "sites",
    rightTable: "assets",
    leftField: "site_id",
    rightField: "site_id",
    fieldMappings: [{ leftField: "site_id", rightField: "site_id" }],
    joinType: "left",
    confirm: true,
  });
  const secondSaved = await postJson("/api/relationships/save", {
    leftTable: "assets",
    rightTable: "observations",
    leftField: "asset_id",
    rightField: "asset_id",
    fieldMappings: [{ leftField: "asset_id", rightField: "asset_id" }],
    joinType: "left",
    confirm: true,
  });
  const prompt = "按站点表的 region 汇总 reading_value";
  const directQuery = await postJson("/api/semantic-query", { prompt, table: "sites", limit: 20 });
  const apiAnswer = await postJson("/api/agent/explain", { prompt, workspaceId: temporaryWorkspaceId });
  const undefinedRatio = await postJson("/api/agent/explain", { prompt: "请计算健康率", workspaceId: temporaryWorkspaceId });
  const workflowReadback = await fetchJson(`/api/workflow/agent-graph?turn=${encodeURIComponent(apiAnswer.agentTurn?.turnKey ?? "")}&workspaceId=${encodeURIComponent(temporaryWorkspaceId)}`);
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
    check("semantic-ui-neutral-fixture-has-no-domain-pack-semantics", (apiAnswer.queryPlanReceipt?.domainPacks?.length ?? 0) === 0 && (apiAnswer.context?.knowledgeRules?.length ?? 0) === 0, { domainPacks: apiAnswer.queryPlanReceipt?.domainPacks, knowledgeRules: apiAnswer.context?.knowledgeRules }),
    check("semantic-ui-direct-api-and-agent-share-plan", directQuery.executed === true && directQuery.executionPlan?.planHash === apiAnswer.executionPlan?.planHash && directQuery.query?.runtime?.executionPlanHash === apiAnswer.queryPlanReceipt?.runtime?.executionPlanHash, { directPlanHash: directQuery.executionPlan?.planHash, agentPlanHash: apiAnswer.executionPlan?.planHash }),
    check("semantic-ui-undefined-ratio-is-blocked-with-required-definition", undefinedRatio.queryPlanReceipt?.status === "blocked" && undefinedRatio.queryPlanReceipt?.validation?.executed === false && undefinedRatio.queryPlanReceipt?.runtime?.compiledSql == null && undefinedRatio.queryPlanReceipt?.unresolved?.some((item) => item?.kind === "compound-analysis-definition") && undefinedRatio.analysisUnit?.status === "blocked" && undefinedRatio.answerCard?.kind === "clarification", { queryPlanReceipt: undefinedRatio.queryPlanReceipt, analysisUnit: undefinedRatio.analysisUnit, answerCard: undefinedRatio.answerCard }),
    check("semantic-ui-workflow-graph-round-trips-from-turn", workflowReadback.workflowGraph?.fingerprint === apiAnswer.evidencePlan?.workflowGraph?.fingerprint && workflowReadback.workflowExecution?.fingerprint === apiAnswer.evidencePlan?.workflowExecution?.fingerprint && workflowReadback.workflowExecution?.join?.status === "passed" && workflowReadback.workflowGraph?.nodes?.some((node) => node.operator === "unit"), { workflowReadback, expectedGraph: apiAnswer.evidencePlan?.workflowGraph }),
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

    const browserSessionBeforeReload = await evaluate(browser.client, (workspaceId) => ({
      sessionKey: localStorage.getItem(`aibi.agentSession.${workspaceId}`) ?? "",
      workspaceId,
    }), temporaryWorkspaceId);
    const sessionBeforeReload = browserSessionBeforeReload.sessionKey
      ? await fetchJson(`/api/agent/sessions/${encodeURIComponent(browserSessionBeforeReload.sessionKey)}?workspaceId=${encodeURIComponent(temporaryWorkspaceId)}`)
      : {};
    await setViewport(browser.client, { width: 390, height: 844 });
    await browser.client.send("Page.reload", { ignoreCache: true });
    const refreshed = await waitFor(browser.client, (expectedWorkspace) => {
      const workspace = document.querySelector('select[aria-label="选择工作区"]')?.value ?? "";
      return {
        ok: Boolean(document.querySelector(".appShell") && document.querySelector('[data-testid="agent-prompt-composer"]')) && workspace === expectedWorkspace,
        workspace,
        expectedWorkspace,
      };
    }, temporaryWorkspaceId, { timeoutMs: 25000, intervalMs: 250 });
    const browserSessionAfterReload = await evaluate(browser.client, (workspaceId) => ({
      sessionKey: localStorage.getItem(`aibi.agentSession.${workspaceId}`) ?? "",
      workspaceId,
    }), temporaryWorkspaceId);
    const followupPrompt = "重新按站点表的 region 汇总 reading_value";
    const followupReady = await waitFor(browser.client, (targetValue) => {
      const button = document.querySelector('[data-testid="agent-prompt-composer"] button');
      const input = document.querySelector('[data-testid="agent-prompt-composer"] textarea');
      if (!(button instanceof HTMLButtonElement) || !(input instanceof HTMLTextAreaElement)) return { ok: false };
      if (input.value !== targetValue && !input.disabled) {
        const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
        const previous = input.value;
        setter?.call(input, targetValue);
        input._valueTracker?.setValue(previous);
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return { ok: !button.disabled && !input.disabled && input.value === targetValue };
    }, followupPrompt, { timeoutMs: 15000, intervalMs: 150 });
    const followupSubmitted = followupReady.ok
      ? await click(browser.client, '[data-testid="agent-prompt-composer"] button')
      : { ok: false, error: "form-not-ready" };
    const continued = await waitFor(browser.client, (previousUnitText) => {
      const unitText = document.querySelector('[data-testid="agent-analysis-unit-strip"]')?.textContent ?? "";
      const button = document.querySelector('[data-testid="agent-prompt-composer"] button');
      return { ok: Boolean(unitText && unitText !== previousUnitText && button instanceof HTMLButtonElement && !button.disabled), unitText };
    }, visibleState.unit, { timeoutMs: 60000, intervalMs: 250 });
    const sessionAfterReload = browserSessionAfterReload.sessionKey
      ? await fetchJson(`/api/agent/sessions/${encodeURIComponent(browserSessionAfterReload.sessionKey)}?workspaceId=${encodeURIComponent(temporaryWorkspaceId)}`)
      : {};
    const continuedTurnKey = sessionAfterReload.session?.currentTurnKey ?? "";
    const continuedTurn = continuedTurnKey
      ? await fetchJson(`/api/agent/turns/${encodeURIComponent(continuedTurnKey)}?workspaceId=${encodeURIComponent(temporaryWorkspaceId)}`)
      : {};
    const narrowMetrics = await evaluate(browser.client, () => {
      const root = document.documentElement;
      const body = document.body;
      const shell = document.querySelector(".appShell");
      return {
        innerWidth,
        documentX: Math.max(0, root.scrollWidth - root.clientWidth),
        bodyX: Math.max(0, body.scrollWidth - body.clientWidth),
        shellX: shell ? Math.max(0, shell.scrollWidth - shell.clientWidth) : null,
        hasError: Boolean(document.querySelector(".appFallback, .fallbackPanel, vite-error-overlay")),
      };
    });
    checks.push(
      check("semantic-ui-session-key-survives-refresh", refreshed.ok && browserSessionBeforeReload.sessionKey.startsWith("session-") && browserSessionAfterReload.sessionKey === browserSessionBeforeReload.sessionKey, { refreshed, browserSessionBeforeReload, browserSessionAfterReload }),
      check("semantic-ui-refreshed-question-continues-same-session", followupReady.ok && followupSubmitted.ok && continued.ok && sessionAfterReload.session?.sessionKey === sessionBeforeReload.session?.sessionKey && sessionAfterReload.context?.turnCount === (sessionBeforeReload.context?.turnCount ?? 0) + 1 && continuedTurn.turn?.parentTurnKey === sessionBeforeReload.session?.currentTurnKey, { followupReady, followupSubmitted, continued, sessionBeforeReload, sessionAfterReload, continuedTurn }),
      check("semantic-ui-390x844-has-no-horizontal-overflow", narrowMetrics.innerWidth === 390 && narrowMetrics.documentX === 0 && narrowMetrics.bodyX === 0 && narrowMetrics.shellX === 0 && !narrowMetrics.hasError, narrowMetrics),
    );
    await captureScreenshot(browser.client, join(screenshotDir, "semantic-execution-agent-390x844.png"));

    const ambiguityPrompt = "看 site_id 和 status";
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
      const sitesId = buttons.find((button) => button.textContent?.includes("站点表.site_id"));
      const observationsStatus = buttons.find((button) => button.textContent?.includes("观测表.status"));
      if (!(sitesId instanceof HTMLButtonElement) || !(observationsStatus instanceof HTMLButtonElement)) return false;
      sitesId.click();
      observationsStatus.click();
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
      evidencePlan: document.querySelector('[data-testid="agent-evidence-plan"]')?.textContent ?? "",
      hasObjectObject: (document.body?.innerText ?? "").includes("[object Object]"),
    }), null, { timeoutMs: 60000, intervalMs: 250 });
    checks.push(
      check("semantic-ui-multiple-ambiguities-use-one-bundle", ambiguityFormIdle.ok && ambiguityFilled && ambiguitySubmitReady.ok && ambiguitySubmitted.ok && ambiguityBundle.ok && ambiguityBundle.groups === 2 && ambiguityBundle.candidates >= 4, { ambiguityFormIdle, ambiguityFilled, ambiguitySubmitReady, ambiguitySubmitted, ambiguityBundle }),
      check("semantic-ui-bundle-requires-all-selections", candidatesSelected && clarificationReady.ok && clarificationConfirmed.ok, { candidatesSelected, clarificationReady, clarificationConfirmed }),
      check("semantic-ui-combined-selection-resolves-field-ambiguity", clarificationResolved.ok && !/需要选择字段所属表|Choose the field's table/.test(clarificationResolved.answer), clarificationResolved),
      check("semantic-ui-confirmed-ambiguity-never-renders-object-object", clarificationResolved.ok && !clarificationResolved.hasObjectObject && !clarificationResolved.evidencePlan.includes("[object Object]"), clarificationResolved),
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
