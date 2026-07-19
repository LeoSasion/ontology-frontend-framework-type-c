import type { AnalysisUnit, ChartAdapter, QueryPlanReceipt } from "../typesAgent";

export type AgentVisualizationKind = "metric" | "bar" | "line" | "pie" | "table" | "pareto";

export type AgentVisualizationPoint = {
  label: string;
  value: number;
  rank?: number;
  contribution?: number;
  cumulativeContribution?: number;
};

export type AgentVisualizationEvidence = {
  method?: string;
  populationEntityCount?: number;
  requestedHeadPercent?: number;
  actualEntityCount?: number;
  actualEntityPercent?: number;
  headContribution?: number;
  entitiesToReach80?: number;
  entityPercentToReach80?: number;
  tieBoundaryPreserved?: boolean;
};

export type AgentVisualizationModel = {
  kind: AgentVisualizationKind;
  sourceKind: string;
  title: string;
  points: AgentVisualizationPoint[];
  columns: string[];
  rows: Array<Record<string, unknown>>;
  dimensionColumn: string;
  measureColumn: string;
  measureLabel: string;
  displayedRowCount: number;
  receiptRowCount: number;
  populationEntityCount: number;
  evidence: AgentVisualizationEvidence;
  isPartialPareto: boolean;
  warnings: string[];
};

type TrustedAnswerRef = {
  resultState?: string;
  queryPlanReceipt?: QueryPlanReceipt;
  analysisUnitRef?: Pick<AnalysisUnit, "unitKey" | "kind" | "status" | "resultFingerprint">;
  chartAdapter?: ChartAdapter;
};

export type VisualizationGate = {
  allowed: boolean;
  blockers: string[];
};

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function finiteNumber(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  if (!/^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(normalized)) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function finiteInteger(value: unknown): number | undefined {
  const parsed = finiteNumber(value);
  return parsed !== null && Number.isInteger(parsed) ? parsed : undefined;
}

function normalizedRatio(value: unknown): number | undefined {
  const parsed = finiteNumber(value);
  if (parsed === null || parsed < 0) return undefined;
  return parsed <= 1 ? parsed : parsed <= 100 ? parsed / 100 : undefined;
}

function requiredString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const item = record(value);
  if (item) {
    return `{${Object.keys(item).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(item[key])}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? "undefined";
}

function pushUnless(blockers: string[], condition: boolean, blocker: string) {
  if (!condition) blockers.push(blocker);
}

export function evaluateTrustedReceiptGate(answer: TrustedAnswerRef): VisualizationGate {
  const receipt = answer.queryPlanReceipt;
  const validation = record(receipt?.validation);
  const coverage = record(receipt?.selection.executionCoverage);
  const resultState = requiredString(answer.resultState ?? receipt?.resultState ?? receipt?.status).toLowerCase();
  const blockers: string[] = [];

  pushUnless(blockers, resultState === "executed", "result-state-not-executed");
  pushUnless(blockers, receipt?.status === "executed", "receipt-not-executed");
  pushUnless(blockers, receipt?.resultState === "executed", "receipt-result-state-not-executed");
  pushUnless(blockers, validation?.executed === true, "receipt-validation-not-executed");
  pushUnless(blockers, validation?.canSupportBusinessConclusion === true, "business-conclusion-not-authorized");
  pushUnless(blockers, validation?.currentSourceRunMatches === true, "current-source-run-not-matched");
  pushUnless(blockers, Boolean(receipt?.source.currentSourceRunId), "current-source-run-missing");
  pushUnless(blockers, validation?.executionCoverageComplete === true, "execution-coverage-not-validated");
  pushUnless(blockers, coverage?.complete === true, "execution-coverage-incomplete");
  pushUnless(blockers, Number(receipt?.resultBinding?.rowCount ?? 0) > 0, "result-row-count-not-positive");
  pushUnless(blockers, Boolean(receipt?.resultBinding?.resultFingerprint), "result-fingerprint-missing");

  return { allowed: blockers.length === 0, blockers };
}

export function evaluateVisualizationGate(answer: TrustedAnswerRef, analysisUnit?: AnalysisUnit): VisualizationGate {
  const receiptGate = evaluateTrustedReceiptGate(answer);
  const receipt = answer.queryPlanReceipt;
  const ref = answer.analysisUnitRef;
  const adapter = answer.chartAdapter;
  const blockers = [...receiptGate.blockers];

  pushUnless(blockers, Boolean(analysisUnit), "analysis-unit-missing");
  pushUnless(blockers, analysisUnit?.status === "ready", "analysis-unit-not-ready");
  pushUnless(blockers, analysisUnit?.validation?.status === "ready", "analysis-unit-validation-not-ready");
  pushUnless(blockers, Boolean(ref), "analysis-unit-ref-missing");
  pushUnless(blockers, ref?.status === "ready", "analysis-unit-ref-not-ready");
  pushUnless(blockers, ref?.unitKey === analysisUnit?.unitKey, "analysis-unit-key-mismatch");
  pushUnless(blockers, ref?.resultFingerprint === analysisUnit?.resultFingerprint, "analysis-unit-ref-fingerprint-mismatch");
  pushUnless(blockers, analysisUnit?.workspaceId === receipt?.source.workspaceId, "analysis-unit-workspace-mismatch");
  pushUnless(blockers, analysisUnit?.queryReceiptKey === receipt?.receiptKey, "analysis-unit-receipt-mismatch");
  pushUnless(blockers, analysisUnit?.resultFingerprint === receipt?.resultBinding?.resultFingerprint, "analysis-unit-result-mismatch");
  pushUnless(blockers, analysisUnit?.rows.length === receipt?.resultBinding?.rowCount, "analysis-unit-row-count-mismatch");
  pushUnless(blockers, adapter?.status === "ready", "chart-adapter-not-ready");
  pushUnless(blockers, Boolean(adapter?.chartType), "chart-type-missing");
  pushUnless(blockers, adapter?.unitKey === analysisUnit?.unitKey, "chart-adapter-unit-mismatch");
  pushUnless(blockers, adapter?.queryReceiptKey === receipt?.receiptKey, "chart-adapter-receipt-mismatch");
  pushUnless(blockers, Boolean(adapter?.inputFingerprint), "chart-adapter-fingerprint-missing");
  pushUnless(blockers, adapter?.inputFingerprint === analysisUnit?.chartAdapter?.inputFingerprint, "chart-adapter-fingerprint-mismatch");
  pushUnless(blockers, adapter?.chartType === analysisUnit?.chartAdapter?.chartType, "chart-adapter-type-mismatch");
  pushUnless(blockers, canonicalJson(adapter?.allowedChartTypes) === canonicalJson(analysisUnit?.chartAdapter?.allowedChartTypes), "chart-adapter-allowlist-mismatch");
  pushUnless(blockers, canonicalJson(adapter?.config) === canonicalJson(analysisUnit?.chartAdapter?.config), "chart-adapter-config-mismatch");
  pushUnless(blockers, Boolean(adapter?.chartType && adapter.allowedChartTypes.includes(adapter.chartType)), "chart-type-not-allowed");

  return { allowed: blockers.length === 0, blockers: [...new Set(blockers)] };
}

function evidenceFromRefs(refs: Array<Record<string, unknown>>): AgentVisualizationEvidence {
  const methodRef = refs.find((item) => String(item.type ?? "").toLowerCase() === "apparelmethodresult")
    ?? refs.find((item) => record(item.evidence) && (item.method || record(item.evidence)?.populationEntityCount));
  if (!methodRef) return {};
  const evidence = record(methodRef.evidence) ?? methodRef;
  return {
    method: requiredString(methodRef.method ?? evidence.method) || undefined,
    populationEntityCount: finiteInteger(evidence.populationEntityCount ?? methodRef.populationRowCount),
    requestedHeadPercent: normalizedRatio(evidence.requestedHeadPercent),
    actualEntityCount: finiteInteger(evidence.actualEntityCount),
    actualEntityPercent: normalizedRatio(evidence.actualEntityPercent),
    headContribution: normalizedRatio(evidence.headContribution),
    entitiesToReach80: finiteInteger(evidence.entitiesToReach80),
    entityPercentToReach80: normalizedRatio(evidence.entityPercentToReach80),
    tieBoundaryPreserved: typeof evidence.tieBoundaryPreserved === "boolean" ? evidence.tieBoundaryPreserved : undefined,
  };
}

function rowLabel(row: Record<string, unknown>, dimensionColumn: string, index: number, fallbackLabel = ""): string {
  const value = row[dimensionColumn];
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (fallbackLabel) return fallbackLabel;
  return `#${index + 1}`;
}

function rowPoint(row: Record<string, unknown>, dimensionColumn: string, measureColumn: string, index: number, fallbackLabel = ""): AgentVisualizationPoint | null {
  const value = finiteNumber(row[measureColumn]);
  if (value === null) return null;
  return {
    label: rowLabel(row, dimensionColumn, index, fallbackLabel),
    value,
    rank: finiteInteger(row.rank),
    contribution: normalizedRatio(row.contribution),
    cumulativeContribution: normalizedRatio(row.cumulativeContribution),
  };
}

function hasValidPareto(points: AgentVisualizationPoint[]): boolean {
  if (points.length < 2 || points.some((point) => point.contribution === undefined || point.cumulativeContribution === undefined)) return false;
  let previous = 0;
  for (const point of points) {
    const cumulative = point.cumulativeContribution ?? -1;
    if (cumulative < previous || cumulative > 1 || (point.contribution ?? -1) < 0) return false;
    previous = cumulative;
  }
  return true;
}

function chartKind(unit: AnalysisUnit, adapter: ChartAdapter, points: AgentVisualizationPoint[], evidence: AgentVisualizationEvidence): AgentVisualizationKind {
  if (requiredString(evidence.method).toLowerCase() === "pareto" && hasValidPareto(points)) return "pareto";
  const requested = adapter.chartType;
  if (requested === "pie" && points.length > 6 && adapter.allowedChartTypes.includes("bar")) return "bar";
  if (requested === "line" && (points.length > 120 || points.length !== unit.rows.length)) return "table";
  if (requested === "bar" && (points.length > 20 || points.length !== unit.rows.length)) return "table";
  if (requested === "pie" && (points.length < 2 || points.length > 12 || points.some((point) => point.value < 0) || !points.reduce((sum, point) => sum + point.value, 0))) return "table";
  return requested === "metric" || requested === "bar" || requested === "line" || requested === "pie" || requested === "table" ? requested : "table";
}

export function buildAgentVisualizationModel(
  unit: AnalysisUnit,
  adapter: ChartAdapter,
  evidenceRefs: Array<Record<string, unknown>>,
): AgentVisualizationModel {
  const shape = record(unit.shape) ?? {};
  const config = record(adapter.config) ?? {};
  const grain = record(unit.grain) ?? {};
  const grainMeasures = Array.isArray(grain.measures) ? grain.measures : [];
  const declaredMeasure = record(grainMeasures[0]);
  const columns = Array.isArray(shape.columns) ? shape.columns.map(String) : [];
  const dimensionColumn = requiredString(config.dimension ?? shape.dimensionColumn);
  const measureColumn = requiredString(config.measure ?? shape.measureColumn);
  const measureLabel = requiredString(declaredMeasure?.field) || measureColumn;
  const warnings: string[] = [];
  const points = measureColumn && (dimensionColumn || adapter.chartType === "metric")
    ? unit.rows.map((row, index) => rowPoint(row, dimensionColumn, measureColumn, index, measureLabel)).filter((point): point is AgentVisualizationPoint => Boolean(point))
    : [];
  if (!dimensionColumn && adapter.chartType !== "metric") warnings.push("dimension-column-missing");
  if (!measureColumn) warnings.push("measure-column-missing");
  if (points.length !== unit.rows.length) warnings.push("non-numeric-or-unlabelled-rows-withheld");
  const evidence = evidenceFromRefs(evidenceRefs);
  const kind = chartKind(unit, adapter, points, evidence);
  const population = evidence.populationEntityCount ?? unit.rows.length;
  const lastCumulative = points.at(-1)?.cumulativeContribution;
  const isPartialPareto = kind === "pareto" && (population > unit.rows.length || lastCumulative === undefined || lastCumulative < 0.999999);
  if (kind === "table" && adapter.chartType !== "table") warnings.push("incompatible-graphic-fell-back-to-table");

  return {
    kind,
    sourceKind: unit.kind,
    title: unit.title,
    points,
    columns,
    rows: unit.rows,
    dimensionColumn,
    measureColumn,
    measureLabel,
    displayedRowCount: kind === "table" ? Math.min(unit.rows.length, 50) : points.length,
    receiptRowCount: unit.rows.length,
    populationEntityCount: population,
    evidence,
    isPartialPareto,
    warnings,
  };
}

export function tableCellText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number" && Number.isFinite(value)) return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 4 }).format(value);
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
