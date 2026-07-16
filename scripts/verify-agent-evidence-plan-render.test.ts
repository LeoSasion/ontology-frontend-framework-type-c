import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentAnswerCard } from "../src/components/AgentAnswerCard";
import { AgentEvidencePlan } from "../src/components/AgentEvidencePlan";
import type { AgentBusinessUnderstanding, AgentEvidencePlan as AgentEvidencePlanContract } from "../src/typesAgent";


function planWithLegacyBlockers(): AgentEvidencePlanContract {
  return {
    schema: "aibi-agent-evidence-plan/v1",
    workspaceId: "default",
    turnKey: "turn-legacy-blockers",
    planVersion: 1,
    status: "blocked",
    steps: [{
      stepKey: "step-004-query",
      kind: "query",
      capabilityId: "agent.query.execute",
      dependsOn: [],
      inputRefs: [],
      inputFingerprint: "i".repeat(64),
      requiredEvidence: [],
      outputSchema: "aibi-query-plan-receipt/v1",
      mutationMode: "runtime-receipt",
      status: "blocked",
      blockers: [
        { kind: "field-binding", mention: "site_id", reason: "multiple-field-candidates" },
        { nested: { z: 1, a: "detail" } },
      ] as unknown as string[],
      retryPolicy: {},
      completionChecks: [],
      artifactRefs: [],
      evidenceRefs: [],
      outputFingerprint: "o".repeat(64),
    }],
    registeredCapabilities: ["agent.query.execute"],
    fingerprint: "p".repeat(64),
  };
}


test("Evidence Plan renders legacy object blockers as stable readable text", () => {
  const html = renderToStaticMarkup(createElement(AgentEvidencePlan, { plan: planWithLegacyBlockers() }));
  assert.doesNotMatch(html, /\[object Object\]/);
  assert.match(html, /field-binding · site_id · multiple-field-candidates/);
  assert.match(html, /nested/);
  assert.match(html, /a: detail/);
  assert.match(html, /z: 1/);
});


test("Evidence Plan tolerates a non-array blocker from an abnormal legacy record", () => {
  const plan = planWithLegacyBlockers();
  plan.steps[0].blockers = { code: "legacy-blocker", message: "review required" } as unknown as string[];
  const html = renderToStaticMarkup(createElement(AgentEvidencePlan, { plan }));
  assert.doesNotMatch(html, /\[object Object\]/);
  assert.match(html, /legacy-blocker · review required/);
});


function businessUnderstandingFixture(): AgentBusinessUnderstanding {
  const activeClarification = {
    clarificationKey: "clarify-refund-denominator",
    kind: "metric-definition",
    mention: "refund rate",
    question: "Which denominator should be used?",
    questionLocalized: { zh: "退款率的分母应使用支付订单还是全部订单？", en: "Should refund rate use paid orders or all orders as its denominator?" },
    reason: { zh: "分母会改变指标口径。", en: "The denominator changes the metric definition." },
    priority: 100,
    slotKeys: ["denominator"],
    active: true,
  };
  return {
    schema: "aibi-business-understanding-frame/v1",
    status: "needs-clarification",
    signals: ["prompt:refund-rate", { signalKey: "signal-refund-rate", kind: "metric-alias", mention: "refund rate", value: "refund_rate", source: "prompt", confidence: 0.98 }],
    slots: {
      measure: { slotKey: "measure", label: { zh: "指标", en: "Measure" }, status: "resolved", value: "refund_rate", source: "semantic-context", required: true },
      denominator: { slotKey: "denominator", label: { zh: "分母", en: "Denominator" }, status: "missing", reason: "missing-denominator", required: true },
    },
    supportingSkills: [{
      skillId: "metric-definition-grounding",
      version: "2.1.0",
      fingerprint: "u".repeat(64),
      status: "ready",
      skillKind: "understanding",
      activeSignals: ["ratio-request"],
      missingSlots: ["denominator"],
      allowedCapabilities: ["agent.context.route"],
    }],
    activeClarification,
    unresolved: [activeClarification, { clarificationKey: "later-question", question: "This lower-value question must stay queued", priority: 10 }],
    blockers: ["missing-denominator-evidence"],
    requiredEvidence: ["metric-definition"],
    guards: ["no-silent-ratio-denominator"],
    clarification: {
      active: activeClarification,
      items: [activeClarification, { clarificationKey: "later-question", question: "This lower-value question must stay queued", priority: 10 }],
      askAtMostOne: true,
    },
    fingerprint: "b".repeat(64),
  };
}


test("Evidence Plan separates analytical and business-understanding Skills with version and status", () => {
  const plan = planWithLegacyBlockers();
  plan.status = "completed";
  plan.steps[0].status = "completed";
  plan.steps[0].blockers = [];
  plan.skillRefs = [{
    skillId: "trend-analysis",
    version: "3.0.0",
    fingerprint: "a".repeat(64),
    status: "matched",
    skillKind: "analytical",
    allowedCapabilities: ["agent.query.execute"],
  }];
  const html = renderToStaticMarkup(createElement(AgentEvidencePlan, { plan, businessUnderstanding: businessUnderstandingFixture() }));
  assert.match(html, /data-testid="agent-evidence-analytical-skills"/);
  assert.match(html, /分析 Skill|Analytical Skill/);
  assert.match(html, /trend-analysis · v3.0.0/);
  assert.match(html, /data-testid="agent-evidence-business-skills"/);
  assert.match(html, /业务理解 Skills|Business understanding Skills/);
  assert.match(html, /metric-definition-grounding · v2.1.0/);
  assert.match(html, />(?:就绪|Ready)</);
  assert.match(html, /data-testid="agent-skill-triggers"/);
  assert.match(html, /ratio-request/);
  assert.match(html, /data-testid="agent-skill-missing-slots"/);
  assert.match(html, /denominator/);
  assert.match(html, /data-testid="agent-skill-capabilities"/);
  assert.match(html, /agent\.context\.route/);
  assert.match(html, /agent\.query\.execute/);
});


test("My understanding renders signals, slot resolution, one active clarification, and a clear blocker", () => {
  const html = renderToStaticMarkup(createElement(AgentAnswerCard, {
    answerCard: {
      kind: "business-answer",
      title: { zh: "退款率分析", en: "Refund rate analysis" },
      summary: { zh: "需要先确认分母。", en: "The denominator needs clarification." },
      confidence: "needs-clarification",
      metrics: [],
      rows: [],
      evidenceRefs: [],
      nextActions: [],
    },
    answerEvidenceSteps: [],
    answerQuery: null,
    businessUnderstanding: businessUnderstandingFixture(),
    runtimeEngine: "",
  }));
  assert.match(html, /data-testid="agent-understanding-signals"/);
  assert.match(html, /prompt:refund-rate/);
  assert.match(html, /metric-alias · refund rate/);
  assert.match(html, /refund_rate/);
  assert.match(html, /semantic-context/);
  assert.match(html, /missing-denominator/);
  assert.match(html, /data-testid="agent-understanding-active-clarification"/);
  assert.match(html, /data-testid="agent-understanding-active-clarification" role="status"/);
  assert.match(html, /退款率的分母应使用支付订单还是全部订单？|Should refund rate use paid orders or all orders as its denominator\?/);
  assert.doesNotMatch(html, /This lower-value question must stay queued/);
  assert.match(html, /data-testid="agent-understanding-blockers"/);
  assert.match(html, /missing-denominator-evidence/);
});


test("My understanding renders a bounded analysis method plan without executable content", () => {
  const understanding = businessUnderstandingFixture();
  understanding.methodPlan = {
    schema: "aibi-analysis-method-plan/v1",
    skillId: "funnel-analysis",
    skillVersion: "1.0.0",
    skillFingerprint: "m".repeat(64),
    status: "blocked",
    activeSignals: ["funnel-request"],
    steps: ["resolve-funnel-stages", "verify-stage-order", "verify-funnel-invariants"],
    requiredSlots: ["funnel-stages", "stage-order"],
    resolvedSlots: {},
    missingSlots: ["funnel-stages", "stage-order"],
    requiredEvidence: ["field-provenance"],
    semanticGuards: ["ordered-stages"],
    allowedCapabilities: ["agent.semantic.plan"],
    resourceLimits: { maxSteps: 18, maxRows: 500 },
    fingerprint: "f".repeat(64),
  };
  const html = renderToStaticMarkup(createElement(AgentAnswerCard, {
    answerCard: {
      kind: "clarification",
      title: { zh: "漏斗定义待确认", en: "Funnel definition pending" },
      summary: { zh: "先确认阶段。", en: "Confirm stages first." },
      confidence: "needs-clarification",
      metrics: [],
      rows: [],
      evidenceRefs: [],
      nextActions: [],
    },
    answerEvidenceSteps: [],
    answerQuery: null,
    businessUnderstanding: understanding,
    runtimeEngine: "",
  }));
  assert.match(html, /data-testid="agent-understanding-method-plan"/);
  assert.match(html, /funnel-analysis · v1.0.0/);
  assert.match(html, /漏斗分析|Funnel analysis/);
  assert.match(html, /resolve-funnel-stages/);
  assert.match(html, /verify-stage-order/);
  assert.doesNotMatch(html, /SELECT\s|https?:\/\/|python\s/i);
});


test("progressive Agent evidence panels may shrink inside a mobile viewport", () => {
  const sharedCss = readFileSync(new URL("../src/components/workspaceShared.css", import.meta.url), "utf8");
  const evidenceCss = readFileSync(new URL("../src/components/agentEvidenceDrafts.css", import.meta.url), "utf8");
  assert.match(sharedCss, /\.progressiveDetailsBody\.single\s*>\s*\*\s*\{[^}]*min-width:\s*0/s);
  assert.match(evidenceCss, /\.agentCheckedPanel\s*\{[^}]*min-width:\s*0[^}]*width:\s*100%/s);
  assert.match(evidenceCss, /\.agentCheckedGrid\s*\{[^}]*min-width:\s*0/s);
  assert.match(evidenceCss, /\.agentLlmAuditPanel\s*\{[^}]*repeat\(auto-fit,\s*minmax\(min\(100%,\s*320px\),\s*1fr\)\)[^}]*min-width:\s*0/s);
});
