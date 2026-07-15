import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  relationshipRecordKey,
  relationshipRecommendationKey,
  relationshipRequestScopeKey,
  relationshipSavePayloadKey,
  withRelationshipIdentity,
} from "../src/dashboardCanvasRelationshipModel";
import {
  buildRelationshipAutoModelGraphViewModel,
  relationshipSaveOptions,
} from "../src/relationshipAutoModelGraphModel";
import {
  invalidateRelationshipRequests,
  latestRelationshipResult,
} from "../src/relationshipRequestGuard";
import type { RelationshipSaveOptions } from "../src/dashboardCanvasContracts";
import type { RelationshipRecommendation, RelationshipRecord } from "../src/types";

function recommendation(fieldMappings: RelationshipRecommendation["fieldMappings"]): RelationshipRecommendation {
  return {
    leftTableKey: "orders",
    leftTableName: "Orders",
    rightTableKey: "refunds",
    rightTableName: "Refunds",
    fieldMappings,
    joinType: "left",
    score: 0.9,
    confidence: 0.9,
    overlapRatio: 0.85,
    existing: false,
    reasons: ["composite key"],
  };
}

function savedRelationship(fieldMappings: RelationshipRecord["fieldMappings"]): RelationshipRecord {
  return {
    relation_key: "orders-refunds",
    name: "Orders to refunds",
    left_table_key: "orders",
    right_table_key: "refunds",
    left_field: "order_id",
    right_field: "order_id",
    fieldMappings,
    join_type: "left",
    confidence: 0.9,
  };
}

const current: RelationshipSaveOptions = {
  leftTable: "orders",
  rightTable: "refunds",
  leftField: "order_id",
  rightField: "order_id",
  fieldMappings: [
    { leftField: "order_id", rightField: "order_id" },
    { leftField: "shop_id", rightField: "shop_id" },
  ],
  filters: [{ side: "right", field: "status", operator: "=", value: "approved" }],
  preaggregation: {
    side: "right",
    groupFields: ["order_id", "shop_id"],
    measures: [{ field: "refund_amount", aggregation: "sum" }],
  },
  joinType: "left",
  limit: 20,
};

test("canonical relationship identity includes every mapping and ignores mapping order", () => {
  const original = recommendation(current.fieldMappings ?? []);
  const reordered = recommendation([...(current.fieldMappings ?? [])].reverse());
  const differentCompositeKey = recommendation([
    { leftField: "order_id", rightField: "order_id" },
    { leftField: "tenant_id", rightField: "tenant_id" },
  ]);

  assert.equal(relationshipRecommendationKey(original), relationshipRecommendationKey(reordered));
  assert.notEqual(relationshipRecommendationKey(original), relationshipRecommendationKey(differentCompositeKey));
  assert.equal(relationshipRecommendationKey(original), relationshipRecordKey(savedRelationship(reordered.fieldMappings)));
  assert.equal(relationshipRecommendationKey(original), relationshipSavePayloadKey(current));
});

test("graph deduplication uses the complete composite identity", () => {
  const original = recommendation(current.fieldMappings ?? []);
  const distinct = recommendation([
    { leftField: "order_id", rightField: "order_id" },
    { leftField: "tenant_id", rightField: "tenant_id" },
  ]);
  const viewModel = buildRelationshipAutoModelGraphViewModel({
    relationshipForm: current,
    relationshipRecommendations: [original, distinct],
    relationships: [savedRelationship([...(current.fieldMappings ?? [])].reverse())],
    tables: [],
  });

  assert.equal(viewModel.graphEdges.length, 2);
  assert.equal(viewModel.graphEdges.filter((edge) => edge.source === "saved").length, 0);
});

test("relationship-specific policies survive only when the complete identity is unchanged", () => {
  const sameIdentity = relationshipSaveOptions(recommendation([...(current.fieldMappings ?? [])].reverse()), current);
  assert.deepEqual(sameIdentity?.filters, current.filters);
  assert.deepEqual(sameIdentity?.preaggregation, current.preaggregation);

  const switchedIdentity = relationshipSaveOptions(recommendation([
    { leftField: "order_id", rightField: "order_id" },
    { leftField: "tenant_id", rightField: "tenant_id" },
  ]), current);
  assert.equal(switchedIdentity?.filters, undefined);
  assert.equal(switchedIdentity?.preaggregation, undefined);

  const manuallySwitched = withRelationshipIdentity(current, { rightTable: "payments" });
  assert.equal(manuallySwitched.fieldMappings, undefined);
  assert.equal(manuallySwitched.filters, undefined);
  assert.equal(manuallySwitched.preaggregation, undefined);
});

test("relationship request scope changes with workspace, identity, and safety policy but not confirmation", () => {
  const scope = relationshipRequestScopeKey("workspace-a", current);
  assert.equal(scope, relationshipRequestScopeKey("workspace-a", { ...current, confirm: true }));
  assert.notEqual(scope, relationshipRequestScopeKey("workspace-b", current));
  assert.notEqual(scope, relationshipRequestScopeKey("workspace-a", { ...current, rightTable: "payments" }));
  assert.notEqual(scope, relationshipRequestScopeKey("workspace-a", {
    ...current,
    filters: [{ side: "right", field: "status", operator: "=", value: "rejected" }],
  }));
});

test("workspace transitions clear relationship previews and invalidate late responses", async () => {
  const appSource = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const sourceWorkbenchView = readFileSync(new URL("../src/components/SourceWorkbenchView.tsx", import.meta.url), "utf8");
  const workspaceActionsSource = readFileSync(new URL("../src/useAppWorkspaceActions.ts", import.meta.url), "utf8");
  let resolveLateResponse: ((value: string) => void) | undefined;
  const lateResponse = latestRelationshipResult(new Promise<string>((resolve) => {
    resolveLateResponse = resolve;
  }));

  invalidateRelationshipRequests();
  resolveLateResponse?.("stale workspace preview");
  assert.equal(await lateResponse, null);
  assert.equal(await latestRelationshipResult(Promise.resolve("current workspace preview")), "current workspace preview");
  assert.doesNotMatch(appSource, /useState<RelationshipPreviewPayload>/);
  assert.match(sourceWorkbenchView, /relationshipRequestScopeKey\(status\.workspace\.id, relationshipForm\)[\s\S]*invalidateRelationshipRequests\(\)/);
  assert.match(sourceWorkbenchView, /relationshipScopeRef\.current === requestScope/);
  assert.match(workspaceActionsSource, /invalidateRelationshipRequests\(\);[\s\S]*refreshStatusDashboardsWorkbenchDrafts\(\)/);
});

test("relationship and Agent proof surfaces expose busy state and complete blockers", () => {
  const relationshipPanel = readFileSync(new URL("../src/components/SourceWorkbenchRelationshipPanel.tsx", import.meta.url), "utf8");
  const semanticPlan = readFileSync(new URL("../src/components/AgentSemanticPlan.tsx", import.meta.url), "utf8");
  const agentPanel = readFileSync(new URL("../src/components/AgentPanel.tsx", import.meta.url), "utf8");
  const semanticPromptSelectors = readFileSync(new URL("../src/semanticPromptSelectors.ts", import.meta.url), "utf8");
  const trustPanel = readFileSync(new URL("../src/components/AgentTrustAdvancedPanel.tsx", import.meta.url), "utf8");
  assert.match(relationshipPanel, /aria-busy=\{relationshipBusy\}/);
  assert.match(relationshipPanel, /aria-live="polite"[\s\S]*role="status"/);
  assert.match(semanticPlan, /relationshipBlockers\.map/);
  assert.match(semanticPlan, /data-testid="agent-semantic-path-candidate"/);
  assert.match(agentPanel, /withSemanticPathSelection\(original, relationKeys\)/);
  assert.match(semanticPromptSelectors, /使用关系路径 \$\{selectors\.relationKeys\.join\(" > "\)\}/);
  assert.match(trustPanel, /hopProofs\.length \|\| sourceTableCount > 1/);
});
