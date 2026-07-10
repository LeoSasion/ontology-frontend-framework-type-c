import type { AgentAskResult, SourceIntelligenceRunSummary } from "../types";
import { buildStarterQuestions } from "../homeOverviewModel";
import { Bilingual, biText } from "./Bilingual";
import type { AppSection } from "./Sidebar";

type HomeOperatingSummaryPanelProps = {
  busy: "profile" | "dashboardDraft" | "dashboardCreate" | "query" | "ask" | null;
  latestDashboardDraft: AgentAskResult["actionDraft"] | null;
  latestRun?: SourceIntelligenceRunSummary;
  onAsk: (prompt: string) => Promise<void>;
  onOpenSection: (section: AppSection) => void;
  onQuery: () => Promise<void>;
  runBusy: <T>(key: Exclude<HomeOperatingSummaryPanelProps["busy"], null>, task: () => Promise<T>, nextSection?: AppSection) => Promise<void>;
  topRow?: Record<string, unknown>;
  topValue: number;
};

export function HomeOperatingSummaryPanel({
  busy,
  latestDashboardDraft,
  latestRun,
  onAsk,
  onOpenSection,
  onQuery,
  runBusy,
  topRow,
  topValue,
}: HomeOperatingSummaryPanelProps) {
  const starterQuestions = buildStarterQuestions(latestRun);
  return (
    <details className="advancedDetails homeOperatingDetails">
      <summary>{biText("查看常见问题和运营摘要", "View common questions and operating summary")}</summary>
      <div className="quickQuestionBox">
        <div>
          <h3><Bilingual zh="常见问题不用配置" en="Common questions need no setup" /></h3>
          <p>
            <Bilingual zh="这些问题会自动使用当前工作区和证据摘要；如果涉及写入，只生成草案。" en="These questions use the current workspace and evidence summary automatically. Writes become drafts only." />
          </p>
        </div>
        <div className="quickQuestionActions">
          {starterQuestions.map((question) => (
            <button
              className="questionChip"
              disabled={busy === "ask"}
              key={question.zh}
              onClick={() => runBusy("ask", () => onAsk(biText(question.zh, question.en)), "agent")}
              type="button"
            >
              <Bilingual {...question} />
            </button>
          ))}
        </div>
      </div>

      <div className="operatingSummaryGrid">
        <article>
          <span className="eyebrow">{biText("当前结论", "Current signal")}</span>
          <strong>
            {topRow
              ? biText(`${String(topRow.label)} 暂时最高`, `${String(topRow.label)} is currently highest`)
              : biText("等待查询结果", "Waiting for query result")}
          </strong>
          <p>
            {topRow
              ? biText(`指标值 ${topValue.toLocaleString()}，可打开仪表盘继续下钻。`, `Value ${topValue.toLocaleString()}. Open the dashboard to drill further.`)
              : biText("刷新一次结果后，这里会显示最重要的业务信号。", "Refresh once and the strongest business signal appears here.")}
          </p>
          <button className="miniButton" disabled={busy === "query"} onClick={() => runBusy("query", onQuery, "dashboards")} type="button">
            {biText("刷新并打开看板", "Refresh and open dashboard")}
          </button>
        </article>
        <article>
          <span className="eyebrow">{biText("证据链", "Evidence chain")}</span>
          <strong>{latestRun ? latestRun.label : biText("摘要待生成", "Summary pending")}</strong>
          <p>
            {latestRun
              ? `${latestRun.source_count} files · ${latestRun.relationship_count} relationships · ${latestRun.metric_sql_executable_count}/${latestRun.metric_sql_plan_count} metrics`
              : biText("先生成证据摘要，后续看板和 Agent 答案才有引用。", "Create the evidence summary first so dashboards and Agent answers can cite it.")}
          </p>
          <button className="miniButton" onClick={() => onOpenSection("evidence")} type="button">{biText("查看证据", "View evidence")}</button>
        </article>
        <article>
          <span className="eyebrow">{biText("动作边界", "Action boundary")}</span>
          <strong>{latestDashboardDraft ? biText("有看板草案", "Dashboard draft ready") : biText("写入先草案", "Writes become drafts")}</strong>
          <p>
            {latestDashboardDraft
              ? biText(`草案 ${latestDashboardDraft.actionKey} 等待确认。`, `Draft ${latestDashboardDraft.actionKey} is waiting for approval.`)
              : biText("导入提交、删除、覆盖、看板写入和关系保存都需要明确确认。", "Import commits, deletes, overwrites, dashboard writes, and relationship saves require explicit approval.")}
          </p>
          <button className="miniButton" onClick={() => onOpenSection("agent")} type="button">{biText("查看草案", "View drafts")}</button>
        </article>
      </div>

      <details className="advancedDetails">
        <summary>{biText("查看系统如何保证可信", "See how the system keeps this trustworthy")}</summary>
        <div className="trustGrid">
          <div>
            <strong>{biText("只读外部参考", "Read-only external references")}</strong>
            <span>{biText("旧项目不被写入，调试数据写在当前项目。", "Legacy projects are not modified; debug evidence stays in this project.")}</span>
          </div>
          <div>
            <strong>{latestRun ? latestRun.label : biText("摘要待生成", "Summary pending")}</strong>
            <span>{latestRun ? `${latestRun.source_count} files · ${latestRun.relationship_count} links · ${latestRun.metric_sql_executable_count}/${latestRun.metric_sql_plan_count} questions` : biText("点击生成摘要后生成证据。", "Create a summary to generate evidence.")}</span>
          </div>
          <div>
            <strong>{biText("写入前确认", "Confirm before writes")}</strong>
            <span>{biText("导入、删除、保存关系和创建看板都先生成草案。", "Imports, deletes, relationships, and dashboards become drafts first.")}</span>
          </div>
        </div>
      </details>
    </details>
  );
}
