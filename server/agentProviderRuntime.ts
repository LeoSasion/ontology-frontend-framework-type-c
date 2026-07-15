import { createHash } from "node:crypto";
import type { AgentProvider, AgentProviderNarrative, GroundedAgentContext } from "./agentProvider";
import { deepSeekProviderForProject } from "./deepseekProvider";
import { compactContextSegments, configuredAgentContextMaxChars } from "./contextBudget";

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function textPair(value: unknown) {
  const pair = record(value);
  return String(pair.zh ?? pair.en ?? value ?? "").slice(0, 600);
}

function redactText(value: string) {
  return value
    .replace(/[A-Za-z]:\\[^\r\n"'<>|]*/g, "[local-path]")
    .replace(/sk-[A-Za-z0-9_-]{8,}/g, "[secret]")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[sensitive-value]")
    .replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, "[sensitive-value]")
    .replace(/(?:api[_-]?key|authorization|bearer)\s*[:=]?\s*[A-Za-z0-9._-]{6,}/gi, "[secret]");
}

function redactPrompt(value: string) {
  return redactText(value).slice(0, 2_000);
}

function redactContext<T>(context: T) {
  return JSON.parse(redactText(JSON.stringify(context))) as T;
}

export function buildGroundedAgentContext(prompt: string, deterministicResult: Record<string, unknown>): GroundedAgentContext {
  const answerCard = record(deterministicResult.answerCard);
  const matched = record(deterministicResult.matched);
  const matchedTable = record(matched.table);
  const matchedDashboard = record(matched.dashboard);
  const context = record(deterministicResult.context);
  const receipt = record(deterministicResult.queryPlanReceipt ?? answerCard.queryPlanReceipt);
  const analysisUnit = record(deterministicResult.analysisUnit);
  const unitValidation = record(analysisUnit.validation);
  const chartAdapter = record(deterministicResult.chartAdapter ?? analysisUnit.chartAdapter ?? answerCard.chartAdapter);
  const selection = record(receipt.selection);
  const actionDraft = record(deterministicResult.actionDraft);
  const evidenceRefs = Array.isArray(answerCard.evidenceRefs) ? answerCard.evidenceRefs.map(record) : [];
  const knowledgeRules = Array.isArray(context.knowledgeRules) ? context.knowledgeRules.map(record) : [];
  const metrics = Array.isArray(answerCard.metrics) ? answerCard.metrics.map(record) : [];
  const redacted = redactContext<GroundedAgentContext>({
    schema: "aibi-agent-provider-context/v1",
    question: redactPrompt(prompt),
    workspaceId: String(deterministicResult.workspaceId ?? "default"),
    answer: {
      kind: String(answerCard.kind ?? "unknown"),
      confidence: String(answerCard.confidence ?? "missing"),
      title: textPair(answerCard.title),
      summary: textPair(answerCard.summary),
      metrics: metrics.slice(0, 12).map((metric) => ({
        label: textPair(metric.label),
        value: typeof metric.rawValue === "number" || typeof metric.rawValue === "string" || metric.rawValue === null
          ? metric.rawValue
          : String(metric.value ?? "").slice(0, 80),
      })),
      blocked: String(receipt.status ?? "blocked") !== "executed",
    },
    matched: {
      table: matchedTable.display_name ? String(matchedTable.display_name).slice(0, 160) : null,
      dashboard: matchedDashboard.name ? textPair(matchedDashboard.name) : null,
    },
    knowledgeRules: knowledgeRules.slice(0, 4).map((rule) => ({
      id: String(rule.ruleId ?? "").slice(0, 120),
      title: String(rule.title ?? "").slice(0, 180),
      grain: String(rule.grain ?? "").slice(0, 260),
    })),
    queryReceipt: {
      key: receipt.receiptKey ? String(receipt.receiptKey) : null,
      status: String(receipt.status ?? "blocked"),
      selection: {
        group: selection.group ?? null,
        measure: selection.measure ?? null,
        aggregation: selection.aggregation ?? null,
        filters: Array.isArray(selection.filters) ? selection.filters.slice(0, 8) : [],
        joins: Array.isArray(selection.joins) ? selection.joins.slice(0, 6) : [],
      },
      evidenceTypes: Array.from(new Set(evidenceRefs.map((item) => String(item.type ?? "")).filter(Boolean))).slice(0, 10),
      unresolved: Array.isArray(receipt.unresolved) ? receipt.unresolved.slice(0, 4) : [],
    },
    analysisUnit: {
      key: analysisUnit.unitKey ? String(analysisUnit.unitKey) : null,
      kind: analysisUnit.kind ? String(analysisUnit.kind) : null,
      status: analysisUnit.status ? String(analysisUnit.status) : null,
      resultFingerprint: analysisUnit.resultFingerprint ? String(analysisUnit.resultFingerprint) : null,
      validationStatus: unitValidation.status ? String(unitValidation.status) : null,
      chartType: chartAdapter.chartType ? String(chartAdapter.chartType) : null,
      chartStatus: chartAdapter.status ? String(chartAdapter.status) : null,
      chartBlockers: Array.isArray(chartAdapter.blockers) ? chartAdapter.blockers.map(String).slice(0, 8) : [],
    },
    actionBoundary: {
      requiresConfirmation: deterministicResult.requiresConfirmation === true,
      kind: String(actionDraft.kind ?? "read-only"),
      status: String(actionDraft.status ?? "read-only"),
    },
  });
  const { metrics: answerMetrics, ...answerCore } = redacted.answer;
  const { selection: budgetSelection, evidenceTypes: budgetEvidenceTypes, ...receiptCore } = redacted.queryReceipt;
  const evidenceReferences = [redacted.queryReceipt.key, ...redacted.queryReceipt.evidenceTypes].filter(Boolean) as string[];
  const compacted = compactContextSegments([
    {
      id: "decision-boundary",
      priority: "critical",
      content: {
        schema: redacted.schema,
        question: redacted.question,
        workspaceId: redacted.workspaceId,
        answer: answerCore,
        queryReceipt: receiptCore,
        actionBoundary: redacted.actionBoundary,
      },
    },
    {
      id: "query-evidence",
      priority: "evidence",
      content: { selection: budgetSelection, evidenceTypes: budgetEvidenceTypes },
      evidenceRefs: evidenceReferences,
    },
    ...(redacted.analysisUnit.key ? [{
      id: "analysis-unit-evidence",
      priority: "evidence" as const,
      content: redacted.analysisUnit,
      evidenceRefs: [redacted.analysisUnit.key, redacted.analysisUnit.resultFingerprint].filter(Boolean) as string[],
    }] : []),
    {
      id: "answer-metrics",
      priority: "supporting",
      content: { metrics: answerMetrics },
    },
    {
      id: "matched-assets",
      priority: "supporting",
      content: redacted.matched,
    },
    {
      id: "knowledge-rules",
      priority: "supporting",
      content: { knowledgeRules: redacted.knowledgeRules },
      evidenceRefs: redacted.knowledgeRules.map((rule) => rule.id).filter(Boolean),
    },
  ], configuredAgentContextMaxChars());
  const kept = new Map(compacted.segments.map((segment) => [segment.id, segment.content]));
  const metricsSegment = record(kept.get("answer-metrics"));
  const evidenceSegment = record(kept.get("query-evidence"));
  const matchedSegment = record(kept.get("matched-assets"));
  const knowledgeSegment = record(kept.get("knowledge-rules"));
  return {
    ...redacted,
    answer: {
      ...redacted.answer,
      metrics: Array.isArray(metricsSegment.metrics) ? metricsSegment.metrics as GroundedAgentContext["answer"]["metrics"] : [],
    },
    matched: kept.has("matched-assets") ? {
      table: typeof matchedSegment.table === "string" ? matchedSegment.table : null,
      dashboard: typeof matchedSegment.dashboard === "string" ? matchedSegment.dashboard : null,
    } : { table: null, dashboard: null },
    knowledgeRules: Array.isArray(knowledgeSegment.knowledgeRules)
      ? knowledgeSegment.knowledgeRules as GroundedAgentContext["knowledgeRules"]
      : [],
    queryReceipt: {
      ...redacted.queryReceipt,
      selection: record(evidenceSegment.selection),
      evidenceTypes: Array.isArray(evidenceSegment.evidenceTypes) ? evidenceSegment.evidenceTypes.map(String) : [],
    },
    contextBudget: compacted.receipt,
  } satisfies GroundedAgentContext;
}

export function validateProviderOutboundContext(context: GroundedAgentContext) {
  const allowedTopLevel = new Set([
    "schema", "question", "workspaceId", "answer", "matched", "knowledgeRules",
    "queryReceipt", "analysisUnit", "actionBoundary", "contextBudget",
  ]);
  const serialized = JSON.stringify(context);
  const checks = {
    exactTopLevel: Object.keys(context).every((key) => allowedTopLevel.has(key)),
    noRawRows: !/(?:"rows"|"rawRows"|"sampleRows"|"records")\s*:/i.test(serialized),
    noSecrets: !/(?:sk-[A-Za-z0-9_-]{8,}|(?:api[_-]?key|authorization|bearer)\s*[:=]\s*[A-Za-z0-9._-]{6,})/i.test(serialized),
    noLocalPaths: !/[A-Za-z]:\\/.test(serialized),
    evidenceBound: Boolean(context.queryReceipt.key || context.answer.blocked),
    deterministicActionBoundary: context.actionBoundary.requiresConfirmation === true || context.actionBoundary.status === "read-only",
  };
  return {
    ok: Object.values(checks).every(Boolean),
    schema: "aibi-agent-provider-outbound-validation/v1" as const,
    checks,
    contextFingerprint: createHash("sha256").update(serialized).digest("hex"),
    outboundRawRowCount: 0,
    outboundSensitiveFieldCount: 0,
  };
}

function providerAudit(narrative: AgentProviderNarrative | null) {
  return narrative ? "provider-grounded" : "deterministic-fallback";
}

export async function enrichAgentResultWithProvider({
  projectRoot,
  prompt,
  deterministicResult,
  provider = deepSeekProviderForProject(projectRoot),
}: {
  projectRoot: string;
  prompt: string;
  deterministicResult: Record<string, unknown>;
  provider?: AgentProvider;
}) {
  const status = provider.status();
  const baseLlm = record(deterministicResult.llm);
  if (!status.enabled || !deterministicResult.answerCard) {
    return {
      ...deterministicResult,
      llm: {
        ...baseLlm,
        configured: status.configured,
        mode: "deterministic-fallback",
        response: null,
        audit: {
          profileId: status.profileId,
          profileFingerprint: status.profileFingerprint,
          provider: status.provider,
          model: status.model,
          configured: status.configured,
          enabled: status.enabled,
          mode: "deterministic-fallback",
          status: status.configured ? "disabled" : "not-configured",
          serverSideOnly: true,
          secretExposed: false,
          contextBoundary: "grounded-provider-context-v1",
          fallbackReason: status.profileId === "deterministic"
            ? "Deterministic local BI is the selected runtime profile."
            : status.configured ? "The selected Provider profile is disabled." : "The selected Provider profile is not configured.",
          regressionStatus: "provider-skipped",
        },
      },
    };
  }

  const context = buildGroundedAgentContext(prompt, deterministicResult);
  const outboundValidation = validateProviderOutboundContext(context);
  if (!outboundValidation.ok) {
    return {
      ...deterministicResult,
      llm: {
        ...baseLlm,
        configured: status.configured,
        mode: "deterministic-fallback",
        response: null,
        audit: {
          profileId: status.profileId,
          profileFingerprint: status.profileFingerprint,
          provider: status.provider,
          model: status.model,
          configured: status.configured,
          enabled: status.enabled,
          mode: "deterministic-fallback",
          status: "outbound-policy-blocked",
          validation: outboundValidation,
          serverSideOnly: true,
          secretExposed: false,
          rawRowsExposed: false,
          fallbackReason: "Provider outbound context failed the fixed allowlist.",
          regressionStatus: "provider-skipped",
        },
      },
    };
  }
  if (context.contextBudget?.status === "blocked") {
    return {
      ...deterministicResult,
      llm: {
        ...baseLlm,
        configured: status.configured,
        mode: "deterministic-fallback",
        response: null,
        audit: {
          profileId: status.profileId,
          profileFingerprint: status.profileFingerprint,
          provider: status.provider,
          model: status.model,
          configured: status.configured,
          enabled: status.enabled,
          mode: "deterministic-fallback",
          status: "context-budget-blocked",
          serverSideOnly: true,
          secretExposed: false,
          contextBoundary: context.schema,
          contextBudget: context.contextBudget,
          fallbackReason: context.contextBudget.blockers.join(","),
          regressionStatus: "provider-skipped",
        },
      },
    };
  }
  const run = await provider.generate(context);
  return {
    ...deterministicResult,
    llm: {
      ...baseLlm,
      configured: status.configured,
      mode: run.ok ? "provider" : "deterministic-fallback",
      response: run.narrative,
      audit: {
        profileId: run.profileId,
        profileFingerprint: run.profileFingerprint,
        provider: run.provider,
        model: run.model,
        configured: status.configured,
        enabled: status.enabled,
        mode: providerAudit(run.narrative),
        status: run.ok ? "ready" : "fallback",
        runId: run.runId,
        attempts: run.attempts,
        durationMs: run.durationMs,
        requestHash: run.requestHash,
        usage: run.usage,
        estimatedCostUsd: run.estimatedCostUsd,
        validation: run.validation,
        serverSideOnly: true,
        secretExposed: false,
        rawRowsExposed: false,
        outboundValidation,
        contextBoundary: context.schema,
        contextBudget: context.contextBudget,
        fallbackReason: run.ok ? null : run.errorCode,
        regressionStatus: run.ok ? "provider-live" : "provider-fallback",
      },
    },
  };
}
