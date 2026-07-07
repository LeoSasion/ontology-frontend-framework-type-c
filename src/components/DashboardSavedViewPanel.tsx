import type { SavedView } from "../types";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardSavedViewPanelProps = {
  busy: string | null;
  selectedViewKey: string;
  views: SavedView[];
  onSelectedViewChange: (viewKey: string) => void;
  onAddView: (view: SavedView) => void;
};

export function DashboardSavedViewPanel({
  busy,
  selectedViewKey,
  views,
  onSelectedViewChange,
  onAddView,
}: DashboardSavedViewPanelProps) {
  const selectedView = views.find((view) => view.view_key === selectedViewKey);

  return (
    <article className="widgetActionPanel" data-testid="dashboard-saved-view-panel">
      <div className="tileHeader compact">
        <h3><Bilingual zh="视图加入看板" en="Add view to dashboard" /></h3>
        <span>{biText(`${views.length} 个视图`, `${views.length} views`)}</span>
      </div>
      <label className="fullWidthLabel">
        <span>{biText("已保存视图", "Saved view")}</span>
        <select value={selectedViewKey} onChange={(event) => onSelectedViewChange(event.target.value)}>
          {views.map((view) => (
            <option key={view.view_key} value={view.view_key}>{view.name} · {view.table_key}</option>
          ))}
        </select>
      </label>
      <button
        className="primaryButton fullWidthButton"
        data-testid="widget-add-view-button"
        disabled={!selectedView || busy === "add-view-widget"}
        onClick={() => selectedView && onAddView(selectedView)}
        type="button"
      >
        <Icon name="dashboard" />
        <Bilingual zh="加入当前看板" en="Add to dashboard" />
      </button>
    </article>
  );
}
