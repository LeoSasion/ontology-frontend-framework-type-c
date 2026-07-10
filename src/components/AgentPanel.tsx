import "./agentEvidenceWorkspace.css";
import { useEffect, useState } from "react";
import type { ActionDraft, AgentAskResult, WorkbenchPayload } from "../types";
import {
  actionImpactGroup,
  actionNeedsDashboard,
  confidenceText,
  dashboardCreateDraft,
  dashboardDraftWidgets,
  defaultAgentPrompt,
  draftDashboardLabel,
  metricPrompt,
  objectRecord,
  resultActionKey,
  sourceRunPrompt,
  viewPrompt,
  type AnswerEvidenceStep,
  type CheckedItem,
} from "../agentPanelModel";
import { AgentAnswerCard } from "./AgentAnswerCard";
import { AgentCanAnswerPanel, type AgentCanAnswerSuggestion } from "./AgentCanAnswerPanel";
import { AgentContextPlanPanel } from "./AgentContextPlanPanel";
import { AgentEvidenceAuditPanels } from "./AgentEvidenceAuditPanels";
import { AgentPendingChangesPanel } from "./AgentPendingChangesPanel";
import { AgentPromptComposer } from "./AgentPromptComposer";
import { AgentTaskPacket } from "./AgentTaskPacket";
import { Bilingual, biText, useLanguage } from "./Bilingual";

type AgentPanelProps = {
  result: AgentAskResult;
  actionDrafts: ActionDraft[];
  workbench: WorkbenchPayload;
  lastActionResult: Record<string, unknown> | null;
  onAsk: (prompt: string) => Promise<void>;
  onConfirmDryRun: (actionKey: string) => Promise<void>;
  onConfirmAction: (actionKey: string) => Promise<void>;
  onRejectAction: (actionKey: string) => Promise<void>;
  onOpenSources: () => void;
};

export function AgentPanel({ result, actionDrafts, workbench, lastActionResult, onAsk, onConfirmDryRun, onConfirmAction, onRejectAction, onOpenSources }: AgentPanelProps) {
  const { resolvedLanguage } = useLanguage();
  const [prompt, setPrompt] = useState(() => defaultAgentPrompt(resolvedLanguage, workbench));
  const [promptTouched, setPromptTouched] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const [runningActionKey, setRunningActionKey] = useState<string | null>(null);

  useEffect(() => {
    if (!promptTouched) {
      setPrompt(defaultAgentPrompt(resolvedLanguage, workbench));
    }
  }, [promptTouched, resolvedLanguage, workbench]);

  async function submit(nextPrompt = prompt) {
    const normalizedPrompt = nextPrompt.trim();
    if (!normalizedPrompt) {
      return;
    }
    setPrompt(normalizedPrompt);
    setIsAsking(true);
    try {
      await onAsk(normalizedPrompt);
    } finally {
      setIsAsking(false);
    }
  }

  const pendingDrafts = actionDrafts.filter((draft) => draft.status === "draft");
  const currentDraft = pendingDrafts.find((draft) => draft.action_key === result.actionDraft.actionKey) ?? pendingDrafts[0];
  const currentDraftIsPending = Boolean(currentDraft);
  const activeActionKey = currentDraft?.action_key ?? result.actionDraft.actionKey;
  const activeActionKind = currentDraft?.kind ?? result.actionDraft.kind;
  const canConfirmCurrent = currentDraftIsPending && activeActionKey !== "read_only_plan";
  const dashboardConfidence = result.matched.dashboardSelectionConfidence;
  const dashboardTarget = result.matched.dashboard;
  const blockedDashboardWrite = actionNeedsDashboard(result.actionDraft.kind) && !result.requiresConfirmation && dashboardConfidence === "missing";
  const activeDashboardConfidence = currentDraft && currentDraft.kind.startsWith("dashboard.")
    ? (currentDraft.kind === "dashboard.create" ? "draft" : "explicit")
    : dashboardConfidence;
  const activeDashboardLabel = draftDashboardLabel(currentDraft, dashboardTarget);
  const activeHasWriteDraft = Boolean(currentDraft) || result.requiresConfirmation;
  const activeBoundaryBlocked = !currentDraft && blockedDashboardWrite;
  const activeActionResult = activeActionKey && resultActionKey(lastActionResult) === activeActionKey ? lastActionResult : null;
  const currentDashboardDraft = dashboardCreateDraft(currentDraft);
  const currentDashboardDraftWidgets = currentDashboardDraft ? dashboardDraftWidgets(currentDashboardDraft) : [];
  const currentDashboardDraftTable = currentDashboardDraft ? String(currentDashboardDraft.defaultTableKey ?? currentDraft?.payload.tableKey ?? "-") : "-";
  const targetBoundaryState = activeBoundaryBlocked
    ? "blocked"
    : canConfirmCurrent
      ? "draft"
      : "readonly";
  const latestRun = workbench.sourceIntelligenceRuns[0];
  const primaryTable = workbench.tables[0];
  const hasData = workbench.tables.length > 0;
  const topMetric = workbench.metrics.find((metric) => metric.enabled !== 0 && metric.measure !== "*") ?? workbench.metrics[0];
  const topView = workbench.savedViews[0];
  const topRelationship = workbench.relationships[0];
  const answerEvidenceRefs = result.answerCard?.evidenceRefs ?? [];
  const queryRuntimeRef = answerEvidenceRefs.find((ref) => String(ref.type ?? "") === "queryRuntime");
  const sourceRunRef = answerEvidenceRefs.find((ref) => String(ref.type ?? "") === "sourceRun") ?? answerEvidenceRefs.find((ref) => String(ref.type ?? "") === "table");
  const metricDefinitionRef = answerEvidenceRefs.find((ref) => String(ref.type ?? "") === "metricDefinition");
  const answerQuery = objectRecord(result.answerCard?.query);
  const runtimeEngine = String(queryRuntimeRef?.engine ?? workbench.queryRuntime?.engine ?? "");
  const answerEvidenceSteps: AnswerEvidenceStep[] = result.answerCard ? [
    {
      key: "source",
      label: biText("数据来源", "Data source"),
      detail: String(sourceRunRef?.name ?? sourceRunRef?.id ?? sourceRunRef?.tableKey ?? answerQuery?.table ?? result.matched.table?.display_name ?? biText("当前工作区数据", "Current workspace data")),
      badge: biText("已定位", "Located"),
      tone: sourceRunRef || result.matched.table ? "ok" : "warn",
    },
    {
      key: "metric",
      label: biText("指标口径", "Metric logic"),
      detail: String(metricDefinitionRef?.label ?? metricDefinitionRef?.metric_key ?? (answerQuery?.measure ? `${String(answerQuery.aggregation ?? "sum")}(${String(answerQuery.measure)})${answerQuery.group ? ` · ${String(answerQuery.group)}` : ""}` : topMetric ? `${topMetric.aggregation}(${topMetric.measure})` : biText("缺少可用指标", "No usable metric"))),
      badge: metricDefinitionRef ? biText("已匹配", "Matched") : biText("查询推导", "Query-derived"),
      tone: metricDefinitionRef || answerQuery?.measure || topMetric ? "ok" : "warn",
    },
    {
      key: "runtime",
      label: biText("查询回执", "Query receipt"),
      detail: runtimeEngine
        ? (queryRuntimeRef?.fallbackReason || answerQuery?.fallbackReason
          ? biText("只读查询已完成，有降级说明可展开查看。", "Read-only query completed; fallback details are available.")
          : biText("只读查询已完成，可追溯到执行回执。", "Read-only query completed and can be traced to its receipt."))
        : biText("还没有查询回执", "No query receipt yet"),
      badge: answerQuery?.sqlIntent ? biText("受控查询", "Controlled query") : biText("只读", "Read-only"),
      tone: runtimeEngine ? "ok" : "neutral",
    },
    {
      key: "boundary",
      label: biText("写入边界", "Write boundary"),
      detail: result.requiresConfirmation || currentDraft
        ? biText("有修改等待确认；确认前不写入。", "A change is waiting; nothing writes before approval.")
        : biText("这是只读回答；需要改数据或看板时才生成待确认修改。", "This is a read-only answer; pending changes are created only for data or dashboard changes."),
      badge: result.requiresConfirmation || currentDraft ? biText("需确认", "Approval needed") : biText("只读", "Read-only"),
      tone: result.requiresConfirmation || currentDraft ? "warn" : "ok",
    },
  ] : [];
  const llmAudit = result.llm.audit;
  const llmAuditItems = [
    {
      key: "provider",
      label: biText("回答方式", "Answer mode"),
      value: result.llm.configured ? biText("模型回答", "Model answer") : biText("本地规则回答", "Local rule answer"),
      tone: result.llm.configured ? "ok" : "neutral",
    },
    {
      key: "mode",
      label: biText("运行模式", "Mode"),
      value: String(llmAudit?.mode ?? result.llm.mode),
      tone: result.llm.mode === "provider" ? "ok" : "neutral",
    },
    {
      key: "boundary",
      label: biText("上下文边界", "Context boundary"),
      value: String(llmAudit?.contextBoundary ?? "active-workspace-sourceRun-workbench"),
      tone: "ok",
    },
    {
      key: "secret",
      label: biText("密钥暴露", "Secret exposure"),
      value: llmAudit?.secretExposed === true ? biText("需检查", "Needs review") : biText("未暴露", "Not exposed"),
      tone: llmAudit?.secretExposed === true ? "warn" : "ok",
    },
  ];
  const checkedItems: CheckedItem[] = [
    result.matched.table
      ? {
        key: "table",
        label: biText("数据表", "Table"),
        detail: biText(`已检查 ${result.matched.table.display_name}`, `Checked ${result.matched.table.display_name}`),
        tone: result.matched.tableSelectionConfidence === "missing" ? "warn" : "ok",
      }
      : primaryTable
        ? {
          key: "table",
          label: biText("数据表", "Table"),
          detail: biText(`默认使用 ${primaryTable.display_name}`, `Defaulted to ${primaryTable.display_name}`),
          tone: "neutral",
        }
        : {
          key: "table",
          label: biText("数据表", "Table"),
          detail: biText("还没有可分析数据表", "No analyzable table yet"),
          tone: "warn",
        },
    latestRun
      ? {
        key: "source-intelligence",
        label: biText("证据摘要", "Evidence summary"),
        detail: `${latestRun.source_count} ${biText("文件", "files")} · ${latestRun.relationship_count} ${biText("业务连接", "business links")} · ${latestRun.metric_sql_executable_count}/${latestRun.metric_sql_plan_count} ${biText("可用问题", "questions")}`,
        tone: latestRun.metric_sql_executable_count ? "ok" : "warn",
      }
      : {
        key: "source-intelligence",
        label: biText("证据摘要", "Evidence summary"),
        detail: biText("等待生成证据摘要", "Waiting for evidence summary"),
        tone: "warn",
      },
    topMetric
      ? {
        key: "metric",
        label: biText("指标口径", "Metric"),
        detail: `${topMetric.aggregation}(${topMetric.measure})${topMetric.dimension ? ` · ${topMetric.dimension}` : ""}`,
        tone: "ok",
      }
      : {
        key: "metric",
        label: biText("指标口径", "Metric"),
        detail: biText("还没有可用指标", "No usable metric yet"),
        tone: "warn",
      },
    runtimeEngine
      ? {
        key: "runtime",
        label: biText("查询回执", "Query receipt"),
        detail: biText("只读查询已完成", "Read-only query completed"),
        tone: "ok",
      }
      : {
        key: "runtime",
        label: biText("查询回执", "Query receipt"),
        detail: biText("等待查询回执", "Waiting for query receipt"),
        tone: "neutral",
      },
    result.matched.dashboard
      ? {
        key: "dashboard",
        label: biText("目标看板", "Dashboard target"),
        detail: `${result.matched.dashboard.name} · ${confidenceText(result.matched.dashboardSelectionConfidence)}`,
        tone: result.matched.dashboardSelectionConfidence === "missing" ? "warn" : "ok",
      }
      : {
        key: "dashboard",
        label: biText("目标看板", "Dashboard target"),
        detail: confidenceText(result.matched.dashboardSelectionConfidence),
        tone: result.matched.dashboardSelectionConfidence === "missing" ? "warn" : "neutral",
      },
  ];
  const canAnswerSuggestions = [
    latestRun
      ? {
        key: "source-run",
        label: biText("从证据摘要开始", "Start from evidence summary"),
        prompt: sourceRunPrompt(latestRun),
        detail: `${latestRun.source_count} ${biText("文件", "files")} · ${latestRun.relationship_count} ${biText("业务连接", "business links")} · ${latestRun.metric_sql_executable_count}/${latestRun.metric_sql_plan_count} ${biText("可用问题", "questions")}`,
      }
      : {
        key: "import-gap",
        label: biText("先判断缺口", "Find the next gap"),
        prompt: {
          zh: "先告诉我当前工作区下一步应该接入什么数据",
          en: "Tell me what data this workspace should add next",
        },
        detail: biText("还没有证据摘要。", "No evidence summary yet."),
      },
    topMetric
      ? {
        key: "metric",
        label: biText("问一个指标", "Ask about a metric"),
        prompt: metricPrompt(topMetric),
        detail: `${topMetric.aggregation}(${topMetric.measure})${topMetric.dimension ? ` · ${topMetric.dimension}` : ""}`,
      }
      : null,
    topView
      ? {
        key: "saved-view",
        label: biText("解释保存口径", "Explain a saved view"),
        prompt: viewPrompt(topView),
        detail: `${topView.table_name ?? topView.table_key} · ${topView.filterCount ?? 0} ${biText("筛选", "filters")}`,
      }
      : null,
    topRelationship
      ? {
        key: "relationship",
        label: biText("检查表间关系", "Check a relationship"),
        prompt: {
          zh: `基于 ${topRelationship.name} 关系检查异常和证据`,
          en: `Check anomalies and evidence using relationship ${topRelationship.name}`,
        },
        detail: `${topRelationship.left_table_key}.${topRelationship.left_field} -> ${topRelationship.right_table_key}.${topRelationship.right_field}`,
      }
      : primaryTable
        ? {
          key: "table",
          label: biText("先问数据表", "Ask about the table"),
          prompt: {
            zh: `分析 ${primaryTable.display_name} 的主要变化，并给出证据`,
            en: `Analyze the main changes in ${primaryTable.display_name} with evidence`,
          },
          detail: `${primaryTable.row_count.toLocaleString()} ${biText("行", "rows")} · ${primaryTable.column_count} ${biText("字段", "fields")}`,
        }
        : null,
  ].filter((item): item is AgentCanAnswerSuggestion => Boolean(item));
  const draftImpactItems = [
    {
      key: "data",
      label: biText("数据写入", "Data writes"),
      count: pendingDrafts.filter((draft) => actionImpactGroup(draft.kind) === "data").length,
      detail: biText("导入、覆盖或新增本地表", "Imports, overwrites, or local table changes"),
    },
    {
      key: "dashboard",
      label: biText("看板配置", "Dashboard config"),
      count: pendingDrafts.filter((draft) => actionImpactGroup(draft.kind) === "dashboard").length,
      detail: biText("页面、组件、筛选或删除", "Pages, widgets, filters, or deletes"),
    },
    {
      key: "model",
      label: biText("分析口径", "Analysis model"),
      count: pendingDrafts.filter((draft) => actionImpactGroup(draft.kind) === "model").length,
      detail: biText("关系、公式、指标或语义", "Relationships, formulas, metrics, or semantics"),
    },
    {
      key: "workspace",
      label: biText("工作区配置", "Workspace config"),
      count: pendingDrafts.filter((draft) => actionImpactGroup(draft.kind) === "workspace").length,
      detail: biText("视图、索引和本地元数据", "Views, indexes, and local metadata"),
    },
  ];
  const nextDraftToReview = pendingDrafts.find((draft) => draft.action_key === activeActionKey) ?? pendingDrafts[0];
  const riskyDraftCount = pendingDrafts.filter((draft) => draft.kind === "dashboard.delete" || draft.kind === "import.commit").length;

  async function runAction(actionKey: string, task: () => Promise<void>) {
    setRunningActionKey(actionKey);
    try {
      await task();
    } finally {
      setRunningActionKey(null);
    }
  }

  if (!hasData) {
    return (
      <section className="mainPanel" aria-labelledby="agent-title">
        <div className="panelHeader">
          <div>
            <p className="kicker">{biText("受控 Agent", "Controlled Agent")}</p>
            <h2 id="agent-title">
              <Bilingual zh="先接入数据，再让 AI 生成图表或回答" en="Add data before asking AI for charts or answers" />
            </h2>
            <p className="panelLead">
              <Bilingual
                zh="当前没有可分析的数据表。AI 可以先带你判断该导入什么，确认前不会写入任何内容。"
                en="There are no analyzable tables yet. AI can help decide what to import, and it will not write anything before confirmation."
              />
            </p>
          </div>
        </div>
        <article className="noDataRoutePanel" data-testid="agent-no-data-route">
          <span className="storyMode"><Bilingual zh="第一步" en="First step" /></span>
          <h3><Bilingual zh="导入或扫描数据" en="Import or scan data" /></h3>
          <p>
            <Bilingual
              zh="完成导入后，AI 助手会基于真实表、字段和证据回执生成图表草案或只读回答。"
              en="After import, AI will use real tables, fields, and receipts to draft charts or produce read-only answers."
            />
          </p>
          <div className="noDataRouteActions">
            <button className="primaryButton" onClick={onOpenSources} type="button">
              <Bilingual zh="去数据源页" en="Go to Sources" />
            </button>
            <button
              className="secondaryButton"
              disabled={isAsking}
              onClick={() => void submit(biText("先告诉我当前工作区应该导入什么数据", "Tell me what data this workspace should import first"))}
              type="button"
            >
              <Bilingual zh="让 AI 判断缺口" en="Ask AI for gaps" />
            </button>
          </div>
        </article>
      </section>
    );
  }

  return (
    <section className="mainPanel" aria-labelledby="agent-title">
      <div className="panelHeader">
        <div>
          <p className="kicker">{biText("受控 Agent", "Controlled Agent")}</p>
          <h2 id="agent-title">
            <Bilingual zh="自然语言到证据链计划" en="Natural language to evidence-backed plan" />
          </h2>
        </div>
        <div className="statusPill">
          <span className="dot ok" />
          <span>{result.llm.mode}</span>
        </div>
      </div>

      <AgentPromptComposer
        isAsking={isAsking}
        prompt={prompt}
        setPrompt={setPrompt}
        setPromptTouched={setPromptTouched}
        submit={submit}
      />

      {result.answerCard ? (
        <AgentAnswerCard
          answerCard={result.answerCard}
          answerEvidenceSteps={answerEvidenceSteps}
          answerQuery={answerQuery}
          onAskCandidate={(candidatePrompt) => {
            setPromptTouched(true);
            void submit(candidatePrompt);
          }}
          queryRuntimeRef={queryRuntimeRef}
          runtimeEngine={runtimeEngine}
        />
      ) : null}

      <details className="progressiveDetails agentProgressiveDetails" data-testid="agent-suggestion-details">
        <summary>{biText("查看可提问建议", "View suggested questions")}</summary>
        <div className="progressiveDetailsBody single">
          <AgentCanAnswerPanel
            executableMetricCount={latestRun?.metric_sql_executable_count}
            isAsking={isAsking}
            onAskSuggestion={(suggestionPrompt) => {
              setPromptTouched(true);
              void submit(biText(suggestionPrompt.zh, suggestionPrompt.en));
            }}
            suggestions={canAnswerSuggestions}
          />
        </div>
      </details>

      <details className="progressiveDetails agentProgressiveDetails" data-testid="agent-evidence-audit-details">
        <summary>{biText("查看证据检查和模型审计", "View evidence checks and model audit")}</summary>
        <div className="progressiveDetailsBody single">
          <AgentEvidenceAuditPanels checkedItems={checkedItems} fallbackReason={llmAudit?.fallbackReason} llmAuditItems={llmAuditItems} />
        </div>
      </details>

      <details className="progressiveDetails agentProgressiveDetails" data-testid="agent-task-packet-details" open={pendingDrafts.length > 0}>
        <summary>{pendingDrafts.length ? biText("处理待确认修改", "Review pending changes") : biText("查看执行边界和任务包", "View execution boundary and task packet")}</summary>
        <div className="progressiveDetailsBody single">
          <AgentTaskPacket
            currentDraft={currentDraft}
            dashboardDraft={currentDashboardDraft}
            dashboardDraftTable={currentDashboardDraftTable}
            dashboardDraftWidgets={currentDashboardDraftWidgets}
            fallbackKind={result.actionDraft.kind}
          />
          <div className="agentGrid">
            <AgentContextPlanPanel
              activeBoundaryBlocked={activeBoundaryBlocked}
              activeDashboardConfidence={activeDashboardConfidence}
              activeDashboardLabel={activeDashboardLabel}
              activeHasWriteDraft={activeHasWriteDraft}
              canConfirmCurrent={canConfirmCurrent}
              result={result}
              targetBoundaryState={targetBoundaryState}
            />

            <AgentPendingChangesPanel
              activeActionKey={activeActionKey}
              activeActionKind={activeActionKind}
              activeActionResult={activeActionResult}
              canConfirmCurrent={canConfirmCurrent}
              currentDraft={currentDraft}
              draftImpactItems={draftImpactItems}
              nextDraftToReview={nextDraftToReview}
              onConfirmAction={onConfirmAction}
              onConfirmDryRun={onConfirmDryRun}
              onRejectAction={onRejectAction}
              onRunAction={runAction}
              pendingDrafts={pendingDrafts}
              riskyDraftCount={riskyDraftCount}
              runningActionKey={runningActionKey}
            />

            <article className="wideArticle">
              <details className="advancedDetails compactAdvanced agentRecommendedCommands" data-testid="agent-recommended-command-details">
                <summary>{biText("查看技术命令", "View technical commands")}</summary>
                <div className="commandList">
                  {result.recommendedCommands.map((command) => (
                    <code key={command}>{command}</code>
                  ))}
                </div>
              </details>
            </article>
          </div>
        </div>
      </details>
    </section>
  );
}
