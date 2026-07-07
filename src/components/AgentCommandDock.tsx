import { FormEvent, useMemo, useState } from "react";
import { getAppSection } from "../appSections";
import type { AppSection } from "../appSections";
import { resolveAgentPromptRoute, type AgentPromptRoute } from "../agentPromptRouting";
import type { ActionDraft, AgentAskResult, WorkspaceStatus } from "../types";
import { Bilingual, biText, translateName } from "./Bilingual";
import { Icon } from "./Icons";

type AgentCommandDockProps = {
  activeSection: AppSection;
  status: WorkspaceStatus;
  agent: AgentAskResult;
  actionDrafts: ActionDraft[];
  onAsk: (prompt: string, targetSection?: AppSection) => Promise<void>;
  onOpenAgent: () => void;
  onOpenSection: (section: AppSection) => void;
};

const starterPrompts = [
  {
    zh: "先告诉我现在能回答什么",
    en: "Tell me what this workspace can answer",
  },
  {
    zh: "生成经营看板修改",
    en: "Create a dashboard change",
  },
  {
    zh: "检查退款压力并给证据",
    en: "Explain refund pressure with evidence",
  },
];

export function AgentCommandDock({ activeSection, status, agent, actionDrafts, onAsk, onOpenAgent, onOpenSection }: AgentCommandDockProps) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [routeHint, setRouteHint] = useState<AgentPromptRoute | null>(null);
  const expanded = assistantOpen;
  const pendingDrafts = actionDrafts.filter((draft) => draft.status === "draft");
  const latestDraft = pendingDrafts[0];
  const matchedDashboard = agent.matched?.dashboard;
  const matchedTable = agent.matched?.table;
  const evidenceCount = Array.isArray(agent.ontology?.evidenceFiles) ? agent.ontology.evidenceFiles.length : 0;
  const sourceIntelligenceCount = status.counts.sourceIntelligenceRuns ?? 0;
  const hasTables = status.counts.tables > 0;
  const hasEvidenceProfile = sourceIntelligenceCount > 0 || evidenceCount > 0;
  const readiness = useMemo(() => {
    if (pendingDrafts.length > 0) {
      return {
        tone: "warn",
        label: biText(`${pendingDrafts.length} 个修改待确认`, `${pendingDrafts.length} changes pending`),
        detail: biText("确认前不会写入数据或看板。", "No data or dashboard write runs before approval."),
      };
    }
    if (!hasTables) {
      return {
        tone: "warn",
        label: biText("先接入数据", "Add data first"),
        detail: biText("从数据源工作台开始，先预检再确认。", "Start in Sources, preview first, then confirm."),
      };
    }
    if (status.counts.dashboards === 0) {
      return {
        tone: "info",
        label: biText("可以生成首个看板", "Ready for first dashboard"),
        detail: biText("Agent 先生成待确认修改，工作台负责落地编辑。", "Agent creates pending changes first; the workbench keeps them editable."),
      };
    }
    return {
      tone: "ok",
      label: biText("可以直接提问", "Ready to ask"),
      detail: biText("问题会绑定当前工作区、数据表和证据。", "Questions stay bound to the current workspace, table, and evidence."),
    };
  }, [hasTables, pendingDrafts.length, status.counts.dashboards]);
  const decisionItems = [
    {
      key: "can-answer",
      tone: hasTables ? "ok" : "muted",
      label: biText("能回答", "Can answer"),
      detail: hasTables
        ? hasEvidenceProfile
          ? biText("可基于当前证据提问", "Ask from current evidence")
          : biText("可先生成缺口计划", "Start with a gap plan")
        : biText("先接入数据", "Add data first"),
      action: () => submitPrompt(undefined, hasEvidenceProfile
        ? biText("先告诉我当前工作区现在能回答什么，并列出证据", "Tell me what this workspace can answer now and list the evidence")
        : biText("先告诉我当前工作区缺什么数据，下一步怎么做", "Tell me what data is missing and what to do next")),
    },
    {
      key: "need-confirmation",
      tone: pendingDrafts.length ? "warn" : "muted",
      label: biText("待确认", "Review needed"),
      detail: pendingDrafts.length
        ? biText(`${pendingDrafts.length} 个修改待处理`, `${pendingDrafts.length} changes pending`)
        : biText("暂无待写入修改", "No write changes pending"),
      action: onOpenAgent,
    },
    {
      key: "missing-data",
      tone: !hasTables || !hasEvidenceProfile ? "warn" : "ok",
      label: biText("缺数据", "Missing data"),
      detail: !hasTables
        ? biText("还没有数据表", "No tables yet")
        : hasEvidenceProfile
          ? biText("证据摘要可用", "Evidence summary ready")
          : biText("缺证据摘要", "Evidence summary missing"),
      action: () => onOpenSection("sources"),
    },
  ];
  const targetLabel = matchedDashboard
    ? translateName(matchedDashboard.name)
    : matchedTable
      ? translateName(matchedTable.display_name)
      : { zh: "尚未匹配目标", en: "No target matched yet" };
  const workspaceLabel = translateName(status.workspace.name);
  const sectionLabel = getAppSection(activeSection);
  const routeSectionLabel = routeHint ? getAppSection(routeHint.section) : null;
  const shouldMinimize = !hasTables && !assistantOpen && activeSection !== "agent";

  async function submitPrompt(event?: FormEvent<HTMLFormElement>, nextPrompt = prompt) {
    event?.preventDefault();
    const normalizedPrompt = nextPrompt.trim();
    if (!normalizedPrompt) {
      return;
    }
    const route = resolveAgentPromptRoute(normalizedPrompt, status);
    setRouteHint(route);
    if (route.section !== activeSection) {
      onOpenSection(route.section);
    }
    setBusy(true);
    try {
      await onAsk(normalizedPrompt, route.section);
      setPrompt("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className={`agentCommandDock floating ${assistantOpen ? "open expanded" : "closed compact"} ${activeSection === "agent" ? "active" : ""} ${shouldMinimize ? "onboardingMinimized" : ""}`}
      aria-busy={busy}
      aria-label={biText("全局 AI 助手", "Global AI assistant")}
      data-testid="agent-command-dock"
    >
      {assistantOpen ? (
        <div className="agentFloatPanel" data-testid="floating-agent-panel">
          <div className="agentFloatHeader">
            <div className="agentDockContext">
              <span className="agentDockMark"><Icon name="agent" /></span>
              <div>
                <strong><Bilingual zh="AI 助手" en="AI assistant" /></strong>
                <span>
                  {biText(`${workspaceLabel.zh} · ${targetLabel.zh}`, `${workspaceLabel.en} · ${targetLabel.en}`)}
                </span>
              </div>
            </div>
            <button
              aria-label={biText("收起 AI 助手", "Collapse AI assistant")}
              className="agentFloatClose"
              data-testid="floating-agent-close"
              onClick={() => setAssistantOpen(false)}
              type="button"
            >
              <Icon name="close" />
            </button>
          </div>

          <div className="agentDockMain">
            <div className="agentDockStatusRow">
              <span className={`agentDockState ${readiness.tone}`}>{readiness.label}</span>
              <span>{readiness.detail}</span>
              <span>{biText(`当前页：${sectionLabel.zh}`, `Page: ${sectionLabel.en}`)}</span>
              <span>{biText(`${evidenceCount} 个证据项`, `${evidenceCount} evidence items`)}</span>
            </div>
          </div>

          <div className="agentDockInputArea">
            <form className="agentDockForm" onSubmit={submitPrompt}>
              <input
                aria-label={biText("输入分析问题", "Enter analysis question")}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder={biText("直接问：本月哪个渠道卖得最好？", "Ask: which channel sold best this month?")}
                value={prompt}
              />
              <button className="primaryButton" disabled={busy} type="submit">
                <Icon name="query" />
                <Bilingual zh="提问" en="Ask" />
              </button>
            </form>

            <div className="agentDockShortcuts" aria-hidden={!expanded}>
              {starterPrompts.map((item) => (
                <button
                  disabled={busy}
                  key={item.zh}
                  onClick={() => {
                    void submitPrompt(undefined, biText(item.zh, item.en));
                  }}
                  type="button"
                >
                  <Bilingual {...item} />
                </button>
              ))}
            </div>
            {routeHint && routeSectionLabel ? (
              <div className="agentRouteHint" data-testid="agent-route-hint" aria-live="polite">
                <Icon name={routeSectionLabel.icon} />
                <span>
                  <Bilingual
                    zh={`已切到${routeSectionLabel.zh}：${routeHint.reasonZh}`}
                    en={`Opened ${routeSectionLabel.en}: ${routeHint.reasonEn}`}
                  />
                </span>
              </div>
            ) : null}
          </div>

          <div className="agentDockDecisionLane" data-testid="agent-decision-lane" aria-label={biText("工作区状态", "Workspace decision state")} aria-hidden={!expanded}>
            {decisionItems.map((item) => (
              <button className={item.tone} data-testid={`agent-decision-${item.key}`} disabled={busy} key={item.key} onClick={() => void item.action()} type="button">
                <strong>{item.label}</strong>
                <span>{item.detail}</span>
              </button>
            ))}
          </div>

          <div className="agentDockTaskStrip" data-testid="agent-task-strip">
            <button data-testid="agent-task-sources" onClick={() => onOpenSection("sources")} title={biText("检查数据源", "Check sources")} type="button">
              <Icon name="source" />
              <span><Bilingual zh={expanded ? "检查数据源" : "数据"} en={expanded ? "Check sources" : "Data"} /></span>
              <small>{biText(`${status.counts.tables} 张表`, `${status.counts.tables} tables`)}</small>
            </button>
            <button
              data-testid="agent-task-dashboard"
              disabled={busy}
              onClick={() => {
                void submitPrompt(undefined, biText("生成一个经营看板待确认修改，先不要直接写入", "Create a pending business dashboard change without writing directly"));
              }}
              title={biText("生成看板修改", "Create dashboard change")}
              type="button"
            >
              <Icon name="dashboard" />
              <span><Bilingual zh={expanded ? "起草看板修改" : "看板"} en={expanded ? "Draft dashboard change" : "Board"} /></span>
              <small>{biText(`${status.counts.dashboards} 个看板`, `${status.counts.dashboards} dashboards`)}</small>
            </button>
            <button data-testid="agent-task-evidence" onClick={() => onOpenSection("evidence")} title={biText("查看证据", "View evidence")} type="button">
              <Icon name="evidence" />
              <span><Bilingual zh={expanded ? "查看完整证据" : "证据"} en={expanded ? "Open full evidence" : "Proof"} /></span>
              <small>{biText(`${evidenceCount} 个文件`, `${evidenceCount} files`)}</small>
            </button>
            {latestDraft ? (
              <button className="draftShortcut" data-testid="agent-task-drafts" onClick={onOpenAgent} type="button">
                <Icon name="check" />
                <span>{biText("确认修改", "Review change")}</span>
                <small>{latestDraft.label}</small>
              </button>
            ) : (
              <button
                className="draftShortcut"
                data-testid="agent-task-ask"
                disabled={busy}
                onClick={() => {
                  void submitPrompt(undefined, biText("先告诉我当前工作区下一步应该做什么", "Tell me the best next step for this workspace"));
                }}
                title={biText("让 Agent 带路", "Let Agent guide")}
                type="button"
              >
                <Icon name="agent" />
                <span><Bilingual zh={expanded ? "让 Agent 带路" : "引导"} en={expanded ? "Let Agent guide" : "Guide"} /></span>
                <small><Bilingual zh="不写入" en="no write" /></small>
              </button>
            )}
          </div>
        </div>
      ) : (
        <button
          aria-expanded="false"
          className="agentFloatButton"
          data-testid="floating-agent-button"
          onClick={() => setAssistantOpen(true)}
          type="button"
        >
          <span className="agentDockMark"><Icon name="agent" /></span>
          <span className="agentFloatButtonText">
            <strong><Bilingual zh="AI 助手" en="AI assistant" /></strong>
            <small>{readiness.label}</small>
          </span>
          {pendingDrafts.length > 0 ? (
            <span className="agentFloatBadge" aria-label={biText(`${pendingDrafts.length} 个待确认修改`, `${pendingDrafts.length} pending changes`)}>
              {pendingDrafts.length}
            </span>
          ) : (
            <span className={`agentFloatStatusDot ${readiness.tone}`} aria-hidden="true" />
          )}
        </button>
      )}
    </section>
  );
}
