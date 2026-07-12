import { useState } from "react";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardBusinessTaskStripProps = {
  dashboardName: string;
  hasDashboard: boolean;
  tableKey?: string;
  tableName?: string;
  busy: string | null;
  compact?: boolean;
  onAsk: (label: string, prompt: string) => void;
  onOpenEvidence: () => void;
};

export function DashboardBusinessTaskStrip({
  dashboardName,
  hasDashboard,
  tableKey = "",
  tableName = "",
  busy,
  compact = false,
  onAsk,
  onOpenEvidence,
}: DashboardBusinessTaskStripProps) {
  const [prompt, setPrompt] = useState("");
  const resolvedPrompt = prompt.trim();
  const promptReady = Boolean(resolvedPrompt);
  const scopedPrompt = tableKey
    ? biText(`基于数据表「${tableName || tableKey}」，${resolvedPrompt}`, `Using table "${tableName || tableKey}", ${resolvedPrompt}`)
    : resolvedPrompt;

  return (
    <section className={`dashboardBusinessTaskStrip dashboardAICreatePanel wide${compact ? " compact" : ""}`} data-testid="dashboard-business-task-strip" aria-label={biText("看板业务任务", "Dashboard business tasks")}>
      <div className="dashboardBusinessTaskLead">
        <span className="storyMode"><Bilingual zh="AI 创建" en="AI create" /></span>
        <h3><Bilingual zh="先说想看的一个图表" en="Describe one chart first" /></h3>
        {!compact ? <p>
          <Bilingual
            zh={hasDashboard
              ? "默认只引导创建一个图表；整套证据看板保留 Beta 入口。涉及写入仍先生成草案。"
              : "当前还没有看板；确认后只创建一个图表。整套证据看板仍保留在 Beta 入口。"}
            en={hasDashboard
              ? "The default path creates one guided chart; full evidence dashboards remain a beta entry. Writes still become drafts first."
              : "There is no dashboard yet. Approval creates one chart only; full evidence dashboards remain a beta entry."}
          />
        </p> : null}
      </div>
      <div className="dashboardAICreateBody">
        {tableKey ? <small className="dashboardTaskContext">{biText(`当前数据：${tableName || tableKey}`, `Current data: ${tableName || tableKey}`)}</small> : null}
        <label className="dashboardAIPromptBox">
          <span>{biText("我想看", "I want to see")}</span>
          <textarea
            data-testid="dashboard-ai-chart-prompt"
            onChange={(event) => setPrompt(event.target.value)}
            placeholder={biText("描述指标、维度、时间范围或想比较的对象", "Describe the metric, dimension, time range, or comparison")}
            value={prompt}
          />
        </label>
        <div className="dashboardBusinessTasks">
          <button
            data-testid="dashboard-task-explain"
            disabled={busy === "dashboard-task-explain" || !promptReady}
            onClick={() => onAsk("dashboard-task-explain", scopedPrompt)}
            type="button"
          >
            <Icon name="agent" />
            <span>
              <strong><Bilingual zh="生成一个图表" en="Create one chart" /></strong>
              <small><Bilingual zh={promptReady ? "单次对话给草案" : "先描述目标"} en={promptReady ? "Guided draft" : "Describe the goal first"} /></small>
            </span>
          </button>
        </div>
        {!compact ? <details className="advancedDetails compactAdvanced dashboardBetaDetails" data-testid="dashboard-beta-details">
          <summary><Bilingual zh="更多" en="More" /></summary>
          <div className="dashboardBusinessTasks secondary">
            <button data-testid="dashboard-task-evidence" onClick={onOpenEvidence} type="button">
              <Icon name="evidence" />
              <span>
                <strong><Bilingual zh="核对完整证据" en="Review full evidence" /></strong>
                <small><Bilingual zh="来源、指标和组件" en="Sources and metrics" /></small>
              </span>
            </button>
            <button
              data-testid="dashboard-task-improve"
              disabled={busy === "dashboard-task-improve"}
              onClick={() => onAsk("dashboard-task-improve", biText(`基于「${dashboardName}」检查当前组件，起草一个最小可确认优化，只改最影响阅读的一处。`, `Inspect "${dashboardName}" and draft the smallest confirmable improvement, changing only the highest-impact readability issue.`))}
              type="button"
            >
              <Icon name="dashboard" />
              <span>
                <strong><Bilingual zh="只改一处" en="Improve one thing" /></strong>
                <small><Bilingual zh="确认前不写入" en="Draft only" /></small>
              </span>
            </button>
            <button
              data-testid="dashboard-task-template"
              disabled={busy === "dashboard-task-template"}
              onClick={() => onAsk("dashboard-task-template", biText(`基于「${dashboardName}」和当前证据中已执行成功的分析，一次起草整套可编辑看板。只使用有字段与查询回执支持的图表，不支持的内容直接省略，先不要写入。`, `Using "${dashboardName}" and analyses successfully executed in current evidence, draft a full editable dashboard. Use only charts supported by fields and query receipts; omit unsupported content and do not write yet.`))}
              type="button"
            >
              <Icon name="check" />
              <span>
                <strong><Bilingual zh="整套看板 Beta" en="Full dashboard beta" /></strong>
                <small><Bilingual zh="证据不足就省略" en="Omit unsupported charts" /></small>
              </span>
            </button>
          </div>
        </details> : null}
      </div>
    </section>
  );
}
