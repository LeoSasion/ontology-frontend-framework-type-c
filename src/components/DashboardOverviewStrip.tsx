import { dashboardAcceptanceItems } from "../dashboardCanvasEditorOptions";
import type { DashboardSummaryModel } from "../dashboardCanvasSummaryModel";
import { Bilingual, biText } from "./Bilingual";

type DashboardOverviewStripProps = {
  dashboardCreatedBy: string;
  dashboardEditBoundary: string;
  dashboardFiltersCount: number;
  dashboardIsAgentManaged: boolean;
  dashboardSourceLabel: string;
  dashboardSummary: DashboardSummaryModel;
  dashboardWidgetsCount: number;
  onOpenEvidence: () => void;
};

export function DashboardOverviewStrip({
  dashboardCreatedBy,
  dashboardEditBoundary,
  dashboardFiltersCount,
  dashboardIsAgentManaged,
  dashboardSourceLabel,
  dashboardSummary,
  dashboardWidgetsCount,
  onOpenEvidence,
}: DashboardOverviewStripProps) {
  return (
    <>
      <section className="dashboardAssetSourceStrip wide" data-testid="dashboard-asset-source-strip" aria-label={biText("看板资产来源", "Dashboard asset source")}>
        <div className="dashboardAssetSourceLead">
          <span className={dashboardIsAgentManaged ? "assetSourceBadge agent" : "assetSourceBadge manual"} data-testid="dashboard-source-label">
            {dashboardSourceLabel}
          </span>
          <div>
            <strong><Bilingual zh="可编辑资产，不是黑盒结果" en="Editable asset, not a black-box result" /></strong>
            <span>{dashboardEditBoundary}</span>
          </div>
        </div>
        <div className="dashboardAssetSourceFacts" data-testid="dashboard-source-facts">
          <span>{biText("来源", "Source")}: {dashboardCreatedBy}</span>
          <span>{dashboardIsAgentManaged ? biText("Agent-managed", "Agent-managed") : biText("Manual-owned", "Manual-owned")}</span>
          <span>{biText(`${dashboardWidgetsCount} 个组件可编辑`, `${dashboardWidgetsCount} editable widgets`)}</span>
          <span>{biText(`${dashboardFiltersCount} 条筛选可预演`, `${dashboardFiltersCount} filters previewable`)}</span>
        </div>
      </section>

      <section className="dashboardStoryStrip wide" aria-label={biText("看板摘要", "Dashboard summary")}>
        <div className="storyLead">
          <span className="storyMode"><Bilingual zh="老板晨会版" en="Executive view" /></span>
          <h3><Bilingual zh="先看结论，再追证据" en="Read the outcome first, then inspect evidence" /></h3>
          <p>
            <Bilingual
              zh="这个看板把指标、筛选、来源和待确认动作放在同一张工作台里；每个结果都优先追到当前工作区证据。"
              en="This dashboard keeps metrics, filters, sources, and confirmable actions in one workspace; each result traces back to current workspace evidence first."
            />
          </p>
        </div>
        <div className="storyMetricGrid">
          <article>
            <span><Bilingual zh="当前最高项" en="Top result" /></span>
            <strong>{dashboardSummary.topRow ? dashboardSummary.topRow.label : "-"}</strong>
            <small>{dashboardSummary.topRow ? dashboardSummary.topRow.value.toLocaleString() : "-"}</small>
          </article>
          <article>
            <span><Bilingual zh="当前范围" en="Current scope" /></span>
            <strong>{dashboardSummary.currentGroupLabel}</strong>
            <small>{dashboardSummary.currentScopeDetail}</small>
          </article>
          <article>
            <span><Bilingual zh="证据覆盖" en="Evidence coverage" /></span>
            <strong>{dashboardSummary.evidenceCoverageValue}</strong>
            <small>{dashboardSummary.evidenceCoverageDetail}</small>
          </article>
          <article>
            <span><Bilingual zh="合计读数" en="Total reading" /></span>
            <strong>{dashboardSummary.totalValue.toLocaleString()}</strong>
            <small>{dashboardSummary.totalDetail}</small>
          </article>
        </div>
      </section>

      <section className="dashboardComponentAcceptanceStrip wide compactAcceptance" data-testid="dashboard-component-acceptance-strip" aria-label={biText("组件能力验收", "Component capability acceptance")}>
        <div className="dashboardComponentAcceptanceLead">
          <span className="storyMode"><Bilingual zh="组件验收" en="Widget acceptance" /></span>
          <strong><Bilingual zh="组件能力已归档到验收清单" en="Widget capabilities are archived in the acceptance checklist" /></strong>
          <p>
            <Bilingual
              zh="验收信息不再占用主流程；需要检查组件能力时再展开。真正修改仍进高级工作台并保留确认边界。"
              en="Acceptance details no longer occupy the main path; expand only when checking widget capabilities. Real edits still go through the advanced workbench with confirmation boundaries."
            />
          </p>
        </div>
        <details className="dashboardComponentAcceptanceDetails">
          <summary>{biText(`${dashboardAcceptanceItems.length} 项能力，按需展开`, `${dashboardAcceptanceItems.length} capabilities, expand when needed`)}</summary>
          <div className="dashboardComponentAcceptanceItems" data-testid="dashboard-component-acceptance-items">
            {dashboardAcceptanceItems.map((item) => (
              <span data-testid={`dashboard-component-acceptance-${item.key}`} key={item.key}>
                <Bilingual zh={item.zh} en={item.en} />
              </span>
            ))}
          </div>
        </details>
        <button className="miniButton" onClick={onOpenEvidence} type="button">
          {biText("看证据", "Evidence")}
        </button>
      </section>
    </>
  );
}
