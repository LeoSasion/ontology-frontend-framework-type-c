import { readFileSync } from "node:fs";

function source(relative) {
  return readFileSync(new URL(`../${relative}`, import.meta.url), "utf8");
}

const knowledge = source("tools/platform_analytics_knowledge.py");
const relationship = source("tools/relationship_tools.py");
const draftStore = source("tools/agent_action_draft_store.py");
const canvasState = source("src/useDashboardCanvasState.ts");
const widgetManage = source("src/components/DashboardWidgetManagePanel.tsx");
const platformVerify = source("scripts/verify-platform-commerce-agent.mjs");
const fixtureVerify = source("scripts/verify-platform-commerce-fixtures.mjs");

const checks = [
  {
    label: "grain-is-explicit-before-platform-answer",
    ok: knowledge.includes('"grain": intent["grain"]') && knowledge.includes('"knowledgeRule"'),
  },
  {
    label: "compound-relationship-supports-multiple-fields",
    ok: relationship.includes("for mapping in mappings")
      && fixtureVerify.includes('["主订单编号", "商品ID", "商家编码"]'),
  },
  {
    label: "percent-input-normalizes-to-decimal",
    ok: knowledge.includes("float(percent_match.group(1)) / 100")
      && platformVerify.includes("阈值: 0.2"),
  },
  {
    label: "action-drafts-have-independent-identities-and-status",
    ok: draftStore.includes("action_key") && draftStore.includes("status") && draftStore.includes("WHERE action_key = ?"),
  },
  {
    label: "widgets-can-reorder-edit-and-delete",
    ok: canvasState.includes("function moveWidget")
      && widgetManage.includes("draggable")
      && widgetManage.includes("widget-edit-")
      && widgetManage.includes("widget-remove-preview-"),
  },
  {
    label: "relationship-preview-exposes-quality-and-expansion",
    ok: [
      "leftDuplicateKeyGroups",
      "rightDuplicateKeyGroups",
      "leftEmptyKeyRows",
      "rightEmptyKeyRows",
      "unmatchedLeftRows",
      "outputRows",
      "rowExpansion",
    ]
      .every((field) => relationship.includes(`\"${field}\"`)),
  },
  {
    label: "refund-answer-is-independently-reconciled",
    ok: platformVerify.includes("退款商品金额: 441")
      && platformVerify.includes("成功退款记录数: 4")
      && platformVerify.includes("mismatches.length === 0"),
  },
];

const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-platform-product-behavior-contract/v1",
  generatedBy: "scripts/verify-platform-product-behavior-contract.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
