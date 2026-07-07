import type { Dispatch, SetStateAction } from "react";
import type { DashboardPage } from "../types";
import type { DashboardOperationOptions } from "../dashboardCanvasContracts";
import { Bilingual, biText, translateName } from "./Bilingual";

type DashboardPageAdminPanelProps = {
  busy: string | null;
  dashboard: DashboardPage;
  dashboardPages: DashboardPage[];
  draftName: string;
  onDashboardOperation: (label: string, options: DashboardOperationOptions) => Promise<void>;
  onDashboardSelect: (dashboardKey: string) => void;
  setDraftName: Dispatch<SetStateAction<string>>;
};

export function DashboardPageAdminPanel({
  busy,
  dashboard,
  dashboardPages,
  draftName,
  onDashboardOperation,
  onDashboardSelect,
  setDraftName,
}: DashboardPageAdminPanelProps) {
  return (
    <details className="advancedDetails dashboardAdminDetails wide" data-testid="dashboard-page-admin-panel">
      <summary>{biText("管理看板页面", "Manage dashboard pages")}</summary>
      <div className="dashboardAdminGrid">
        <article className="chartTile dashboardListTile">
          <div className="tileHeader">
            <h3><Bilingual zh="看板页面" en="Dashboard pages" /></h3>
            <span>{biText(`${dashboardPages.length} 页`, `${dashboardPages.length} pages`)}</span>
          </div>
          <div className="dashboardList">
            {dashboardPages.map((item) => (
              <button
                className={item.dashboard_key === dashboard.dashboard_key ? "dashboardSelect active" : "dashboardSelect"}
                key={item.dashboard_key}
                onClick={() => onDashboardSelect(item.dashboard_key)}
                type="button"
              >
                <strong><Bilingual {...translateName(item.name)} /></strong>
                <span>{biText(`${item.created_by} · ${(Array.isArray(item.widgets) ? item.widgets.length : 0)} 组件`, `${item.created_by} · ${(Array.isArray(item.widgets) ? item.widgets.length : 0)} widgets`)}</span>
              </button>
            ))}
          </div>
        </article>

        <article className="chartTile dashboardOpsTile">
          <div className="tileHeader">
            <h3><Bilingual zh="看板操作" en="Dashboard operations" /></h3>
            <span>{dashboard.dashboard_key}</span>
          </div>
          <div className="formGrid oneCol">
            <label>
              <span>{biText("名称", "Name")}</span>
              <input value={draftName} onChange={(event) => setDraftName(event.target.value)} />
            </label>
          </div>
          <div className="dashboardOps">
            <button
              className="miniButton"
              data-testid="dashboard-create-button"
              disabled={busy === "create"}
              onClick={() => onDashboardOperation("create", { op: "create", name: draftName || biText("新看板", "New dashboard"), table: dashboard.default_table_key, confirm: true })}
              type="button"
            >
              {biText("确认新增", "Confirm create")}
            </button>
            <button
              className="miniButton"
              data-testid="dashboard-copy-button"
              disabled={busy === "copy"}
              onClick={() => onDashboardOperation("copy", { op: "copy", dashboardKey: dashboard.dashboard_key, name: `${draftName || dashboard.name} Copy`, confirm: true })}
              type="button"
            >
              {biText("复制", "Copy")}
            </button>
            <button
              className="miniButton"
              data-testid="dashboard-rename-button"
              disabled={busy === "rename"}
              onClick={() => onDashboardOperation("rename", { op: "rename", dashboardKey: dashboard.dashboard_key, name: draftName, confirm: true })}
              type="button"
            >
              {biText("重命名", "Rename")}
            </button>
            <button
              className="miniButton dangerButton"
              data-testid="dashboard-delete-button"
              disabled={busy === "delete" || dashboardPages.length <= 1}
              onClick={() => onDashboardOperation("delete", { op: "delete", dashboardKey: dashboard.dashboard_key, confirm: true })}
              type="button"
            >
              {biText("删除", "Delete")}
            </button>
          </div>
        </article>
      </div>
    </details>
  );
}
