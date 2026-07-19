import assert from "node:assert/strict";
import test from "node:test";
import type { AnalysisUnit, ChartAdapter, QueryPlanReceipt } from "../src/typesAgent";
import {
  buildAgentVisualizationModel,
  evaluateTrustedReceiptGate,
  evaluateVisualizationGate,
} from "../src/components/agentAnswerVisualizationModel";

function fixture(rows: Array<Record<string, unknown>> = [
  { label: "SPU-01", value: 24000 },
  { label: "SPU-02", value: 18000 },
]) {
  const resultFingerprint = "result-fingerprint";
  const receipt: QueryPlanReceipt = {
    schema: "aibi-query-plan-receipt/v1",
    receiptKey: "receipt-1",
    request: "按款式排行",
    status: "executed",
    resultState: "executed",
    source: {
      workspaceId: "workspace-1",
      currentSourceRunId: "source-run-1",
      schemaFingerprint: "schema-1",
      dataFingerprint: "data-1",
    },
    selection: {
      group: "label",
      measure: "value",
      aggregation: "sum",
      filters: [],
      joins: [],
      executionCoverage: { complete: true },
    },
    runtime: { sqlIntent: "whitelist aggregate query" },
    validation: {
      executed: true,
      canSupportBusinessConclusion: true,
      currentSourceRunMatches: true,
      executionCoverageComplete: true,
    },
    resultBinding: {
      resultFingerprint,
      rowCount: rows.length,
      columns: Object.keys(rows[0] ?? {}),
      snapshotStored: true,
    },
    contextRefs: [],
    evidenceRefs: [],
    unresolved: [],
    createdAt: "2026-07-20T00:00:00Z",
  };
  const adapter: ChartAdapter = {
    schema: "aibi-chart-adapter/v1",
    status: "ready",
    unitKey: "unit-1",
    queryReceiptKey: receipt.receiptKey,
    chartType: "bar",
    allowedChartTypes: ["bar", "table"],
    config: { dimension: "label", measure: "value", barOrientation: "horizontal" },
    rationale: [],
    blockers: [],
    inputFingerprint: "adapter-fingerprint",
  };
  const unit: AnalysisUnit = {
    schema: "aibi-analysis-unit/v1",
    unitKey: adapter.unitKey,
    workspaceId: "workspace-1",
    queryReceiptKey: receipt.receiptKey,
    kind: "ranking",
    status: "ready",
    title: "款式销售排行",
    definitionFingerprint: "definition-1",
    resultFingerprint,
    grain: {},
    shape: {
      rowCount: rows.length,
      columns: Object.keys(rows[0] ?? {}),
      dimensionColumn: "label",
      measureColumn: "value",
    },
    rows,
    calculation: {},
    validation: { status: "ready", blockers: [], warnings: [], checks: { receiptExecuted: true } },
    chartAdapter: adapter,
    createdAt: "2026-07-20T00:00:00Z",
    updatedAt: "2026-07-20T00:00:00Z",
  };
  const answer = {
    resultState: "executed",
    queryPlanReceipt: receipt,
    analysisUnitRef: {
      unitKey: unit.unitKey,
      kind: unit.kind,
      status: unit.status,
      resultFingerprint: unit.resultFingerprint,
    },
    chartAdapter: adapter,
  };
  return { receipt, adapter, unit, answer };
}

test("visualization opens only for a fully bound executed receipt", () => {
  const { answer, unit } = fixture();
  assert.deepEqual(evaluateTrustedReceiptGate(answer), { allowed: true, blockers: [] });
  assert.deepEqual(evaluateVisualizationGate(answer, unit), { allowed: true, blockers: [] });
});

test("every non-executed state fails closed and cannot retain a chart", () => {
  for (const resultState of ["draft", "blocked", "simulation", "stale", "unknown"]) {
    const { answer, unit } = fixture();
    assert.equal(evaluateVisualizationGate({ ...answer, resultState }, unit).allowed, false, resultState);
  }
});

test("missing trust flags and mismatched receipt bindings are blockers", () => {
  const { answer, unit, receipt, adapter } = fixture();
  const unsafeReceipt = { ...receipt, validation: { ...receipt.validation, currentSourceRunMatches: undefined } };
  assert.ok(evaluateTrustedReceiptGate({ ...answer, queryPlanReceipt: unsafeReceipt }).blockers.includes("current-source-run-not-matched"));
  assert.ok(evaluateVisualizationGate(answer, { ...unit, resultFingerprint: "other" }).blockers.includes("analysis-unit-ref-fingerprint-mismatch"));
  assert.ok(evaluateVisualizationGate(answer, { ...unit, rows: [...unit.rows, { label: "SPU-03", value: 1 }] }).blockers.includes("analysis-unit-row-count-mismatch"));
  assert.ok(evaluateVisualizationGate(answer, { ...unit, workspaceId: "other-workspace" }).blockers.includes("analysis-unit-workspace-mismatch"));
  assert.ok(evaluateVisualizationGate({ ...answer, chartAdapter: { ...adapter, config: { ...adapter.config, measure: "other" } } }, unit).blockers.includes("chart-adapter-config-mismatch"));
});

test("single-row metrics render without inventing a dimension", () => {
  const { unit, adapter } = fixture([{ sales_amount: 42000 }]);
  const metricAdapter: ChartAdapter = {
    ...adapter,
    chartType: "metric",
    allowedChartTypes: ["metric", "table"],
    config: { dimension: null, measure: "sales_amount" },
  };
  const metricUnit: AnalysisUnit = {
    ...unit,
    kind: "metric",
    grain: { measures: [{ field: "sales_amount" }] },
    shape: { rowCount: 1, columns: ["sales_amount"], dimensionColumn: null, measureColumn: "sales_amount" },
    chartAdapter: metricAdapter,
  };
  const model = buildAgentVisualizationModel(metricUnit, metricAdapter, []);
  assert.equal(model.kind, "metric");
  assert.deepEqual(model.points.map((point) => [point.label, point.value]), [["sales_amount", 42000]]);
});

test("ranking preserves receipt row order and exact numeric values", () => {
  const { unit, adapter } = fixture([
    { label: "SPU-B", value: 18, rank: 2 },
    { label: "SPU-A", value: 24, rank: 1 },
  ]);
  const model = buildAgentVisualizationModel(unit, adapter, []);
  assert.equal(model.kind, "bar");
  assert.deepEqual(model.points.map((point) => [point.label, point.value, point.rank]), [
    ["SPU-B", 18, 2],
    ["SPU-A", 24, 1],
  ]);
});

test("invalid values never become zero and graphical output falls back to table", () => {
  const { unit, adapter } = fixture([
    { label: "SPU-A", value: 24 },
    { label: "SPU-B", value: "¥18" },
  ]);
  const model = buildAgentVisualizationModel(unit, adapter, []);
  assert.equal(model.kind, "table");
  assert.deepEqual(model.points.map((point) => point.value), [24]);
  assert.ok(model.warnings.includes("non-numeric-or-unlabelled-rows-withheld"));
});

test("partial Pareto rows render only a disclosed boundary proof", () => {
  const rows = [
    { label: "SPU-01", value: 24000, rank: 1, contribution: 0.308, cumulativeContribution: 0.308 },
    { label: "SPU-02", value: 18000, rank: 2, contribution: 0.23, cumulativeContribution: 0.538 },
    { label: "SPU-03", value: 12000, rank: 3, contribution: 0.154, cumulativeContribution: 0.692 },
    { label: "SPU-04", value: 8000, rank: 4, contribution: 0.103, cumulativeContribution: 0.795 },
    { label: "SPU-05", value: 5000, rank: 5, contribution: 0.064, cumulativeContribution: 0.859 },
  ];
  const { unit, adapter } = fixture(rows);
  const model = buildAgentVisualizationModel(unit, adapter, [{
    type: "apparelMethodResult",
    method: "pareto",
    evidence: {
      populationEntityCount: 10,
      requestedHeadPercent: 0.2,
      actualEntityCount: 3,
      actualEntityPercent: 0.3,
      headContribution: 0.538,
      entitiesToReach80: 5,
      entityPercentToReach80: 0.5,
    },
  }]);
  assert.equal(model.kind, "pareto");
  assert.equal(model.isPartialPareto, true);
  assert.equal(model.populationEntityCount, 10);
  assert.equal(model.receiptRowCount, 5);
  assert.equal(model.evidence.actualEntityCount, 3);
  assert.equal(model.evidence.headContribution, 0.538);
});

test("concentration rows with cumulative columns remain concentration, not Pareto", () => {
  const rows = [
    { label: "SPU-01", value: 24000, rank: 1, contribution: 0.6, cumulativeContribution: 0.6 },
    { label: "SPU-02", value: 16000, rank: 2, contribution: 0.4, cumulativeContribution: 1 },
  ];
  const { unit, adapter } = fixture(rows);
  const model = buildAgentVisualizationModel(unit, adapter, [{
    type: "apparelMethodResult",
    method: "concentration",
    evidence: { populationEntityCount: 10, headContribution: 0.6 },
  }]);
  assert.equal(model.kind, "bar");
  assert.equal(model.isPartialPareto, false);
});
