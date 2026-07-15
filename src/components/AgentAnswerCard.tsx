import { lazy, Suspense } from "react";
import type { AgentAskResult } from "../types";
import { confidenceText, evidenceRefText, pairText, type AnswerEvidenceStep } from "../agentPanelModel";
import { formatBusinessValue } from "../businessPresentation";
import { Bilingual, biText } from "./Bilingual";

const AgentProviderNarrative = lazy(() => import("./AgentProviderNarrative").then((module) => ({ default: module.AgentProviderNarrative })));
const AgentSemanticPlan = lazy(() => import("./AgentSemanticPlan").then((module) => ({ default: module.AgentSemanticPlan })));

type AgentAnswerCardProps = {
  answerCard: NonNullable<AgentAskResult["answerCard"]>;
  answerEvidenceSteps: AnswerEvidenceStep[];
  answerQuery: Record<string, unknown> | null;
  onAskCandidate?: (prompt: string) => void;
  onSelectSemanticCandidates?: (candidates: import("../typesAgent").SemanticFieldCandidate[]) => void;
  providerResponse?: AgentAskResult["llm"]["response"];
  intentFrame?: AgentAskResult["intentFrame"];
  clarificationBundle?: AgentAskResult["clarification"];
  semanticPlan?: AgentAskResult["semanticPlan"];
  executionPlan?: AgentAskResult["executionPlan"];
  tableNameByKey?: Map<string, string>;
  queryRuntimeRef?: Record<string, unknown>;
  runtimeEngine: string;
  onExportAnalysis?: () => void;
  analysisExportStatus?: "idle" | "exporting" | "ready" | "error";
  analysisExportMessage?: string;
};

function widgetTypeText(widgetType?: string) {
  if (widgetType === "line") return biText("折线图", "line chart");
  if (widgetType === "pie") return biText("饼图", "pie chart");
  if (widgetType === "metric") return biText("指标卡", "metric card");
  if (widgetType === "table") return biText("明细表", "table");
  if (widgetType === "slicer") return biText("筛选器", "slicer");
  return biText("柱状图", "bar chart");
}

function analysisKindText(kind?: string) {
  if (kind === "metric") return biText("指标", "metric");
  if (kind === "trend") return biText("趋势", "trend");
  if (kind === "composition") return biText("构成", "composition");
  if (kind === "ranking") return biText("排名", "ranking");
  if (kind === "anomaly") return biText("异常", "anomaly");
  return biText("比较", "comparison");
}

function rowFieldValues(rows: Array<Record<string, unknown>>, role: string) {
  return rows
    .filter((row) => String(row.role ?? "") === role)
    .map((row) => String(row.field ?? "").trim())
    .filter(Boolean);
}

function intentTypeText(taskType?: string) {
  const labels: Record<string, string> = {
    overview: biText("概览", "Overview"), comparison: biText("比较", "Comparison"), trend: biText("趋势", "Trend"),
    composition: biText("构成", "Composition"), ranking: biText("排名", "Ranking"), anomaly: biText("异常核查", "Anomaly"),
    reconciliation: biText("对账", "Reconciliation"), diagnosis: biText("诊断", "Diagnosis"),
  };
  return labels[taskType ?? ""] ?? taskType ?? biText("分析", "Analysis");
}

export function AgentAnswerCard({ answerCard, answerEvidenceSteps, answerQuery, clarificationBundle, executionPlan, intentFrame, onAskCandidate, onSelectSemanticCandidates, providerResponse, queryRuntimeRef, runtimeEngine, semanticPlan, tableNameByKey, onExportAnalysis, analysisExportStatus = "idle", analysisExportMessage = "" }: AgentAnswerCardProps) {
  const fallbackReason = queryRuntimeRef?.fallbackReason ?? answerQuery?.fallbackReason;
  const clarification = answerCard.clarification?.kind === "widget-fields" ? answerCard.clarification : null;
  const candidateMeasures = clarification?.candidateMeasures?.length ? clarification.candidateMeasures : rowFieldValues(answerCard.rows, "measure");
  const candidateDimensions = clarification?.candidateDimensions?.length ? clarification.candidateDimensions : rowFieldValues(answerCard.rows, "dimension");
  const chartType = widgetTypeText(clarification?.widgetType);
  const defaultDimension = candidateDimensions[0] ?? "";
  const defaultMeasure = candidateMeasures[0] ?? "";

  function candidatePrompt(role: "measure" | "dimension", field: string) {
    if (role === "measure") {
      return defaultDimension
        ? biText(`用 ${field} 按 ${defaultDimension} 做${chartType}`, `Build a ${chartType} with ${field} by ${defaultDimension}`)
        : biText(`用 ${field} 做${chartType}`, `Build a ${chartType} with ${field}`);
    }
    return defaultMeasure
      ? biText(`用 ${defaultMeasure} 按 ${field} 做${chartType}`, `Build a ${chartType} with ${defaultMeasure} by ${field}`)
      : biText(`按 ${field} 分组做${chartType}`, `Build a ${chartType} grouped by ${field}`);
  }

  return (
    <article className="agentAnswerCard" data-testid="agent-answer-card">
      <div className="agentAnswerLead">
        <div>
          <p className="kicker">{biText("业务回答", "Business answer")}</p>
          <h3>{pairText(answerCard.title)}</h3>
          <p>{pairText(answerCard.summary)}</p>
        </div>
        <span className="statusPill compact">{confidenceText(answerCard.confidence)}</span>
      </div>
      {providerResponse?.summary ? (
        <Suspense fallback={null}>
          <AgentProviderNarrative response={providerResponse} />
        </Suspense>
      ) : null}
      {intentFrame ? (
        <details className="agentIntentFrame" data-testid="agent-intent-frame" open={Boolean(clarificationBundle?.required)}>
          <summary>
            <span>{biText("我理解的问题", "My understanding")}</span>
            <strong>{intentTypeText(intentFrame.taskType)}</strong>
          </summary>
          <div className="agentIntentFrameBody">
            <div className="agentIntentChips">
              {intentFrame.measureConcepts.map((item) => <span key={`measure-${item.tableKey}-${item.field}`}>{biText("指标", "Measure")} · {item.tableKey}.{item.field}</span>)}
              {intentFrame.dimensionConcepts.map((item) => <span key={`dimension-${item.tableKey}-${item.field}`}>{biText("维度", "Dimension")} · {item.tableKey}.{item.field}</span>)}
              {intentFrame.timeScope?.expression ? <span>{biText("时间", "Time")} · {intentFrame.timeScope.expression}</span> : null}
              <span>{biText("输出", "Output")} · {intentFrame.requestedOutput}</span>
              <span>{biText("粒度", "Grain")} · {intentFrame.grainExpectation.description}</span>
            </div>
            {clarificationBundle?.required ? <p>{clarificationBundle.message}</p> : <p>{biText("字段均保留表级来源；写入仍需确认。", "Every field keeps table provenance; writes still require confirmation.")}</p>}
          </div>
        </details>
      ) : null}
      {semanticPlan && semanticPlan.status !== "not-applicable" ? (
        <Suspense fallback={null}>
          <AgentSemanticPlan executionPlan={executionPlan} onSelectCandidates={onSelectSemanticCandidates} plan={semanticPlan} tableNameByKey={tableNameByKey} />
        </Suspense>
      ) : null}
      <div className="agentAnswerMetrics">
        {answerCard.metrics.map((metric, index) => (
          <div key={`${pairText(metric.label)}-${index}`}>
            <span>{pairText(metric.label)}</span>
            <strong>{formatBusinessValue(metric.value)}</strong>
          </div>
        ))}
      </div>
      {answerCard.rows.length && !clarification ? (
        <div className="agentAnswerRows" data-testid="agent-answer-rows">
          {answerCard.rows.slice(0, 5).map((row, index) => (
            <div key={`${String(row.label ?? index)}-${index}`}>
              <span>{String(row.label ?? biText("合计", "Total"))}</span>
              <strong>{formatBusinessValue(row.value)}</strong>
            </div>
          ))}
        </div>
      ) : null}
      {clarification ? (
        <div className="agentClarificationChoices" data-testid="agent-clarification-choices">
          {candidateMeasures.length ? (
            <div>
              <strong>{biText("选择指标", "Choose measure")}</strong>
              <div className="agentClarificationChipGrid">
                {candidateMeasures.map((field) => (
                  <button className="miniButton" data-testid="agent-clarification-measure" disabled={!onAskCandidate} key={`measure-${field}`} onClick={() => onAskCandidate?.(candidatePrompt("measure", field))} type="button">
                    {field}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {candidateDimensions.length ? (
            <div>
              <strong>{biText("选择分组", "Choose grouping")}</strong>
              <div className="agentClarificationChipGrid">
                {candidateDimensions.map((field) => (
                  <button className="miniButton" data-testid="agent-clarification-dimension" disabled={!onAskCandidate} key={`dimension-${field}`} onClick={() => onAskCandidate?.(candidatePrompt("dimension", field))} type="button">
                    {field}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
      {answerCard.analysisUnitRef && answerCard.chartAdapter ? (
        <div className={`agentAnalysisUnitStrip ${answerCard.chartAdapter.status}`} data-testid="agent-analysis-unit-strip">
          <div>
            <span className="storyMode"><Bilingual zh="可复算分析单元" en="Recomputable analysis unit" /></span>
            <strong>
              {analysisKindText(answerCard.analysisUnitRef.kind)}
              {answerCard.chartAdapter.status === "ready" && answerCard.chartAdapter.chartType
                ? ` · ${widgetTypeText(answerCard.chartAdapter.chartType)}`
                : ` · ${biText("图表已阻断", "chart blocked")}`}
            </strong>
            <small>{answerCard.analysisUnitRef.unitKey} · {answerCard.analysisUnitRef.resultFingerprint.slice(0, 12)}</small>
          </div>
          <details>
            <summary>{biText("查看适配依据", "View adaptation rationale")}</summary>
            <ul>
              {(answerCard.chartAdapter.status === "ready"
                ? answerCard.chartAdapter.rationale
                : answerCard.chartAdapter.blockers).map((item) => <li key={item}>{item}</li>)}
            </ul>
          </details>
          {answerCard.analysisUnitRef.status === "ready" ? (
            <div className="agentAnalysisUnitExport">
              <button
                className="miniButton"
                data-testid="agent-analysis-export"
                disabled={!onExportAnalysis || analysisExportStatus === "exporting"}
                onClick={onExportAnalysis}
                type="button"
              >
                {analysisExportStatus === "exporting"
                  ? biText("正在导出…", "Exporting…")
                  : biText("导出 Excel + 报告", "Export Excel + report")}
              </button>
              {analysisExportMessage ? <small className={analysisExportStatus}>{analysisExportMessage}</small> : null}
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="agentAnswerEvidenceRoute" data-testid="agent-answer-evidence-route">
        <div className="agentAnswerEvidenceRouteLead">
          <span className="storyMode"><Bilingual zh="证据路线" en="Evidence route" /></span>
          <strong><Bilingual zh="先看结论，再追到数据、口径和查询回执" en="Read the answer first, then trace source, metric, and query receipt" /></strong>
        </div>
        <div className="agentAnswerEvidenceSteps" data-testid="agent-answer-evidence-steps">
          {answerEvidenceSteps.map((item) => (
            <div className={item.tone} data-testid={`agent-answer-evidence-route-${item.key}`} key={item.key}>
              <span>{item.badge}</span>
              <strong>{item.label}</strong>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
        {runtimeEngine || answerQuery?.sqlIntent || fallbackReason ? (
          <details className="agentAnswerRuntimeTechnical" data-testid="agent-answer-runtime-technical">
            <summary>{biText("查看查询回执技术信息", "View query receipt technical details")}</summary>
            <div>
              {runtimeEngine ? <span>{biText("执行引擎", "Engine")}: {runtimeEngine}</span> : null}
              {answerQuery?.sqlIntent ? <span>{biText("查询意图", "Query intent")}: {String(answerQuery.sqlIntent)}</span> : null}
              {fallbackReason ? <span>{biText("降级说明", "Fallback")}: {String(fallbackReason)}</span> : null}
            </div>
          </details>
        ) : null}
      </div>
      <div className="agentAnswerFooter">
        <div>
          <strong>{biText("证据", "Evidence")}</strong>
          <ul>
            {answerCard.evidenceRefs.slice(0, 4).map((ref, index) => (
              <li key={`${String(ref.type ?? "evidence")}-${index}`}>{evidenceRefText(ref)}</li>
            ))}
          </ul>
        </div>
        <div>
          <strong>{biText("下一步", "Next")}</strong>
          <ul>
            {answerCard.nextActions.slice(0, 3).map((action, index) => (
              <li key={`${pairText(action)}-${index}`}>{pairText(action)}</li>
            ))}
          </ul>
        </div>
      </div>
    </article>
  );
}
