import type { DashboardWidget } from "../types";
import { Bilingual, biText, translateName } from "./Bilingual";

type DashboardContractBoundaryPanelProps = {
  widgets: DashboardWidget[];
};

export function DashboardContractBoundaryPanel({ widgets }: DashboardContractBoundaryPanelProps) {
  return (
    <details className="advancedDetails dashboardAdminDetails wide" data-testid="dashboard-contract-boundary-panel">
      <summary>{biText("查看组件合同和动作边界", "View widget contract and action boundary")}</summary>
      <div className="dashboardAdminGrid">
        <article className="chartTile">
          <div className="tileHeader">
            <h3><Bilingual zh="组件合同" en="Widget contract" /></h3>
            <span>{biText(`${widgets.length} 组件`, `${widgets.length} widgets`)}</span>
          </div>
          <ul className="widgetList">
            {widgets.map((widget) => (
              <li key={widget.widget_key}>
                <span>{widget.widget_type}</span>
                <strong><Bilingual {...translateName(widget.title)} /></strong>
                <small>{widget.table_key} · {Object.entries(widget.config ?? {}).map(([key, value]) => `${key}:${String(value)}`).join(" · ")}</small>
              </li>
            ))}
          </ul>
        </article>

        <article className="chartTile">
          <div className="tileHeader">
            <h3><Bilingual zh="动作边界" en="Action boundary" /></h3>
            <span>{biText("仅草案", "draft only")}</span>
          </div>
          <div className="actionBoundary">
            <div>
              <strong>{biText("当前允许", "Allowed now")}</strong>
              <p>{biText("读取数据运行、编译指标计划、运行白名单查询、创建动作草案。", "Read source runs, compile metric plans, run whitelist queries, create action drafts.")}</p>
            </div>
            <div>
              <strong>{biText("需要确认", "Needs confirmation")}</strong>
              <p>{biText("导入提交、看板写入、关系保存、索引创建、外部同步。", "Import commit, dashboard write, relationship save, index creation, external sync.")}</p>
            </div>
          </div>
        </article>
      </div>
    </details>
  );
}
