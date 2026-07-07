import { B_DASHBOARD_WIDGET_CATALOG } from "../biDashboardModel";
import { B_WIDGET_ACCEPTANCE_ITEMS, B_WIDGET_READING_PURPOSES } from "../biDashboardWidgetKitModel";
import type { BiDashboardWidget } from "../biDashboardModel";
import type { DashboardPage, EvidenceFocus, SourceIntelligenceRunSummary } from "../types";
import { Bilingual, biText } from "./Bilingual";

type BiDashboardWidgetKitOverviewProps = {
  dashboard: DashboardPage;
  evidenceState: string;
  latestRun?: SourceIntelligenceRunSummary;
  onOpenEvidence?: (focus: EvidenceFocus) => void;
  widgetTypeSet: Set<BiDashboardWidget["type"]>;
};

export function BiDashboardWidgetKitOverview({ dashboard, evidenceState, latestRun, onOpenEvidence, widgetTypeSet }: BiDashboardWidgetKitOverviewProps) {
  const catalogTypes = new Set(B_DASHBOARD_WIDGET_CATALOG.map((item) => item.type));

  return (
    <>
      <div className="bKitHeader">
        <div>
          <p className="kicker">{biText("自动分析结果", "Generated results")}</p>
          <h3 id="b-dashboard-kit-title">
            <Bilingual zh="关键结果" en="Key results" />
          </h3>
        </div>
        <div className="bKitStatus">
          <span>{biText(`${catalogTypes.size} 个结果卡片`, `${catalogTypes.size} result cards`)}</span>
          <span>{biText("已连接证据", "Evidence linked")}</span>
          <span>{latestRun ? biText(`已更新: ${latestRun.label}`, `Updated: ${latestRun.label}`) : biText("等待证据摘要", "Waiting for evidence summary")}</span>
        </div>
      </div>

      <section className="bReadPath" data-testid="b-dashboard-read-path" aria-label={biText("看板阅读顺序", "Dashboard reading path")}>
        <div className="bReadPathLead">
          <strong><Bilingual zh="按这个顺序读，不用先学组件配置" en="Read in this order; no widget setup knowledge required" /></strong>
          <span>{evidenceState}</span>
        </div>
        <div className="bReadPathSteps">
          {B_DASHBOARD_WIDGET_CATALOG.map((item, index) => {
            const purpose = B_WIDGET_READING_PURPOSES[item.type];
            const ready = widgetTypeSet.has(item.type);
            return (
              <div className={ready ? "bReadPathStep ready" : "bReadPathStep"} data-testid={`b-read-path-${item.type}`} key={item.type}>
                <em>{index + 1}</em>
                <strong><Bilingual {...purpose.title} /></strong>
                <span><Bilingual {...purpose.detail} /></span>
                <small><Bilingual {...purpose.action} /></small>
              </div>
            );
          })}
        </div>
      </section>

      <section className="bWidgetAcceptanceGallery" data-testid="b-widget-acceptance-gallery" aria-label={biText("看板任务验收清单", "Dashboard task acceptance checklist")}>
        <div className="bWidgetAcceptanceLead">
          <div>
            <span className="storyMode"><Bilingual zh="验收看板动作" en="Accept dashboard actions" /></span>
            <h4><Bilingual zh="用户会做的事都集中可测" en="User tasks are testable together" /></h4>
            <p>
              <Bilingual
                zh="这里按用户任务验收：看总量、看排行、看趋势、查明细、筛选、跨表、下钻和维护组件。组件类型和命令证据仍可展开核对。"
                en="This checks user tasks: totals, rankings, trends, rows, filters, cross-table analysis, drilldown, and widget maintenance. Widget types and command evidence remain expandable."
              />
            </p>
          </div>
          <button className="miniButton" onClick={() => onOpenEvidence?.({
            source: "dashboard-widget-gallery",
            title: biText("看板任务验收清单", "Dashboard task acceptance checklist"),
            subtitle: biText("阅读、筛选、下钻和维护边界", "Reading, filtering, drilldown, and maintenance boundaries"),
            refs: ["dashboard-widget-catalog", "dashboard-widgets", "query-runtime", "dashboardSelectionConfidence"],
            dashboardKey: dashboard.dashboard_key,
            tableKey: dashboard.default_table_key,
            detail: {
              acceptedItems: B_WIDGET_ACCEPTANCE_ITEMS.map((item) => item.key),
              dashboardName: dashboard.name,
            },
          })} type="button">
            {biText("证据", "Evidence")}
          </button>
        </div>
        <div className="bWidgetAcceptanceGrid" data-testid="b-widget-acceptance-grid">
          {B_WIDGET_ACCEPTANCE_ITEMS.map((item) => {
            const widgetReady = B_DASHBOARD_WIDGET_CATALOG.some((catalog) => catalog.type === item.key) ? widgetTypeSet.has(item.key as BiDashboardWidget["type"]) : true;
            return (
              <div className={widgetReady ? "bWidgetAcceptanceItem ready" : "bWidgetAcceptanceItem"} data-testid={`b-widget-acceptance-${item.key}`} key={item.key}>
                <strong><Bilingual {...item.label} /></strong>
                <span><Bilingual {...item.detail} /></span>
                <em>{widgetReady ? biText("可验收", "Covered") : biText("待生成", "Pending")}</em>
                <details className="bWidgetAcceptanceTechnical" data-testid={`b-widget-acceptance-technical-${item.key}`}>
                  <summary>{biText("验收依据", "Acceptance evidence")}</summary>
                  <small><Bilingual {...item.technical} /></small>
                  <code>{item.key}</code>
                </details>
              </div>
            );
          })}
        </div>
      </section>

      <details className="advancedDetails compactAdvanced" data-testid="b-widget-catalog-technical-details">
        <summary>{biText("查看组件目录和命令证据", "View widget catalog and command evidence")}</summary>
        <div className="bComponentPalette" aria-label={biText("组件类型", "Widget types")}>
          {B_DASHBOARD_WIDGET_CATALOG.map((item) => (
            <div className="bPaletteItem" key={item.type}>
              <strong><Bilingual {...item.label} /></strong>
              <span><Bilingual {...item.description} /></span>
              <small>{biText(`类型 ${item.type} · 数据来源 ${item.dataModes.join(", ")}`, `Type ${item.type} · data modes ${item.dataModes.join(", ")}`)}</small>
            </div>
          ))}
        </div>
      </details>
    </>
  );
}
