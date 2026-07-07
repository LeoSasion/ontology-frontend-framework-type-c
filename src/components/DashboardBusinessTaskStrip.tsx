import { useState } from "react";
import type { BusinessDashboardOptions } from "../dashboardCanvasContracts";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardBusinessTaskStripProps = {
  dashboardName: string;
  defaultTableKey: string;
  busy: string | null;
  onAsk: (label: string, prompt: string) => void;
  onOpenEvidence: () => void;
  onBusinessTemplate: (label: string, options: BusinessDashboardOptions) => void;
};

export function DashboardBusinessTaskStrip({
  dashboardName,
  defaultTableKey,
  busy,
  onAsk,
  onOpenEvidence,
  onBusinessTemplate,
}: DashboardBusinessTaskStripProps) {
  const singleChartPrompt = biText(
    `基于「${dashboardName}」和 ${defaultTableKey}，先问我最多一个必要问题，然后起草一个可确认的单图表。优先在折线图、柱状图、指标卡或表格中选择，说明字段、口径和证据，不直接写入。`,
    `Using "${dashboardName}" and ${defaultTableKey}, ask at most one needed question, then draft one confirmable chart. Prefer line, bar, metric card, or table; explain fields, metric definition, and evidence. Do not write directly.`,
  );
  const [prompt, setPrompt] = useState(singleChartPrompt);
  const resolvedPrompt = prompt.trim() || singleChartPrompt;

  return (
    <section className="dashboardBusinessTaskStrip dashboardAICreatePanel wide" data-testid="dashboard-business-task-strip" aria-label={biText("看板业务任务", "Dashboard business tasks")}>
      <div className="dashboardBusinessTaskLead">
        <span className="storyMode"><Bilingual zh="AI 创建" en="AI create" /></span>
        <h3><Bilingual zh="先说想看的一个图表" en="Describe one chart first" /></h3>
        <p>
          <Bilingual
            zh="默认只引导创建一个图表；行业整套看板保留 beta 入口。涉及写入仍先生成草案。"
            en="The default path creates one guided chart; full industry dashboards remain a beta entry. Writes still become drafts first."
          />
        </p>
      </div>
      <div className="dashboardAICreateBody">
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
            disabled={busy === "dashboard-task-explain"}
            onClick={() => onAsk("dashboard-task-explain", resolvedPrompt)}
            type="button"
          >
            <Icon name="agent" />
            <span>
              <strong><Bilingual zh="生成一个图表" en="Create one chart" /></strong>
              <small><Bilingual zh="单次对话给草案" en="Guided draft" /></small>
            </span>
          </button>
          <button data-testid="dashboard-task-evidence" onClick={onOpenEvidence} type="button">
            <Icon name="evidence" />
            <span>
              <strong><Bilingual zh="完整证据" en="Full evidence" /></strong>
              <small><Bilingual zh="来源、指标和组件" en="Sources and metrics" /></small>
            </span>
          </button>
        </div>
        <details className="advancedDetails compactAdvanced dashboardBetaDetails" data-testid="dashboard-beta-details">
          <summary><Bilingual zh="高级：优化或行业看板 Beta" en="Advanced: optimize or industry beta" /></summary>
          <div className="dashboardBusinessTasks secondary">
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
              disabled={busy === "business-template-preview"}
              onClick={() => onBusinessTemplate("business-template-preview", { op: "draft", table: defaultTableKey, template: "erp-units", limit: 24 })}
              type="button"
            >
              <Icon name="check" />
              <span>
                <strong><Bilingual zh="经营模板 Beta" en="Industry beta" /></strong>
                <small><Bilingual zh="先预演影响" en="Preview impact" /></small>
              </span>
            </button>
          </div>
        </details>
      </div>
    </section>
  );
}
