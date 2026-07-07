import type { DashboardWidget } from "../types";
import { Bilingual, biText, translateName } from "./Bilingual";

type DashboardWidgetManagePanelProps = {
  busy: string | null;
  dashboardKey: string;
  onCopyPreview: (widget: DashboardWidget) => void;
  onRemovePreview: (widget: DashboardWidget) => void;
  onSelectWidget: (widgetKey: string) => void;
  selectedWidgetKey?: string;
  widgets: DashboardWidget[];
};

export function DashboardWidgetManagePanel({
  busy,
  dashboardKey,
  onCopyPreview,
  onRemovePreview,
  onSelectWidget,
  selectedWidgetKey,
  widgets,
}: DashboardWidgetManagePanelProps) {
  return (
    <article className="widgetActionPanel widgetListActionPanel" data-testid="dashboard-widget-manage-panel">
      <div className="tileHeader compact">
        <h3><Bilingual zh="当前组件" en="Current widgets" /></h3>
        <span>{dashboardKey}</span>
      </div>
      <div className="widgetManageList">
        {widgets.map((widget) => (
          <div className="widgetManageItem" key={widget.widget_key}>
            <div>
              <span>{widget.widget_type}</span>
              <strong><Bilingual {...translateName(widget.title)} /></strong>
              <small>{widget.table_key}</small>
            </div>
            <div className="widgetManageActions">
              <button
                className="miniButton"
                data-testid={`widget-edit-${widget.widget_key}`}
                disabled={selectedWidgetKey === widget.widget_key}
                onClick={() => onSelectWidget(widget.widget_key)}
                type="button"
              >
                {biText("编辑", "Edit")}
              </button>
              <button
                className="miniButton"
                data-testid={`widget-copy-preview-${widget.widget_key}`}
                disabled={busy === `copy-preview-${widget.widget_key}`}
                onClick={() => onCopyPreview(widget)}
                type="button"
              >
                {biText("预览复制", "Preview copy")}
              </button>
              <button
                className="miniButton dangerButton"
                data-testid={`widget-remove-preview-${widget.widget_key}`}
                disabled={busy === `remove-preview-${widget.widget_key}`}
                onClick={() => onRemovePreview(widget)}
                type="button"
              >
                {biText("预览删除", "Preview delete")}
              </button>
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}
