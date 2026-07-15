import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentSemanticRootClarification } from "../src/components/AgentSemanticRootClarification";
import {
  parseSemanticPromptSelectors,
  withSemanticPathSelection,
  withSemanticRootSelection,
} from "../src/semanticPromptSelectors";

test("root ambiguity renders one actionable button for each distinct root candidate", () => {
  const html = renderToStaticMarkup(createElement(AgentSemanticRootClarification, {
    candidates: ["customers", "orders"],
    onSelect: () => undefined,
    tableNameByKey: new Map([
      ["customers", "客户表"],
      ["orders", "订单表"],
    ]),
  }));

  assert.match(html, /data-testid="agent-semantic-root-clarification"/);
  assert.equal((html.match(/data-testid="agent-semantic-root-candidate"/g) ?? []).length, 2);
  assert.match(html, /客户表 · customers/);
  assert.match(html, /订单表 · orders/);
  assert.doesNotMatch(html, /agent-semantic-root-candidate"[^>]*disabled/);
});

test("root and path retries replace stale selectors while preserving the other explicit choice", () => {
  const original = "按地区汇总销售额，使用根表 stale_root，使用关系路径 old_a > old_b，使用根表 older_root";
  const rootRetry = withSemanticRootSelection(original, "regions");
  assert.equal(rootRetry, "按地区汇总销售额，使用根表 regions，使用关系路径 old_a > old_b");

  const pathRetry = withSemanticPathSelection(
    `${rootRetry}，使用关系路径 stale_again`,
    ["regions_sites", "sites_orders"],
  );
  assert.equal(pathRetry, "按地区汇总销售额，使用根表 regions，使用关系路径 regions_sites > sites_orders");
  assert.deepEqual(parseSemanticPromptSelectors(pathRetry), {
    basePrompt: "按地区汇总销售额",
    rootTable: "regions",
    relationKeys: ["regions_sites", "sites_orders"],
  });
});

test("Agent callback chain forwards root selection and uses normalized prompt helpers", () => {
  const semanticPlanSource = readFileSync(new URL("../src/components/AgentSemanticPlan.tsx", import.meta.url), "utf8");
  const answerCardSource = readFileSync(new URL("../src/components/AgentAnswerCard.tsx", import.meta.url), "utf8");
  const panelSource = readFileSync(new URL("../src/components/AgentPanel.tsx", import.meta.url), "utf8");

  assert.match(semanticPlanSource, /requiresRootClarification/);
  assert.match(semanticPlanSource, /<AgentSemanticRootClarification candidates=\{rootCandidates\} onSelect=\{onSelectRoot\}/);
  assert.match(answerCardSource, /onSelectSemanticRoot\?: \(tableKey: string\) => void/);
  assert.match(answerCardSource, /onSelectRoot=\{onSelectSemanticRoot\}/);
  assert.match(panelSource, /onSelectSemanticRoot=\{\(tableKey\) =>/);
  assert.match(panelSource, /withSemanticRootSelection\(original, tableKey\)/);
  assert.match(panelSource, /withSemanticPathSelection\(original, relationKeys\)/);
  assert.doesNotMatch(panelSource, /submit\(`\$\{original\}，使用关系路径/);
});
