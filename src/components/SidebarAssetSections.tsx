import type { ActionDraft, AgentAskResult, DashboardPage, DashboardPayload, NavigationModule, WorkbenchPayload, WorkspaceStatus } from "../types";
import { getAppSection } from "../appSections";
import { getUserPreferences, resolveThemePalette } from "../theme";
import type { AppSection } from "./Sidebar";
import { Bilingual, biText, translateName } from "./Bilingual";
import { Icon } from "./Icons";

type SidebarAssetSectionsProps = {
  activeRailSection: AppSection;
  activeDashboardKey: string;
  actionDrafts: ActionDraft[];
  agent: AgentAskResult;
  assetBusy: boolean;
  dashboards: DashboardPayload;
  onDashboardSelect: (dashboardKey: string) => void;
  onSectionChange: (section: AppSection) => void;
  runSourceRefresh: () => Promise<void>;
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
};

type DashboardAsset = {
  key: string;
  dashboard: DashboardPage;
  name: string;
};

function resolveDashboardAsset(item: NavigationModule | DashboardPage, dashboardPages: DashboardPage[]): DashboardAsset | null {
  if ("dashboardKey" in item || "moduleKey" in item) {
    const dashboardKey = item.dashboardKey;
    if (!dashboardKey) return null;
    const dashboard = dashboardPages.find((candidate) => candidate.dashboard_key === dashboardKey);
    if (!dashboard) return null;
    return {
      key: item.moduleKey,
      dashboard,
      name: item.name || dashboard.name,
    };
  }
  return {
    key: item.dashboard_key,
    dashboard: item,
    name: item.name,
  };
}

export function SidebarAssetSections({
  activeRailSection,
  activeDashboardKey,
  actionDrafts,
  agent,
  assetBusy,
  dashboards,
  onDashboardSelect,
  onSectionChange,
  runSourceRefresh,
  status,
  workbench,
}: SidebarAssetSectionsProps) {
  const dashboardPages = Array.isArray(dashboards.dashboards) ? dashboards.dashboards : [];
  const tables = Array.isArray(workbench.tables) ? workbench.tables : [];
  const navigationModules = Array.isArray(workbench.navigation) ? workbench.navigation.filter((module) => module.enabled !== false) : [];
  const sourceModules = navigationModules.filter((module) => module.type === "table" && module.tableKey);
  const dashboardModules = navigationModules.filter((module) => module.type === "dashboard" && module.dashboardKey);
  const savedViews = Array.isArray(workbench.savedViews) ? workbench.savedViews : [];
  const sourceRuns = Array.isArray(status.sourceRuns) ? status.sourceRuns : [];
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const preferences = getUserPreferences(workbench);
  const activeTheme = resolveThemePalette(workbench, preferences);
  const latestRun = sourceIntelligenceRuns[0];
  const evidenceFiles = Array.isArray(agent.ontology?.evidenceFiles) ? agent.ontology.evidenceFiles : [];
  const homeNextSection: AppSection = status.counts.tables <= 0
    ? "sources"
    : !latestRun
      ? "sources"
      : status.counts.dashboards <= 0
        ? "dashboards"
        : "agent";
  const homeNextMeta = getAppSection(homeNextSection);
  const homeNextDetail = homeNextSection === "sources"
    ? biText("先完成预检、导入和证据摘要。", "Finish preflight, import, and evidence summary first.")
    : homeNextSection === "dashboards"
      ? biText("证据已生成，下一步整理成看板。", "Evidence is ready; organize it into a dashboard next.")
      : biText("数据、看板和证据已连接，可以直接提问。", "Data, dashboards, and evidence are connected; ask directly.");

  return (
    <>
      {activeRailSection === "home" ? (
        <section className="assetSection" aria-labelledby="start-assets-title">
          <div className="assetSectionTitle">
            <span className="eyebrow">{biText("起步路径", "Start path")}</span>
            <strong id="start-assets-title"><Bilingual zh="从业务问题开始" en="Start from a business question" /></strong>
          </div>
          <dl className="assetCounts stacked">
            <div>
              <dt>{biText("数据表", "Tables")}</dt>
              <dd>{status.counts.tables}</dd>
            </div>
            <div>
              <dt>{biText("指标", "Metrics")}</dt>
              <dd>{status.counts.metrics}</dd>
            </div>
            <div>
              <dt>{biText("证据画像", "Profiles")}</dt>
              <dd>{sourceIntelligenceRuns.length}</dd>
            </div>
          </dl>
          <button className="assetRow primaryAssetRow" onClick={() => onSectionChange(homeNextSection)} type="button">
            <strong>{biText(`继续：${homeNextMeta.zh}`, `Continue: ${homeNextMeta.en}`)}</strong>
            <span>{homeNextDetail}</span>
          </button>
          <button className="assetAction" disabled={assetBusy} onClick={runSourceRefresh} type="button">
            <Icon name="evidence" />
            <span><Bilingual zh="生成证据摘要" en="Create evidence summary" /></span>
          </button>
        </section>
      ) : null}

      {activeRailSection === "sources" ? (
        <section className="assetSection" aria-labelledby="source-assets-title">
          <div className="assetSectionTitle">
            <span className="eyebrow">{biText("数据源", "Sources")}</span>
            <strong id="source-assets-title">{biText(`${sourceModules.length || sourceRuns.length || tables.length} 个数据资产`, `${sourceModules.length || sourceRuns.length || tables.length} data assets`)}</strong>
          </div>
          <details className="sidebarAssetDetails" data-testid="sidebar-source-asset-details">
            <summary>{biText("查看数据资产列表", "View data asset list")}</summary>
            <div className="assetList">
              {(sourceModules.length ? sourceModules : (sourceRuns.length ? sourceRuns : tables)).slice(0, 8).map((item) => {
                const tableKey = "tableKey" in item ? item.tableKey : ("table_key" in item ? item.table_key : "");
                const table = tables.find((candidate) => candidate.table_key === tableKey);
                const run = sourceRuns.find((candidate) => candidate.table_key === tableKey);
                const key = "moduleKey" in item ? item.moduleKey : ("id" in item ? item.id : item.table_key);
                const name = "moduleKey" in item ? item.name : ("name" in item ? item.name : item.display_name);
                const rows = run?.row_count ?? table?.row_count ?? ("row_count" in item ? item.row_count : 0);
                const cols = run?.column_count ?? table?.column_count ?? ("column_count" in item ? item.column_count : 0);
                const file = run?.source_file ?? table?.source_file ?? ("source_file" in item ? item.source_file : "");
                return (
                  <button className="assetRow" key={key} onClick={() => onSectionChange("sources")} type="button">
                    <strong><Bilingual {...translateName(name)} /></strong>
                    <span>{rows.toLocaleString()} {biText("行", "rows")} · {cols} {biText("列", "cols")}</span>
                    {file ? <small>{file}</small> : null}
                  </button>
                );
              })}
            </div>
          </details>
          <button className="assetAction" disabled={assetBusy} onClick={runSourceRefresh} type="button">
            <Icon name="agent" />
            <span><Bilingual zh="生成证据摘要" en="Create evidence summary" /></span>
          </button>
        </section>
      ) : null}

      {activeRailSection === "views" ? (
        <section className="assetSection" aria-labelledby="view-assets-title">
          <div className="assetSectionTitle">
            <span className="eyebrow">{biText("分析视图", "Analysis views")}</span>
            <strong id="view-assets-title">{biText(`${savedViews.length} 个明细口径`, `${savedViews.length} detail scopes`)}</strong>
          </div>
          <details className="sidebarAssetDetails" data-testid="sidebar-view-asset-details">
            <summary>{biText("查看明细口径列表", "View detail scope list")}</summary>
            <div className="assetList">
              {savedViews.slice(0, 8).map((view) => (
                <button className="assetRow" key={view.view_key} onClick={() => onSectionChange("views")} type="button">
                  <strong><Bilingual {...translateName(view.name)} /></strong>
                  <span>{view.table_name ?? view.table_key} · {view.columnCount ?? 0} {biText("列", "cols")}</span>
                  <small>{view.filterCount ?? 0} {biText("筛选", "filters")} · {view.tag_name}</small>
                </button>
              ))}
            </div>
          </details>
          <button className="assetAction" onClick={() => onSectionChange("views")} type="button">
            <Icon name="query" />
            <span><Bilingual zh="打开明细分页" en="Open detail query" /></span>
          </button>
        </section>
      ) : null}

      {activeRailSection === "dashboards" ? (
        <section className="assetSection" aria-labelledby="dashboard-assets-title">
          <div className="assetSectionTitle">
            <span className="eyebrow">{biText("仪表盘", "Dashboards")}</span>
            <strong id="dashboard-assets-title">{biText(`${dashboardPages.length} 个页面`, `${dashboardPages.length} pages`)}</strong>
          </div>
          <details className="sidebarAssetDetails" data-testid="sidebar-dashboard-asset-details">
            <summary>{biText("查看看板页面列表", "View dashboard page list")}</summary>
            <div className="assetList">
              {(dashboardModules.length ? dashboardModules : dashboardPages).map((item) => {
                const asset = resolveDashboardAsset(item, dashboardPages);
                if (!asset) return null;
                const { dashboard, name } = asset;
                return (
                  <button
                    className={dashboard.dashboard_key === activeDashboardKey ? "assetRow active" : "assetRow"}
                    key={asset.key}
                    onClick={() => {
                      onDashboardSelect(dashboard.dashboard_key);
                      onSectionChange("dashboards");
                    }}
                    type="button"
                  >
                    <strong><Bilingual {...translateName(name)} /></strong>
                    <span>{dashboard.default_table_key} · {(Array.isArray(dashboard.widgets) ? dashboard.widgets.length : 0)} {biText("组件", "widgets")}</span>
                    <small>{dashboard.created_by === "agent" ? biText("Agent 生成", "Agent generated") : biText("手动维护", "Manual")}</small>
                  </button>
                );
              })}
            </div>
          </details>
        </section>
      ) : null}

      {activeRailSection === "agent" ? (
        <section className="assetSection" aria-labelledby="agent-assets-title">
          <div className="assetSectionTitle">
            <span className="eyebrow">{biText("AI 助手", "AI assistant")}</span>
            <strong id="agent-assets-title"><Bilingual zh="全局提问与确认" en="Global ask and review" /></strong>
          </div>
          <p className="quietText">
            {biText(
              "任意页面右下角都可以直接提问；这里专注查看回答、证据和待确认修改。",
              "Ask from the lower-right assistant on any page. This workspace focuses on answers, evidence, and pending changes.",
            )}
          </p>
          <div className="assetSubsection">
            <span>{biText("最近动作草案", "Recent drafts")}</span>
            {actionDrafts.slice(0, 4).map((draft) => (
              <div className="assetMiniRow" key={draft.action_key}>
                <strong>{draft.label}</strong>
                <small>{draft.status}</small>
              </div>
            ))}
            {!actionDrafts.length ? <p className="quietText">{biText("暂无草案", "No drafts yet")}</p> : null}
          </div>
        </section>
      ) : null}

      {activeRailSection === "evidence" ? (
        <section className="assetSection" aria-labelledby="evidence-assets-title">
          <div className="assetSectionTitle">
            <span className="eyebrow">{biText("证据链", "Evidence chain")}</span>
            <strong id="evidence-assets-title">{latestRun ? latestRun.label : biText("等待画像", "Waiting for profile")}</strong>
          </div>
          {latestRun ? (
            <dl className="assetCounts stacked">
              <div>
                <dt>{biText("文件", "Files")}</dt>
                <dd>{latestRun.source_count}</dd>
              </div>
              <div>
                <dt>{biText("关系", "Relations")}</dt>
                <dd>{latestRun.relationship_count}</dd>
              </div>
              <div>
                <dt>{biText("可执行指标", "Executable metrics")}</dt>
                <dd>{latestRun.metric_sql_executable_count}</dd>
              </div>
            </dl>
          ) : null}
          <details className="sidebarAssetDetails" data-testid="sidebar-evidence-asset-details">
            <summary>{biText("查看引用证据列表", "View evidence reference list")}</summary>
            <div className="assetList compactEvidenceList">
              {evidenceFiles.slice(0, 7).map((file) => (
                <button className="assetRow" key={file} onClick={() => onSectionChange("evidence")} type="button">
                  <strong>{file.split(/[\\/]/).pop() ?? file}</strong>
                  <span>{file}</span>
                </button>
              ))}
              {!evidenceFiles.length ? <p className="quietText">{biText("Agent 回答后会在这里列出引用证据。", "Evidence references appear here after an Agent answer.")}</p> : null}
            </div>
          </details>
        </section>
      ) : null}

      {activeRailSection === "settings" ? (
        <section className="assetSection" aria-labelledby="settings-assets-title">
          <div className="assetSectionTitle">
            <span className="eyebrow">{biText("偏好", "Preferences")}</span>
            <strong id="settings-assets-title"><Bilingual zh="工作区设置" en="Workspace settings" /></strong>
          </div>
          <dl className="assetCounts stacked">
            <div>
              <dt>{biText("主题", "Theme")}</dt>
              <dd>{activeTheme.name}</dd>
            </div>
            <div>
              <dt>{biText("删除保护", "Delete guard")}</dt>
              <dd>{preferences.requireDeleteNameConfirmation ? biText("开启", "On") : biText("关闭", "Off")}</dd>
            </div>
            <div>
              <dt>{biText("Agent 手动资产", "Agent manual assets")}</dt>
              <dd>{preferences.agentCanManageManualAssets ? biText("允许", "Allowed") : biText("禁止", "Blocked")}</dd>
            </div>
          </dl>
          <button className="assetAction" onClick={() => onSectionChange("settings")} type="button">
            <Icon name="settings" />
            <span><Bilingual zh="打开偏好设置" en="Open preferences" /></span>
          </button>
        </section>
      ) : null}
    </>
  );
}
