import { resolve } from "node:path";
import type { AgentProvider, GroundedAgentContext } from "../server/agentProvider";
import { buildGroundedAgentContext, enrichAgentResultWithProvider } from "../server/agentProviderRuntime";
import { createDeepSeekProvider, loadDeepSeekProviderConfig } from "../server/deepseekProvider";
import { compactContextSegments } from "../server/contextBudget";

const root = resolve(import.meta.dirname, "..");
const live = process.argv.includes("--live");
const checks: Array<{ label: string; ok: boolean; detail?: string }> = [];
const check = (label: string, ok: boolean, detail = "") => checks.push({ label, ok, detail });

const context: GroundedAgentContext = {
  schema: "aibi-agent-provider-context/v1",
  question: "退款商品金额和成功退款记录数是多少？",
  workspaceId: "verify-provider",
  answer: {
    kind: "platform_analysis",
    confidence: "query-runtime",
    title: "成功退款口径",
    summary: "退款商品金额 441；成功退款记录数 4",
    metrics: [
      { label: "退款商品金额", value: 441 },
      { label: "成功退款记录数", value: 4 },
    ],
    blocked: false,
  },
  matched: { table: "售后明细", dashboard: null },
  knowledgeRules: [{ id: "successful-refunds", title: "成功退款", grain: "一行一个售后单" }],
  queryReceipt: {
    key: "receipt-provider-verify",
    status: "executed",
    selection: { measure: "退商品金额", aggregation: "sum", filters: [] },
    evidenceTypes: ["knowledgeRule", "queryRuntime"],
    unresolved: [],
  },
  analysisUnit: {
    key: "analysis_unit_provider_fixture",
    kind: "comparison",
    status: "ready",
    resultFingerprint: "a".repeat(64),
    validationStatus: "ready",
    chartType: "bar",
    chartStatus: "ready",
    chartBlockers: [],
  },
  actionBoundary: { requiresConfirmation: false, kind: "read-only", status: "read-only" },
};

const config = {
  apiKey: "provider-test-secret",
  baseUrl: "https://api.deepseek.com" as const,
  model: "deepseek-v4-flash",
  enabled: true,
  timeoutMs: 3_000,
  maxTokens: 300,
};

function providerPayload(content: string) {
  return {
    choices: [{ message: { role: "assistant", content }, finish_reason: "stop" }],
    usage: { prompt_tokens: 120, completion_tokens: 40, total_tokens: 160 },
  };
}

const validNarrative = JSON.stringify({
  summary: "退款商品金额为 441，成功退款记录数为 4，结论来自本地查询回执。",
  rationale: ["统计粒度是一行一个售后单", "仅使用成功退款口径"],
  clarification: null,
  nextActions: ["查看退款原因分布"],
  citedEvidence: ["knowledgeRule", "queryRuntime"],
  certainty: "grounded",
});

let authorization = "";
const successFetch = (async (_input: string | URL | Request, init?: RequestInit) => {
  authorization = String((init?.headers as Record<string, string> | undefined)?.Authorization ?? "");
  return new Response(JSON.stringify(providerPayload(validNarrative)), { status: 200, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;
const provider = createDeepSeekProvider({ config, fetchImpl: successFetch });
const success = await provider.generate(context);
check("provider-status-is-real", provider.status().enabled && provider.status().configured && provider.status().mode === "provider");
check("provider-sends-server-side-bearer", authorization === `Bearer ${config.apiKey}`);
check("provider-parses-grounded-json", success.ok && success.narrative?.summary.includes("441") === true && success.usage?.totalTokens === 160);
check("provider-receipt-never-exposes-secret", !JSON.stringify(success).includes(config.apiKey));

let retryCalls = 0;
const retryFetch = (async () => {
  retryCalls += 1;
  const content = retryCalls === 1 ? "" : validNarrative;
  return new Response(JSON.stringify(providerPayload(content)), { status: 200, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;
const retryRun = await createDeepSeekProvider({ config, fetchImpl: retryFetch }).generate(context);
check("provider-retries-empty-json-once", retryRun.ok && retryRun.attempts === 2 && retryCalls === 2);

const invalidNumber = JSON.stringify({
  summary: "退款商品金额为 999",
  rationale: [],
  clarification: null,
  nextActions: [],
  citedEvidence: ["queryRuntime"],
  certainty: "grounded",
});
const invalidFetch = (async () => new Response(JSON.stringify(providerPayload(invalidNumber)), { status: 200 })) as typeof fetch;
const invalidRun = await createDeepSeekProvider({ config, fetchImpl: invalidFetch }).generate(context);
check("provider-rejects-ungrounded-number", !invalidRun.ok && invalidRun.errorCode === "provider_invalid_grounding");

const extraSchemaKey = JSON.stringify({
  ...JSON.parse(validNarrative),
  sql: "SELECT * FROM forbidden",
});
const extraSchemaFetch = (async () => new Response(JSON.stringify(providerPayload(extraSchemaKey)), { status: 200 })) as typeof fetch;
const extraSchemaRun = await createDeepSeekProvider({ config, fetchImpl: extraSchemaFetch }).generate(context);
check("provider-rejects-fields-outside-exact-json-schema", !extraSchemaRun.ok && extraSchemaRun.validation.status === "failed" && extraSchemaRun.validation.checks.exactSchema === false);

const unknownEvidence = JSON.stringify({
  ...JSON.parse(validNarrative),
  citedEvidence: ["unknown-provider-claim"],
});
const unknownEvidenceFetch = (async () => new Response(JSON.stringify(providerPayload(unknownEvidence)), { status: 200 })) as typeof fetch;
const unknownEvidenceRun = await createDeepSeekProvider({ config, fetchImpl: unknownEvidenceFetch }).generate(context);
check("provider-rejects-unknown-evidence-refs", !unknownEvidenceRun.ok && unknownEvidenceRun.validation.checks.evidenceRefs === false);

const unauthorizedFetch = (async () => new Response(JSON.stringify({ error: { message: "do not expose this body" } }), { status: 401 })) as typeof fetch;
const unauthorizedRun = await createDeepSeekProvider({ config, fetchImpl: unauthorizedFetch }).generate(context);
check("provider-sanitizes-http-error", !unauthorizedRun.ok && unauthorizedRun.errorCode === "provider_http_401" && unauthorizedRun.attempts === 1 && !JSON.stringify(unauthorizedRun).includes("do not expose"));

let rateLimitCalls = 0;
const rateLimitFetch = (async () => {
  rateLimitCalls += 1;
  return new Response(JSON.stringify({ error: { message: "rate limited detail must stay hidden" } }), { status: 429 });
}) as typeof fetch;
const rateLimitProvider = createDeepSeekProvider({ config, fetchImpl: rateLimitFetch });
const rateLimitRun = await rateLimitProvider.generate(context);
check("provider-retries-rate-limit-then-falls-back", !rateLimitRun.ok && rateLimitRun.errorCode === "provider_http_429" && rateLimitRun.attempts === 2 && rateLimitCalls === 2 && !JSON.stringify(rateLimitRun).includes("rate limited detail"));

const timeoutFetch = ((_input: string | URL | Request, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
  const abort = () => reject(new DOMException("Aborted", "AbortError"));
  if (init?.signal?.aborted) abort();
  else init?.signal?.addEventListener("abort", abort, { once: true });
})) as typeof fetch;
const timeoutProvider = createDeepSeekProvider({ config: { ...config, timeoutMs: 5 }, fetchImpl: timeoutFetch });
const timeoutRun = await timeoutProvider.generate(context);
check("provider-timeout-retries-then-falls-back", !timeoutRun.ok && timeoutRun.errorCode === "provider_timeout" && timeoutRun.attempts === 2);

const deterministicResult = {
  ok: true,
  workspaceId: "verify-provider",
  answerCard: {
    kind: "platform_analysis",
    confidence: "query-runtime",
    title: { zh: "成功退款", en: "Successful refunds" },
    summary: { zh: "退款商品金额 441，来源 C:\\private data\\orders.xlsx", en: "Refund amount 441" },
    metrics: [
      { label: { zh: "退款商品金额", en: "Refund amount" }, value: "441", rawValue: 441 },
      { label: { zh: "成功退款记录数", en: "Successful refunds" }, value: "4", rawValue: 4 },
    ],
    evidenceRefs: [{ type: "queryRuntime" }, { type: "knowledgeRule" }],
  },
  matched: { table: { display_name: "售后明细 sk-local-test-secret" }, dashboard: null },
  context: { knowledgeRules: [{ ruleId: "successful-refunds", title: "成功退款", grain: "一行一个售后单" }] },
  queryPlanReceipt: { receiptKey: "receipt-provider-verify", status: "executed", selection: {}, unresolved: [] },
  analysisUnit: {
    unitKey: "analysis_unit_provider_verify",
    kind: "comparison",
    status: "ready",
    resultFingerprint: "b".repeat(64),
    validation: { status: "ready" },
    chartAdapter: { status: "ready", chartType: "bar", blockers: [] },
  },
  actionDraft: { kind: "read-only", status: "read-only" },
  requiresConfirmation: false,
  llm: {},
};
const groundedContext = buildGroundedAgentContext("C:\\private\\orders.xlsx 的退款金额", deterministicResult);
const serializedGroundedContext = JSON.stringify(groundedContext);
check("provider-context-has-budget-receipt", groundedContext.contextBudget?.schema === "aibi-context-budget/v1" && groundedContext.contextBudget.status !== "blocked");
check(
  "provider-context-preserves-analysis-unit-evidence",
  groundedContext.analysisUnit.key === "analysis_unit_provider_verify"
    && groundedContext.analysisUnit.chartType === "bar"
    && groundedContext.contextBudget?.keptIds.includes("analysis-unit-evidence") === true
    && groundedContext.contextBudget?.requiredEvidenceRefs.includes("analysis_unit_provider_verify") === true,
);
check(
  "provider-context-redacts-local-path-and-secret",
  serializedGroundedContext.includes("[local-path]")
    && serializedGroundedContext.includes("[secret]")
    && !serializedGroundedContext.includes("private")
    && !serializedGroundedContext.includes("sk-local-test-secret"),
);
const compactedContext = compactContextSegments([
  { id: "receipt", priority: "evidence", content: { receiptKey: "receipt-provider-verify" }, evidenceRefs: ["receipt-provider-verify"] },
  { id: "diagnostic", priority: "diagnostic", content: { trace: "x".repeat(2_000) } },
], 320);
check(
  "provider-budget-preserves-receipt-before-diagnostic",
  compactedContext.receipt.status === "compacted"
    && compactedContext.receipt.keptIds.includes("receipt")
    && compactedContext.receipt.droppedIds.includes("diagnostic")
    && compactedContext.receipt.missingRequiredEvidenceRefs.length === 0,
);
const enriched = await enrichAgentResultWithProvider({ projectRoot: root, prompt: context.question, deterministicResult, provider });
const enrichedRecord = enriched as Record<string, unknown>;
check("runtime-preserves-deterministic-answer", JSON.stringify(enrichedRecord.answerCard) === JSON.stringify(deterministicResult.answerCard));
check("runtime-attaches-provider-narrative", (enrichedRecord.llm as Record<string, unknown>).mode === "provider" && Boolean((enrichedRecord.llm as Record<string, unknown>).response));
const fallbackEnriched = await enrichAgentResultWithProvider({ projectRoot: root, prompt: context.question, deterministicResult, provider: rateLimitProvider });
const fallbackRecord = fallbackEnriched as Record<string, unknown>;
const fallbackAudit = ((fallbackRecord.llm as Record<string, unknown>).audit ?? {}) as Record<string, unknown>;
check("runtime-rate-limit-preserves-deterministic-answer", JSON.stringify(fallbackRecord.answerCard) === JSON.stringify(deterministicResult.answerCard) && (fallbackRecord.llm as Record<string, unknown>).mode === "deterministic-fallback" && fallbackAudit.fallbackReason === "provider_http_429");

if (live) {
  const liveConfig = loadDeepSeekProviderConfig(root);
  const liveProvider = createDeepSeekProvider({ config: liveConfig });
  const liveRun = await liveProvider.generate(context);
  check("provider-live-call", liveRun.ok, liveRun.errorCode ?? `tokens=${liveRun.usage?.totalTokens ?? "unknown"}`);
}

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-deepseek-provider-verify/v1",
  live,
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
