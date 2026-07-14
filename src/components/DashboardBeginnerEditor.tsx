import type { DashboardFilterRule, DashboardWidget, SourceIntelligenceRunSummary, WorkbenchTable } from "../types";
import type { DashboardHealthItem, DashboardHealthTone } from "../dashboardCanvasReadinessModel";
import type { DashboardSourceSwitchViewModel } from "../dashboardCanvasSourceSwitchViewModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardBeginnerEditorProps = {
  defaultTableKey: string;
  widgets: DashboardWidget[];
  filters: DashboardFilterRule[];
  selectedWidget?: DashboardWidget;
  latestRun?: SourceIntelligenceRunSummary | null;
  busy: string | null;
  healthTone: DashboardHealthTone;
  healthTitle: string;
  healthDetail: string;
  healthItems: DashboardHealthItem[];
  sourceSwitchTableKey: string;
  sourceSwitchTable?: WorkbenchTable;
  editableTables: WorkbenchTable[];
  sourceSwitchChanged: boolean;
  sourceSwitchView: DashboardSourceSwitchViewModel;
  plannedWidgetCount: number;
  hasPendingPreview: boolean;
  hasModuleSaveResult: boolean;
  onRecommendWidgets: () => void;
  onSourceSwitchTableChange: (tableKey: string) => void;
  onSourceSwitch: (confirm: boolean) => void;
  onPreviewTemplate: () => void;
  onSaveDashboard: () => void;
  onAgentDraft: () => void;
};

export function DashboardBeginnerEditor({
  defaultTableKey,
  widgets,
  filters,
  selectedWidget,
  latestRun,
  busy,
  healthTone,
  healthTitle,
  healthDetail,
  healthItems,
  sourceSwitchTableKey,
  sourceSwitchTable,
  editableTables,
  sourceSwitchChanged,
  sourceSwitchView,
  plannedWidgetCount,
  hasPendingPreview,
  hasModuleSaveResult,
  onRecommendWidgets,
  onSourceSwitchTableChange,
  onSourceSwitch,
  onPreviewTemplate,
  onSaveDashboard,
  onAgentDraft,
}: DashboardBeginnerEditorProps) {
  return (
    <details className="advancedDetails dashboardBeginnerEditorShell wide" data-testid="dashboard-beginner-editor" aria-label={biText("看板编辑驾驶台", "Dashboard editing cockpit")}>
      <summary>{biText("看板维护和数据源切换", "Dashboard maintenance and source switch")}</summary>
      <section className="dashboardBeginnerEditor">
        <div className="beginnerEditorLead">
          <span className="storyMode"><Bilingual zh="入门编辑" en="Beginner editing" /></span>
          <h3><Bilingual zh="先完成一张能用的看板" en="Make the current dashboard usable first" /></h3>
          <p>
            <Bilingual
              zh="推荐组件、保存整张看板、让 Agent 继续修改，是默认路径。字段、关系、局部筛选和样式仍在组件维护区里。"
              en="The default path is recommendations, full-dashboard save, and Agent-assisted edits. Field, relationship, local-filter, and style controls stay in widget maintenance."
            />
          </p>
        </div>
        <div className="beginnerEditorSteps" data-testid="dashboard-beginner-steps">
          <article>
            <strong>{widgets.length}</strong>
            <span><Bilingual zh="当前组件" en="current widgets" /></span>
            <small>{selectedWidget ? selectedWidget.title : biText("还没有选中组件", "No widget selected")}</small>
          </article>
          <article>
            <strong>{filters.length}</strong>
            <span><Bilingual zh="全局筛选" en="global filters" /></span>
            <small>{defaultTableKey}</small>
          </article>
          <article>
            <strong>{latestRun ? latestRun.metric_sql_executable_count : 0}</strong>
            <span><Bilingual zh="可执行指标" en="executable metrics" /></span>
            <small>{latestRun?.label ?? biText("等待画像", "waiting for profile")}</small>
          </article>
        </div>
      <div className={`dashboardReadinessPanel ${healthTone}`} data-testid="dashboard-readiness-panel">
        <div className="dashboardReadinessLead">
          <span>{healthTone === "ok" ? biText("状态可用", "Ready") : healthTone === "info" ? biText("需要确认", "Needs review") : biText("需要补齐", "Needs setup")}</span>
          <strong>{healthTitle}</strong>
          <small>{healthDetail}</small>
        </div>
        <div className="dashboardReadinessFacts" data-testid="dashboard-readiness-facts">
          {healthItems.map((item) => (
            <span key={item.key}>
              <strong>{item.value}</strong>
              <em>{item.label}</em>
              <small>{item.state}</small>
            </span>
          ))}
        </div>
      </div>
      <div className="dashboardSourceSwitchPanel" data-testid="dashboard-source-switch-panel">
        <div className="sourceSwitchCopy">
          <span className="storyMode"><Bilingual zh="数据源切换预检" en="Source switch preview" /></span>
          <strong>{sourceSwitchTable ? sourceSwitchTable.display_name : sourceSwitchTableKey}</strong>
          <p>
            {sourceSwitchChanged
              ? biText("切换前先预览失效字段、筛选和组件影响；确认前不会改写看板。", "Preview stale fields, filters, and affected widgets first. Nothing changes before confirmation.")
              : biText("当前看板仍使用默认数据源。选择另一张表后再预演。", "This dashboard still uses its default source. Pick another table to preview the impact.")}
          </p>
        </div>
        <div className="sourceSwitchControls">
          <label>
            <span>{biText("目标表", "Target table")}</span>
            <select data-testid="dashboard-source-switch-select" value={sourceSwitchTableKey} onChange={(event) => onSourceSwitchTableChange(event.target.value)}>
              {editableTables.map((table) => (
                <option key={table.table_key} value={table.table_key}>{table.display_name} · {table.table_key}</option>
              ))}
            </select>
          </label>
          <div className="sourceSwitchActions">
            <button
              className="secondaryButton"
              data-testid="dashboard-source-switch-preview"
              disabled={!sourceSwitchChanged || busy === "dashboard-source-switch-preview"}
              onClick={() => onSourceSwitch(false)}
              type="button"
            >
              <Icon name="evidence" />
              <Bilingual zh="预演切换" en="Preview switch" />
            </button>
            <button
              className="primaryButton"
              data-testid="dashboard-source-switch-confirm"
              disabled={!sourceSwitchChanged || busy === "dashboard-source-switch-confirm"}
              onClick={() => onSourceSwitch(true)}
              type="button"
            >
              <Icon name="check" />
              <Bilingual zh="确认切换" en="Confirm switch" />
            </button>
          </div>
        </div>
        <div className="sourceSwitchImpact" data-testid="dashboard-source-switch-impact">
          {sourceSwitchView.impactItems.map((item) => (
            <span key={item.key}>{item.label}</span>
          ))}
        </div>
        {sourceSwitchView.showStaleList ? (
          <div className="sourceSwitchStaleList" data-testid="dashboard-source-switch-stale-list">
            {sourceSwitchView.staleItems.map((item) => (
              <span key={item.key}>{item.label}</span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="beginnerEditorActions" data-testid="dashboard-beginner-actions">
        <button
          className="secondaryButton"
          data-testid="dashboard-beginner-recommend"
          disabled={busy === "recommend-widgets"}
          onClick={onRecommendWidgets}
          type="button"
        >
          <Icon name="evidence" />
          <Bilingual zh="推荐组件" en="Recommend widgets" />
        </button>
        <button
          className="secondaryButton"
          data-testid="dashboard-beginner-preview-template"
          disabled={busy === "business-template-preview"}
          onClick={onPreviewTemplate}
          type="button"
        >
          <Icon name="dashboard" />
          <Bilingual zh="预演分析模板" en="Preview template" />
        </button>
        <button
          className="primaryButton"
          data-testid="dashboard-beginner-save"
          disabled={busy === "dashboard-modules-confirm"}
          onClick={onSaveDashboard}
          type="button"
        >
          <Icon name="check" />
          <Bilingual zh="保存当前看板" en="Save dashboard" />
        </button>
        <button className="secondaryButton" data-testid="dashboard-beginner-agent" onClick={onAgentDraft} type="button">
          <Icon name="agent" />
          <Bilingual zh="起草修改" en="Draft change" />
        </button>
      </div>
        {hasPendingPreview || plannedWidgetCount || hasModuleSaveResult ? (
          <div className="beginnerEditorResult" data-testid="dashboard-beginner-result">
            {plannedWidgetCount ? <span>{biText(`${plannedWidgetCount} 个推荐组件`, `${plannedWidgetCount} recommended widgets`)}</span> : null}
            {hasPendingPreview ? <span>{biText("预演已生成，写入仍需确认", "Preview ready; writes still require confirmation")}</span> : null}
            {hasModuleSaveResult ? <span>{biText("最近保存结果已更新", "Latest save result updated")}</span> : null}
          </div>
        ) : null}
      </section>
    </details>
  );
}
