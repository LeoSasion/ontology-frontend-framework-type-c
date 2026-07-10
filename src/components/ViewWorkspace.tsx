import "./viewWorkspace.css";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { EvidenceFocus, SavedView, TableQueryPayload, WorkbenchPayload } from "../types";
import {
  buildViewAgentPrompts,
  buildViewBridgeSteps,
  type ViewOperationReceipt,
  viewColumns,
  viewFilters,
  viewName,
  viewSearch,
  viewSort,
} from "../viewWorkspaceModel";
import { Bilingual, biText, translateName } from "./Bilingual";
import { Icon } from "./Icons";
import { ViewSavedListPanel } from "./ViewSavedListPanel";

const loadViewDashboardBridgePanel = () => import("./ViewDashboardBridgePanel").then((module) => ({ default: module.ViewDashboardBridgePanel }));
const loadViewAgentTaskStrip = () => import("./ViewAgentTaskStrip").then((module) => ({ default: module.ViewAgentTaskStrip }));
const ViewDashboardBridgePanel = lazy(loadViewDashboardBridgePanel);
const ViewAgentTaskStrip = lazy(loadViewAgentTaskStrip);

type ViewWorkspaceProps = {
  workbench: WorkbenchPayload;
  tableQuery: TableQueryPayload;
  activeViewKey: string;
  onSelectView: (viewKey: string) => void;
  onRunTableQuery: (options: {
    table?: string;
    view?: string;
    mode?: "detail" | "aggregate";
    columns?: string[];
    filters?: Array<{ field: string; operator: string; value?: string }>;
    sort?: Array<{ field: string; direction?: string }>;
    search?: string;
    offset?: number;
    limit?: number;
  }) => Promise<void>;
  onSaveView: (options: {
    view?: string;
    table: string;
    name: string;
    tag?: string;
    mode?: "detail" | "aggregate";
    columns?: string[];
    filters?: Array<{ field: string; operator: string; value?: string }>;
    sort?: Array<{ field: string; direction?: string }>;
    search?: string;
    confirm?: boolean;
  }) => Promise<void>;
  onCopyView: (options: { view: string; name?: string; confirm?: boolean }) => Promise<void>;
  onDeleteView: (options: { view: string; confirm?: boolean }) => Promise<void>;
  onOpenEvidence: (focus: EvidenceFocus) => void;
  onOpenSources: () => void;
  onAsk: (prompt: string) => Promise<void>;
};

export function ViewWorkspace({ workbench, tableQuery, activeViewKey, onSelectView, onRunTableQuery, onSaveView, onCopyView, onDeleteView, onOpenEvidence, onOpenSources, onAsk }: ViewWorkspaceProps) {
  const savedViews = Array.isArray(workbench.savedViews) ? workbench.savedViews : [];
  const tables = Array.isArray(workbench.tables) ? workbench.tables : [];
  const activeView = savedViews.find((view) => view.view_key === activeViewKey) ?? savedViews[0];
  const table = tables.find((item) => item.table_key === activeView?.table_key) ?? tables[0];
  const query = tableQuery?.tableQuery ?? {
    mode: "detail",
    tableKey: activeView?.table_key ?? table?.table_key ?? "",
    tableName: table?.display_name,
    columns: viewColumns(activeView),
    rows: [],
    totalRows: 0,
    filteredRows: 0,
    limit: 50,
    offset: 0,
    page: 1,
    pageCount: 1,
    filters: [],
    sort: [],
    search: "",
    sqlIntent: "Controlled detail query; user SQL is not accepted",
  };
  const columns = Array.isArray(query.columns) ? query.columns : [];
  const rows = Array.isArray(query.rows) ? query.rows : [];
  const pageCount = Math.max(1, query.pageCount ?? 1);
  const currentPage = Math.max(1, Math.min(pageCount, query.page ?? 1));
  const [search, setSearch] = useState(viewSearch(activeView));
  const [busy, setBusy] = useState<string | null>(null);
  const [viewOperationReceipt, setViewOperationReceipt] = useState<ViewOperationReceipt | null>(null);
  const [dashboardBridgeMounted, setDashboardBridgeMounted] = useState(false);
  const [agentTaskMounted, setAgentTaskMounted] = useState(false);
  const activeTableName = activeView?.table_name ?? table?.display_name ?? activeView?.table_key ?? table?.table_key ?? "";
  const activeViewFilters = viewFilters(activeView);
  const activeViewSort = viewSort(activeView);
  const activeViewColumns = viewColumns(activeView);
  const latestSourceProfile = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns[0] : undefined;
  const viewCanFeedDashboard = Boolean(activeView && columns.length >= 2 && (query.filteredRows ?? rows.length) > 0);
  const bridgeEvidenceCount = 3 + (latestSourceProfile ? 2 : 0) + activeViewFilters.length + activeViewSort.length;
  const bridgeFilterScopeCount = activeViewFilters.length + (search ? 1 : 0);
  const viewReadinessLabel = viewCanFeedDashboard ? biText("可用", "Ready") : biText("待刷新", "Refresh");
  const viewScopeScore = [columns.length > 0, bridgeFilterScopeCount > 0, Boolean(latestSourceProfile)].filter(Boolean).length;
  const bridgeSteps = buildViewBridgeSteps({
    activeView,
    activeViewColumns,
    bridgeFilterScopeCount,
    rowCount: rows.length,
    filteredRows: query.filteredRows ?? rows.length,
    latestSourceProfile,
    viewCanFeedDashboard,
  });
  const viewAgentPrompts = buildViewAgentPrompts(activeView?.name ?? activeTableName);

  useEffect(() => {
    setSearch(viewSearch(activeView));
  }, [activeView?.view_key]);

  async function runBusy(label: string, action: () => Promise<void>) {
    setBusy(label);
    try {
      await action();
    } finally {
      setBusy(null);
    }
  }

  const queryOptions = useMemo(() => ({
    table: activeView?.table_key ?? table?.table_key,
    view: activeView?.view_key,
    mode: "detail" as const,
    search,
    limit: query.limit || 50,
  }), [activeView?.table_key, activeView?.view_key, query.limit, search, table?.table_key]);

  async function runViewQueryAction(label: string, options: Parameters<typeof onRunTableQuery>[0], selectedView = activeView) {
    await onRunTableQuery(options);
    const selectedName = viewName(selectedView, activeTableName);
    const offsetText = typeof options.offset === "number" ? `${options.offset}` : `${query.offset ?? 0}`;
    setViewOperationReceipt({
      title: label,
      detail: biText(
        `已按「${selectedName}」的字段、筛选和搜索读取明细，可继续翻页、看证据或让 Agent 解释。`,
        `Rows were read using "${selectedName}" columns, filters, and search. You can page, review evidence, or ask Agent to explain.`,
      ),
      nextStep: viewCanFeedDashboard
        ? biText("这份视图已经能作为看板组件来源。", "This view can already feed a dashboard widget.")
        : biText("如果没有结果，先放宽搜索或检查视图字段。", "If no rows appear, loosen the search or check view fields."),
      technical: `view=${selectedView?.view_key ?? "-"}; table=${options.table ?? "-"}; limit=${options.limit ?? query.limit ?? 50}; offset=${offsetText}; search=${options.search ?? ""}`,
      tone: viewCanFeedDashboard ? "ok" : "warn",
    });
  }

  async function runSelectView(view: SavedView) {
    setBusy(`select-${view.view_key}`);
    try {
      onSelectView(view.view_key);
      await runViewQueryAction(biText("视图已切换并刷新", "View switched and refreshed"), { view: view.view_key, limit: query.limit || 50 }, view);
    } finally {
      setBusy(null);
    }
  }

  async function runSaveCurrentSearch() {
    if (!activeView) return;
    await onSaveView({
      view: activeView.view_key,
      table: activeView.table_key,
      name: activeView.name,
      tag: activeView.tag_name,
      mode: "detail",
      columns: viewColumns(activeView),
      filters: viewFilters(activeView),
      sort: viewSort(activeView),
      search,
      confirm: true,
    });
    setViewOperationReceipt({
      title: biText("当前搜索已保存到视图", "Current search saved to view"),
      detail: biText(
        `「${activeView.name}」会记住这次搜索、字段、筛选和排序，后续下钻和看板组件可以复用。`,
        `"${activeView.name}" now keeps this search, columns, filters, and sort for drilldown and dashboard widgets.`,
      ),
      nextStep: biText("下一步可以刷新明细确认结果，或生成看板组件修改。", "Next, refresh rows to confirm results or create a dashboard widget change."),
      technical: `view=${activeView.view_key}; columns=${activeViewColumns.join(",")}; filters=${activeViewFilters.length}; sort=${activeViewSort.length}; search=${search}`,
      tone: "ok",
    });
  }

  async function runCopyView(confirm: boolean) {
    if (!activeView) return;
    const copyName = `${activeView.name} Copy`;
    await onCopyView({ view: activeView.view_key, name: copyName, confirm });
    setViewOperationReceipt({
      title: confirm ? biText("视图已复制", "View copied") : biText("复制影响已预演", "Copy impact previewed"),
      detail: confirm
        ? biText(`已创建「${copyName}」，原视图不会被改动。`, `"${copyName}" was created. The original view was not changed.`)
        : biText(`这次只预演复制「${activeView.name}」，不会创建新视图。`, `This only previews copying "${activeView.name}" and does not create a new view.`),
      nextStep: confirm ? biText("切换到新视图后可单独调整搜索和筛选。", "Switch to the new view to tune search and filters separately.") : biText("确认复制后再调整新视图。", "Confirm the copy before tuning the new view."),
      technical: `sourceView=${activeView.view_key}; name=${copyName}; confirm=${confirm}`,
      tone: confirm ? "ok" : "warn",
    });
  }

  async function runDeleteView() {
    if (!activeView) return;
    await onDeleteView({ view: activeView.view_key, confirm: true });
    setViewOperationReceipt({
      title: biText("视图删除已确认", "View delete confirmed"),
      detail: biText(`已删除「${activeView.name}」；这只删除保存口径，不删除源数据表。`, `"${activeView.name}" was removed. This deletes saved scope only, not source tables.`),
      nextStep: biText("如需继续分析，请选择其他视图或重新保存一个视图。", "Choose another view or save a new one to continue analysis."),
      technical: `view=${activeView.view_key}; confirm=true`,
      tone: "warn",
    });
  }

  function openViewEvidence() {
    if (!activeView) return;
    onOpenEvidence({
      source: "saved-view",
      title: activeView.name,
      subtitle: biText("保存视图证据", "Saved view evidence"),
      refs: [
        "query-runtime",
        "saved-view-config",
        "table-query-contract",
        ...(latestSourceProfile ? [`source-intelligence:${latestSourceProfile.run_key}`] : []),
        ...(latestSourceProfile ? [`source-count:${latestSourceProfile.source_count}`] : []),
      ],
      viewKey: activeView.view_key,
      tableKey: activeView.table_key,
      detail: {
        viewName: activeView.name,
        tableName: activeView.table_name ?? table?.display_name ?? activeView.table_key,
        tag: activeView.tag_name,
        columns: activeViewColumns,
        columnCount: activeViewColumns.length,
        filterCount: activeViewFilters.length,
        sortCount: activeViewSort.length,
        search,
        runtime: query.runtime?.engine ?? workbench.queryRuntime?.engine ?? "unknown",
        filteredRows: query.filteredRows,
        totalRows: query.totalRows,
        page: query.page,
        pageCount: query.pageCount,
        sqlIntent: query.sqlIntent,
      },
    });
  }

  if (!savedViews.length) {
    const hasTables = tables.length > 0;
    return (
      <section className="mainPanel viewMainPanel" aria-labelledby="view-workbench-title">
        <div className="panelHeader">
          <div>
            <p className="kicker">{biText("明细视图", "Detail views")}</p>
            <h2 id="view-workbench-title"><Bilingual zh="先保存一个明细口径" en="Save a detail scope first" /></h2>
            <p className="panelIntro">
              {hasTables
                ? biText("已有数据，但还没有保存的明细视图。让 AI 起草一个，再确认保存。", "Data is ready, but no detail view is saved. Let AI draft one for review.")
                : biText("还没有数据，请先导入一份真实数据。", "No data yet. Import a real dataset first.")}
            </p>
          </div>
        </div>
        <div className="viewEmptyState" data-testid="view-empty-state">
          <Icon name={hasTables ? "agent" : "source"} />
          <strong>{hasTables ? biText("从一个必要视图开始", "Start with one necessary view") : biText("先接入数据", "Connect data first")}</strong>
          <span>{hasTables ? biText("AI 只选择查询和下钻所需字段。", "AI selects only fields needed for query and drilldown.") : biText("导入完成后再保存明细口径。", "Save a detail scope after import.")}</span>
          <div className="buttonRow">
            {hasTables ? <button className="primaryButton" data-testid="view-empty-ai-draft" disabled={busy === "empty-draft"} onClick={() => runBusy("empty-draft", () => onAsk(biText("基于当前表起草一个明细视图，只选查询和下钻所需字段，先不写入。", "Draft one detail view using only fields needed for query and drilldown. Do not write yet.")))} type="button">
              <Icon name="agent" />
              {biText("让 AI 起草视图", "Ask AI to draft")}
            </button> : null}
            <button className={hasTables ? "secondaryButton" : "primaryButton"} data-testid="view-empty-open-sources" onClick={onOpenSources} type="button">
              <Icon name="source" />
              {hasTables ? biText("检查数据字段", "Check data fields") : biText("去导入数据", "Import data")}
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="mainPanel viewMainPanel" aria-labelledby="view-workbench-title">
      <div className="panelHeader">
        <div>
          <p className="kicker">{biText("明细视图", "Detail views")}</p>
          <h2 id="view-workbench-title"><Bilingual zh="业务明细口径" en="Business detail scopes" /></h2>
          <p className="panelIntro">
            <Bilingual zh="这里不管理原始文件，只保存可复用的字段、筛选、搜索和排序，用于明细分页、下钻和仪表盘组件。" en="This area does not manage raw files. It saves reusable columns, filters, search, and sort for detail paging, drilldowns, and dashboard widgets." />
          </p>
        </div>
        <div className="buttonRow">
          <button
            className="secondaryButton"
            disabled={!activeView || busy === "copy-dry"}
            onClick={() => runBusy("copy-dry", () => runCopyView(false))}
            type="button"
          >
            <Icon name="source" />
            <Bilingual zh="预演复制" en="Preview copy" />
          </button>
          <button
            className="primaryButton"
            disabled={!activeView || busy === "save"}
            onClick={() => runBusy("save", runSaveCurrentSearch)}
            type="button"
          >
            <Icon name="check" />
            <Bilingual zh="保存当前搜索" en="Save search" />
          </button>
        </div>
      </div>

      <div className="viewWorkspaceGrid">
        <ViewSavedListPanel activeView={activeView} onSelectView={(view) => void runSelectView(view)} savedViews={savedViews} />

        <section className="viewQueryPanel">
          <div className="viewToolbar">
            <div>
              <span className="storyMode"><Bilingual zh="受控明细" en="Controlled details" /></span>
              <h3>{activeView ? <Bilingual {...translateName(activeView.name)} /> : biText("未选择视图", "No view selected")}</h3>
            </div>
            <label className="viewSearch">
              <span>{biText("搜索", "Search")}</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={biText("搜索当前视图", "Search this view")} />
            </label>
            <button
              className="secondaryButton"
              disabled={!activeView || busy === "query"}
              onClick={() => runBusy("query", () => runViewQueryAction(biText("明细已刷新", "Rows refreshed"), queryOptions))}
              type="button"
            >
              <Icon name="query" />
              <Bilingual zh="刷新明细" en="Refresh rows" />
            </button>
            <button
              className="secondaryButton"
              data-testid="view-evidence-button"
              disabled={!activeView}
              onClick={openViewEvidence}
              type="button"
            >
              <Icon name="evidence" />
              <Bilingual zh="查看证据" en="Review evidence" />
            </button>
          </div>

          <div className="viewStats">
            <div><strong>{query.filteredRows?.toLocaleString?.() ?? 0}</strong><span>{biText("筛选后", "filtered")}</span></div>
            <div><strong>{query.totalRows?.toLocaleString?.() ?? 0}</strong><span>{biText("总行数", "total")}</span></div>
            <div><strong>{currentPage}/{pageCount}</strong><span>{biText("页", "page")}</span></div>
            <div><strong>{viewReadinessLabel}</strong><span>{biText("看板来源", "dashboard source")}</span></div>
          </div>
          {viewOperationReceipt ? (
            <div className={`viewOperationReceipt ${viewOperationReceipt.tone}`} data-testid="view-operation-receipt">
              <div>
                <strong>{viewOperationReceipt.title}</strong>
                <span>{viewOperationReceipt.detail}</span>
                <small>{viewOperationReceipt.nextStep}</small>
              </div>
              <details data-testid="view-operation-technical-details">
                <summary>{biText("查看视图口径和分页", "View scope and paging")}</summary>
                <span>{viewOperationReceipt.technical}</span>
              </details>
            </div>
          ) : null}
          <details className="advancedDetails compactAdvanced viewQueryTechnical" data-testid="view-query-diagnostics">
            <summary>{biText("查看分页、执行引擎和查询口径", "View paging, runtime, and query scope")}</summary>
            <div className="formulaMeta">
              <span>{biText("口径完整度", "Scope completeness")}: {viewScopeScore}/3</span>
              <span>{biText("每页行数", "Rows per page")}: {query.limit || 50}</span>
              <span>{biText("执行引擎", "Runtime")}: {query.runtime?.engine ?? workbench.queryRuntime?.engine ?? "-"}</span>
              <span>{biText("查询意图", "Query intent")}: {query.sqlIntent}</span>
            </div>
          </details>

          <details className="progressiveDetails viewProgressiveDetails" data-testid="view-dashboard-bridge-details" onToggle={(event) => {
            if (event.currentTarget.open) setDashboardBridgeMounted(true);
          }}>
            <summary>{biText("把当前视图用于看板", "Use this view in dashboards")}</summary>
            {dashboardBridgeMounted ? <div className="progressiveDetailsBody single">
              <Suspense fallback={<div className="viewDeferredLoading" aria-busy="true">{biText("正在准备看板建议", "Preparing dashboard guidance")}</div>}>
              <ViewDashboardBridgePanel
                activeTableName={activeTableName}
                activeView={activeView}
                bridgeEvidenceCount={bridgeEvidenceCount}
                bridgeFilterScopeCount={bridgeFilterScopeCount}
                bridgeSteps={bridgeSteps}
                busy={busy}
                columns={columns}
                latestSourceProfile={latestSourceProfile}
                onAsk={onAsk}
                openViewEvidence={openViewEvidence}
                runBusy={runBusy}
                viewCanFeedDashboard={viewCanFeedDashboard}
              />
              </Suspense>
            </div>
            : null}
          </details>

          <details className="progressiveDetails viewProgressiveDetails" data-testid="view-agent-task-details" onToggle={(event) => {
            if (event.currentTarget.open) setAgentTaskMounted(true);
          }}>
            <summary>{biText("让 Agent 解释或复用这个视图", "Ask Agent to explain or reuse this view")}</summary>
            {agentTaskMounted ? <div className="progressiveDetailsBody single">
              <Suspense fallback={<div className="viewDeferredLoading" aria-busy="true">{biText("正在准备当前视图上下文", "Preparing view context")}</div>}>
              <ViewAgentTaskStrip
                activeView={activeView}
                busy={busy}
                onAsk={onAsk}
                runBusy={runBusy}
                viewAgentPrompts={viewAgentPrompts}
              />
              </Suspense>
            </div>
            : null}
          </details>

          <div className={columns.length ? "tableScroll viewTableScroll" : "tableScroll viewTableScroll empty"}>
            <table>
              <thead>
                <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={index}>
                    {columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="viewFooter">
            <div className="buttonRow tight">
              <button
                className="miniButton"
                disabled={!activeView || (query.offset ?? 0) <= 0 || busy === "prev"}
                onClick={() => runBusy("prev", () => runViewQueryAction(biText("上一页已读取", "Previous page loaded"), { ...queryOptions, offset: Math.max(0, (query.offset ?? 0) - (query.limit || 50)) }))}
                type="button"
              >
                {biText("上一页", "Prev")}
              </button>
              <button
                className="miniButton"
                disabled={!activeView || currentPage >= pageCount || busy === "next"}
                onClick={() => runBusy("next", () => runViewQueryAction(biText("下一页已读取", "Next page loaded"), { ...queryOptions, offset: (query.offset ?? 0) + (query.limit || 50) }))}
                type="button"
              >
                {biText("下一页", "Next")}
              </button>
            </div>
            <details className="viewManageDetails" data-testid="view-manage-details">
              <summary>{biText("管理视图", "Manage view")}</summary>
              <div className="buttonRow tight">
                <button
                  className="miniButton"
                  disabled={!activeView || busy === "copy"}
                  onClick={() => runBusy("copy", () => runCopyView(true))}
                  type="button"
                >
                  {biText("复制视图", "Copy view")}
                </button>
                <button
                  className="miniButton dangerButton"
                  disabled={!activeView || activeView.is_default || busy === "delete"}
                  onClick={() => runBusy("delete", runDeleteView)}
                  type="button"
                >
                  {biText("删除视图", "Delete view")}
                </button>
              </div>
            </details>
          </div>
          <details className="advancedDetails compactAdvanced viewQueryTechnical" data-testid="view-query-technical-details">
            <summary>{biText("查看生成查询", "View generated query")}</summary>
            <pre className="compactCode viewSql">{query.runtime?.compiledSql ?? query.sqlIntent}</pre>
          </details>
        </section>
      </div>
    </section>
  );
}
