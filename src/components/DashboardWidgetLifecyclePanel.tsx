import type { DashboardWidget } from "../types";
import type { DashboardWidgetOperationOptions } from "../dashboardCanvasContracts";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardWidgetLifecyclePanelProps = {
  busy: string | null;
  dashboardKey: string;
  onWidgetOperation: (label: string, options: DashboardWidgetOperationOptions) => Promise<void>;
  selectedWidget: DashboardWidget;
};

export function DashboardWidgetLifecyclePanel({
  busy,
  dashboardKey,
  onWidgetOperation,
  selectedWidget,
}: DashboardWidgetLifecyclePanelProps) {
  return (
    <details className="widgetLifecycleActions" data-testid="widget-lifecycle-actions">
      <summary>{biText("复制或删除组件", "Copy or delete widget")}</summary>
      <div className="widgetEditorActions">
        <button
          className="secondaryButton"
          data-testid="widget-copy-preview-button"
          disabled={busy === "copy-widget-dry"}
          onClick={() => onWidgetOperation("copy-widget-dry", {
            op: "copy",
            widgetKey: selectedWidget.widget_key,
            dashboardKey,
            title: `${selectedWidget.title} Copy`,
            confirm: false,
          })}
          type="button"
        >
          <Icon name="copy" />
          <Bilingual zh="预览复制" en="Preview copy" />
        </button>
        <button
          className="primaryButton"
          data-testid="widget-copy-confirm-button"
          disabled={busy === "copy-widget"}
          onClick={() => onWidgetOperation("copy-widget", {
            op: "copy",
            widgetKey: selectedWidget.widget_key,
            dashboardKey,
            title: `${selectedWidget.title} Copy`,
            confirm: true,
          })}
          type="button"
        >
          <Icon name="check" />
          <Bilingual zh="确认复制" en="Confirm copy" />
        </button>
        <button
          className="secondaryButton dangerSoft"
          data-testid="widget-remove-preview-button"
          disabled={busy === "remove-widget-dry"}
          onClick={() => onWidgetOperation("remove-widget-dry", {
            op: "remove",
            widgetKey: selectedWidget.widget_key,
            confirm: false,
          })}
          type="button"
        >
          <Icon name="evidence" />
          <Bilingual zh="预览删除" en="Preview delete" />
        </button>
        <button
          className="miniButton dangerButton"
          data-testid="widget-remove-confirm-button"
          disabled={busy === "remove-widget"}
          onClick={() => onWidgetOperation("remove-widget", {
            op: "remove",
            widgetKey: selectedWidget.widget_key,
            confirm: true,
          })}
          type="button"
        >
          {biText("确认删除", "Confirm delete")}
        </button>
      </div>
    </details>
  );
}
