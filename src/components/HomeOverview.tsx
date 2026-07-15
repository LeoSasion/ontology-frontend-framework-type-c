import "./homeOverview.css";
import { FormEvent, useMemo, useState } from "react";
import type { AgentAskResult, WorkbenchPayload, WorkspaceStatus } from "../types";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import { latestUsableSourceIntelligenceRun } from "../workspaceFlowModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type HomeOverviewProps = {
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  agent: AgentAskResult;
  onAsk: (prompt: string) => Promise<void>;
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

export function HomeOverview({ status, workbench, agent, onAsk, onSourceIntelligenceRun, onOpenSection }: HomeOverviewProps) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState<"profile" | "ask" | null>(null);
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const latestRun = sourceIntelligenceRuns[0];
  const latestUsableRun = latestUsableSourceIntelligenceRun(sourceIntelligenceRuns);
  const hasData = status.counts.tables > 0 || workbench.tables.length > 0;
  const hasCurrentEvidence = Boolean(latestUsableRun);
  const hasDashboard = status.counts.dashboards > 0;
  const hasPendingDraft = agent.requiresConfirmation === true || (status.counts.actionDrafts ?? 0) > 0;
  const currentStep = !hasData ? 0 : !hasCurrentEvidence ? 1 : hasPendingDraft ? 3 : 2;
  const mainTable = workbench.tables[0];
  const workspaceName = status.workspace?.name || biText("当前工作区", "Current workspace");
  const workflowSteps = useMemo(() => [
    { key: "data", label: biText("接入数据", "Connect data"), detail: biText("本地文件或连接器", "Local files or connectors"), section: "sources" as AppSection },
    { key: "evidence", label: biText("准备证据", "Prepare evidence"), detail: biText("字段、关系与可执行口径", "Fields, relationships, and executable definitions"), section: "sources" as AppSection },
    { key: "question", label: biText("提出问题", "Ask a question"), detail: biText("描述答案或图表", "Describe an answer or chart"), section: "agent" as AppSection },
    { key: "review", label: biText("核对结果", "Review result"), detail: biText("来源、口径与回执", "Sources, definitions, and receipts"), section: "evidence" as AppSection },
  ], []);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedPrompt = prompt.trim();
    if (!normalizedPrompt || busy) return;
    setBusy("ask");
    try {
      await onAsk(normalizedPrompt);
      setPrompt("");
      onOpenSection("agent");
    } finally {
      setBusy(null);
    }
  }

  async function generateEvidence() {
    if (busy) return;
    setBusy("profile");
    try {
      await onSourceIntelligenceRun();
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mainPanel workspaceHome" aria-labelledby="workspace-home-title">
      <div className="workspaceHomeIntro">
        <div>
          <span className="workspaceHomeLabel">{workspaceName}</span>
          <h2 id="workspace-home-title">
            <Bilingual zh="从一个问题开始" en="Start with one question" />
          </h2>
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
          const state = index < currentStep ? "complete" : index === currentStep ? "current" : "upcoming";
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

      <div className="workspacePrimaryTask" data-testid="workspace-primary-task">
        {!hasData ? (
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
        ) : !hasCurrentEvidence ? (
          <div className="workspaceTaskEmpty">
            <span className="workspaceTaskIcon"><Icon name="evidence" /></span>
            <div>
              <h3><Bilingual zh="生成证据摘要，再开始提问" en="Prepare evidence before asking" /></h3>
              <p>
                {latestRun?.freshness?.usableForPlanning === false
                  ? biText("数据已经变化，旧证据不可继续用于规划。重新运行后再分析。", "The data changed, so previous evidence cannot be used for planning. Run it again before analysis.")
                  : biText("系统会检查字段候选、关系路径和可执行指标，并明确无法判断的部分。", "The system checks field candidates, relationship paths, and executable metrics, and clearly marks unresolved items.")}
              </p>
            </div>
            <button className="primaryButton" data-testid="workspace-prepare-evidence" disabled={busy === "profile"} onClick={() => void generateEvidence()} type="button">
              {busy === "profile" ? biText("正在生成…", "Preparing…") : biText("生成证据摘要", "Prepare evidence")}
            </button>
          </div>
        ) : hasPendingDraft ? (
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
        ) : (
          <div className="workspaceQuestionTask">
            <div className="workspaceQuestionLead">
              <span className="workspaceTaskIcon"><Icon name="agent" /></span>
              <div>
                <h3><Bilingual zh="你想从数据里知道什么？" en="What do you want to know from the data?" /></h3>
                <p>
                  {mainTable
                    ? biText(`当前从「${mainTable.display_name}」开始；字段不明确时，系统会一次性列出候选。`, `Starting from “${mainTable.display_name}”. If a field is ambiguous, the system lists candidates once.`)
                    : biText("描述答案、比较对象或想看的图表。", "Describe the answer, comparison, or chart you need.")}
                </p>
              </div>
            </div>
            <form className="workspaceQuestionForm" data-testid="workspace-question-form" onSubmit={submitQuestion}>
              <label htmlFor="workspace-question"><Bilingual zh="分析问题" en="Analysis question" /></label>
              <div>
                <textarea
                  id="workspace-question"
                  aria-describedby="workspace-question-help"
                  disabled={busy === "ask"}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder={biText("例如：按月份比较各产品的收入变化，并标出异常月份", "For example: compare monthly revenue by product and flag unusual months")}
                  rows={3}
                  value={prompt}
                />
                <button className="primaryButton" disabled={busy === "ask" || !prompt.trim()} type="submit">
                  <Icon name="query" />
                  {busy === "ask" ? biText("正在分析…", "Analyzing…") : biText("开始分析", "Analyze")}
                </button>
              </div>
              <small id="workspace-question-help"><Bilingual zh="只读回答直接展示；任何真实写入都会停在确认步骤。" en="Read-only answers appear immediately. Any real write stops for review." /></small>
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
      </div>

      <div className="workspaceSecondaryActions">
        {hasDashboard && hasCurrentEvidence ? <button data-testid="workspace-open-board" onClick={() => onOpenSection("dashboards")} type="button"><Icon name="dashboard" /><span><Bilingual zh="打开最近看板" en="Open latest board" /></span></button> : null}
        {hasCurrentEvidence ? <button onClick={() => onOpenSection("evidence")} type="button"><Icon name="evidence" /><span><Bilingual zh="核对证据" en="Review evidence" /></span></button> : null}
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
