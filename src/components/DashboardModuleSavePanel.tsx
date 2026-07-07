import type { DashboardCanvasWidthMode } from "../dashboardCanvasWidgetModel";
import { dashboardModuleSaveReceipt } from "../dashboardCanvasPlanModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardModuleSavePanelProps = {
  busy: string | null;
  canvasWidthMode: DashboardCanvasWidthMode;
  moduleSaveResult: Record<string, unknown> | null;
  requiresConfirmation: boolean;
  widgetCount: number;
  filterCount: number;
  onCanvasWidthModeChange: (mode: DashboardCanvasWidthMode) => void;
  onSave: (confirm: boolean) => void;
};

export function DashboardModuleSavePanel({
  busy,
  canvasWidthMode,
  moduleSaveResult,
  requiresConfirmation,
  widgetCount,
  filterCount,
  onCanvasWidthModeChange,
  onSave,
}: DashboardModuleSavePanelProps) {
  const receipt = moduleSaveResult
    ? dashboardModuleSaveReceipt(moduleSaveResult, requiresConfirmation, widgetCount, filterCount, canvasWidthMode)
    : null;

  return (
    <article className="dashboardModuleSavePanel" data-testid="dashboard-module-save-panel">
      <div>
        <span className="storyMode"><Bilingual zh="批量保存" en="Bulk save" /></span>
        <h3><Bilingual zh="保存整张看板的组件、布局和筛选" en="Save the full dashboard modules, layout, and filters" /></h3>
        <p>
          <Bilingual
            zh="先预演再确认。确认后会用当前画布状态重建这张看板的组件集合，并保留给 Agent 和证据链读取。"
            en="Preview first, then confirm. Confirming rebuilds this dashboard module set from the current canvas state for Agent and evidence access."
          />
        </p>
      </div>
      <div className="dashboardModuleSaveControls">
        <label>
          <span>{biText("画布宽度", "Canvas width")}</span>
          <select value={canvasWidthMode} onChange={(event) => onCanvasWidthModeChange(event.target.value as DashboardCanvasWidthMode)}>
            <option value="stretch">{biText("拉伸", "Stretch")}</option>
            <option value="center">{biText("居中", "Center")}</option>
          </select>
        </label>
        <button
          className="secondaryButton"
          data-testid="dashboard-modules-dry-run"
          disabled={busy === "dashboard-modules-dry-run"}
          onClick={() => onSave(false)}
          type="button"
        >
          <Icon name="evidence" />
          <Bilingual zh="预演保存" en="Preview save" />
        </button>
        <button
          className="primaryButton"
          data-testid="dashboard-modules-confirm"
          disabled={busy === "dashboard-modules-confirm"}
          onClick={() => onSave(true)}
          type="button"
        >
          <Icon name="check" />
          <Bilingual zh="确认保存" en="Confirm save" />
        </button>
      </div>
      {receipt ? (
        <div className="dashboardModuleSaveResult" data-testid="dashboard-modules-result">
          <div className="dashboardModuleSaveBusiness">
            <span>{receipt.title}</span>
            <strong>{receipt.impact}</strong>
            <small>{receipt.nextStep}</small>
          </div>
          <div className="dashboardModuleSaveCounts" data-testid="dashboard-modules-impact-summary">
            <span>{receipt.widgetCount} {biText("个组件", "widgets")}</span>
            <span>{receipt.filterCount} {biText("条筛选", "filters")}</span>
            <span>{receipt.widthMode === "center" ? biText("居中画布", "Centered canvas") : biText("拉伸画布", "Stretch canvas")}</span>
          </div>
          <details className="dashboardModuleTechnicalDetails" data-testid="dashboard-modules-result-technical">
            <summary>{biText("查看模块回执", "View module receipt")}</summary>
            <pre>{JSON.stringify(moduleSaveResult, null, 2)}</pre>
          </details>
        </div>
      ) : null}
    </article>
  );
}
