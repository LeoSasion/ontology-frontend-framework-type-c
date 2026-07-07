import { Bilingual } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardWidgetRecommendationPanelProps = {
  busy: string | null;
  dashboardKey: string;
  defaultTableKey: string;
  plannedWidgets: Array<Record<string, unknown>>;
  onRecommendWidgets: () => void;
  onAddRecommendedWidgets: () => void;
};

export function DashboardWidgetRecommendationPanel({
  busy,
  defaultTableKey,
  plannedWidgets,
  onRecommendWidgets,
  onAddRecommendedWidgets,
}: DashboardWidgetRecommendationPanelProps) {
  return (
    <article className="widgetActionPanel" data-testid="widget-recommendation-panel">
      <div className="tileHeader compact">
        <h3><Bilingual zh="一键生成" en="One-click build" /></h3>
        <span>{defaultTableKey}</span>
      </div>
      <div className="dashboardOps">
        <button
          className="secondaryButton"
          data-testid="widget-recommend-button"
          disabled={busy === "recommend-widgets"}
          onClick={onRecommendWidgets}
          type="button"
        >
          <Icon name="evidence" />
          <Bilingual zh="推荐组件" en="Recommend" />
        </button>
        <button
          className="primaryButton"
          data-testid="widget-add-recommended-button"
          disabled={busy === "add-recommended"}
          onClick={onAddRecommendedWidgets}
          type="button"
        >
          <Icon name="check" />
          <Bilingual zh="添加推荐" en="Add recommended" />
        </button>
      </div>
      <div className="widgetPlanList">
        {plannedWidgets.length ? plannedWidgets.slice(0, 5).map((item, index) => (
          <div className="widgetPlanItem" key={`${String(item.widget_key ?? item.title ?? index)}-${index}`}>
            <span>{String(item.widget_type ?? item.type ?? "widget")}</span>
            <strong>{String(item.title ?? "-")}</strong>
            <small>{String(item.reason ?? item.table_key ?? item.tableKey ?? "")}</small>
          </div>
        )) : (
          <p className="emptyFilterHint"><Bilingual zh="点击推荐组件，系统会基于字段语义给出可加入看板的组件。" en="Use Recommend to generate widget candidates from field semantics." /></p>
        )}
      </div>
    </article>
  );
}
