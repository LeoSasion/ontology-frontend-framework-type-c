import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentEvidencePlan } from "../src/components/AgentEvidencePlan";
import type { AgentEvidencePlan as AgentEvidencePlanContract } from "../src/typesAgent";


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
