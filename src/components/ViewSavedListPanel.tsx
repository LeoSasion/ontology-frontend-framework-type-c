import type { SavedView } from "../types";
import { viewColumns, viewFilters } from "../viewWorkspaceModel";
import { Bilingual, biText, translateName } from "./Bilingual";

type ViewSavedListPanelProps = {
  activeView?: SavedView;
  onSelectView: (view: SavedView) => void;
  savedViews: SavedView[];
};

export function ViewSavedListPanel({ activeView, onSelectView, savedViews }: ViewSavedListPanelProps) {
  return (
    <aside className="viewListPanel">
      <div className="tileHeader">
        <h3><Bilingual zh="已保存视图" en="Saved views" /></h3>
        <span>{savedViews.length}</span>
      </div>
      <div className="viewList">
        {savedViews.map((view) => (
          <button
            className={view.view_key === activeView?.view_key ? "viewRow active" : "viewRow"}
            key={view.view_key}
            onClick={() => onSelectView(view)}
            type="button"
          >
            <strong><Bilingual {...translateName(view.name)} /></strong>
            <span>{view.table_name ?? view.table_key} · {view.columnCount ?? viewColumns(view).length} {biText("列", "cols")}</span>
            <small>{view.filterCount ?? viewFilters(view).length} {biText("筛选", "filters")} · {view.tag_name}</small>
          </button>
        ))}
      </div>
    </aside>
  );
}
