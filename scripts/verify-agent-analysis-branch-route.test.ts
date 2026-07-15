import assert from "node:assert/strict";
import test from "node:test";

import { buildAgentAskTurnArgs } from "../server/agentRoutes";

test("agent ask preserves Analysis Run branch parameters without confusing Agent Turn lineage", () => {
  const args = buildAgentAskTurnArgs({
    workspaceId: "workspace-a",
    sessionKey: "session-a",
    parentRunKey: "analysis-run-a",
    branchLabel: "按分类比较",
    reviewedStaleRefs: true,
    parentTurnKey: "must-not-cross-contracts",
  }, "请按分类比较");

  assert.deepEqual(args, [
    "agent-turn-run",
    "--workspace", "workspace-a",
    "--session", "session-a",
    "--parent-run", "analysis-run-a",
    "--branch-label", "按分类比较",
    "--review-stale-context",
    "请按分类比较",
  ]);
  assert.equal(args.includes("--parent-turn"), false);
});

test("ordinary agent ask does not invent branch parameters", () => {
  assert.deepEqual(buildAgentAskTurnArgs({}, ""), ["agent-turn-run", "生成分析计划"]);
});
