import type { AgentAskResult } from "../types";
import { evidenceRefText, pairText, type AnswerEvidenceStep } from "../agentPanelModel";
import { Bilingual, biText } from "./Bilingual";

type AgentAnswerCardProps = {
  answerCard: NonNullable<AgentAskResult["answerCard"]>;
  answerEvidenceSteps: AnswerEvidenceStep[];
  answerQuery: Record<string, unknown> | null;
  onAskCandidate?: (prompt: string) => void;
  queryRuntimeRef?: Record<string, unknown>;
  runtimeEngine: string;
};

function widgetTypeText(widgetType?: string) {
  if (widgetType === "line") return biText("折线图", "line chart");
  if (widgetType === "pie") return biText("饼图", "pie chart");
  if (widgetType === "metric") return biText("指标卡", "metric card");
  if (widgetType === "table") return biText("明细表", "table");
  if (widgetType === "slicer") return biText("筛选器", "slicer");
  return biText("柱状图", "bar chart");
}

function rowFieldValues(rows: Array<Record<string, unknown>>, role: string) {
  return rows
    .filter((row) => String(row.role ?? "") === role)
    .map((row) => String(row.field ?? "").trim())
    .filter(Boolean);
}

export function AgentAnswerCard({ answerCard, answerEvidenceSteps, answerQuery, onAskCandidate, queryRuntimeRef, runtimeEngine }: AgentAnswerCardProps) {
  const fallbackReason = queryRuntimeRef?.fallbackReason ?? answerQuery?.fallbackReason;
  const clarification = answerCard.clarification?.kind === "widget-fields" ? answerCard.clarification : null;
  const candidateMeasures = clarification?.candidateMeasures?.length ? clarification.candidateMeasures : rowFieldValues(answerCard.rows, "measure");
  const candidateDimensions = clarification?.candidateDimensions?.length ? clarification.candidateDimensions : rowFieldValues(answerCard.rows, "dimension");
  const chartType = widgetTypeText(clarification?.widgetType);
  const defaultDimension = candidateDimensions[0] ?? "";
  const defaultMeasure = candidateMeasures[0] ?? "";

  function candidatePrompt(role: "measure" | "dimension", field: string) {
    const tablePrefix = clarification?.tableKey ? biText(`在 ${clarification.tableKey} 中，`, `In ${clarification.tableKey}, `) : "";
    if (role === "measure") {
      return defaultDimension
        ? biText(`${tablePrefix}用 ${field} 按 ${defaultDimension} 做${chartType}`, `${tablePrefix}build a ${chartType} with ${field} by ${defaultDimension}`)
        : biText(`${tablePrefix}用 ${field} 做${chartType}`, `${tablePrefix}build a ${chartType} with ${field}`);
    }
    return defaultMeasure
      ? biText(`${tablePrefix}用 ${defaultMeasure} 按 ${field} 做${chartType}`, `${tablePrefix}build a ${chartType} with ${defaultMeasure} by ${field}`)
      : biText(`${tablePrefix}按 ${field} 分组做${chartType}`, `${tablePrefix}build a ${chartType} grouped by ${field}`);
  }

  return (
    <article className="agentAnswerCard" data-testid="agent-answer-card">
      <div className="agentAnswerLead">
        <div>
          <p className="kicker">{biText("业务回答", "Business answer")}</p>
          <h3>{pairText(answerCard.title)}</h3>
          <p>{pairText(answerCard.summary)}</p>
        </div>
        <span className="statusPill compact">{answerCard.confidence}</span>
      </div>
      <div className="agentAnswerMetrics">
        {answerCard.metrics.map((metric, index) => (
          <div key={`${pairText(metric.label)}-${index}`}>
            <span>{pairText(metric.label)}</span>
            <strong>{metric.value}</strong>
          </div>
        ))}
      </div>
      {answerCard.rows.length && !clarification ? (
        <div className="agentAnswerRows" data-testid="agent-answer-rows">
          {answerCard.rows.slice(0, 5).map((row, index) => (
            <div key={`${String(row.label ?? index)}-${index}`}>
              <span>{String(row.label ?? biText("合计", "Total"))}</span>
              <strong>{String(row.value ?? "-")}</strong>
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
