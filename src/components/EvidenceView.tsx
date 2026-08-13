import "./agentEvidenceWorkspace.css";
import { Suspense, useMemo, useState } from "react";
import type { AgentAskResult, EvidenceFocus, WorkbenchPayload } from "../types";
import type { BusinessPathStepKey } from "../businessPathModel";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import { useQualityDoctor } from "../useQualityDoctor";
import {
  actionBoundaryBusinessDetail,
  actionBoundaryBusinessLabel,
  actionReceiptDetail,
  actionReceiptTechnical,
  actionReceiptTitle,
  agentEvidenceBusinessDetail,
  agentEvidenceBusinessLabel,
  agentEvidenceTechnicalText,
  detailLabel,
  detailValue,
  evidenceCoverageText,
  evidenceDecisionText,
  evidenceLabel,
  evidenceRunReadinessText,
  evidenceTechnicalLabel,
  isTechnicalFocusDetail,
  sourceRunFromFocus,
} from "../evidenceViewModel";
import { buildMetricRepairPlan } from "../metricRepairModel";
import { buildEvidenceNarrative } from "../productIntelligenceModel";
import { lazyWithRetry } from "../lazyWithRetry";
import { Bilingual, biText } from "./Bilingual";
import { EvidenceBusinessSummaryPanel } from "./EvidenceBusinessSummaryPanel";
import { MetricSemanticRepairActions } from "./MetricSemanticRepairActions";

const EvidenceTrustActions = lazyWithRetry(() => import("./EvidenceTrustActions"));
const EvidenceNumberExplainerPanel = lazyWithRetry(() => import("./EvidenceNumberExplainerPanel").then((module) => ({ default: module.EvidenceNumberExplainerPanel })));
const EvidenceWorkspaceManifestPanel = lazyWithRetry(() => import("./EvidenceWorkspaceManifestPanel"));
const EvidenceReviewedPublicationsPanel = lazyWithRetry(() => import("./EvidenceReviewedPublicationsPanel"));

type EvidenceViewProps = {
  agent: AgentAskResult;
  focus?: EvidenceFocus | null;
  lastActionResult?: Record<string, unknown> | null;
  pendingDraftCount?: number;
  workspaceId: string;
  workbench: WorkbenchPayload;
  onSetSemantic: (options: { table: string; field: string; role: string; tags?: string[]; usage?: string[]; confidence?: number; note?: string; confirm?: boolean; stayOnPage?: boolean }) => Promise<Record<string, unknown>>;
  onSourceIntelligenceRun: (options?: SourceIntelligenceRunOptions) => Promise<Record<string, unknown> | void>;
  onOpenBusinessStep: (step: BusinessPathStepKey) => void;
  onOpenAgent: () => void;
  onOpenDashboard: (dashboardKey?: string) => void;
};

export function EvidenceView({ agent, focus, lastActionResult, pendingDraftCount, workspaceId, workbench, onSetSemantic, onSourceIntelligenceRun, onOpenBusinessStep, onOpenAgent, onOpenDashboard }: EvidenceViewProps) {
  const [showWorkspaceManifest, setShowWorkspaceManifest] = useState(false);
  const runs = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const activeRun = sourceRunFromFocus(focus, runs);
  const activeRefs = focus?.refs?.length ? focus.refs : agent.ontology.evidenceFiles;
  const allFocusDetails = Object.entries(focus?.detail ?? {}).filter(([key]) => key !== "columns");
  const businessFocusDetails = allFocusDetails.filter(([key]) => !isTechnicalFocusDetail(key));
  const technicalFocusDetails = allFocusDetails.filter(([key]) => isTechnicalFocusDetail(key));
  const activeAnswer = agent.answerCard;
  const evidenceNarrative = buildEvidenceNarrative(focus, agent, workbench);
  const hasData = workbench.tables.length > 0 || runs.length > 0;
  const qualityDoctorResult = useQualityDoctor(hasData, workbench);
  const metricRepairPlan = useMemo(() => buildMetricRepairPlan(qualityDoctorResult, workbench), [qualityDoctorResult, workbench]);

  if (!hasData) {
    return (
      <section className="mainPanel" aria-labelledby="evidence-title">
        <div className="panelHeader">
          <div>
            <p className="kicker">{biText("核对", "Review")}</p>
            <h2 id="evidence-title">
              <Bilingual zh="还没有证据可核对" en="No evidence to review yet" />
            </h2>
            <p className="panelLead">
              <Bilingual
                zh="当前工作区没有数据表或导入回执。证据页只展示真实来源、口径、查询和动作回执；没有真实来源时保持空状态。"
                en="This workspace has no tables or import receipts. Evidence only shows real sources, metric logic, query receipts, and action receipts; without real sources it stays empty."
              />
            </p>
          </div>
        </div>
        <button className="primaryButton" data-testid="evidence-open-sources" onClick={() => onOpenBusinessStep("data")} type="button">
          {biText("接入数据", "Connect data")}
        </button>
        <details className="progressiveDetails evidenceProgressiveDetails" data-testid="evidence-reviewed-publications-empty-details" onToggle={(event) => setShowWorkspaceManifest(event.currentTarget.open)}>
          <summary>{biText("查看既有审核制品", "View existing reviewed publications")}</summary>
          <div className="progressiveDetailsBody evidenceProgressiveGrid">
            {showWorkspaceManifest ? <Suspense fallback={null}><EvidenceReviewedPublicationsPanel workspaceId={workspaceId} /></Suspense> : null}
          </div>
        </details>
      </section>
    );
  }
  const businessTitle =
    focus?.title ??
    (activeAnswer?.title ? biText(activeAnswer.title.zh, activeAnswer.title.en) : biText("当前证据可以解释什么", "What this evidence can explain"));
  const businessMetrics = [
    {
      label: biText("已纳入分析", "included in analysis"),
      value: activeRun ? biText(`${activeRun.source_count} 个文件`, `${activeRun.source_count} files`) : "-",
    },
    {
      label: activeRun
        ? biText(`可直接回答（共识别 ${activeRun.metric_sql_plan_count} 个候选）`, `directly answerable (${activeRun.metric_sql_plan_count} candidates)`)
        : biText("可直接回答", "directly answerable"),
      value: activeRun ? biText(`${activeRun.metric_sql_executable_count} 个`, `${activeRun.metric_sql_executable_count}`) : "-",
    },
    {
      label: biText("已验证业务连接", "validated business links"),
      value: activeRun ? biText(`${activeRun.relationship_count} 条`, `${activeRun.relationship_count}`) : "-",
    },
    {
      label: biText("本次结论引用", "cited by this result"),
      value: biText(`${activeRefs.length} 条`, `${activeRefs.length}`),
    },
  ];
  const nextEvidenceActions = [
    activeRun ? evidenceCoverageText(activeRun) : biText("先生成证据摘要", "Create an evidence summary first"),
    activeAnswer ? biText("Agent 回答已绑定查询和指标证据", "Agent answer is bound to query and metric evidence") : biText("先让 Agent 生成一个只读回答", "Ask Agent for a read-only answer first"),
    biText("任何导入、关系保存、看板写入仍走确认", "Imports, relationship saves, and dashboard writes still require approval"),
  ];
  return (
    <section className="mainPanel" aria-labelledby="evidence-title">
      <div className="panelHeader">
        <div>
          <p className="kicker">{biText("核对", "Review")}</p>
          <h2 id="evidence-title">
            <Bilingual zh="证据与回执" en="Evidence and receipts" />
          </h2>
          <p className="panelLead">
            <Bilingual
              zh="从看板或 Agent 进入这里时，先看本次结论引用了哪些数据来源、指标口径、查询回执、业务连接和动作边界。"
              en="When opened from a dashboard or Agent answer, this view shows the data source, metric logic, query receipt, business links, and action boundaries behind the result."
            />
          </p>
        </div>
      </div>
      <div className="evidenceGrid">
        <section className="evidenceNextAction wideArticle" data-testid="evidence-next-action">
          <div>
            <strong>{biText("证据可核对", "Evidence ready to review")} · {pendingDraftCount ? biText("审阅写入", "approve write") : focus?.dashboardKey ? biText("返回看板", "return to dashboard") : biText("继续分析", "continue analysis")}</strong>
            <span>{pendingDraftCount ? biText(`${pendingDraftCount} 个草案仍未确认`, `${pendingDraftCount} drafts still need approval`) : biText("当前来源和口径会随下一步继续保留。", "The current source and metric context will carry into the next step.")}</span>
          </div>
          <button
            className="primaryButton"
            onClick={() => pendingDraftCount ? onOpenBusinessStep("confirm") : focus?.dashboardKey ? onOpenDashboard(focus.dashboardKey) : onOpenAgent()}
            type="button"
          >
            {pendingDraftCount ? biText("审阅待确认动作", "Review pending action") : focus?.dashboardKey ? biText("返回当前看板", "Return to dashboard") : biText("继续分析", "Continue analysis")}
          </button>
        </section>

        <EvidenceBusinessSummaryPanel
          businessMetrics={businessMetrics}
          businessTitle={businessTitle}
          coverageText={evidenceCoverageText(activeRun)}
          decisionText={evidenceDecisionText(activeRun, activeRefs)}
          nextEvidenceActions={nextEvidenceActions}
        />

        <Suspense fallback={null}>
          <EvidenceTrustActions agent={agent} lastActionResult={lastActionResult} />
        </Suspense>

        <details className="progressiveDetails evidenceProgressiveDetails" data-testid="evidence-explanation-details">
          <summary>{biText("查看数字解释、缺口和追溯依据", "View number explanation, gaps, and trace basis")}</summary>
          <div className="progressiveDetailsBody evidenceProgressiveGrid">
            <Suspense fallback={null}>
              <EvidenceNumberExplainerPanel evidenceNarrative={evidenceNarrative} />
            </Suspense>

            <article className="wideArticle evidenceGapPanel" data-testid="evidence-gap-panel">
              <div className="tileHeader">
                <div>
                  <span className="storyMode"><Bilingual zh="证据缺口" en="Evidence gaps" /></span>
                  <h3><Bilingual zh="哪些问题暂时不能放心回答" en="Questions not ready to trust yet" /></h3>
                  <span>{metricRepairPlan.blocked > 0 ? metricRepairPlan.summary : biText("当前没有指标 SQL 阻塞项。", "No metric SQL blockers are present.")}</span>
                </div>
                <strong>{biText(`${metricRepairPlan.executable} / ${metricRepairPlan.planned || activeRun?.metric_sql_plan_count || 0} 个候选问题可执行`, `${metricRepairPlan.executable} / ${metricRepairPlan.planned || activeRun?.metric_sql_plan_count || 0} candidate questions executable`)}</strong>
              </div>
              <div className="evidenceGapStats">
                <span className={metricRepairPlan.blocked > 0 ? "warn" : "ok"}>
                  <strong>{metricRepairPlan.blocked}</strong>
                  <small>{biText("待补语义", "semantic blockers")}</small>
                </span>
                <span>
                  <strong>{Math.round((metricRepairPlan.rate || 0) * 100)}%</strong>
                  <small>{biText("可执行率", "executable rate")}</small>
                </span>
                <span>
                  <strong>{metricRepairPlan.bindingDrafts.length}</strong>
                  <small>{biText("字段确认草案", "field drafts")}</small>
                </span>
              </div>
              {metricRepairPlan.bindingDrafts.length ? (
                <MetricSemanticRepairActions
                  actionsTestId="evidence-gap-semantic-actions"
                  loopTestId="evidence-semantic-confirm-loop"
                  maxDrafts={6}
                  onSetSemantic={onSetSemantic}
                  onSourceIntelligenceRun={onSourceIntelligenceRun}
                  plan={metricRepairPlan}
                />
              ) : null}
              <div className="evidenceGapItems" data-testid="evidence-gap-items">
                {metricRepairPlan.evidenceGaps.length ? metricRepairPlan.evidenceGaps.slice(0, 6).map((gap) => (
                  <div className={gap.severity} key={gap.key}>
                    <strong>{gap.title}</strong>
                    <span>{gap.detail}</span>
                    {gap.missingSemantics.length ? <small>{gap.missingSemantics.join("、")}</small> : null}
                  </div>
                )) : (
                  <div className="info">
                    <strong><Bilingual zh="暂无可核对缺口" en="No reviewable gaps" /></strong>
                    <span><Bilingual zh="生成 Source Intelligence 后，这里会列出不能推入看板的问题。" en="After Source Intelligence runs, questions that cannot enter dashboards appear here." /></span>
                  </div>
                )}
              </div>
            </article>

            <article className="wideArticle evidenceFocusCard" data-testid="evidence-focus-card">
              <div className="tileHeader">
                <div>
                  <h3>{biText("追溯依据", "Trace basis")}: {focus?.title ?? biText("当前工作区证据", "Current workspace evidence")}</h3>
                  <span>{focus?.subtitle ?? biText("数据来源、查询回执、业务连接和动作边界的可追溯引用", "Traceable data-source, query-receipt, business-link, and action-boundary references")}</span>
                </div>
                <strong>{focus?.source ?? biText("工作区", "workspace")}</strong>
              </div>
              <div className="evidenceFocusMeta">
                {focus?.dashboardKey ? <span>{biText("看板", "Dashboard")}: {focus.dashboardKey}</span> : null}
                {focus?.viewKey ? <span>{biText("视图", "View")}: {focus.viewKey}</span> : null}
                {focus?.tableKey ? <span>{biText("表", "Table")}: {focus.tableKey}</span> : null}
                {focus?.widgetType ? <span>{biText("组件", "Widget")}: {focus.widgetType}</span> : null}
                {activeRun ? <span>{biText("证据摘要", "Evidence summary")}: {activeRun.label}</span> : null}
              </div>
              <div className="evidenceChipGrid" data-testid="evidence-focus-refs">
                {activeRefs.map((ref) => (
                  <span key={ref}>{evidenceLabel(ref)}</span>
                ))}
              </div>
              <details className="advancedDetails compactAdvanced" data-testid="evidence-technical-ref-details">
                <summary>{biText("查看技术引用名", "View technical reference names")}</summary>
                <div className="evidenceChipGrid">
                  {activeRefs.map((ref) => (
                    <span key={`technical-${ref}`}>{evidenceTechnicalLabel(ref)}</span>
                  ))}
                </div>
              </details>
              {businessFocusDetails.length ? (
                <dl className="evidenceDetailGrid" data-testid="evidence-focus-detail">
                  {businessFocusDetails.slice(0, 12).map(([key, value]) => (
                    <div key={key}>
                      <dt>{detailLabel(key)}</dt>
                      <dd>{detailValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
              {technicalFocusDetails.length ? (
                <details className="advancedDetails compactAdvanced" data-testid="evidence-focus-technical-detail">
                  <summary>{biText("查看查询和分页技术细节", "View query and paging technical details")}</summary>
                  <dl className="evidenceDetailGrid">
                    {technicalFocusDetails.map(([key, value]) => (
                      <div key={key}>
                        <dt>{detailLabel(key)}</dt>
                        <dd>{detailValue(value)}</dd>
                      </div>
                    ))}
                  </dl>
                </details>
              ) : null}
            </article>
          </div>
        </details>

        <details className="progressiveDetails evidenceProgressiveDetails" data-testid="evidence-receipts-details" onToggle={(event) => setShowWorkspaceManifest(event.currentTarget.open)}>
          <summary>{biText("查看回执、动作边界和原始合同", "View receipts, action boundaries, and raw contracts")}</summary>
          <div className="progressiveDetailsBody evidenceProgressiveGrid">
            {showWorkspaceManifest ? <Suspense fallback={null}><EvidenceWorkspaceManifestPanel /></Suspense> : null}
            {showWorkspaceManifest ? <Suspense fallback={null}><EvidenceReviewedPublicationsPanel workspaceId={workspaceId} /></Suspense> : null}
            <article data-testid="evidence-source-intelligence-summary">
              <h3><Bilingual zh="证据摘要回执" en="Evidence summary receipt" /></h3>
              {activeRun ? (
                <div className="evidenceReceipt">
                  <strong>{activeRun.label}</strong>
                  <span>{evidenceRunReadinessText(activeRun)}</span>
                  <dl className="definitionGrid">
                    <div><dt>{biText("源文件", "Sources")}</dt><dd>{activeRun.source_count}</dd></div>
                    <div><dt>{biText("表", "Tables")}</dt><dd>{activeRun.table_count}</dd></div>
                    <div><dt>{biText("可识别字段", "Detected fields")}</dt><dd>{activeRun.field_candidate_count}</dd></div>
                    <div><dt>{biText("业务连接", "Business links")}</dt><dd>{activeRun.relationship_count}</dd></div>
                    <div><dt>{biText("可用问题", "Answerable questions")}</dt><dd>{activeRun.metric_sql_executable_count}/{activeRun.metric_sql_plan_count}</dd></div>
                    <div><dt>{biText("覆盖", "Coverage")}</dt><dd>{activeRun.fileCoverage?.complete ? biText("完整", "complete") : biText("待确认", "pending")}</dd></div>
                  </dl>
                  <details className="advancedDetails compactAdvanced" data-testid="evidence-receipt-technical-details">
                    <summary>{biText("查看技术回执路径", "View technical receipt path")}</summary>
                    <small>{activeRun.output_dir}</small>
                  </details>
                </div>
              ) : (
                <p className="quietText">{biText("尚未生成证据摘要回执。", "No evidence summary receipt has been generated yet.")}</p>
              )}
            </article>

            <article data-testid="evidence-agent-answer-business-refs">
              <h3><Bilingual zh="Agent 答案证据" en="Agent answer evidence" /></h3>
              <div className="evidenceChipGrid">
                {(agent.answerCard?.evidenceRefs ?? []).slice(0, 6).map((ref, index) => (
                  <span key={`${String(ref.type ?? "evidence")}-${index}`}>
                    <strong>{agentEvidenceBusinessLabel(ref)}</strong>
                    <small>{agentEvidenceBusinessDetail(ref)}</small>
                  </span>
                ))}
                {!agent.answerCard?.evidenceRefs?.length ? <span>{biText("等待 Agent 回答", "Waiting for Agent answer")}</span> : null}
              </div>
              {agent.answerCard?.evidenceRefs?.length ? (
                <details className="advancedDetails compactAdvanced evidenceAgentTechnicalRefs" data-testid="evidence-agent-answer-technical-refs">
                  <summary>{biText("查看 Agent 证据原始引用", "View raw Agent evidence refs")}</summary>
                  <div className="evidenceTechnicalList">
                    {agent.answerCard.evidenceRefs.slice(0, 6).map((ref, index) => (
                      <code key={`${String(ref.type ?? "evidence")}-${index}`}>{agentEvidenceTechnicalText(ref)}</code>
                    ))}
                  </div>
                </details>
              ) : null}
            </article>

            <article>
              <h3><Bilingual zh="动作边界" en="Action boundaries" /></h3>
              <div className="evidenceActionList">
                {agent.coreSemanticRuntime.actionGateHints.slice(0, 6).map((action) => (
                  <div key={action.id}>
                    <strong>{actionBoundaryBusinessLabel(action)}</strong>
                    <span>{actionBoundaryBusinessDetail(action)}</span>
                    <details className="evidenceActionBoundaryTechnical" data-testid={`evidence-action-boundary-technical-${action.id}`}>
                      <summary>{biText("查看动作合同", "View action contract")}</summary>
                      <code>{action.actionTypeId}</code>
                      <small>{action.confirmationPolicy}</small>
                    </details>
                  </div>
                ))}
              </div>
            </article>

            <article data-testid="evidence-action-receipt">
              <h3><Bilingual zh="最近动作回执" en="Latest action receipt" /></h3>
              <div className={lastActionResult?.confirmed === true ? "evidenceActionReceipt confirmed" : lastActionResult?.ok === false ? "evidenceActionReceipt failed" : "evidenceActionReceipt preview"}>
                <strong data-testid="evidence-action-receipt-title">{actionReceiptTitle(lastActionResult)}</strong>
                <span data-testid="evidence-action-receipt-detail">{actionReceiptDetail(lastActionResult)}</span>
                {actionReceiptTechnical(lastActionResult) ? (
                  <details className="evidenceActionTechnical" data-testid="evidence-action-receipt-technical">
                    <summary>{biText("查看动作技术标识", "View action technical id")}</summary>
                    <span>{actionReceiptTechnical(lastActionResult)}</span>
                  </details>
                ) : null}
              </div>
            </article>

            <article className="wideArticle">
              <details className="advancedDetails">
                <summary>{biText("查看原始本体合同", "View raw ontology contract")}</summary>
                <div className="evidenceRawGrid">
                  <pre>{JSON.stringify(agent.ontology.objects, null, 2)}</pre>
                  <pre>{JSON.stringify(agent.ontology.functions, null, 2)}</pre>
                  <pre>{JSON.stringify(agent.ontology.links, null, 2)}</pre>
                  <pre>{JSON.stringify(agent.coreSemanticRuntime.actionGateHints, null, 2)}</pre>
                </div>
              </details>
            </article>
          </div>
        </details>
      </div>
    </section>
  );
}
