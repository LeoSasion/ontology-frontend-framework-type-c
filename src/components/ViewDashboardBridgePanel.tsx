import "./viewDashboardBridgePanel.css";
import type { SavedView, SourceIntelligenceRunSummary } from "../types";
import type { ViewBridgeStep } from "../viewWorkspaceModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type ViewDashboardBridgePanelProps = {
  activeTableName: string;
  activeView?: SavedView;
  bridgeEvidenceCount: number;
  bridgeFilterScopeCount: number;
  bridgeSteps: ViewBridgeStep[];
  busy: string | null;
  columns: string[];
  latestSourceProfile?: SourceIntelligenceRunSummary;
  onAsk: (prompt: string) => Promise<void>;
  openViewEvidence: () => void;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  viewCanFeedDashboard: boolean;
};

export function ViewDashboardBridgePanel({
  activeTableName,
  activeView,
  bridgeEvidenceCount,
  bridgeFilterScopeCount,
  bridgeSteps,
  busy,
  columns,
  latestSourceProfile,
  onAsk,
  openViewEvidence,
  runBusy,
  viewCanFeedDashboard,
}: ViewDashboardBridgePanelProps) {
  return (
    <div className="viewBridgePanel" data-testid="view-dashboard-bridge">
      <div className="viewBridgeLead">
        <span className="storyMode"><Bilingual zh="视图到看板" en="View to dashboard" /></span>
        <strong>
          {viewCanFeedDashboard
            ? biText("当前视图可以作为看板组件来源", "This view can feed a dashboard widget")
            : biText("先刷新明细或补足字段，再进入看板", "Refresh rows or add fields before dashboarding")}
        </strong>
        <p>
          {biText(
            "视图保存字段、筛选、搜索和排序；Agent 起草组件时会沿用这些口径，确认前不会写入看板。",
            "A view saves columns, filters, search, and sort. Agent changes reuse that scope, and nothing writes to dashboards before approval.",
          )}
        </p>
      </div>
      <div className="viewBridgeFacts" data-testid="view-dashboard-bridge-facts">
        <div className={viewCanFeedDashboard ? "ok" : "warn"}>
          <strong>{columns.length}</strong>
          <span>{biText("可用列", "Columns")}</span>
        </div>
        <div className={bridgeFilterScopeCount ? "ok" : "neutral"}>
          <strong>{bridgeFilterScopeCount}</strong>
          <span>{biText("筛选口径", "Filter scope")}</span>
        </div>
        <div className={latestSourceProfile ? "ok" : "warn"}>
          <strong>{latestSourceProfile ? latestSourceProfile.relationship_count : 0}</strong>
          <span>{biText("关系证据", "Relationship evidence")}</span>
        </div>
        <div className="neutral">
          <strong>{bridgeEvidenceCount}</strong>
          <span>{biText("证据引用", "Evidence refs")}</span>
        </div>
      </div>
      <div className="viewBridgeSteps" data-testid="view-dashboard-bridge-steps">
        {bridgeSteps.map((step) => (
          <div className={`viewBridgeStep ${step.status}`} data-testid={`view-bridge-step-${step.key}`} key={step.key}>
            <span aria-hidden="true" />
            <strong>{step.title}</strong>
            <p>{step.detail}</p>
            <small>{step.meta}</small>
          </div>
        ))}
      </div>
      <div className="viewBridgeActions">
        <button data-testid="view-bridge-evidence" disabled={!activeView} onClick={openViewEvidence} type="button">
          <Icon name="evidence" />
          <Bilingual zh="查看视图证据" en="Review view evidence" />
        </button>
        <button
          data-testid="view-bridge-agent-widget"
          disabled={!activeView || busy === "view-bridge-agent-widget"}
          onClick={() => runBusy("view-bridge-agent-widget", () => onAsk(biText(
            `基于视图「${activeView?.name ?? activeTableName}」生成一个待确认的看板组件，沿用当前字段、筛选、搜索和排序；先说明证据和影响范围，不要直接写入。`,
            `Create a pending dashboard widget from view "${activeView?.name ?? activeTableName}" using the current columns, filters, search, and sort. Explain evidence and impact first; do not write directly.`,
          )))}
          type="button"
        >
          <Icon name="dashboard" />
          <Bilingual zh="生成组件修改" en="Create widget change" />
        </button>
      </div>
    </div>
  );
}
