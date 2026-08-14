import "./homeOverview.css";
import { FormEvent, useEffect, useState } from "react";
import type { AgentAskResult, WorkbenchPayload, WorkspaceStatus } from "../types";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import type { AnalysisJob } from "../typesJobs";
import { buildTrustedAnswerCoordinator } from "../trustedAnswerCoordinator";
import { Bilingual, biText, useLanguage } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type HomeOverviewProps = {
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  agent: AgentAskResult;
  pendingDraftCount: number;
  sourceIntelligenceJobs: AnalysisJob[];
  onAsk: (prompt: string) => Promise<AgentAskResult | null>;
  onSourceIntelligenceRun: (options?: SourceIntelligenceRunOptions) => Promise<Record<string, unknown> | void>;
  onOpenSection: (section: AppSection) => void;
};

const questionStarters = [
  {
    zh: "按时间查看一个核心指标的变化",
    en: "Show how one key metric changes over time",
  },
  {
    zh: "比较不同类别的结果差异",
    en: "Compare results across categories",
  },
  {
    zh: "找出异常值和需要补充的数据",
    en: "Find anomalies and missing data",
  },
];

export function HomeOverview({
  status,
  workbench,
  agent,
  pendingDraftCount,
  sourceIntelligenceJobs,
  onAsk,
  onSourceIntelligenceRun,
  onOpenSection,
}: HomeOverviewProps) {
  useLanguage();
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState<"profile" | "ask" | null>(null);
  const [submitError, setSubmitError] = useState("");
  const [evidenceError, setEvidenceError] = useState("");
  const coordinator = buildTrustedAnswerCoordinator({ status, workbench, agent, sourceIntelligenceJobs, pendingDraftCount });
  const { journey, recommendation } = coordinator;
  const latestRun = journey.latestRun;
  const latestUsableRun = journey.latestUsableRun;
  const workspaceName = status.workspace?.name || biText("当前工作区", "Current workspace");
  const workflowSteps = [
    { key: "data", label: biText("接入数据", "Connect data"), detail: biText("本地文件或连接器", "Local files or connectors"), section: "sources" as AppSection },
    { key: "evidence", label: biText("系统理解", "System understanding"), detail: biText("自动检查字段、关系与口径", "Automatically checks fields, relationships, and definitions"), section: "sources" as AppSection },
    { key: "question", label: biText("提出问题", "Ask a question"), detail: biText("描述答案或图表", "Describe an answer or chart"), section: "agent" as AppSection },
    { key: "review", label: biText("核对与确认", "Review and confirm"), detail: biText("结果、来源、口径与写入边界", "Results, sources, definitions, and write boundary"), section: "evidence" as AppSection },
  ];

  useEffect(() => {
    setSubmitError("");
    setEvidenceError("");
  }, [status.workspace?.id]);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedPrompt = prompt.trim();
    if (!normalizedPrompt || busy) return;
    setSubmitError("");
    setBusy("ask");
    try {
      const result = await onAsk(normalizedPrompt);
      if (!result) {
        setSubmitError(biText("分析没有完成；你的问题已保留。请重试，或检查本地服务状态。", "The analysis did not finish. Your question is preserved; retry or check the local service."));
        return;
      }
      setPrompt("");
      onOpenSection("agent");
    } catch {
      setSubmitError(biText("分析没有完成；你的问题已保留。请重试，或检查本地服务状态。", "The analysis did not finish. Your question is preserved; retry or check the local service."));
    } finally {
      setBusy(null);
    }
  }

  async function generateEvidence() {
    if (busy) return;
    setEvidenceError("");
    setBusy("profile");
    try {
      if (!journey.understanding.inputRoots.length) {
        onOpenSection("sources");
        return;
      }
      await onSourceIntelligenceRun({
        inputs: journey.understanding.inputRoots,
        label: latestRun?.label || biText("工作区证据", "Workspace evidence"),
        stayOnPage: true,
      });
    } catch {
      setEvidenceError(biText(
        "证据检查没有完成；原始数据未被改写。请检查本地服务或数据路径后重试。",
        "The evidence check did not finish and source data was not changed. Check the local service or data path, then retry.",
      ));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mainPanel workspaceHome" aria-labelledby="workspace-home-title">
      <div className="workspaceHomeIntro">
        <div>
          <span className="workspaceHomeLabel">{workspaceName}</span>
          <h1 id="workspace-home-title">
            <Bilingual zh="从一个问题开始" en="Start with one question" />
          </h1>
          <p>
            <Bilingual
              zh="系统负责检查数据、计算结果并保留证据；高级建模只在需要时出现。"
              en="The system checks data, calculates results, and keeps evidence. Advanced modeling appears only when needed."
            />
          </p>
        </div>
        <dl className="workspaceFacts" aria-label={biText("工作区概览", "Workspace summary")}>
          <div><dt><Bilingual zh="数据表" en="Tables" /></dt><dd>{status.counts.tables}</dd></div>
          <div><dt><Bilingual zh="证据运行" en="Evidence runs" /></dt><dd>{status.counts.sourceIntelligenceRuns ?? 0}</dd></div>
          <div><dt><Bilingual zh="看板" en="Boards" /></dt><dd>{status.counts.dashboards}</dd></div>
        </dl>
      </div>

      <ol className="workspaceJourney" data-testid="workspace-journey" aria-label={biText("可信分析流程", "Trusted analysis flow")}>
        {workflowSteps.map((step, index) => {
          const state = journey.stepStates[index];
          return (
            <li className={state} key={step.key}>
              <button
                aria-current={state === "current" ? "step" : undefined}
                disabled={state === "upcoming"}
                onClick={() => onOpenSection(step.section)}
                type="button"
              >
                <span className="journeyMarker">{state === "complete" ? <Icon name="check" /> : index + 1}</span>
                <span><strong>{step.label}</strong><small>{step.detail}</small></span>
              </button>
            </li>
          );
        })}
      </ol>

      {journey.hasData ? (
        <section
          aria-busy={Boolean(journey.activeJob)}
          className={`workspacePrimaryTask workspaceUnderstanding workspaceTaskEmpty ${journey.understanding.state}`}
          data-testid="workspace-understanding"
        >
          <span className="workspaceTaskIcon"><Icon name={journey.hasCurrentEvidence ? "check" : "evidence"} /></span>
          <div
            aria-label={biText("数据理解进度", "Data understanding progress")}
            aria-valuemax={journey.activeJob ? 100 : undefined}
            aria-valuemin={journey.activeJob ? 0 : undefined}
            aria-valuenow={journey.activeJob ? journey.understanding.progress : undefined}
            role={journey.activeJob ? "progressbar" : "status"}
          >
            <h3>
              {journey.understanding.state === "ready"
                ? biText("数据理解已就绪", "Data understanding is ready")
                : journey.understanding.state === "failed"
                  ? biText("自动理解没有完成", "Automatic understanding did not finish")
                  : journey.understanding.state === "stale"
                    ? biText("数据已变化，正在等待重新理解", "Data changed and is waiting to be understood again")
                    : biText("系统正在自动理解数据", "The system is understanding the data automatically")}
            </h3>
            <p>
              {latestUsableRun
                ? biText(
                  `已核对 ${latestUsableRun.source_count} 个来源中的 ${latestUsableRun.table_count} 张表和 ${latestUsableRun.relationship_count} 条关系路径；可据此计算 ${latestUsableRun.metric_sql_executable_count} 个指标问题。`,
                  `Verified ${latestUsableRun.table_count} tables across ${latestUsableRun.source_count} sources and ${latestUsableRun.relationship_count} relationship paths; ${latestUsableRun.metric_sql_executable_count} metric questions can be calculated from this evidence.`,
                )
                : journey.activeJob
                  ? biText(`后台进度 ${journey.understanding.progress}%${journey.understanding.stage ? ` · ${journey.understanding.stage}` : ""}`, `Background progress ${journey.understanding.progress}%${journey.understanding.stage ? ` · ${journey.understanding.stage}` : ""}`)
                  : biText("导入确认后自动检查，无需再配置一遍。", "Checks start automatically after import confirmation, with no repeated setup.")}
            </p>
          </div>
          {latestUsableRun ? (
            <button className="secondaryButton workspaceEvidenceButton" onClick={() => onOpenSection("evidence")} type="button">
              <Bilingual zh="查看依据" en="View evidence" />
            </button>
          ) : null}
        </section>
      ) : null}

      <div
        aria-label={biText("当前唯一推荐动作", "Current single recommended action")}
        className="workspacePrimaryTask"
        data-recommended-action={recommendation.actionKey}
        data-testid="workspace-primary-task"
      >
        <div className="workspaceRecommendation" data-testid="workspace-recommendation" role="status">
          <span><Bilingual zh="推荐下一步" en="Recommended next" /></span>
          <strong>{recommendation.label}</strong>
          <small>{recommendation.detail}</small>
        </div>
        {!journey.hasData ? (
          <div className="workspaceTaskEmpty">
            <span className="workspaceTaskIcon"><Icon name="source" /></span>
            <div>
              <h3><Bilingual zh="先接入一份真实数据" en="Connect one real dataset first" /></h3>
              <p><Bilingual zh="支持本地 CSV、Excel、文件夹或已配置的 Connector。系统会先预检，不会直接写入。" en="Use a local CSV, Excel file, folder, or configured connector. The system previews before any write." /></p>
            </div>
            <button className="primaryButton" data-testid="workspace-connect-data" onClick={() => onOpenSection("sources")} type="button">
              <Bilingual zh="接入数据" en="Connect data" />
            </button>
          </div>
        ) : !journey.hasCurrentEvidence ? (
          <div className="workspaceTaskEmpty">
            <span className="workspaceTaskIcon"><Icon name="evidence" /></span>
            <div>
              <h3>
                {journey.activeJob
                  ? biText("系统正在理解数据，完成后即可提问", "The system is understanding the data; questions unlock when it finishes")
                  : biText("系统理解需要处理", "System understanding needs attention")}
              </h3>
              <p>
                {journey.understanding.state === "failed"
                  ? biText("后台任务没有改写原始数据。可以检查路径后安全重试。", "The background job did not alter source data. Check the path and retry safely.")
                  : latestRun?.freshness?.usableForPlanning === false
                  ? biText("数据已经变化，旧证据不可继续用于规划。重新运行后再分析。", "The data changed, so previous evidence cannot be used for planning. Run it again before analysis.")
                  : biText("字段候选、关系路径和可执行口径会在后台自动完成；不确定项会明确阻断。", "Field candidates, relationship paths, and executable definitions are prepared automatically; uncertainty is explicitly blocked.")}
              </p>
            </div>
            {journey.activeJob ? null : (
              <button className="primaryButton" data-testid="workspace-prepare-evidence" disabled={busy === "profile"} onClick={() => void generateEvidence()} type="button">
                {busy === "profile" ? biText("正在重试…", "Retrying…") : biText("检查并重试", "Check and retry")}
              </button>
            )}
          </div>
        ) : journey.hasPendingDraft ? (
          <div className="workspaceTaskEmpty">
            <span className="workspaceTaskIcon"><Icon name="check" /></span>
            <div>
              <h3><Bilingual zh="核对等待确认的修改" en="Review the pending change" /></h3>
              <p><Bilingual zh="确认前不会写入数据、关系、视图或看板；也可以直接拒绝草案。" en="Nothing writes to data, relationships, views, or boards before approval. You can also reject the draft." /></p>
            </div>
            <button className="primaryButton" data-testid="workspace-review-draft" onClick={() => onOpenSection("agent")} type="button">
              <Bilingual zh="去核对" en="Review change" />
            </button>
          </div>
        ) : journey.hasAnswer ? (
          <div className="workspaceTaskEmpty">
            <span className="workspaceTaskIcon"><Icon name="evidence" /></span>
            <div>
              <h3>
                {journey.resultState === "blocked"
                  ? <Bilingual zh="分析需要补充一个条件" en="The analysis needs one more condition" />
                  : <Bilingual zh="可信结果已经生成" en="A trusted result is ready" />}
              </h3>
              <p>
                {journey.resultState === "blocked"
                  ? <Bilingual zh="系统没有发布未经证实的数字。请先处理结果中最高价值的澄清，再继续分析。" en="The system did not publish an unverified number. Resolve the highest-value clarification in the result before continuing." />
                  : <Bilingual zh="先核对结论、来源、指标口径和查询回执；需要继续比较时可在同一分析上下文追问。" en="Review the conclusion, sources, metric definition, and query receipt first. Continue comparing in the same analysis context when needed." />}
              </p>
            </div>
            <button className="primaryButton" data-testid="workspace-review-result" onClick={() => onOpenSection("agent")} type="button">
              <Bilingual zh="查看结果" en="Review result" />
            </button>
          </div>
        ) : (
          <div className="workspaceQuestionTask">
            <div className="workspaceQuestionLead">
              <span className="workspaceTaskIcon"><Icon name="agent" /></span>
              <div>
                <h3><Bilingual zh="你想从数据里知道什么？" en="What do you want to know from the data?" /></h3>
                <p>
                  {biText(
                    `系统会在当前工作区的 ${workbench.tables.length} 张表中匹配证据；字段或关系不明确时会一次列出候选。`,
                    `The system matches evidence across all ${workbench.tables.length} tables in this workspace and lists ambiguous fields or relationships once.`,
                  )}
                </p>
              </div>
            </div>
            <form className="workspaceQuestionForm" data-testid="workspace-question-form" onSubmit={submitQuestion}>
              <label htmlFor="workspace-question"><Bilingual zh="分析问题" en="Analysis question" /></label>
              <div>
                <textarea
                  id="workspace-question"
                  aria-describedby={busy === "ask" ? "workspace-question-help workspace-question-progress" : "workspace-question-help"}
                  disabled={busy === "ask"}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder={biText("例如：按月份比较各产品的收入变化，并标出异常月份", "For example: compare monthly revenue by product and flag unusual months")}
                  rows={3}
                  value={prompt}
                />
                <button className="primaryButton" disabled={busy === "ask" || !prompt.trim()} type="submit">
                  <Icon name="query" />
                  {busy === "ask" ? biText("正在匹配证据…", "Matching evidence…") : biText("开始分析", "Analyze")}
                </button>
              </div>
              <small id="workspace-question-help"><Bilingual zh="只读回答直接展示；任何真实写入都会停在确认步骤。" en="Read-only answers appear immediately. Any real write stops for review." /></small>
              {busy === "ask" ? (
                <small className="workspaceQuestionProgress" id="workspace-question-progress" role="status" aria-live="polite">
                  <Bilingual zh="正在匹配工作区数据并核对证据；可以切换页面，完成后结果会保留。" en="Matching workspace data and checking evidence. You can switch pages; the result is retained when complete." />
                </small>
              ) : null}
              {submitError ? <p className="workspaceQuestionError" role="alert">{submitError}</p> : null}
            </form>
            <div className="workspaceQuestionStarters" aria-label={biText("问题示例", "Question examples")}>
              {questionStarters.map((starter) => (
                <button disabled={busy === "ask"} key={starter.zh} onClick={() => setPrompt(biText(starter.zh, starter.en))} type="button">
                  <Bilingual {...starter} />
                </button>
              ))}
            </div>
          </div>
        )}
        {evidenceError ? <p className="workspaceQuestionError" role="alert">{evidenceError}</p> : null}
      </div>

      <div className="workspaceSecondaryActions">
        {journey.hasDashboard && journey.hasCurrentEvidence ? <button data-testid="workspace-open-board" onClick={() => onOpenSection("dashboards")} type="button"><Icon name="dashboard" /><span><Bilingual zh="打开最近看板" en="Open latest board" /></span></button> : null}
        {journey.hasCurrentEvidence ? <button onClick={() => onOpenSection("evidence")} type="button"><Icon name="evidence" /><span><Bilingual zh="核对证据" en="Review evidence" /></span></button> : null}
        <button onClick={() => onOpenSection("sources")} type="button"><Icon name="source" /><span><Bilingual zh="管理数据" en="Manage data" /></span></button>
        <details>
          <summary><Bilingual zh="高级工具" en="Advanced tools" /></summary>
          <div>
            <button onClick={() => onOpenSection("views")} type="button"><Bilingual zh="明细视图" en="Detail views" /></button>
            <button onClick={() => onOpenSection("settings")} type="button"><Bilingual zh="设置与迁移" en="Settings and migration" /></button>
          </div>
        </details>
      </div>
    </section>
  );
}
