import { lazy, Suspense } from "react";
import type { AgentAskResult } from "../types";
import { confidenceText, evidenceRefText, pairText, type AnswerEvidenceStep } from "../agentPanelModel";
import { formatBusinessValue } from "../businessPresentation";
import { Bilingual, biText } from "./Bilingual";

const AgentProviderNarrative = lazy(() => import("./AgentProviderNarrative").then((module) => ({ default: module.AgentProviderNarrative })));
const AgentSemanticPlan = lazy(() => import("./AgentSemanticPlan").then((module) => ({ default: module.AgentSemanticPlan })));
const AgentEvidencePlan = lazy(() => import("./AgentEvidencePlan").then((module) => ({ default: module.AgentEvidencePlan })));

type AgentAnswerCardProps = {
  answerCard: NonNullable<AgentAskResult["answerCard"]>;
  answerEvidenceSteps: AnswerEvidenceStep[];
  answerQuery: Record<string, unknown> | null;
  onAskCandidate?: (prompt: string) => void;
  onSelectSemanticCandidates?: (candidates: import("../typesAgent").SemanticFieldCandidate[]) => void;
  onSelectSemanticRoot?: (tableKey: string) => void;
  onSelectSemanticPath?: (relationKeys: string[]) => void;
  providerResponse?: AgentAskResult["llm"]["response"];
  intentFrame?: AgentAskResult["intentFrame"];
  businessUnderstanding?: AgentAskResult["businessUnderstanding"];
  clarificationBundle?: AgentAskResult["clarification"];
  evidencePlan?: AgentAskResult["evidencePlan"];
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

type BusinessUnderstanding = NonNullable<AgentAskResult["businessUnderstanding"]>;
type BusinessClarification = NonNullable<BusinessUnderstanding["activeClarification"]>;

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function understandingText(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value.trim() || fallback;
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") return String(value);
  if (Array.isArray(value)) {
    const items = value.map((item) => understandingText(item)).filter(Boolean);
    return items.length ? items.join(biText("、", ", ")) : fallback;
  }
  const record = objectValue(value);
  if (!record) return fallback;
  const zh = typeof record.zh === "string" ? record.zh.trim() : "";
  const en = typeof record.en === "string" ? record.en.trim() : "";
  if (zh || en) return biText(zh || en, en || zh);
  for (const key of ["displayValue", "label", "question", "message", "mention", "value", "reason", "name", "slotKey", "kind", "code"]) {
    const text = understandingText(record[key]);
    if (text) return text;
  }
  return fallback;
}

function understandingStatusText(status?: string) {
  const normalized = String(status ?? "").toLowerCase();
  if (["ready", "resolved", "completed", "grounded"].includes(normalized)) return biText("已理解", "Understood");
  if (["blocked", "failed"].includes(normalized)) return biText("已阻断", "Blocked");
  if (["needs-clarification", "clarification-required", "ambiguous"].includes(normalized)) return biText("需澄清", "Needs clarification");
  if (["partial", "incomplete"].includes(normalized)) return biText("部分理解", "Partially understood");
  return biText("正在核对", "Checking");
}

function businessSignalText(signal: string) {
  const labels: Record<string, string> = {
    "underspecified-question": biText("问题范围未完整", "Question scope incomplete"),
    "ratio-request": biText("比率指标", "Ratio metric"),
    "distinct-count-request": biText("去重统计", "Distinct count"),
    "unresolved-field": biText("字段待确认", "Field unresolved"),
    "cross-table-request": biText("跨表分析", "Cross-table analysis"),
    "time-comparison": biText("时间对比", "Time comparison"),
    "comparison-request": biText("对比分析", "Comparison"),
    "data-quality-risk": biText("数据质量风险", "Data-quality risk"),
  };
  return labels[signal] ?? signal;
}

function businessSlotText(slotKey: string, fallback?: unknown) {
  const labels: Record<string, string> = {
    "decision-goal": biText("分析目的", "Decision goal"),
    measure: biText("指标字段", "Measure"),
    dimension: biText("分析维度", "Dimension"),
    "time-scope": biText("时间范围", "Time scope"),
    "time-field": biText("时间字段", "Time field"),
    "comparison-baseline": biText("对比基线", "Comparison baseline"),
    "output-purpose": biText("输出形式", "Output purpose"),
    population: biText("统计范围", "Population"),
    grain: biText("统计粒度", "Grain"),
    "entity-key": biText("去重主键", "Entity key"),
    "term-definition": biText("业务术语", "Business term"),
    "field-binding": biText("字段绑定", "Field binding"),
    "business-rule": biText("业务规则", "Business rule"),
    unit: biText("单位", "Unit"),
    "null-policy": biText("空值规则", "Null policy"),
    "status-meaning": biText("状态含义", "Status meaning"),
    "filter-semantics": biText("筛选口径", "Filter semantics"),
    "metric-concept": biText("指标概念", "Metric concept"),
    numerator: biText("分子", "Numerator"),
    denominator: biText("分母", "Denominator"),
    "relationship-path": biText("关联路径", "Relationship path"),
    "source-profile": biText("数据画像", "Source profile"),
  };
  return labels[slotKey] ?? understandingText(fallback, slotKey);
}

function businessReasonText(reason: unknown, fallback = "") {
  const raw = understandingText(reason, fallback);
  const labels: Record<string, string> = {
    "required-by-understanding-skill": biText("需要业务定义", "Business definition needed"),
    "multiple-field-candidates": biText("存在多个字段候选", "Multiple field candidates"),
    "missing-numerator-denominator": biText("缺少分子与分母", "Numerator and denominator missing"),
    "unverified-relationship-path": biText("关联路径尚未验证", "Relationship path unverified"),
  };
  return labels[raw] ?? raw;
}

function businessSourceText(source: unknown) {
  const raw = understandingText(source);
  const labels: Record<string, string> = {
    "explicit-question": biText("用户问题", "User question"),
    "explicit-output-intent": biText("用户指定", "User requested"),
    "explicit-business-definition": biText("用户定义", "User definition"),
    "business-question": biText("用户问题", "User question"),
    "semantic-field": biText("语义字段", "Semantic field"),
    "semantic-fields": biText("语义字段", "Semantic fields"),
    "confirmed-context-term": biText("已确认术语", "Confirmed term"),
    "confirmed-context-rule": biText("已确认规则", "Confirmed rule"),
    "domain-pack-rule": biText("领域规则", "Domain rule"),
    "domain-pack-metric-definition": biText("指标定义", "Metric definition"),
    "domain-pack-business-definition": biText("业务定义", "Business definition"),
    "verified-semantic-path": biText("已验证关联", "Verified relationship"),
    "verified-comparison-plan": biText("已验证时间窗", "Verified windows"),
  };
  return labels[raw] ?? raw;
}

function understandingTone(status?: string) {
  const normalized = String(status ?? "").toLowerCase();
  if (["blocked", "failed"].includes(normalized)) return "blocked";
  if (["needs-clarification", "clarification-required", "ambiguous", "partial", "incomplete"].includes(normalized)) return "clarifying";
  return "ready";
}

function activeBusinessClarification(frame: BusinessUnderstanding): BusinessClarification | null {
  if (frame.activeClarification) return frame.activeClarification;
  if (frame.clarification?.active) return frame.clarification.active;
  return frame.clarifications?.find((item) => item.active)
    ?? frame.clarification?.items?.[0]
    ?? frame.unresolved?.[0]
    ?? null;
}

function businessClarificationQuestion(item: BusinessClarification | null) {
  if (!item) return "";
  const explicit = understandingText(item.questionLocalized ?? item.question);
  if (explicit) return explicit;
  const mention = understandingText(item.mention);
  if (mention) return biText(`请确认“${mention}”具体指什么。`, `Please clarify what “${mention}” means.`);
  return understandingText(item.reason, biText("请补充完成分析所需的业务定义。", "Add the business definition needed to continue."));
}

function businessBlockerText(value: string | Record<string, unknown>) {
  if (typeof value === "string") return businessReasonText(value);
  const kind = understandingText(value.kind);
  const kindText = kind === "business-slot" ? biText("业务槽位", "Business slot") : kind;
  const mention = understandingText(value.mention);
  const parts = [value.code, kindText, mention ? businessSlotText(mention, mention) : "", businessReasonText(value.reason), value.message]
    .map((item) => understandingText(item))
    .filter(Boolean);
  return [...new Set(parts)].join(" · ") || biText("业务定义仍不完整", "Business definition is still incomplete");
}

function IntentFrameChips({ frame }: { frame: NonNullable<AgentAskResult["intentFrame"]> }) {
  return (
    <div className="agentIntentChips">
      {frame.measureConcepts.map((item) => <span key={`measure-${item.tableKey}-${item.field}`}>{biText("指标", "Measure")} · {item.tableKey}.{item.field}</span>)}
      {frame.dimensionConcepts.map((item) => <span key={`dimension-${item.tableKey}-${item.field}`}>{biText("维度", "Dimension")} · {item.tableKey}.{item.field}</span>)}
      {frame.timeScope?.expression ? <span>{biText("时间", "Time")} · {frame.timeScope.expression}</span> : null}
      <span>{biText("输出", "Output")} · {frame.requestedOutput}</span>
      <span>{biText("粒度", "Grain")} · {frame.grainExpectation.description}</span>
    </div>
  );
}

export function AgentAnswerCard({ answerCard, answerEvidenceSteps, answerQuery, businessUnderstanding, clarificationBundle, evidencePlan, executionPlan, intentFrame, onAskCandidate, onSelectSemanticCandidates, onSelectSemanticPath, onSelectSemanticRoot, providerResponse, queryRuntimeRef, runtimeEngine, semanticPlan, tableNameByKey, onExportAnalysis, analysisExportStatus = "idle", analysisExportMessage = "" }: AgentAnswerCardProps) {
  const fallbackReason = queryRuntimeRef?.fallbackReason ?? answerQuery?.fallbackReason;
  const clarification = answerCard.clarification?.kind === "widget-fields" ? answerCard.clarification : null;
  const candidateMeasures = clarification?.candidateMeasures?.length ? clarification.candidateMeasures : rowFieldValues(answerCard.rows, "measure");
  const candidateDimensions = clarification?.candidateDimensions?.length ? clarification.candidateDimensions : rowFieldValues(answerCard.rows, "dimension");
  const chartType = widgetTypeText(clarification?.widgetType);
  const defaultDimension = candidateDimensions[0] ?? "";
  const defaultMeasure = candidateMeasures[0] ?? "";
  const explicitUnderstandingSlots = businessUnderstanding
    ? Object.entries(businessUnderstanding.slots ?? {}).map(([slotKey, slotValue]) => {
      const record = objectValue(slotValue) ?? { value: slotValue };
      const status = String(record.status ?? (record.value == null ? "missing" : "resolved"));
      return {
        slotKey: String(record.slotKey ?? slotKey),
        status,
        label: record.label,
        displayValue: record.displayValue,
        value: record.value,
        reason: record.reason,
        source: record.source,
      };
    })
    : [];
  const unresolvedUnderstandingBySlot = new Map(
    (businessUnderstanding?.unresolved ?? [])
      .map((item) => [String(item.slot ?? item.mention ?? "").trim(), item] as const)
      .filter(([slotKey]) => Boolean(slotKey)),
  );
  const declaredMissingSlots = (businessUnderstanding?.missingSlots ?? [])
    .map((slotKey) => String(slotKey).trim())
    .filter(Boolean)
    .filter((slotKey) => !explicitUnderstandingSlots.some((slot) => slot.slotKey === slotKey))
    .map((slotKey) => {
      const unresolved = unresolvedUnderstandingBySlot.get(slotKey);
      return {
        slotKey,
        status: "missing",
        label: unresolved?.mention ?? slotKey,
        displayValue: undefined,
        value: undefined,
        reason: unresolved?.reason ?? "required-by-understanding-skill",
        source: undefined,
      };
    });
  const understandingSlots = [...explicitUnderstandingSlots, ...declaredMissingSlots];
  const resolvedSlots = understandingSlots.filter((slot) => ["resolved", "ready", "filled", "grounded"].includes(slot.status.toLowerCase()));
  const unresolvedSlots = understandingSlots.filter((slot) => !["resolved", "ready", "filled", "grounded"].includes(slot.status.toLowerCase()));
  const activeUnderstandingClarification = businessUnderstanding ? activeBusinessClarification(businessUnderstanding) : null;
  const activeQuestion = businessClarificationQuestion(activeUnderstandingClarification)
    || (clarificationBundle?.required ? understandingText(clarificationBundle.message) : "");
  const understandingBlockers = (businessUnderstanding?.blockers ?? []).map(businessBlockerText).filter(Boolean);
  const understandingNeedsAttention = Boolean(
    activeQuestion
    || unresolvedSlots.length
    || understandingBlockers.length
    || clarificationBundle?.required
    || (businessUnderstanding && understandingTone(businessUnderstanding.status) !== "ready"),
  );

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
      {intentFrame || businessUnderstanding ? (
        <details className={`agentIntentFrame ${businessUnderstanding ? understandingTone(businessUnderstanding.status) : "ready"}`} data-testid="agent-intent-frame" open={understandingNeedsAttention}>
          <summary>
            <span>{biText("我理解的问题", "My understanding")}</span>
            <strong className="agentUnderstandingStatus">
              {businessUnderstanding ? understandingStatusText(businessUnderstanding.status) : intentTypeText(intentFrame?.taskType)}
            </strong>
          </summary>
          <div className="agentIntentFrameBody">
            {businessUnderstanding ? (
              <>
                <div className="agentUnderstandingOverview">
                  <div className="agentUnderstandingSignals" data-testid="agent-understanding-signals">
                    <span>{biText("触发信号", "Trigger signals")}</span>
                    {businessUnderstanding.signals?.length ? (
                      <ul aria-label={biText("已识别的业务信号", "Recognized business signals")}>
                        {businessUnderstanding.signals.slice(0, 5).map((signal, index) => {
                          const record = objectValue(signal);
                          const kind = understandingText(record?.kind);
                          const label = understandingText(record?.label ?? record?.mention ?? record?.value ?? record?.signalKey ?? signal, kind);
                          const raw = understandingText(record?.signalKey, kind || label);
                          const kindLabel = businessSignalText(kind);
                          const valueLabel = businessSignalText(label || raw);
                          return <li key={`${raw}-${index}`}>{kind && kind !== label ? `${kindLabel} · ${valueLabel}` : valueLabel}</li>;
                        })}
                        {businessUnderstanding.signals.length > 5 ? <li>+{businessUnderstanding.signals.length - 5}</li> : null}
                      </ul>
                    ) : <small>{biText("暂无显式业务信号", "No explicit business signals")}</small>}
                  </div>
                  <div className="agentUnderstandingSlotSummary" data-testid="agent-understanding-slot-summary">
                    <span>{biText("业务槽位", "Business slots")}</span>
                    <strong>{resolvedSlots.length} {biText("已解析", "resolved")} · {unresolvedSlots.length} {biText("待确认", "open")}</strong>
                  </div>
                </div>
                {understandingSlots.length ? (
                  <div className="agentUnderstandingSlots">
                    {resolvedSlots.length ? (
                      <section aria-label={biText("已解析槽位", "Resolved slots")}>
                        <span>{biText("已解析", "Resolved")}</span>
                        <ul>
                          {resolvedSlots.slice(0, 6).map((slot) => (
                            <li key={slot.slotKey}>
                              <span>{businessSlotText(slot.slotKey, slot.label)}</span>
                              <strong>
                                {understandingText(slot.displayValue ?? slot.value, biText("已确认", "Confirmed"))}
                                {slot.source ? ` · ${businessSourceText(slot.source)}` : ""}
                              </strong>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}
                    {unresolvedSlots.length ? (
                      <section aria-label={biText("缺失或歧义槽位", "Missing or ambiguous slots")}>
                        <span>{biText("待确认", "Open")}</span>
                        <ul>
                          {unresolvedSlots.slice(0, 6).map((slot) => (
                            <li key={slot.slotKey}>
                              <span>{businessSlotText(slot.slotKey, slot.label)}</span>
                              <strong>{businessReasonText(slot.reason, slot.status)}</strong>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}
                  </div>
                ) : intentFrame ? <IntentFrameChips frame={intentFrame} /> : null}
                {activeQuestion ? (
                  <section className="agentUnderstandingClarification" data-testid="agent-understanding-active-clarification" role="status">
                    <span>{biText("当前只需确认这一点", "One decision needed now")}</span>
                    <strong>{activeQuestion}</strong>
                    {activeUnderstandingClarification?.reason ? <small>{businessReasonText(activeUnderstandingClarification.reason)}</small> : null}
                  </section>
                ) : null}
                {understandingBlockers.length ? (
                  <div className="agentUnderstandingBlockers" data-testid="agent-understanding-blockers" role="alert">
                    <strong>{biText("暂不能继续", "Cannot continue yet")}</strong>
                    <ul>
                      {understandingBlockers.slice(0, 3).map((blocker, index) => <li key={`${blocker}-${index}`}>{blocker}</li>)}
                    </ul>
                    {understandingBlockers.length > 3 ? <small>+{understandingBlockers.length - 3} {biText("项阻断", "more blockers")}</small> : null}
                  </div>
                ) : null}
                {!understandingNeedsAttention ? <p>{biText("业务槽位已解析；执行仍以当前证据与安全规则为准。", "Business slots are resolved; execution still follows current evidence and safety rules.")}</p> : null}
              </>
            ) : intentFrame ? (
              <>
                <IntentFrameChips frame={intentFrame} />
                {clarificationBundle?.required ? <p>{clarificationBundle.message}</p> : <p>{biText("字段均保留表级来源；写入仍需确认。", "Every field keeps table provenance; writes still require confirmation.")}</p>}
              </>
            ) : null}
          </div>
        </details>
      ) : null}
      {evidencePlan ? (
        <Suspense fallback={null}>
          <AgentEvidencePlan businessUnderstanding={businessUnderstanding} plan={evidencePlan} />
        </Suspense>
      ) : null}
      {semanticPlan && semanticPlan.status !== "not-applicable" ? (
        <Suspense fallback={null}>
          <AgentSemanticPlan executionPlan={executionPlan} onSelectCandidates={onSelectSemanticCandidates} onSelectPath={onSelectSemanticPath} onSelectRoot={onSelectSemanticRoot} plan={semanticPlan} tableNameByKey={tableNameByKey} />
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
