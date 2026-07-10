import { existsSync } from "node:fs";
import { join } from "node:path";
import { writeCostMonitorFixtures } from "./verify/fixtures.mjs";
import { createVerifyRuntime, finishVerify, hasCssRule } from "./verify/runtime.mjs";
import { readProjectJsonIfExists, readVerifySourceCatalog } from "./verify/sourceCatalog.mjs";

const { fullOutput, root, run, runExpectedFailure, verifyDataDir, verifyReceiptPath, walk } = createVerifyRuntime();
const { verifyFundsPath, verifyPolicyPath } = writeCostMonitorFixtures(verifyDataDir);
const bCostMonitorComparison = readProjectJsonIfExists(root, "data", "validation", "b-cost-monitor", "b-cost-monitor-comparison.json");
const retiredSeedEnvName = "AIBI_ENABLE_" + "SEED_DATA";
const forbiddenPatterns = [
  /^financial_reports\.sqlite/i,
  /\.sqlite($|-)/i,
  /^源数据-/,
  /^exports($|[\\/])/,
  /^reports($|[\\/])/,
  /^backups($|[\\/])/,
  /^archives($|[\\/])/,
  /^\.env$/,
  /^\.env\.(?!example$)/,
];

function runWorkspaceIsolationSmoke() {
  const sourceRun = run("workspace-isolation-source-intelligence-default", "python", [
    "tools/bi_cli.py",
    "--json",
    "source-intelligence",
    "validation-inputs",
    "--label",
    "workspace-isolation-default",
    "--output-dir",
    join(verifyDataDir, "workspace-isolation-source-intelligence"),
  ]);
  const imported = run("workspace-isolation-import", "python", [
    "tools/bi_cli.py",
    "--json",
    "import-commit",
    "validation-inputs/orders.csv",
    "--table",
    "workspace_isolation_orders",
    "--name",
    "Workspace Isolation Orders",
    "--mode",
    "create",
    "--yes",
  ]);
  const draft = run("workspace-isolation-default-draft", "python", ["tools/bi_cli.py", "--json", "source-dashboard-draft", "--name", "工作区隔离验证看板", "--limit", "3"]);
  const draftKey = draft.parsed?.actionDraft?.actionKey;
  const defaultDrafts = run("workspace-isolation-default-drafts", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "5"]);
  const create = run("workspace-isolation-create", "python", ["tools/bi_cli.py", "--json", "workspace-create", "--name", "isolation_workspace", "--yes"]);
  const select = run("workspace-isolation-select", "python", ["tools/bi_cli.py", "--json", "workspace-select", "isolation_workspace", "--yes"]);
  const isolatedDrafts = run("workspace-isolation-drafts-after-select", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "5"]);
  const isolatedRuns = run("workspace-isolation-runs-after-select", "python", ["tools/bi_cli.py", "--json", "source-intelligence-runs", "--limit", "5"]);
  const blockedConfirm = draftKey
    ? runExpectedFailure("workspace-isolation-cross-confirm-blocked", "python", ["tools/bi_cli.py", "--json", "confirm-action", draftKey, "--yes"])
    : { ok: false, parsed: { error: "Missing draft key" } };
  const isolatedStatus = run("workspace-isolation-status", "python", ["tools/bi_cli.py", "--json", "status"]);
  const selectDefault = run("workspace-isolation-select-default", "python", ["tools/bi_cli.py", "--json", "workspace-select", "default", "--yes"]);
  const cleanup = draftKey
    ? run("workspace-isolation-cleanup-draft", "python", ["tools/bi_cli.py", "--json", "confirm-action", draftKey, "--reject", "--yes"])
    : { ok: false, parsed: { error: "Missing draft key" } };
  const deleteImported = run("workspace-isolation-delete-import", "python", ["tools/bi_cli.py", "--json", "delete-source", "workspace_isolation_orders", "--yes"]);
  return {
    label: "workspace-source-intelligence-action-draft-isolation",
    ok: sourceRun.ok &&
      imported.ok &&
      draft.ok &&
      Boolean(draftKey) &&
      defaultDrafts.parsed?.actionDrafts?.some((item) => item.action_key === draftKey && item.workspace_id === "default") &&
      create.parsed?.created?.id === "isolation_workspace" &&
      select.parsed?.workspace?.id === "isolation_workspace" &&
      isolatedDrafts.parsed?.pendingCount === 0 &&
      isolatedRuns.parsed?.sourceIntelligenceRuns?.length === 0 &&
      blockedConfirm.ok &&
      String(blockedConfirm.parsed?.error ?? "").includes("active workspace isolation_workspace") &&
      isolatedStatus.parsed?.counts?.actionDrafts === 0 &&
      isolatedStatus.parsed?.counts?.sourceIntelligenceRuns === 0 &&
      selectDefault.parsed?.workspace?.id === "default" &&
      cleanup.ok &&
      deleteImported.ok,
    details: {
      draftKey,
      sourceRun: sourceRun.parsed?.runKey,
      importedTable: imported.parsed?.result?.tableKey,
      defaultDraftWorkspace: defaultDrafts.parsed?.actionDrafts?.find((item) => item.action_key === draftKey)?.workspace_id,
      isolatedDraftCount: isolatedDrafts.parsed?.pendingCount,
      isolatedRunCount: isolatedRuns.parsed?.sourceIntelligenceRuns?.length,
      blockedError: blockedConfirm.parsed?.error,
      cleanupDecision: cleanup.parsed?.decision,
      deleteImported: deleteImported.parsed?.deletedSource,
    },
  };
}

function runWorkspaceModelIsolationSmoke() {
  const create = run("workspace-model-isolation-create", "python", ["tools/bi_cli.py", "--json", "workspace-create", "--name", "model_isolation_workspace", "--yes"]);
  const select = run("workspace-model-isolation-select", "python", ["tools/bi_cli.py", "--json", "workspace-select", "model_isolation_workspace", "--yes"]);
  const status = run("workspace-model-isolation-status", "python", ["tools/bi_cli.py", "--json", "status"]);
  const workbench = run("workspace-model-isolation-workbench", "python", ["tools/bi_cli.py", "--json", "workbench", "--limit", "8"]);
  const tables = run("workspace-model-isolation-tables", "python", ["tools/bi_cli.py", "--json", "list-tables"]);
  const semantics = run("workspace-model-isolation-semantics", "python", ["tools/bi_cli.py", "--json", "list-semantics"]);
  const metrics = run("workspace-model-isolation-metrics", "python", ["tools/bi_cli.py", "--json", "list-metrics"]);
  const formulas = run("workspace-model-isolation-formulas", "python", ["tools/bi_cli.py", "--json", "list-formulas", "--all"]);
  const relationships = run("workspace-model-isolation-relationships", "python", ["tools/bi_cli.py", "--json", "list-relationships"]);
  const widgets = run("workspace-model-isolation-widget-recommendations", "python", ["tools/bi_cli.py", "--json", "recommend-widgets", "--all"]);
  const selectDefault = run("workspace-model-isolation-select-default", "python", ["tools/bi_cli.py", "--json", "workspace-select", "default", "--yes"]);
  const counts = status.parsed?.counts ?? {};
  const workbenchData = workbench.parsed ?? {};
  return {
    label: "workspace-bi-metadata-isolation",
    ok: create.parsed?.created?.id === "model_isolation_workspace" &&
      select.parsed?.workspace?.id === "model_isolation_workspace" &&
      counts.tables === 0 &&
      counts.fields === 0 &&
      counts.metrics === 0 &&
      counts.relationships === 0 &&
      Array.isArray(workbenchData.navigation) && workbenchData.navigation.length === 0 &&
      Array.isArray(workbenchData.tables) && workbenchData.tables.length === 0 &&
      Array.isArray(workbenchData.fields) && workbenchData.fields.length === 0 &&
      Array.isArray(workbenchData.metrics) && workbenchData.metrics.length === 0 &&
      Array.isArray(workbenchData.formulas) && workbenchData.formulas.length === 0 &&
      Array.isArray(workbenchData.relationships) && workbenchData.relationships.length === 0 &&
      tables.parsed?.count === 0 &&
      semantics.parsed?.count === 0 &&
      metrics.parsed?.count === 0 &&
      formulas.parsed?.count === 0 &&
      relationships.parsed?.relationships?.length === 0 &&
      widgets.parsed?.recommendations?.length === 0 &&
      selectDefault.parsed?.workspace?.id === "default",
    details: {
      statusCounts: counts,
      workbenchCounts: {
        navigation: workbenchData.navigation?.length,
        tables: workbenchData.tables?.length,
        fields: workbenchData.fields?.length,
        metrics: workbenchData.metrics?.length,
        formulas: workbenchData.formulas?.length,
        relationships: workbenchData.relationships?.length,
      },
      listCounts: {
        tables: tables.parsed?.count,
        semantics: semantics.parsed?.count,
        metrics: metrics.parsed?.count,
        formulas: formulas.parsed?.count,
        relationships: relationships.parsed?.relationships?.length,
        widgetRecommendations: widgets.parsed?.recommendations?.length,
      },
    },
  };
}

function runWorkspaceSameKeyIsolationSmoke() {
  const defaultTablesBefore = run("workspace-same-key-default-tables-before", "python", ["tools/bi_cli.py", "--json", "list-tables"]);
  const defaultViewsBefore = run("workspace-same-key-default-views-before", "python", ["tools/bi_cli.py", "--json", "list-views"]);
  const defaultNavigationBefore = run("workspace-same-key-default-navigation-before", "python", ["tools/bi_cli.py", "--json", "list-navigation"]);
  const defaultDashboardBefore = run("workspace-same-key-default-dashboard-before", "python", ["tools/bi_cli.py", "--json", "dashboards", "--dashboard", "default"]);
  const create = run("workspace-same-key-create", "python", ["tools/bi_cli.py", "--json", "workspace-create", "--name", "same_key_workspace", "--yes"]);
  const select = run("workspace-same-key-select", "python", ["tools/bi_cli.py", "--json", "workspace-select", "same_key_workspace", "--yes"]);
  const imported = run("workspace-same-key-import", "python", ["tools/bi_cli.py", "--json", "import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Workspace Orders", "--mode", "create", "--yes"]);
  const navRename = run("workspace-same-key-nav-rename", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "rename", "--name", "Workspace Orders Nav", "--yes"]);
  const viewSave = run("workspace-same-key-save-view", "python", [
    "tools/bi_cli.py",
    "--json",
    "save-view",
    "--table",
    "orders",
    "--view",
    "view_orders_default",
    "--name",
    "Workspace Orders View",
    "--columns",
    "order_id,order_date,channel,net_sales",
    "--yes",
  ]);
  const workspaceDashboardWidgets = JSON.stringify([
    {
      id: "sales_by_channel",
      type: "metric",
      title: "Workspace Sales",
      tableKey: "orders",
      measure: "net_sales",
      aggregation: "sum",
      valueFormat: "currency",
    },
  ]);
  const workspaceDashboardLayout = JSON.stringify([{ i: "sales_by_channel", x: 0, y: 0, w: 3, h: 2 }]);
  const dashboardSave = run("workspace-same-key-save-dashboard", "python", [
    "tools/bi_cli.py",
    "--json",
    "save-dashboard-modules",
    "--dashboard",
    "default",
    "--name",
    "Workspace Default Dashboard",
    "--default-table",
    "orders",
    "--canvas-width-mode",
    "center",
    "--widgets-json",
    workspaceDashboardWidgets,
    "--layout-json",
    workspaceDashboardLayout,
    "--filters-json",
    "[]",
    "--yes",
  ]);
  const workspaceTables = run("workspace-same-key-workspace-tables", "python", ["tools/bi_cli.py", "--json", "list-tables"]);
  const workspaceMetrics = run("workspace-same-key-workspace-metrics", "python", ["tools/bi_cli.py", "--json", "list-metrics"]);
  const workspaceViews = run("workspace-same-key-workspace-views", "python", ["tools/bi_cli.py", "--json", "list-views"]);
  const workspaceNavigation = run("workspace-same-key-workspace-navigation", "python", ["tools/bi_cli.py", "--json", "list-navigation"]);
  const workspaceDashboard = run("workspace-same-key-workspace-dashboard", "python", ["tools/bi_cli.py", "--json", "dashboards", "--dashboard", "default"]);
  const workspaceCatalog = run("workspace-same-key-workspace-widget-catalog", "python", ["tools/bi_cli.py", "--json", "dashboard-widget-catalog"]);
  const workspaceQuery = run("workspace-same-key-workspace-query", "python", ["tools/bi_cli.py", "--json", "query", "--table", "orders", "--agg", "count", "--measure", "*", "--limit", "5"]);
  const selectDefault = run("workspace-same-key-select-default", "python", ["tools/bi_cli.py", "--json", "workspace-select", "default", "--yes"]);
  const defaultTablesAfter = run("workspace-same-key-default-tables-after", "python", ["tools/bi_cli.py", "--json", "list-tables"]);
  const defaultViewsAfter = run("workspace-same-key-default-views-after", "python", ["tools/bi_cli.py", "--json", "list-views"]);
  const defaultNavigationAfter = run("workspace-same-key-default-navigation-after", "python", ["tools/bi_cli.py", "--json", "list-navigation"]);
  const defaultDashboardAfter = run("workspace-same-key-default-dashboard-after", "python", ["tools/bi_cli.py", "--json", "dashboards", "--dashboard", "default"]);

  const defaultOrdersBefore = defaultTablesBefore.parsed?.tables?.find((table) => table.table_key === "orders");
  const defaultOrdersAfter = defaultTablesAfter.parsed?.tables?.find((table) => table.table_key === "orders");
  const workspaceOrders = workspaceTables.parsed?.tables?.find((table) => table.table_key === "orders");
  const defaultViewBefore = defaultViewsBefore.parsed?.savedViews?.find((view) => view.view_key === "view_orders_default");
  const defaultViewAfter = defaultViewsAfter.parsed?.savedViews?.find((view) => view.view_key === "view_orders_default");
  const workspaceView = workspaceViews.parsed?.savedViews?.find((view) => view.view_key === "view_orders_default");
  const defaultNavBefore = defaultNavigationBefore.parsed?.navigation?.find((item) => item.moduleKey === "table:orders");
  const defaultNavAfter = defaultNavigationAfter.parsed?.navigation?.find((item) => item.moduleKey === "table:orders");
  const workspaceNav = workspaceNavigation.parsed?.navigation?.find((item) => item.moduleKey === "table:orders");
  const defaultDashboardBeforeRow = defaultDashboardBefore.parsed?.dashboards?.[0];
  const defaultDashboardAfterRow = defaultDashboardAfter.parsed?.dashboards?.[0];
  const workspaceDashboardRow = workspaceDashboard.parsed?.dashboards?.[0];
  const defaultWidgetBefore = defaultDashboardBeforeRow?.widgets?.find((widget) => widget.widget_key === "sales_by_channel");
  const defaultWidgetAfter = defaultDashboardAfterRow?.widgets?.find((widget) => widget.widget_key === "sales_by_channel");
  const workspaceWidget = workspaceDashboardRow?.widgets?.find((widget) => widget.widget_key === "sales_by_channel");
  return {
    label: "workspace-same-key-physical-isolation",
    ok: create.parsed?.created?.id === "same_key_workspace" &&
      select.parsed?.workspace?.id === "same_key_workspace" &&
      imported.ok &&
      navRename.ok &&
      viewSave.ok &&
      dashboardSave.ok &&
      workspaceOrders?.workspace_id === "same_key_workspace" &&
      workspaceOrders?.physical_table &&
      workspaceOrders.physical_table !== defaultOrdersBefore?.physical_table &&
      workspaceMetrics.parsed?.metrics?.some((metric) => metric.metricKey === "orders_net_sales_sum" && metric.tableKey === "orders") &&
      workspaceView?.name === "Workspace Orders View" &&
      workspaceNav?.name === "Workspace Orders Nav" &&
      workspaceDashboardRow?.workspace_id === "same_key_workspace" &&
      workspaceDashboardRow?.name === "Workspace Default Dashboard" &&
      workspaceWidget?.title === "Workspace Sales" &&
      workspaceCatalog.parsed?.integration?.workspaceCounts?.dashboards === 1 &&
      workspaceCatalog.parsed?.integration?.workspaceCounts?.widgets === 1 &&
      workspaceQuery.parsed?.rows?.[0]?.value === 10 &&
      selectDefault.parsed?.workspace?.id === "default" &&
      defaultOrdersAfter?.physical_table === defaultOrdersBefore?.physical_table &&
      defaultOrdersAfter?.display_name === defaultOrdersBefore?.display_name &&
      defaultViewAfter?.name === defaultViewBefore?.name &&
      defaultNavAfter?.name === defaultNavBefore?.name &&
      (
        (!defaultDashboardBeforeRow && !defaultDashboardAfterRow) ||
        (
          defaultDashboardAfterRow?.workspace_id === "default" &&
          defaultDashboardAfterRow?.name === defaultDashboardBeforeRow?.name &&
          defaultWidgetAfter?.title === defaultWidgetBefore?.title
        )
      ),
    details: {
      defaultPhysicalBefore: defaultOrdersBefore?.physical_table,
      defaultPhysicalAfter: defaultOrdersAfter?.physical_table,
      workspacePhysical: workspaceOrders?.physical_table,
      workspaceViewName: workspaceView?.name,
      defaultViewNameAfter: defaultViewAfter?.name,
      workspaceNavigationName: workspaceNav?.name,
      defaultNavigationNameAfter: defaultNavAfter?.name,
      workspaceDashboardName: workspaceDashboardRow?.name,
      defaultDashboardNameAfter: defaultDashboardAfterRow?.name,
      workspaceWidgetTitle: workspaceWidget?.title,
      defaultWidgetTitleAfter: defaultWidgetAfter?.title,
      workspaceCatalogCounts: {
        dashboards: workspaceCatalog.parsed?.integration?.workspaceCounts?.dashboards,
        widgets: workspaceCatalog.parsed?.integration?.workspaceCounts?.widgets,
      },
      queryRows: workspaceQuery.parsed?.rows,
    },
  };
}

const verifyDashboardModulesWidgets = JSON.stringify([
  {
    id: "verify_bulk_metric",
    type: "metric",
    title: "验证批量指标",
    tableKey: "orders",
    measure: "net_sales",
    aggregation: "sum",
    valueFormat: "currency",
  },
  {
    id: "verify_bulk_table",
    type: "table",
    title: "验证批量明细",
    tableKey: "orders",
    columns: ["order_date", "channel", "net_sales"],
    aggregation: "count",
    topN: 100,
  },
]);
const verifyDashboardModulesLayout = JSON.stringify([
  { i: "verify_bulk_metric", x: 0, y: 0, w: 3, h: 2 },
  { i: "verify_bulk_table", x: 3, y: 0, w: 7, h: 5 },
]);
const verifyDashboardModulesFilters = JSON.stringify([
  { id: "verify_bulk_filter", field: "channel", operator: "equals", value: "Douyin", enabled: true },
]);

const fileViolations = walk(root).filter((file) => forbiddenPatterns.some((pattern) => pattern.test(file)));
const checks = [
  {
    label: "data-policy-no-real-business-files",
    ok: fileViolations.length === 0,
    violations: fileViolations,
  },
  run("cli-status", "python", ["tools/bi_cli.py", "--json", "status"]),
  run("cli-contract", "python", ["tools/bi_cli.py", "--json", "cli-contract"]),
  run("cli-contract-markdown-output", "python", ["tools/bi_cli.py", "--json", "cli-contract", "--format", "markdown", "--output", join(verifyDataDir, "bi-cli-contract.md")]),
  run("cli-list-dashboard-write-commands", "python", ["tools/bi_cli.py", "--json", "list-commands", "--domain", "dashboard", "--writes", "yes"]),
  runWorkspaceIsolationSmoke(),
  runWorkspaceModelIsolationSmoke(),
  runWorkspaceSameKeyIsolationSmoke(),
  run("cli-workspace-create-dry-run", "python", ["tools/bi_cli.py", "--json", "workspace-create", "--name", "验证工作区"]),
  run("cli-workspace-create-confirm", "python", ["tools/bi_cli.py", "--json", "workspace-create", "--name", "verify_workspace", "--yes"]),
  run("cli-workspace-select-dry-run", "python", ["tools/bi_cli.py", "--json", "workspace-select", "verify_workspace"]),
  run("cli-workspace-select-confirm", "python", ["tools/bi_cli.py", "--json", "workspace-select", "verify_workspace", "--yes"]),
  run("cli-status-after-workspace-select", "python", ["tools/bi_cli.py", "--json", "status"]),
  run("cli-workspace-select-default", "python", ["tools/bi_cli.py", "--json", "workspace-select", "default", "--yes"]),
  run("cli-workspace-delete-target-create", "python", ["tools/bi_cli.py", "--json", "workspace-create", "--name", "delete_workspace_target", "--yes"]),
  run("cli-workspace-delete-dry-run", "python", ["tools/bi_cli.py", "--json", "workspace-delete", "delete_workspace_target"]),
  run("cli-workspace-delete-confirm", "python", ["tools/bi_cli.py", "--json", "workspace-delete", "delete_workspace_target", "--yes"]),
  runExpectedFailure("cli-workspace-delete-default-blocked", "python", ["tools/bi_cli.py", "--json", "workspace-delete", "default", "--yes"]),
  run("cli-workspace-active-delete-target-create", "python", ["tools/bi_cli.py", "--json", "workspace-create", "--name", "active_delete_workspace", "--yes"]),
  run("cli-workspace-active-delete-target-select", "python", ["tools/bi_cli.py", "--json", "workspace-select", "active_delete_workspace", "--yes"]),
  runExpectedFailure("cli-workspace-delete-active-blocked", "python", ["tools/bi_cli.py", "--json", "workspace-delete", "active_delete_workspace", "--yes"]),
  run("cli-workspace-select-default-after-delete-check", "python", ["tools/bi_cli.py", "--json", "workspace-select", "default", "--yes"]),
  run("cli-workspace-create-chinese-dry-run", "python", ["tools/bi_cli.py", "--json", "workspace-create", "--name", "验证中文工作区"]),
  runExpectedFailure("cli-source-intelligence-no-input-blocked", "python", ["tools/bi_cli.py", "--json", "source-intelligence"]),
  run("verify-bootstrap-import-orders", "python", ["tools/bi_cli.py", "--json", "import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]),
  run("verify-bootstrap-import-refunds", "python", ["tools/bi_cli.py", "--json", "import-commit", "validation-inputs/refunds.csv", "--table", "refunds", "--name", "Refunds", "--mode", "create", "--yes"]),
  run("verify-bootstrap-relationship", "python", ["tools/bi_cli.py", "--json", "relationship-save", "--left-table", "orders", "--right-table", "refunds", "--left-field", "order_id", "--right-field", "order_id", "--yes"]),
  run("verify-bootstrap-orders-view", "python", ["tools/bi_cli.py", "--json", "save-view", "--view", "view_orders_default", "--table", "orders", "--name", "订单明细视图", "--columns", "order_date,channel,shop,sku,net_sales,status", "--sort", "order_date:desc", "--yes"]),
  run("verify-bootstrap-refunds-view", "python", ["tools/bi_cli.py", "--json", "save-view", "--view", "view_refunds_default", "--table", "refunds", "--name", "退款明细视图", "--columns", "apply_date,channel,sku,refund_amount,refund_status,resolution_hours", "--sort", "apply_date:desc", "--yes"]),
  run("verify-bootstrap-dashboard", "python", ["tools/bi_cli.py", "--json", "business-dashboard", "--op", "create", "--table", "orders", "--limit", "8", "--yes"]),
  run("verify-bootstrap-default-dashboard", "python", ["tools/bi_cli.py", "--json", "save-dashboard-modules", "--dashboard", "default", "--name", "验证默认看板", "--default-table", "orders", "--canvas-width-mode", "center", "--widgets-json", verifyDashboardModulesWidgets, "--layout-json", verifyDashboardModulesLayout, "--filters-json", verifyDashboardModulesFilters, "--yes"]),
  run("cli-list-tables", "python", ["tools/bi_cli.py", "--json", "list-tables"]),
  run("cli-list-navigation", "python", ["tools/bi_cli.py", "--json", "list-navigation"]),
  run("cli-default-dashboard-bootstrap", "python", ["tools/bi_cli.py", "--json", "dashboards", "--dashboard", "default"]),
  run("cli-navigation-rename-dry-run", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "rename", "--name", "验证导航订单"]),
  run("cli-navigation-rename-confirm", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "rename", "--name", "验证导航订单", "--yes"]),
  run("cli-navigation-move-dry-run", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "move", "--sort", "88"]),
  run("cli-navigation-move-confirm", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "move", "--sort", "88", "--yes"]),
  run("cli-navigation-hide-dry-run", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "hide"]),
  run("cli-navigation-hide-confirm", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "hide", "--yes"]),
  run("cli-navigation-show-dry-run", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "show"]),
  run("cli-navigation-show-confirm", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "show", "--yes"]),
  run("cli-navigation-move-restore", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "move", "--sort", "10", "--yes"]),
  run("cli-navigation-rename-restore", "python", ["tools/bi_cli.py", "--json", "navigation-op", "--module", "table:orders", "--op", "rename", "--name", "Orders", "--yes"]),
  run("cli-inspect-table", "python", ["tools/bi_cli.py", "--json", "inspect-table", "orders"]),
  run("cli-rename-source-dry-run", "python", ["tools/bi_cli.py", "--json", "rename-source", "refunds", "--name", "验证退款表"]),
  run("cli-rename-source-confirm", "python", ["tools/bi_cli.py", "--json", "rename-source", "refunds", "--name", "验证退款表", "--yes"]),
  run("cli-import-delete-source-validation-input", "python", ["tools/bi_cli.py", "--json", "import-commit", "validation-inputs/refunds.csv", "--table", "verify_delete_source", "--name", "验证删除源", "--mode", "create", "--yes"]),
  run("cli-delete-source-dry-run", "python", ["tools/bi_cli.py", "--json", "delete-source", "verify_delete_source"]),
  run("cli-delete-source-confirm", "python", ["tools/bi_cli.py", "--json", "delete-source", "verify_delete_source", "--yes"]),
  run("cli-source-intelligence-runs", "python", ["tools/bi_cli.py", "--json", "source-intelligence-runs", "--limit", "3"]),
  run("cli-source-intelligence-validation-inputs", "python", ["tools/bi_cli.py", "--json", "source-intelligence", "validation-inputs", "--label", "verify-validation-inputs-source-intelligence", "--output-dir", join(verifyDataDir, "source-intelligence-validation-inputs")]),
  run("cli-source-intelligence-runs-after-validation-input", "python", ["tools/bi_cli.py", "--json", "source-intelligence-runs", "--limit", "3"]),
  run("cli-source-intelligence-runs-after-validation-input-all", "python", ["tools/bi_cli.py", "--json", "source-intelligence-runs", "--limit", "3", "--all"]),
  run("cli-source-dashboard-draft", "python", ["tools/bi_cli.py", "--json", "source-dashboard-draft", "--name", "验证回执候选看板", "--limit", "3"]),
  run("cli-workbench", "python", ["tools/bi_cli.py", "--json", "workbench", "--limit", "3"]),
  run("cli-dashboard-widget-catalog", "python", ["tools/bi_cli.py", "--json", "dashboard-widget-catalog"]),
  run("cli-erp-unit-library-summary", "python", ["tools/bi_cli.py", "--json", "erp-unit-library", "--summary"]),
  run("cli-erp-unit-library-selection", "python", ["tools/bi_cli.py", "--json", "erp-unit-library", "--select", "--summary", "--table", "orders", "--limit", "12"]),
  run("cli-recommend-widgets", "python", ["tools/bi_cli.py", "--json", "recommend-widgets", "--table", "orders", "--limit", "7"]),
  run("cli-add-recommended-widgets-dry-run", "python", ["tools/bi_cli.py", "--json", "add-recommended-widgets", "--dashboard", "default", "--table", "orders", "--limit", "3"]),
  run("cli-add-widget-view-dry-run", "python", ["tools/bi_cli.py", "--json", "add-widget", "--dashboard", "default", "--type", "table", "--view", "view_orders_default", "--title", "验证视图组件"]),
  run("cli-add-widget-view-confirm", "python", ["tools/bi_cli.py", "--json", "add-widget", "--dashboard", "default", "--widget", "verify_view_widget", "--type", "table", "--view", "view_orders_default", "--title", "验证视图组件", "--yes"]),
  run("cli-set-widget-dry-run", "python", ["tools/bi_cli.py", "--json", "set-widget", "--widget", "verify_view_widget", "--title", "验证视图组件更新", "--subtitle", "验证配置编辑", "--dimension", "channel", "--measure", "net_sales", "--agg", "sum", "--top-n", "20", "--value-format", "currency"]),
  run("cli-set-widget-style-dry-run", "python", ["tools/bi_cli.py", "--json", "set-widget", "--widget", "verify_view_widget", "--color-palette", "contrast", "--bar-orientation", "horizontal", "--ranking-mode", "ranked", "--show-data-label", "--hide-legend", "--hide-axis", "--area-fill", "--pie-shape", "pie", "--slicer-display", "dropdown", "--decimal-places", "1", "--table-column-limit", "8", "--x-axis-title", "渠道", "--y-axis-title", "净销售额", "--legend-title", "渠道分类", "--drill-down", "--cross-filter"]),
  run("cli-set-widget-style-confirm", "python", ["tools/bi_cli.py", "--json", "set-widget", "--widget", "verify_view_widget", "--color-palette", "contrast", "--bar-orientation", "horizontal", "--ranking-mode", "ranked", "--show-data-label", "--hide-legend", "--hide-axis", "--area-fill", "--pie-shape", "pie", "--slicer-display", "dropdown", "--decimal-places", "1", "--table-column-limit", "8", "--x-axis-title", "渠道", "--y-axis-title", "净销售额", "--legend-title", "渠道分类", "--drill-down", "--cross-filter", "--yes"]),
  run("cli-set-widget-filter-dry-run", "python", ["tools/bi_cli.py", "--json", "set-widget", "--widget", "verify_view_widget", "--filter", "channel:equals:Douyin"]),
  run("cli-set-widget-filter-confirm", "python", ["tools/bi_cli.py", "--json", "set-widget", "--widget", "verify_view_widget", "--filter", "channel:equals:Douyin", "--yes"]),
  run("cli-set-widget-clear-filter-dry-run", "python", ["tools/bi_cli.py", "--json", "set-widget", "--widget", "verify_view_widget", "--clear-filters"]),
  run("cli-copy-widget-dry-run", "python", ["tools/bi_cli.py", "--json", "copy-widget", "--widget", "verify_view_widget", "--title", "验证视图组件副本"]),
  run("cli-remove-widget-dry-run", "python", ["tools/bi_cli.py", "--json", "remove-widget", "--widget", "verify_view_widget"]),
  run("cli-save-dashboard-modules-dry-run", "python", ["tools/bi_cli.py", "--json", "save-dashboard-modules", "--dashboard", "default", "--name", "验证批量看板", "--default-table", "orders", "--canvas-width-mode", "center", "--widgets-json", verifyDashboardModulesWidgets, "--layout-json", verifyDashboardModulesLayout, "--filters-json", verifyDashboardModulesFilters]),
  run("cli-save-dashboard-modules-confirm", "python", ["tools/bi_cli.py", "--json", "save-dashboard-modules", "--dashboard", "default", "--name", "验证批量看板", "--default-table", "orders", "--canvas-width-mode", "center", "--widgets-json", verifyDashboardModulesWidgets, "--layout-json", verifyDashboardModulesLayout, "--filters-json", verifyDashboardModulesFilters, "--yes"]),
  run("cli-dashboard-source-switch-dry-run", "python", ["tools/bi_cli.py", "--json", "save-dashboard-modules", "--dashboard", "default", "--name", "验证源切换看板", "--default-table", "refunds", "--canvas-width-mode", "center", "--widgets-json", verifyDashboardModulesWidgets, "--layout-json", verifyDashboardModulesLayout, "--filters-json", "[]"]),
  run("cli-dashboards-after-module-save", "python", ["tools/bi_cli.py", "--json", "dashboards", "--dashboard", "default"]),
  run("cli-business-dashboard-draft", "python", ["tools/bi_cli.py", "--json", "business-dashboard", "--op", "draft", "--table", "orders", "--limit", "8"]),
  run("cli-business-dashboard-erp-units-draft", "python", ["tools/bi_cli.py", "--json", "business-dashboard", "--op", "draft", "--template", "erp-units", "--table", "orders", "--limit", "12"]),
  run("cli-business-dashboard-create-dry-run", "python", ["tools/bi_cli.py", "--json", "business-dashboard", "--op", "create", "--table", "orders", "--limit", "8"]),
  run("cli-business-dashboard-create-confirm", "python", ["tools/bi_cli.py", "--json", "business-dashboard", "--op", "create", "--table", "orders", "--limit", "8", "--yes"]),
  run("cli-business-dashboard-overwrite-dry-run", "python", ["tools/bi_cli.py", "--json", "business-dashboard", "--op", "overwrite", "--dashboard", "default", "--table", "orders", "--limit", "8"]),
  run("cli-cost-monitor-import-funds", "python", ["tools/bi_cli.py", "--json", "import-commit", verifyFundsPath, "--table", "verify_cost_funds", "--name", "验证资金", "--mode", "create", "--yes"]),
  run("cli-cost-monitor-import-policy", "python", ["tools/bi_cli.py", "--json", "import-commit", verifyPolicyPath, "--table", "verify_cost_policy", "--name", "验证保单明细", "--mode", "create", "--yes"]),
  run("cli-cost-monitor-dashboard-draft", "python", ["tools/bi_cli.py", "--json", "business-dashboard", "--op", "draft", "--template", "cost-monitor", "--table", "verify_cost_funds", "--limit", "24"]),
  run("cli-cost-monitor-dashboard-create-dry-run", "python", ["tools/bi_cli.py", "--json", "business-dashboard", "--op", "create", "--template", "cost-monitor", "--table", "verify_cost_funds", "--limit", "24"]),
  run("cli-b-cli-capabilities", "python", ["tools/bi_cli.py", "--json", "b-cli-capabilities"]),
  run("cli-set-import-policy-dry-run", "python", ["tools/bi_cli.py", "--json", "set-import-policy", "--table", "orders", "--unique-fields", "order_id", "--conflict-rule", "fill-empty"]),
  run("cli-set-import-policy-confirm", "python", ["tools/bi_cli.py", "--json", "set-import-policy", "--table", "orders", "--unique-fields", "order_id", "--conflict-rule", "fill-empty", "--yes"]),
  run("cli-list-import-jobs", "python", ["tools/bi_cli.py", "--json", "list-import-jobs", "--limit", "5"]),
  run("cli-preview-import", "python", ["tools/bi_cli.py", "--json", "preview-import", "validation-inputs/orders.csv"]),
  run("cli-preview-import-folder", "python", ["tools/bi_cli.py", "--json", "preview-import-folder", "validation-inputs", "--limit", "10"]),
  run("cli-import-folder-dry-run", "python", ["tools/bi_cli.py", "--json", "import-folder", "validation-inputs", "--limit", "10"]),
  run("cli-save-connector-dry-run", "python", ["tools/bi_cli.py", "--json", "save-connector", "--connector", "verify_file_connector", "--name", "验证文件连接器", "--type", "file", "--provider", "local-file", "--status", "active", "--endpoint", "validation-inputs/orders.csv", "--target-table", "orders", "--unique-fields", "order_id", "--conflict-rule", "overwrite"]),
  run("cli-save-connector-confirm", "python", ["tools/bi_cli.py", "--json", "save-connector", "--connector", "verify_file_connector", "--name", "验证文件连接器", "--type", "file", "--provider", "local-file", "--status", "active", "--endpoint", "validation-inputs/orders.csv", "--target-table", "orders", "--unique-fields", "order_id", "--conflict-rule", "overwrite", "--yes"]),
  run("cli-save-external-connector-confirm", "python", ["tools/bi_cli.py", "--json", "save-connector", "--connector", "verify_erp_connector", "--name", "验证 ERP 连接器", "--type", "erp", "--provider", "jushuitan", "--status", "draft", "--endpoint", "https://example.invalid/api", "--target-table", "erp_orders", "--yes"]),
  run("cli-list-connectors", "python", ["tools/bi_cli.py", "--json", "list-connectors"]),
  run("cli-sync-connector-dry-run", "python", ["tools/bi_cli.py", "--json", "sync-connector", "--connector", "verify_file_connector"]),
  run("cli-sync-connector-confirm", "python", ["tools/bi_cli.py", "--json", "sync-connector", "--connector", "verify_file_connector", "--yes"]),
  run("cli-sync-external-connector-blocked", "python", ["tools/bi_cli.py", "--json", "sync-connector", "--connector", "verify_erp_connector", "--yes"]),
  run("cli-remove-connector-dry-run", "python", ["tools/bi_cli.py", "--json", "remove-connector", "--connector", "verify_file_connector"]),
  run("cli-preferences", "python", ["tools/bi_cli.py", "--json", "preferences"]),
  run("cli-preferences-dry-run", "python", ["tools/bi_cli.py", "--json", "preferences", "--theme-key", "D1"]),
  run("cli-preferences-confirm", "python", ["tools/bi_cli.py", "--json", "preferences", "--theme-key", "L1", "--yes"]),
  run("cli-theme-palettes", "python", ["tools/bi_cli.py", "--json", "theme-palettes"]),
  run("cli-theme-save-dry-run", "python", ["tools/bi_cli.py", "--json", "theme-palettes", "--action", "save", "--theme-key", "verify_custom", "--name", "验证自定义主题", "--mode", "light", "--tokens-json", "{\"railTop\":\"#eef4f8\",\"railMid\":\"#e8f0f6\",\"railBottom\":\"#dbe8f0\",\"railActive\":\"#ffffff\",\"primary\":\"#0e7490\",\"primaryHover\":\"#155e75\",\"selected\":\"#ccecf1\",\"soft\":\"#e7f6f8\",\"bg\":\"#f5f7fb\",\"surface\":\"#ffffff\",\"panel\":\"#f8fafd\",\"border\":\"#d7e0ec\",\"text\":\"#172033\",\"muted\":\"#5f6b7b\"}"]),
  run("cli-theme-save-confirm", "python", ["tools/bi_cli.py", "--json", "theme-palettes", "--action", "save", "--theme-key", "verify_custom", "--name", "验证自定义主题", "--mode", "light", "--tokens-json", "{\"railTop\":\"#eef4f8\",\"railMid\":\"#e8f0f6\",\"railBottom\":\"#dbe8f0\",\"railActive\":\"#ffffff\",\"primary\":\"#0e7490\",\"primaryHover\":\"#155e75\",\"selected\":\"#ccecf1\",\"soft\":\"#e7f6f8\",\"bg\":\"#f5f7fb\",\"surface\":\"#ffffff\",\"panel\":\"#f8fafd\",\"border\":\"#d7e0ec\",\"text\":\"#172033\",\"muted\":\"#5f6b7b\"}", "--yes"]),
  run("cli-theme-delete-dry-run", "python", ["tools/bi_cli.py", "--json", "theme-palettes", "--action", "delete", "--theme-key", "verify_custom"]),
  run("cli-validate-config", "python", ["tools/bi_cli.py", "--json", "validate-config"]),
  run("cli-export-config", "python", ["tools/bi_cli.py", "--json", "export-config", join(verifyDataDir, "metadata-config.json")]),
  run("cli-apply-config-dry-run", "python", ["tools/bi_cli.py", "--json", "apply-config", join(verifyDataDir, "metadata-config.json")]),
  run("cli-workbench-after-connectors", "python", ["tools/bi_cli.py", "--json", "workbench", "--limit", "3"]),
  run("cli-query", "python", ["tools/bi_cli.py", "--json", "query", "--table", "orders", "--group", "channel", "--measure", "net_sales", "--agg", "sum"]),
  run("cli-query-table-detail", "python", ["tools/bi_cli.py", "--json", "query-table", "--table", "orders", "--mode", "detail", "--column", "order_date", "--column", "channel", "--column", "net_sales", "--filter", "channel:equals:Douyin", "--sort", "net_sales:desc", "--limit", "5"]),
  run("cli-query-table-view", "python", ["tools/bi_cli.py", "--json", "query-table", "--view", "view_orders_default", "--limit", "3"]),
  run("cli-list-views", "python", ["tools/bi_cli.py", "--json", "list-views"]),
  run("cli-save-view-dry-run", "python", ["tools/bi_cli.py", "--json", "save-view", "--table", "orders", "--name", "抖音订单视图", "--columns", "order_date,channel,sku,net_sales,status", "--filter", "channel:equals:Douyin", "--sort", "net_sales:desc"]),
  run("cli-save-view-confirm", "python", ["tools/bi_cli.py", "--json", "save-view", "--table", "orders", "--name", "抖音订单视图", "--columns", "order_date,channel,sku,net_sales,status", "--filter", "channel:equals:Douyin", "--sort", "net_sales:desc", "--yes"]),
  run("cli-recommend-relationships", "python", ["tools/bi_cli.py", "--json", "recommend-relationships", "--limit", "5"]),
  run("cli-relationship-preview", "python", ["tools/bi_cli.py", "--json", "relationship-preview", "--left-table", "orders", "--right-table", "refunds", "--left-field", "order_id", "--right-field", "order_id"]),
  run("cli-relationship-save-dry-run", "python", ["tools/bi_cli.py", "--json", "relationship-save", "--left-table", "orders", "--right-table", "refunds", "--left-field", "order_id", "--right-field", "order_id"]),
  run("cli-list-relationships", "python", ["tools/bi_cli.py", "--json", "list-relationships"]),
  run("cli-query-relationship", "python", ["tools/bi_cli.py", "--json", "query-relationship", "--relationship", "orders_refunds_order_id_order_id", "--group", "left:channel", "--measure", "left:net_sales", "--agg", "sum", "--limit", "5"]),
  run("cli-remove-relationship-dry-run", "python", ["tools/bi_cli.py", "--json", "remove-relationship", "--relationship", "orders_refunds_order_id_order_id"]),
  run("cli-add-relationship-widget-dry-run", "python", ["tools/bi_cli.py", "--json", "add-relationship-widget", "--dashboard", "default", "--relationship", "orders_refunds_order_id_order_id", "--type", "bar", "--title", "验证关系组件", "--group", "order_id", "--agg", "count"]),
  run("cli-add-relationship-widget-confirm", "python", ["tools/bi_cli.py", "--json", "add-relationship-widget", "--dashboard", "default", "--widget", "verify_relationship_widget", "--relationship", "orders_refunds_order_id_order_id", "--type", "bar", "--title", "验证关系组件", "--group", "order_id", "--agg", "count", "--yes"]),
  run("cli-field-update-dry-run", "python", ["tools/bi_cli.py", "--json", "field-update", "--table", "orders", "--field", "channel", "--role", "dimension", "--usage", "groupable"]),
  run("cli-infer-semantics-dry-run", "python", ["tools/bi_cli.py", "--json", "infer-semantics", "--table", "orders"]),
  run("cli-set-semantic-dry-run", "python", ["tools/bi_cli.py", "--json", "set-semantic", "orders", "sku", "--role", "identity_key", "--tag", "product", "--usage", "joinable", "--usage", "groupable"]),
  run("cli-set-semantic-confirm", "python", ["tools/bi_cli.py", "--json", "set-semantic", "orders", "sku", "--role", "identity_key", "--tag", "product", "--usage", "joinable", "--usage", "groupable", "--yes"]),
  run("cli-list-semantics", "python", ["tools/bi_cli.py", "--json", "list-semantics", "--table", "orders"]),
  run("cli-infer-metrics-dry-run", "python", ["tools/bi_cli.py", "--json", "infer-metrics", "--table", "orders"]),
  run("cli-infer-metrics-confirm", "python", ["tools/bi_cli.py", "--json", "infer-metrics", "--table", "orders", "--yes"]),
  run("cli-list-metrics", "python", ["tools/bi_cli.py", "--json", "list-metrics", "--table", "orders"]),
  run("cli-add-metric-dry-run", "python", ["tools/bi_cli.py", "--json", "add-metric", "--id", "verify_avg_net_sales", "--name", "验证平均经营额", "--table", "orders", "--field", "net_sales", "--agg", "avg", "--dimension", "channel"]),
  run("cli-add-metric-confirm", "python", ["tools/bi_cli.py", "--json", "add-metric", "--id", "verify_avg_net_sales", "--name", "验证平均经营额", "--table", "orders", "--field", "net_sales", "--agg", "avg", "--dimension", "channel", "--yes"]),
  run("cli-query-metric", "python", ["tools/bi_cli.py", "--json", "query-metric", "orders_net_sales_sum", "--group", "channel", "--limit", "5"]),
  run("cli-formula-preview", "python", ["tools/bi_cli.py", "--json", "formula-preview", "SAFE_DIVIDE(SUM([net_sales]), SUM([quantity]))"]),
  run("cli-save-formula-dry-run", "python", ["tools/bi_cli.py", "--json", "save-formula", "--id", "verify_formula_metric", "--name", "验证公式指标", "--table", "orders", "--expression", "SAFE_DIVIDE(SUM([net_sales]), SUM([quantity]))", "--mode", "aggregate", "--dimension", "channel"]),
  run("cli-save-formula-confirm", "python", ["tools/bi_cli.py", "--json", "save-formula", "--id", "verify_formula_metric", "--name", "验证公式指标", "--table", "orders", "--expression", "SAFE_DIVIDE(SUM([net_sales]), SUM([quantity]))", "--mode", "aggregate", "--dimension", "channel", "--yes"]),
  run("cli-query-formula-metric", "python", ["tools/bi_cli.py", "--json", "query-metric", "verify_formula_metric", "--group", "channel", "--limit", "5"]),
  run("cli-save-row-formula-confirm", "python", ["tools/bi_cli.py", "--json", "save-formula", "--id", "verify_row_formula", "--name", "net_sales_per_unit", "--table", "orders", "--expression", "SAFE_DIVIDE([net_sales],[quantity])", "--mode", "row", "--yes"]),
  run("cli-query-row-formula-detail", "python", ["tools/bi_cli.py", "--json", "query-table", "--table", "orders", "--mode", "detail", "--column", "channel", "--column", "net_sales_per_unit", "--filter", "net_sales_per_unit:gt:300", "--sort", "net_sales_per_unit:desc", "--limit", "3"]),
  run("cli-query-row-formula-aggregate", "python", ["tools/bi_cli.py", "--json", "query-table", "--table", "orders", "--mode", "aggregate", "--group", "channel", "--measure", "net_sales_per_unit", "--agg", "avg", "--limit", "5"]),
  run("cli-save-row-formula-view", "python", ["tools/bi_cli.py", "--json", "save-view", "--view", "verify_row_formula_view", "--table", "orders", "--name", "验证公式字段视图", "--columns", "channel,net_sales_per_unit", "--filter", "net_sales_per_unit:gt:300", "--yes"]),
  run("cli-delete-row-formula-dry-blocked", "python", ["tools/bi_cli.py", "--json", "delete-formula", "verify_row_formula"]),
  runExpectedFailure("cli-delete-row-formula-confirm-blocked", "python", ["tools/bi_cli.py", "--json", "delete-formula", "verify_row_formula", "--yes"]),
  run("cli-delete-row-formula-view-confirm", "python", ["tools/bi_cli.py", "--json", "delete-view", "--view", "verify_row_formula_view", "--yes"]),
  run("cli-list-formulas", "python", ["tools/bi_cli.py", "--json", "list-formulas", "--table", "orders"]),
  run("cli-delete-formula-dry-run", "python", ["tools/bi_cli.py", "--json", "delete-formula", "verify_formula_metric"]),
  run("cli-delete-formula-confirm", "python", ["tools/bi_cli.py", "--json", "delete-formula", "verify_formula_metric", "--yes"]),
  run("cli-delete-row-formula-confirm", "python", ["tools/bi_cli.py", "--json", "delete-formula", "verify_row_formula", "--yes"]),
  run("cli-dashboard-op-dry-run", "python", ["tools/bi_cli.py", "--json", "dashboard-op", "--op", "copy", "--dashboard", "default", "--name", "默认副本"]),
  run("cli-filter-add-dry-run", "python", ["tools/bi_cli.py", "--json", "add-filter", "--dashboard", "default", "--field", "channel", "--operator", "equals", "--value", "Douyin"]),
  run("cli-filter-add-confirm", "python", ["tools/bi_cli.py", "--json", "add-filter", "--dashboard", "default", "--field", "channel", "--operator", "equals", "--value", "Douyin", "--yes"]),
  run("cli-filter-list", "python", ["tools/bi_cli.py", "--json", "list-filters", "--dashboard", "default"]),
  run("cli-filter-remove-stale-dry-run", "python", ["tools/bi_cli.py", "--json", "remove-stale-filters", "--dashboard", "default"]),
  run("cli-filter-clear-dry-run", "python", ["tools/bi_cli.py", "--json", "clear-filters", "--dashboard", "default"]),
  run("cli-recommend-indexes", "python", ["tools/bi_cli.py", "--json", "recommend-indexes", "--table", "orders", "--limit", "5"]),
  run("cli-create-index-dry-run", "python", ["tools/bi_cli.py", "--json", "create-index", "--table", "orders", "--field", "channel"]),
  run("cli-create-index-confirm", "python", ["tools/bi_cli.py", "--json", "create-index", "--table", "orders", "--field", "channel", "--yes"]),
  run("frontend-widget-filter-model", "node", ["--import", "tsx", "-e", "Promise.all([import('./src/biDashboardRuntime.ts'), import('./src/biDashboardModel.ts')]).then(([runtime, model]) => { const {aggregateWidgetRows}=runtime; const {normalizeBiDashboardFilters}=model; const query={ok:true,query:{table:'orders',mode:'aggregate',group:'channel',measure:'net_sales',aggregation:'sum',sqlIntent:'test'},rows:[{label:'Douyin',value:3440},{label:'JD',value:2410},{label:'Tmall',value:2440}]}; const widget={id:'w',type:'bar',title:'w',tableKey:'orders',dataMode:'table',dimension:'channel',measure:'net_sales',aggregation:'sum',sortBy:'metric',sortDirection:'desc',topN:12,valueFormat:'auto',decimalPlaces:2,tableColumnLimit:6,slicerDisplay:'list',slicerMultiSelect:false,slicerSearchable:true,filters:normalizeBiDashboardFilters([{field:'channel',operator:'equals',value:'Douyin',enabled:true}]),showLegend:true,showAxis:true,showDataLabel:false,rankingMode:'standard',colorPalette:'default',barOrientation:'vertical',lineSmooth:true,areaFill:false,pieShape:'donut',crossFilter:true,drillDown:true,globalFilterTarget:false,evidence:[]}; const localRows=aggregateWidgetRows(widget,query,[]); const globalRows=aggregateWidgetRows({...widget,filters:[]},query,normalizeBiDashboardFilters([{field:'channel',operator:'equals',value:'JD',enabled:true}])); console.log(JSON.stringify({ok:localRows.length===1&&localRows[0].label==='Douyin'&&globalRows.length===1&&globalRows[0].label==='JD',localRows,globalRows})); })"]),
  run("frontend-slicer-cross-filter-model", "node", ["--import", "tsx", "-e", "Promise.all([import('./src/biDashboardRuntime.ts'), import('./src/biDashboardModel.ts')]).then(([runtime, model]) => { const {aggregateWidgetRows}=runtime; const {buildBiDashboardWidgets, normalizeBiDashboardFilters}=model; const query={ok:true,query:{table:'orders',mode:'aggregate',group:'channel',measure:'net_sales',aggregation:'sum',sqlIntent:'test'},rows:[{label:'Douyin',value:3440},{label:'JD',value:2410},{label:'Tmall',value:2440}]}; const dashboard={dashboard_key:'default',name:'Default',workspace_id:'default',default_table_key:'orders',created_by:'verify',agent_managed:0,layout:{version:1},widgets:[]}; const workbench={ok:true,tables:[{table_key:'orders'}],fields:[],metrics:[],relationships:[],importJobs:[],savedViews:[],sourceIntelligenceRuns:[],fieldRoles:[],fieldUsages:[],safeAggregations:['count'],formulaDsl:{allowedFunctions:[],fieldReference:'[field]',acceptsSql:false}}; const widgets=buildBiDashboardWidgets({dashboard,dashboards:{ok:true,dashboards:[dashboard]},query,workbench}); const slicer=widgets.find((widget)=>widget.type==='slicer'); const bar=widgets.find((widget)=>widget.type==='bar'); const filtered=aggregateWidgetRows({...bar,filters:[]},query,normalizeBiDashboardFilters([{field:'label',operator:'equals',value:'JD',enabled:true}])); console.log(JSON.stringify({ok:slicer?.drillDown===false&&slicer?.globalFilterTarget===true&&filtered.length===1&&filtered[0].label==='JD',slicer:{drillDown:slicer?.drillDown,globalFilterTarget:slicer?.globalFilterTarget},filtered})); })"]),
  run("frontend-relationship-widget-model", "node", ["--import", "tsx", "-e", "import('./src/biDashboardModel.ts').then(({buildBiDashboardWidgets}) => { const dashboard={dashboard_key:'default',name:'Default',workspace_id:'default',default_table_key:'orders',created_by:'verify',agent_managed:0,layout:{version:1},widgets:[{widget_key:'rel',dashboard_key:'default',widget_type:'bar',title:'rel',table_key:'orders',sort_order:10,config:{dataMode:'relationship',dimension:'order_id',measure:'',aggregation:'count',relationship:{relationKey:'orders_refunds_order_id_order_id',leftTableKey:'orders',rightTableKey:'refunds',fieldMappings:[{leftField:'order_id',rightField:'order_id'}],joinType:'left',groupFields:[{side:'left',field:'order_id'}],measure:null,aggregation:'count'}}}]}; const widgets=buildBiDashboardWidgets({dashboard,dashboards:{ok:true,dashboards:[dashboard]},query:{ok:true,query:{table:'orders',mode:'aggregate',group:'order_id',measure:'value',aggregation:'count',sqlIntent:'test'},rows:[{label:'O-1',value:1}]},workbench:{ok:true,tables:[],fields:[],metrics:[],relationships:[],importJobs:[],savedViews:[],sourceIntelligenceRuns:[],fieldRoles:[],fieldUsages:[],safeAggregations:['count'],formulaDsl:{allowedFunctions:[],fieldReference:'[field]',acceptsSql:false}}}); const rel=widgets.find((widget)=>widget.id==='rel'); console.log(JSON.stringify({ok:rel?.dataMode==='relationship'&&rel?.relationship?.relationKey==='orders_refunds_order_id_order_id'&&rel?.evidence?.includes('relationship:orders_refunds_order_id_order_id'),relationship:rel?.relationship,evidence:rel?.evidence})); })"]),
  run("frontend-metric-repair-risk-model", "node", ["--import", "tsx", "-e", "import('./src/metricRepairModel.ts').then(({buildMetricRepairPlan}) => { const workbench={tables:[{table_key:'orders',display_name:'Orders'}],fields:[{table_key:'orders',field_name:'net_sales_paid_gmv_candidate',role:'measure',usage:'aggregatable',confidence:0.96,tags_json:'',usage_json:'',note:'净销售 derived net_sales'}],metrics:[],relationships:[],importJobs:[],savedViews:[],sourceIntelligenceRuns:[],fieldRoles:[],fieldUsages:[],safeAggregations:['sum'],formulaDsl:{allowedFunctions:[],fieldReference:'[field]',acceptsSql:false}}; const plan=buildMetricRepairPlan({metricSql:{planned:10,executable:2,blocked:8,rate:0.2,missingSemantics:[{semantic:'paid_gmv',count:5}],failedSamples:[]}},workbench); const draft=plan.bindingDrafts[0]; console.log(JSON.stringify({ok:draft?.semantic==='paid_gmv'&&draft?.tone==='warn'&&draft?.requiresPreview===true&&draft?.riskLevel==='high'&&draft?.status==='preview-required',draft})); })"]),
  run("cli-agent-ask", "python", ["tools/bi_cli.py", "--json", "ask", "生成经营分析计划"]),
  run("cli-agent-dashboard-draft", "python", ["tools/bi_cli.py", "--json", "ask", "请创建经营分析看板"]),
  run("cli-agent-ambiguous-chart-clarification", "python", ["tools/bi_cli.py", "--json", "ask", "创建一个图表"]),
  run("cli-agent-erp-dashboard-draft", "python", ["tools/bi_cli.py", "--json", "ask", "基于当前 ERP 数据生成一张经营看板，让 Agent 自己选择需要的组件"]),
  run("cli-agent-index-draft", "python", ["tools/bi_cli.py", "--json", "ask", "给 orders 的 channel 建索引来优化查询"]),
  run("cli-agent-relationship-draft", "python", ["tools/bi_cli.py", "--json", "ask", "保存 orders 和 refunds 的 order_id 关系"]),
  run("cli-agent-import-draft", "python", ["tools/bi_cli.py", "--json", "ask", "导入 validation-inputs/refunds.csv"]),
  run("cli-agent-formula-draft", "python", ["tools/bi_cli.py", "--json", "ask", "保存客单价公式"]),
  run("cli-agent-view-draft", "python", ["tools/bi_cli.py", "--json", "ask", "把 orders 中 channel=Douyin 的明细保存为 Douyin订单视图"]),
  run("cli-agent-metric-draft", "python", ["tools/bi_cli.py", "--json", "ask", "新增 orders 的 net_sales 合计指标，按 channel 分组"]),
  run("cli-agent-widget-draft", "python", ["tools/bi_cli.py", "--json", "ask", "在默认看板添加 orders 的 net_sales 指标卡"]),
  run("cli-agent-view-bridge-widget-draft", "python", ["tools/bi_cli.py", "--json", "ask", "基于当前视图起草一个 orders 的 net_sales 指标卡，不要直接写入"]),
  run("cli-agent-dashboard-filter-draft", "python", ["tools/bi_cli.py", "--json", "ask", "给 default 看板筛选 channel=Douyin"]),
  run("cli-agent-semantic-draft", "python", ["tools/bi_cli.py", "--json", "ask", "把 orders 的 channel 字段设为维度"]),
  run("cli-agent-english-generic-dashboard-draft", "python", ["tools/bi_cli.py", "--json", "ask", "Draft a business dashboard without writing directly"]),
  run("cli-agent-missing-dashboard", "python", ["tools/bi_cli.py", "--json", "ask", "在资金仪表盘增加一个税收指标卡"]),
  run("old-project-status", "node", ["scripts/verify-old-projects-readonly.mjs"]),
];

const readOnlyAgentCheck = run("cli-agent-read-only-explain-no-draft", "python", [
  "tools/bi_cli.py",
  "--json",
  "ask",
  "--read-only",
  "Read-only summary only: state what this workspace can answer, evidence files, usable metrics, and gaps.",
]);
checks.push({
  ...readOnlyAgentCheck,
  ok: readOnlyAgentCheck.ok &&
    readOnlyAgentCheck.parsed?.requiresConfirmation === false &&
    readOnlyAgentCheck.parsed?.actionDraft?.kind === "analysis.explain" &&
    readOnlyAgentCheck.parsed?.actionDraft?.status === "read-only",
});

const bootstrapOrdersSourceRunId = checks.find((check) => check.label === "verify-bootstrap-import-orders")?.parsed?.result?.sourceRunId;
if (bootstrapOrdersSourceRunId) {
  checks.push(run("cli-source-run-detail", "python", ["tools/bi_cli.py", "--json", "source-run", bootstrapOrdersSourceRunId]));
}

const ordersImportJobKey = checks
  .find((check) => check.label === "cli-list-import-jobs")
  ?.parsed?.importJobs?.find((job) => job.table_key === "orders")?.job_key;
if (ordersImportJobKey) {
  checks.push(run("cli-remove-import-job-dry-run", "python", ["tools/bi_cli.py", "--json", "remove-import-job", "--job", ordersImportJobKey]));
}

const sourceDashboardDraftKey = checks.find((check) => check.label === "cli-source-dashboard-draft")?.parsed?.actionDraft?.actionKey;
if (sourceDashboardDraftKey) {
  checks.push(run("cli-source-dashboard-confirm-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", sourceDashboardDraftKey]));
  checks.push(run("cli-source-dashboard-confirm", "python", ["tools/bi_cli.py", "--json", "confirm-action", sourceDashboardDraftKey, "--yes"]));
  const sourceDashboardKey = checks.find((check) => check.label === "cli-source-dashboard-confirm")?.parsed?.createdDashboardKey;
  if (sourceDashboardKey) {
    checks.push(run("cli-source-dashboard-after-confirm", "python", ["tools/bi_cli.py", "--json", "dashboards", "--dashboard", sourceDashboardKey]));
  }
  checks.push(run("cli-source-dashboard-action-drafts-after-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
}

const agentDashboardDraftKey = checks.find((check) => check.label === "cli-agent-dashboard-draft")?.parsed?.actionDraft?.actionKey;
if (agentDashboardDraftKey) {
  checks.push(run("cli-agent-action-drafts-before-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-confirm-dashboard-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardDraftKey]));
  checks.push(run("cli-agent-confirm-dashboard", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardDraftKey, "--yes"]));
  checks.push(run("cli-navigation-after-agent-confirm", "python", ["tools/bi_cli.py", "--json", "list-navigation"]));
  checks.push(run("cli-agent-action-drafts-after-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-dashboard-copy-draft", "python", ["tools/bi_cli.py", "--json", "ask", "把 default 看板复制为 Agent复制验证看板"]));
  const agentDashboardCopyDraftKey = checks.find((check) => check.label === "cli-agent-dashboard-copy-draft")?.parsed?.actionDraft?.actionKey;
  if (agentDashboardCopyDraftKey) {
    checks.push(run("cli-agent-confirm-dashboard-copy-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardCopyDraftKey]));
    checks.push(run("cli-agent-confirm-dashboard-copy", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardCopyDraftKey, "--yes"]));
    checks.push(run("cli-agent-dashboard-rename-draft", "python", ["tools/bi_cli.py", "--json", "ask", "把 Agent复制验证看板 重命名为 Agent重命名验证看板"]));
    const agentDashboardRenameDraftKey = checks.find((check) => check.label === "cli-agent-dashboard-rename-draft")?.parsed?.actionDraft?.actionKey;
    if (agentDashboardRenameDraftKey) {
      checks.push(run("cli-agent-confirm-dashboard-rename-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardRenameDraftKey]));
      checks.push(run("cli-agent-confirm-dashboard-rename", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardRenameDraftKey, "--yes"]));
      checks.push(run("cli-agent-dashboard-delete-draft", "python", ["tools/bi_cli.py", "--json", "ask", "删除 Agent重命名验证看板"]));
      const agentDashboardDeleteDraftKey = checks.find((check) => check.label === "cli-agent-dashboard-delete-draft")?.parsed?.actionDraft?.actionKey;
      if (agentDashboardDeleteDraftKey) {
        checks.push(run("cli-agent-confirm-dashboard-delete-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardDeleteDraftKey]));
        checks.push(run("cli-agent-confirm-dashboard-delete", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardDeleteDraftKey, "--yes"]));
        checks.push(run("cli-agent-dashboards-after-crud", "python", ["tools/bi_cli.py", "--json", "dashboards"]));
        checks.push(run("cli-agent-action-drafts-after-dashboard-crud", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
      }
    }
  }
}
const agentIndexDraftKey = checks.find((check) => check.label === "cli-agent-index-draft")?.parsed?.actionDraft?.actionKey;
if (agentIndexDraftKey) {
  checks.push(run("cli-agent-confirm-index-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentIndexDraftKey]));
  checks.push(run("cli-agent-confirm-index", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentIndexDraftKey, "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-index-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
}
const agentRelationshipDraftKey = checks.find((check) => check.label === "cli-agent-relationship-draft")?.parsed?.actionDraft?.actionKey;
if (agentRelationshipDraftKey) {
  checks.push(run("cli-agent-confirm-relationship-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentRelationshipDraftKey]));
  checks.push(run("cli-agent-confirm-relationship", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentRelationshipDraftKey, "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-relationship-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-relationships-after-confirm", "python", ["tools/bi_cli.py", "--json", "list-relationships"]));
}
const agentImportDraftKey = checks.find((check) => check.label === "cli-agent-import-draft")?.parsed?.actionDraft?.actionKey;
if (agentImportDraftKey) {
  checks.push(run("cli-agent-confirm-import-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentImportDraftKey]));
  checks.push(run("cli-agent-confirm-import", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentImportDraftKey, "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-import-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-import-jobs-after-confirm", "python", ["tools/bi_cli.py", "--json", "list-import-jobs", "--table", "refunds", "--limit", "5"]));
}
const agentFormulaDraftKey = checks.find((check) => check.label === "cli-agent-formula-draft")?.parsed?.actionDraft?.actionKey;
const agentFormulaKey = checks.find((check) => check.label === "cli-agent-formula-draft")?.parsed?.matched?.formula?.formulaKey;
if (agentFormulaDraftKey) {
  checks.push(run("cli-agent-confirm-formula-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentFormulaDraftKey]));
  checks.push(run("cli-agent-confirm-formula", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentFormulaDraftKey, "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-formula-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-formulas-after-confirm", "python", ["tools/bi_cli.py", "--json", "list-formulas", "--table", "orders", "--all"]));
  if (agentFormulaKey) {
    checks.push(run("cli-agent-query-formula-after-confirm", "python", ["tools/bi_cli.py", "--json", "query-metric", agentFormulaKey, "--group", "channel", "--limit", "5"]));
    checks.push(run("cli-agent-delete-formula-confirm", "python", ["tools/bi_cli.py", "--json", "delete-formula", agentFormulaKey, "--yes"]));
  }
}
const agentViewDraftKey = checks.find((check) => check.label === "cli-agent-view-draft")?.parsed?.actionDraft?.actionKey;
if (agentViewDraftKey) {
  checks.push(run("cli-agent-confirm-view-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentViewDraftKey]));
  checks.push(run("cli-agent-confirm-view", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentViewDraftKey, "--yes"]));
  const agentViewKey = checks.find((check) => check.label === "cli-agent-confirm-view")?.parsed?.savedView?.view_key;
  checks.push(run("cli-agent-action-drafts-after-view-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-views-after-confirm", "python", ["tools/bi_cli.py", "--json", "list-views", "--table", "orders"]));
  checks.push(run("cli-agent-navigation-after-view-confirm", "python", ["tools/bi_cli.py", "--json", "list-navigation"]));
  if (agentViewKey) {
    checks.push(run("cli-agent-query-view-after-confirm", "python", ["tools/bi_cli.py", "--json", "query-table", "--view", agentViewKey, "--limit", "5"]));
  }
}
const agentMetricDraftKey = checks.find((check) => check.label === "cli-agent-metric-draft")?.parsed?.actionDraft?.actionKey;
if (agentMetricDraftKey) {
  checks.push(run("cli-agent-confirm-metric-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentMetricDraftKey]));
  checks.push(run("cli-agent-confirm-metric", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentMetricDraftKey, "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-metric-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-metrics-after-confirm", "python", ["tools/bi_cli.py", "--json", "list-metrics", "--table", "orders", "--all"]));
}
const agentWidgetDraftKey = checks.find((check) => check.label === "cli-agent-widget-draft")?.parsed?.actionDraft?.actionKey;
if (agentWidgetDraftKey) {
  checks.push(run("cli-agent-confirm-widget-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentWidgetDraftKey]));
  checks.push(run("cli-agent-confirm-widget", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentWidgetDraftKey, "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-widget-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-dashboard-after-widget-confirm", "python", ["tools/bi_cli.py", "--json", "dashboards", "--dashboard", "default"]));
}
const agentDashboardFilterDraftKey = checks.find((check) => check.label === "cli-agent-dashboard-filter-draft")?.parsed?.actionDraft?.actionKey;
if (agentDashboardFilterDraftKey) {
  checks.push(run("cli-agent-confirm-dashboard-filter-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardFilterDraftKey]));
  checks.push(run("cli-agent-confirm-dashboard-filter", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentDashboardFilterDraftKey, "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-dashboard-filter-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-dashboard-filters-after-confirm", "python", ["tools/bi_cli.py", "--json", "list-filters", "--dashboard", "default"]));
}
const agentSemanticDraftKey = checks.find((check) => check.label === "cli-agent-semantic-draft")?.parsed?.actionDraft?.actionKey;
if (agentSemanticDraftKey) {
  checks.push(run("cli-agent-confirm-semantic-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentSemanticDraftKey]));
  checks.push(run("cli-agent-confirm-semantic", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentSemanticDraftKey, "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-semantic-confirm", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
  checks.push(run("cli-agent-semantics-after-confirm", "python", ["tools/bi_cli.py", "--json", "list-semantics", "--table", "orders"]));
}
const agentRejectDraft = run("cli-agent-dashboard-reject-draft", "python", ["tools/bi_cli.py", "--json", "ask", "请创建一个待拒绝的经营分析看板"]);
checks.push(agentRejectDraft);
const agentRejectDraftKey = agentRejectDraft.parsed?.actionDraft?.actionKey;
if (agentRejectDraftKey) {
  checks.push(run("cli-agent-reject-dashboard-dry-run", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentRejectDraftKey, "--reject"]));
  checks.push(run("cli-agent-reject-dashboard", "python", ["tools/bi_cli.py", "--json", "confirm-action", agentRejectDraftKey, "--reject", "--yes"]));
  checks.push(run("cli-agent-action-drafts-after-reject", "python", ["tools/bi_cli.py", "--json", "action-drafts", "--limit", "20"]));
}
checks.push(run("cli-quality-doctor", "python", ["tools/bi_cli.py", "--json", "quality-doctor"]));

const byLabel = Object.fromEntries(checks.map((check) => [check.label, check]));
const {
  bDashboardDrilldownSheetSource,
  bDashboardWidgetCardSource,
  bWidgetKitSource,
  bWidgetKitOverviewSource,
  biDashboardModelSource,
  biDashboardValueModelSource,
  biDashboardPresentationSource,
  biDashboardRuntimeSource,
  biDashboardWidgetFactorySource,
  bWidgetKitModelSource,
  dashboardCanvasSource,
  dashboardCanvasWidgetModelSource,
  dashboardCanvasSourceSwitchModelSource,
  dashboardCanvasReadinessModelSource,
  dashboardCanvasPlanModelSource,
  dashboardCanvasFilterModelSource,
  dashboardCanvasFieldModelSource,
  dashboardCanvasActionRunnerSource,
  dashboardCanvasActionsSource,
  dashboardCanvasStateSource,
  dashboardCanvasRelationshipModelSource,
  dashboardCanvasSourceSwitchViewModelSource,
  dashboardCanvasEditorOptionsSource,
  dashboardCanvasSummaryModelSource,
  dashboardCanvasViewModelSource,
  dashboardCanvasContractsSource,
  dashboardAdvancedWidgetWorkbenchSource,
  dashboardBusinessTaskStripSource,
  dashboardBeginnerEditorSource,
  dashboardModuleSavePanelSource,
  dashboardBusinessTemplatePanelSource,
  dashboardWidgetRecommendationPanelSource,
  dashboardSavedViewPanelSource,
  dashboardRelationshipRecommendationPanelSource,
  dashboardRelationshipWidgetPanelSource,
  dashboardWidgetManagePanelSource,
  dashboardWidgetEditorPanelSource,
  dashboardWidgetBasicFormSource,
  dashboardWidgetStylePanelSource,
  dashboardWidgetLocalFilterPanelSource,
  dashboardWidgetLifecyclePanelSource,
  dashboardPageAdminPanelSource,
  dashboardContractBoundaryPanelSource,
  dashboardFilterWorkbenchSource,
  dashboardOverviewStripSource,
  bWidgetModelSource,
  serverIndexSource,
  serverRuntimeSource,
  serverStaticSource,
  serverWorkspaceRoutesSource,
  serverDashboardRoutesSource,
  serverSourceRoutesSource,
  serverSettingsRoutesSource,
  serverModelRoutesSource,
  serverQueryRoutesSource,
  serverAgentRoutesSource,
  agentPromptRoutingSource,
  agentCommandDockSource,
  agentPanelSource,
  agentPanelModelSource,
  agentAnswerCardSource,
  agentCanAnswerPanelSource,
  agentContextPlanPanelSource,
  agentEvidenceAuditPanelsSource,
  agentPendingChangesPanelSource,
  agentPromptComposerSource,
  agentTaskPacketSource,
  evidenceViewSource,
  evidenceBusinessSummaryPanelSource,
  evidenceNumberExplainerPanelSource,
  evidenceViewModelSource,
  viewWorkspaceSource,
  viewAgentTaskStripSource,
  viewDashboardBridgePanelSource,
  viewSavedListPanelSource,
  viewWorkspaceModelSource,
  homeActionDockSource,
  homeDetailedPathPanelSource,
  homeOverviewSource,
  productActivationPanelSource,
  homeOverviewModelSource,
  safeValueSource,
  homeOperatingSummaryPanelSource,
  homeProductIntelligencePanelSource,
  homeScenarioPacksPanelSource,
  homeWorkspaceStartGuideSource,
  businessPathModelSource,
  businessPathBarSource,
  metricSemanticRepairActionsSource,
  inspectorPanelSource,
  inspectorPanelModelSource,
  apiSource,
  useQualityDoctorSource,
  apiAgentSource,
  apiClientSource,
  apiDashboardSource,
  apiModelSource,
  apiSettingsSource,
  apiSourceApiSource,
  apiViewsSource,
  apiWorkspaceSource,
  erpUnitLibraryViewModelSource,
  appSource,
  appSectionsSource,
  appLazyModulesSource,
  appWorkspaceModelSource,
  emptyWorkspaceDataSource,
  actionRecoveryModelSource,
  appAgentActionsSource,
  appDataActionsSource,
  appDashboardActionsSource,
  appSettingsActionsSource,
  appRefreshModelSource,
  defaultThemeDataSource,
  productIntelligenceModelSource,
  productActivationModelSource,
  workspaceFlowModelSource,
  metricRepairModelSource,
  packageJson,
  readmeSource,
  devScriptSource,
  verifyUiRealImportSource,
  verifyAAdversarialSource,
  indexHtmlSource,
  topBarSource,
  sourceWorkbenchSource,
  sourceWorkbenchConnectorControllerSource,
  sourceWorkbenchImportControllerSource,
  agentPromptGridSource,
  sourceWorkbenchAgentStarterSource,
  sourceWorkbenchActionPanelSource,
  sourceWorkbenchConnectorPanelSource,
  sourceWorkbenchDataManagementPanelSource,
  sourceWorkbenchDataEntryPanelSource,
  sourceWorkbenchFieldMetricPanelSource,
  sourceWorkbenchFieldSemanticPanelSource,
  sourceWorkbenchHeaderSource,
  sourceWorkbenchImportPanelSource,
  sourceWorkbenchMetricDefinitionPanelSource,
  sourceWorkbenchOperationsPanelSource,
  sourceWorkbenchQueryFormulaPanelSource,
  sourceWorkbenchRelationshipPanelSource,
  relationshipAutoModelGraphSource,
  relationshipAutoModelGraphModelSource,
  sourceWorkbenchContractsSource,
  sourceWorkbenchFieldMetricTypesSource,
  sourceWorkbenchGuidanceModelSource,
  sourceWorkbenchModelSource,
  sourceWorkbenchReceiptModelSource,
  sourceWorkbenchCommandModelSource,
  sourceIntelligenceRunModelSource,
  sourceWorkbenchDraftModelSource,
  sidebarSource,
  sidebarAssetSectionsSource,
  sidebarWorkspaceCardSource,
  settingsPanelSource,
  settingsAcceptanceEvidencePanelSource,
  settingsConfigPortabilityPanelSource,
  settingsSandboxBoundaryPanelSource,
  settingsThemePreferencePanelSource,
  stylesSource,
  typesSource,
  typesAgentSource,
  typesDashboardSource,
  typesDomainSource,
  typesQuerySource,
  typesSourceContractsSource,
  typesSourceIntelligenceSource,
  typesWorkspaceSource,
  themeSource,
  verifyFixturesSource,
  verifySource,
  verifyRuntimeSource,
  verifySourceCatalogSource,
  biCliSource,
  biCliContractsSource,
  biCliEnvelopeSource,
  biCliEvidenceBundlesSource,
  biCliContractDocSource,
  docsReadmeSource,
  productUxStandardDocSource,
  productAcceptanceMatrixDocSource,
  developmentRoadmapDocSource,
  prdDocSource,
  verifyBiCliAgentContractSource,
  agentActionConfirmationsSource,
  agentActionDraftStoreSource,
  agentConfirmExecutionHandlersSource,
  agentPromptResolutionSource,
  agentRecommendedCommandsSource,
  biCliCoreSource,
  businessDashboardServiceSource,
  erpDashboardUnitLibrarySource,
  configCommandServiceSource,
  connectorCommandServiceSource,
  importJobCommandServiceSource,
  importCommandServiceSource,
  importTableWriterServiceSource,
  relationshipCommandServiceSource,
  sourceManagementCommandServiceSource,
  dashboardModuleOrchestrationSource,
  dashboardWidgetContractsSource,
  dashboardWidgetOperationsSource,
  dashboardWidgetProposalServiceSource,
  dashboardWidgetCommandServiceSource,
  dashboardSaveTransactionsSource,
  sourceIntelligenceReceiptsSource,
  sourceIntelligenceRunStoreSource,
  sourceIntelligenceDashboardDraftsSource,
  semanticTextSource,
  sourceReadModelServiceSource,
  savedViewQueryServiceSource,
  metricFormulaCommandServiceSource,
  workspaceCommandServiceSource,
  preferencesThemeCommandServiceSource,
  implementationStatusSource,
} = readVerifySourceCatalog(root);
const sourceCoverageRuns = byLabel["cli-source-intelligence-runs-after-validation-input"].parsed?.sourceIntelligenceRuns ?? [];
const sourceCoverageAllRuns = byLabel["cli-source-intelligence-runs-after-validation-input-all"].parsed?.sourceIntelligenceRuns ?? [];
checks.push(
  {
    label: "native-bi-cli-agent-contract-boundary",
    ok: existsSync(join(root, "tools", "bi_cli_contracts.py")) &&
      existsSync(join(root, "tools", "bi_cli_envelope.py")) &&
      existsSync(join(root, "tools", "bi_cli_evidence_bundles.py")) &&
      existsSync(join(root, "scripts", "verify-bi-cli-agent-contract.mjs")) &&
      biCliSource.includes("from bi_cli_contracts import") &&
      biCliSource.includes("from bi_cli_envelope import enrich_cli_output, error_output") &&
      biCliSource.includes("from bi_cli_evidence_bundles import artifact_ref, write_evidence_bundle") &&
      biCliSource.includes("def cli_contract_command(") &&
      biCliSource.includes("def list_commands_command(") &&
      biCliContractsSource.includes("CONTRACT_SCHEMA_VERSION = \"aibi-bi-cli-contract/v1\"") &&
      biCliContractsSource.includes("def build_cli_contract(") &&
      biCliEnvelopeSource.includes("ENVELOPE_SCHEMA_VERSION = \"aibi-bi-cli-envelope/v1\"") &&
      biCliEnvelopeSource.includes("def enrich_cli_output(") &&
      biCliEvidenceBundlesSource.includes("EVIDENCE_BUNDLE_SCHEMA = \"aibi-evidence-bundle/v1\"") &&
      biCliEvidenceBundlesSource.includes("def write_evidence_bundle(") &&
      verifyBiCliAgentContractSource.includes("preview-import-evidence-bundle") &&
      biCliContractDocSource.includes("# BI CLI Contract") &&
      biCliContractDocSource.includes("`source-intelligence`") &&
      byLabel["cli-contract"].parsed?.contract?.schema === "aibi-bi-cli-contract/v1" &&
      byLabel["cli-contract"].parsed?.contract?.commandCount >= 70 &&
      byLabel["cli-contract-markdown-output"].parsed?.outputPath &&
      existsSync(byLabel["cli-contract-markdown-output"].parsed.outputPath) &&
      byLabel["cli-list-dashboard-write-commands"].parsed?.commands?.some((command) => command.name === "business-dashboard" && command.writesEvidence === true) &&
      byLabel["cli-status"].parsed?.envelope?.schema === "aibi-bi-cli-envelope/v1" &&
      byLabel["cli-status"].parsed?.artifacts?.some((artifact) => artifact.label === "database") &&
      byLabel["cli-preview-import"].parsed?.evidenceBundle?.schema === "aibi-evidence-bundle/v1" &&
      existsSync(byLabel["cli-preview-import"].parsed?.evidenceBundle?.manifestPath ?? "") &&
      byLabel["cli-business-dashboard-draft"].parsed?.requiresConfirmation === false &&
      byLabel["cli-business-dashboard-draft"].parsed?.evidenceBundle?.schema === "aibi-evidence-bundle/v1" &&
      byLabel["cli-source-intelligence-validation-inputs"].parsed?.evidenceBundle?.schema === "aibi-evidence-bundle/v1",
  },
  {
    label: "agent-prompt-resolution-boundary",
    ok: existsSync(join(root, "tools", "agent_prompt_resolution.py")) &&
      biCliSource.includes("from agent_prompt_resolution import (") &&
      !biCliSource.includes("def prompt_mentions_widget_add(") &&
      !biCliSource.includes("def prompt_mentions_dashboard_filter(") &&
      !biCliSource.includes("def prompt_mentions_view_save(") &&
      !biCliSource.includes("def dashboard_operation_from_prompt(") &&
      agentPromptResolutionSource.includes("class AgentPromptIntents") &&
      agentPromptResolutionSource.includes("def resolve_agent_prompt_intents(") &&
      agentPromptResolutionSource.includes("def select_agent_table(") &&
      agentPromptResolutionSource.includes("def should_create_agent_draft(") &&
      agentPromptResolutionSource.includes("def build_agent_action_payload(") &&
      agentPromptResolutionSource.includes("def agent_action_kind(") &&
      agentPromptResolutionSource.includes("def agent_action_evidence(") &&
      byLabel["cli-agent-widget-draft"].parsed?.actionDraft?.kind === "dashboard.widget.add" &&
      byLabel["cli-agent-dashboard-filter-draft"].parsed?.actionDraft?.kind === "dashboard.filter.add",
  },
  {
    label: "agent-action-confirmation-boundary",
    ok: existsSync(join(root, "tools", "agent_action_confirmations.py")) &&
      biCliSource.includes("from agent_action_confirmations import (") &&
      !biCliSource.includes("UPDATE action_drafts SET status = 'confirmed'") &&
      !biCliSource.includes("UPDATE action_drafts SET status = 'rejected'") &&
      !agentActionConfirmationsSource.includes("UPDATE action_drafts SET status") &&
      agentActionConfirmationsSource.includes("def confirm_dry_run_response(") &&
      agentActionConfirmationsSource.includes("def reject_dry_run_response(") &&
      agentActionConfirmationsSource.includes("from agent_action_draft_store import mark_action_confirmed, mark_action_rejected") &&
      agentActionConfirmationsSource.includes("def confirmed_response(") &&
      agentActionConfirmationsSource.includes("def rejected_response(") &&
      byLabel["cli-agent-confirm-widget"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-filter"].parsed?.confirmed === true &&
      byLabel["cli-agent-reject-dashboard"].parsed?.decision === "reject",
  },
  {
    label: "agent-action-draft-store-boundary",
    ok: existsSync(join(root, "tools", "agent_action_draft_store.py")) &&
      biCliSource.includes("from agent_action_draft_store import") &&
      biCliSource.includes("create_action_draft(") &&
      biCliSource.includes("get_action_draft(") &&
      biCliSource.includes("list_action_drafts(") &&
      biCliSource.includes("count_pending_action_drafts(") &&
      biCliSource.includes("action_draft_payload(") &&
      !biCliSource.includes("INSERT INTO action_drafts(action_key, workspace_id, kind, label, status, payload_json, evidence_json, created_at)") &&
      !biCliSource.includes("SELECT * FROM action_drafts") &&
      !biCliSource.includes("SELECT COUNT(*) FROM action_drafts WHERE status = 'draft'") &&
      agentActionDraftStoreSource.includes("def create_action_draft(") &&
      agentActionDraftStoreSource.includes("def get_action_draft(") &&
      agentActionDraftStoreSource.includes("def action_draft_payload(") &&
      agentActionDraftStoreSource.includes("def list_action_drafts(") &&
      agentActionDraftStoreSource.includes("def count_pending_action_drafts(") &&
      agentActionDraftStoreSource.includes("def mark_action_confirmed(") &&
      agentActionDraftStoreSource.includes("def mark_action_rejected(") &&
      byLabel["cli-agent-widget-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-source-dashboard-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-action-drafts-after-widget-confirm"].parsed?.pendingCount >= 0 &&
      byLabel["cli-source-dashboard-action-drafts-after-confirm"].parsed?.pendingCount >= 0,
  },
  {
    label: "agent-confirm-execution-handlers-phase1-boundary",
    ok: existsSync(join(root, "tools", "agent_confirm_execution_handlers.py")) &&
      biCliSource.includes("from agent_confirm_execution_handlers import (") &&
      biCliSource.includes("return handle_index_create_confirmation(") &&
      biCliSource.includes("return handle_relationship_save_confirmation(") &&
      biCliSource.includes("return handle_import_commit_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_index_create_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_relationship_save_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_import_commit_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("build_index_plan: Callable") &&
      agentConfirmExecutionHandlersSource.includes("build_relationship_save_plan: Callable") &&
      agentConfirmExecutionHandlersSource.includes("build_import_preview: Callable") &&
      byLabel["cli-agent-confirm-index"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-relationship"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-import"].parsed?.confirmed === true,
  },
  {
    label: "agent-confirm-execution-handlers-phase2-boundary",
    ok: existsSync(join(root, "tools", "agent_confirm_execution_handlers.py")) &&
      biCliSource.includes("return handle_formula_save_confirmation(") &&
      biCliSource.includes("return handle_view_save_confirmation(") &&
      biCliSource.includes("return handle_metric_add_confirmation(") &&
      biCliSource.includes("return handle_semantic_set_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_formula_save_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_view_save_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_metric_add_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_semantic_set_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("build_formula_save_plan: Callable") &&
      agentConfirmExecutionHandlersSource.includes("build_save_view_plan: Callable") &&
      agentConfirmExecutionHandlersSource.includes("build_metric_add_plan: Callable") &&
      agentConfirmExecutionHandlersSource.includes("build_semantic_set_plan: Callable") &&
      byLabel["cli-agent-confirm-formula"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-view"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-metric"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-semantic"].parsed?.confirmed === true,
  },
  {
    label: "agent-confirm-execution-handlers-phase3-boundary",
    ok: existsSync(join(root, "tools", "agent_confirm_execution_handlers.py")) &&
      biCliSource.includes("return handle_dashboard_widget_add_confirmation(") &&
      biCliSource.includes("return handle_dashboard_filter_add_confirmation(") &&
      biCliSource.includes("return handle_dashboard_operation_confirmation(") &&
      biCliSource.includes("return handle_dashboard_create_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_dashboard_widget_add_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_dashboard_filter_add_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_dashboard_operation_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("def handle_dashboard_create_confirmation(") &&
      agentConfirmExecutionHandlersSource.includes("build_widget_proposal: Callable") &&
      agentConfirmExecutionHandlersSource.includes("build_dashboard_filter_add_plan: Callable") &&
      agentConfirmExecutionHandlersSource.includes("build_dashboard_operation_plan: Callable") &&
      agentConfirmExecutionHandlersSource.includes("build_agent_dashboard_create_draft: Callable") &&
      byLabel["cli-agent-confirm-widget"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-filter"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-copy"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-rename"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-delete"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard"].parsed?.confirmed === true,
  },
  {
    label: "agent-recommended-commands-boundary",
    ok: existsSync(join(root, "tools", "agent_recommended_commands.py")) &&
      biCliSource.includes("from agent_recommended_commands import build_agent_recommended_commands") &&
      biCliSource.includes("recommended = build_agent_recommended_commands(") &&
      !biCliSource.includes("recommended.append(") &&
      agentRecommendedCommandsSource.includes("def build_agent_recommended_commands(") &&
      agentRecommendedCommandsSource.includes("python tools/bi_cli.py --json status") &&
      agentRecommendedCommandsSource.includes("python tools/bi_cli.py --json add-widget") &&
      agentRecommendedCommandsSource.includes("python tools/bi_cli.py --json add-filter") &&
      agentRecommendedCommandsSource.includes("python tools/bi_cli.py --json save-view") &&
      byLabel["cli-agent-widget-draft"].parsed?.recommendedCommands?.some((command) => command.includes("add-widget")) &&
      byLabel["cli-agent-dashboard-filter-draft"].parsed?.recommendedCommands?.some((command) => command.includes("add-filter")) &&
      readOnlyAgentCheck.parsed?.recommendedCommands?.some((command) => command.includes("--json query")),
  },
  {
    label: "saved-view-query-service-boundary",
    ok: existsSync(join(root, "tools", "saved_view_query_service.py")) &&
      biCliSource.includes("from saved_view_query_service import (") &&
      biCliSource.includes("query_table_command_service(") &&
      biCliSource.includes("save_view_command_service(") &&
      biCliSource.includes("copy_view_command_service(") &&
      biCliSource.includes("delete_view_command_service(") &&
      biCliSource.includes("build_save_view_plan_service(") &&
      biCliSource.includes("execute_save_view_plan_service(") &&
      !biCliSource.includes("def table_query_payload_from_args(") &&
      !biCliSource.includes("def view_row_to_dict(") &&
      !biCliSource.includes("SELECT * FROM saved_views WHERE view_key = ? AND table_key = ? AND workspace_id = ?") &&
      !biCliSource.includes("DELETE FROM saved_views WHERE view_key = ? AND workspace_id = ?") &&
      savedViewQueryServiceSource.includes("def table_query_payload_from_args(") &&
      savedViewQueryServiceSource.includes("def query_table_command(") &&
      savedViewQueryServiceSource.includes("def build_save_view_plan(") &&
      savedViewQueryServiceSource.includes("def execute_save_view_plan(") &&
      savedViewQueryServiceSource.includes("def copy_view_command(") &&
      savedViewQueryServiceSource.includes("def delete_view_command(") &&
      byLabel["cli-save-view-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-save-view-confirm"].parsed?.confirmed === true,
  },
  {
    label: "metric-formula-command-service-boundary",
    ok: existsSync(join(root, "tools", "metric_formula_command_service.py")) &&
      biCliSource.includes("from metric_formula_command_service import (") &&
      biCliSource.includes("add_metric_command_service(") &&
      biCliSource.includes("query_metric_command_service(") &&
      biCliSource.includes("formula_preview_command_service(") &&
      biCliSource.includes("save_formula_command_service(") &&
      biCliSource.includes("delete_formula_command_service(") &&
      metricFormulaCommandServiceSource.includes("def add_metric_command(") &&
      metricFormulaCommandServiceSource.includes("def query_metric_command(") &&
      metricFormulaCommandServiceSource.includes("def formula_preview_command(") &&
      metricFormulaCommandServiceSource.includes("def save_formula_command(") &&
      metricFormulaCommandServiceSource.includes("def delete_formula_command(") &&
      metricFormulaCommandServiceSource.includes("def metric_key_for(") &&
      metricFormulaCommandServiceSource.includes("def metric_row_to_payload(") &&
      metricFormulaCommandServiceSource.includes("def upsert_metric_definition(") &&
      metricFormulaCommandServiceSource.includes("def build_metric_add_plan(") &&
      metricFormulaCommandServiceSource.includes("def formula_key_for(") &&
      metricFormulaCommandServiceSource.includes("def calculated_field_row_to_payload(") &&
      metricFormulaCommandServiceSource.includes("def calculated_field_usage(") &&
      metricFormulaCommandServiceSource.includes("def compile_formula_for_table(") &&
      metricFormulaCommandServiceSource.includes("def build_formula_save_plan(") &&
      metricFormulaCommandServiceSource.includes("def execute_formula_save_plan(") &&
      metricFormulaCommandServiceSource.includes("def build_formula_metric_query(") &&
      !biCliSource.includes("INSERT INTO metric_definitions(") &&
      !biCliSource.includes("INSERT INTO calculated_fields(") &&
      !biCliSource.includes("\"sqlite-formula-metric\"") &&
      byLabel["cli-add-metric-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-query-metric"].parsed?.tableQuery?.rows?.some((row) => row.channel === "Douyin" && Number(row.sum_net_sales) === 3440) &&
      byLabel["cli-formula-preview"].parsed?.compiledSql?.includes("CASE WHEN") &&
      byLabel["cli-save-formula-confirm"].parsed?.confirmed === true &&
      byLabel["cli-delete-formula-confirm"].parsed?.confirmed === true,
  },
  {
    label: "connector-command-service-boundary",
    ok: existsSync(join(root, "tools", "connector_command_service.py")) &&
      biCliSource.includes("from connector_command_service import (") &&
      biCliSource.includes("list_connectors_command_service(") &&
      biCliSource.includes("save_connector_command_service(") &&
      biCliSource.includes("sync_connector_command_service(") &&
      biCliSource.includes("remove_connector_command_service(") &&
      connectorCommandServiceSource.includes("VALID_CONNECTOR_TYPES") &&
      connectorCommandServiceSource.includes("def connector_row_to_dict(") &&
      connectorCommandServiceSource.includes("def load_connectors(") &&
      connectorCommandServiceSource.includes("def connector_by_key_or_name(") &&
      connectorCommandServiceSource.includes("def list_connectors_command(") &&
      connectorCommandServiceSource.includes("def save_connector_command(") &&
      connectorCommandServiceSource.includes("def sync_connector_command(") &&
      connectorCommandServiceSource.includes("def remove_connector_command(") &&
      connectorCommandServiceSource.includes("INSERT OR REPLACE INTO data_connectors(") &&
      connectorCommandServiceSource.includes("DELETE FROM data_connectors WHERE connector_key = ?") &&
      connectorCommandServiceSource.includes("last_sync_status = 'blocked'") &&
      connectorCommandServiceSource.includes("last_sync_status = 'success'") &&
      !biCliSource.includes("INSERT OR REPLACE INTO data_connectors(") &&
      !biCliSource.includes("DELETE FROM data_connectors WHERE connector_key = ?") &&
      byLabel["cli-save-connector-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-save-connector-confirm"].parsed?.confirmed === true &&
      byLabel["cli-sync-connector-confirm"].parsed?.connectorSync?.importResult?.tableKey === "orders" &&
      byLabel["cli-sync-external-connector-blocked"].parsed?.blocked === true &&
      byLabel["cli-remove-connector-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "import-job-command-service-boundary",
    ok: existsSync(join(root, "tools", "import_job_command_service.py")) &&
      biCliSource.includes("from import_job_command_service import (") &&
      biCliSource.includes("set_import_policy_command_service(") &&
      biCliSource.includes("list_import_jobs_command_service(") &&
      biCliSource.includes("remove_import_job_command_service(") &&
      importJobCommandServiceSource.includes("def set_import_policy_command(") &&
      importJobCommandServiceSource.includes("def list_import_jobs_command(") &&
      importJobCommandServiceSource.includes("def remove_import_job_command(") &&
      importJobCommandServiceSource.includes("INSERT OR REPLACE INTO import_policies(table_key, workspace_id, unique_fields_json, conflict_rule, updated_at)") &&
      importJobCommandServiceSource.includes("DELETE FROM import_jobs WHERE job_key = ? AND workspace_id = ?") &&
      !biCliSource.includes("INSERT OR REPLACE INTO import_policies(table_key, workspace_id, unique_fields_json, conflict_rule, updated_at)") &&
      !biCliSource.includes("DELETE FROM import_jobs WHERE job_key = ? AND workspace_id = ?") &&
      byLabel["cli-set-import-policy-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-set-import-policy-confirm"].parsed?.confirmed === true &&
      byLabel["cli-list-import-jobs"].parsed?.importJobs?.some((job) => job.table_key === "orders" && job.status === "success") &&
      byLabel["cli-remove-import-job-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "import-command-service-boundary",
    ok: existsSync(join(root, "tools", "import_command_service.py")) &&
      biCliSource.includes("from import_command_service import (") &&
      biCliSource.includes("build_import_preview_service(") &&
      biCliSource.includes("preview_import_command_service(") &&
      biCliSource.includes("execute_import_commit_service(") &&
      biCliSource.includes("import_commit_command_service(") &&
      importCommandServiceSource.includes("def build_import_preview(") &&
      importCommandServiceSource.includes("def preview_import_command(") &&
      importCommandServiceSource.includes("def build_folder_import_plan(") &&
      importCommandServiceSource.includes("def preview_import_folder_command(") &&
      importCommandServiceSource.includes("def import_folder_command(") &&
      importCommandServiceSource.includes("def execute_import_commit(") &&
      importCommandServiceSource.includes("def import_commit_command(") &&
      importCommandServiceSource.includes("\"matchType\": \"exactOrder\"") &&
      importCommandServiceSource.includes("\"sourcePipelineContract\": source_pipeline_contract()") &&
      importCommandServiceSource.includes("\"mergePolicyPreview\"") &&
      importCommandServiceSource.includes("merge_import_into_table(") &&
      importCommandServiceSource.includes("import_csv_as_table(") &&
      importCommandServiceSource.includes("upsert_navigation_module(") &&
      importCommandServiceSource.includes("recommendedCommand") &&
      !biCliSource.includes("\"matchType\": \"exactOrder\"") &&
      byLabel["cli-preview-import"].parsed?.sourcePipelineContract?.stages?.length > 0 &&
      byLabel["cli-preview-import"].parsed?.mergePolicyPreview?.mergePlan?.incomingRows &&
      byLabel["cli-preview-import-folder"].parsed?.fileCount >= 2 &&
      byLabel["cli-preview-import-folder"].parsed?.tableCount >= 2 &&
      byLabel["cli-preview-import-folder"].parsed?.items?.length === byLabel["cli-preview-import-folder"].parsed?.fileCount &&
      byLabel["cli-preview-import-folder"].parsed?.groups?.length === byLabel["cli-preview-import-folder"].parsed?.tableCount &&
      byLabel["cli-import-folder-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-import-folder-dry-run"].parsed?.willWrite === false &&
      byLabel["cli-import-delete-source-validation-input"].parsed?.committed === true &&
      byLabel["cli-import-delete-source-validation-input"].parsed?.result?.tableKey === "verify_delete_source" &&
      byLabel["cli-agent-confirm-import"].parsed?.confirmed === true,
  },
  {
    label: "import-table-writer-service-boundary",
    ok: existsSync(join(root, "tools", "import_table_writer_service.py")) &&
      biCliSource.includes("from import_table_writer_service import (") &&
      biCliSource.includes("import_csv_as_table_service(") &&
      biCliSource.includes("merge_import_into_table_service(") &&
      biCliSource.includes("update_table_metadata_after_write_service(") &&
      biCliSource.includes("create_metrics_for_profile_service(") &&
      importTableWriterServiceSource.includes("def import_csv_as_table(") &&
      importTableWriterServiceSource.includes("def merge_import_into_table(") &&
      importTableWriterServiceSource.includes("def update_table_metadata_after_write(") &&
      importTableWriterServiceSource.includes("def create_metrics_for_profile(") &&
      importTableWriterServiceSource.includes("def should_create_metric_for_measure(") &&
      importTableWriterServiceSource.includes("def default_metric_dimension(") &&
      importTableWriterServiceSource.includes('not text.startswith("__")') &&
      importTableWriterServiceSource.includes("CREATE TABLE") &&
      importTableWriterServiceSource.includes("INSERT OR REPLACE INTO table_registry(") &&
      importTableWriterServiceSource.includes("INSERT OR REPLACE INTO source_runs(") &&
      importTableWriterServiceSource.includes("INSERT OR REPLACE INTO field_semantics(") &&
      importTableWriterServiceSource.includes("INSERT OR REPLACE INTO import_jobs(") &&
      importTableWriterServiceSource.includes("existing_rows_by_unique_key(") &&
      importTableWriterServiceSource.includes("\"writeSummary\"") &&
      importTableWriterServiceSource.includes("导入文件字段与目标表不匹配") &&
      byLabel["cli-import-delete-source-validation-input"].parsed?.committed === true &&
      byLabel["cli-import-delete-source-validation-input"].parsed?.result?.sourceRunId &&
      byLabel["cli-sync-connector-confirm"].parsed?.connectorSync?.importResult?.writeSummary?.rowCountAfter === 10 &&
      byLabel["cli-agent-confirm-import"].parsed?.importResult?.sourceRunId,
  },
  {
    label: "ui-real-import-folder-flow",
    ok: verifyUiRealImportSource.includes("const importFolder =") &&
      verifyUiRealImportSource.includes("const importTarget = existsSync(importFolder)") &&
      verifyUiRealImportSource.includes('data-testid="folder-import-preview-button"') &&
      verifyUiRealImportSource.includes('data-testid="folder-import-plan"') &&
      verifyUiRealImportSource.includes('data-testid="folder-import-confirm-button"') &&
      apiSourceApiSource.includes("function normalizeFolderImportPlan(") &&
      apiSourceApiSource.includes("Array.isArray(plan.groups) ? plan.groups : []") &&
      verifyUiRealImportSource.includes("api-folder-import-real-tables-merged") &&
      verifyUiRealImportSource.includes('rowCountsByName["保单明细"] === 426') &&
      verifyUiRealImportSource.includes('rowCountsByName["售后单"] === 1393') &&
      verifyUiRealImportSource.includes('rowCountsByName["订单"] === 2351') &&
      verifyUiRealImportSource.includes('rowCountsByName["资金"] === 1376') &&
      productAcceptanceMatrixDocSource.includes("real local folder when present or a real file as fallback") &&
      implementationStatusSource.includes("real folder import loop with file fallback"),
  },
  {
    label: "relationship-command-service-boundary",
    ok: existsSync(join(root, "tools", "relationship_command_service.py")) &&
      biCliSource.includes("from relationship_command_service import (") &&
      biCliSource.includes("list_relationships_command_service(") &&
      biCliSource.includes("query_relationship_command_service(") &&
      biCliSource.includes("relationship_preview_command_service(") &&
      biCliSource.includes("relationship_save_command_service(") &&
      biCliSource.includes("remove_relationship_command_service(") &&
      relationshipCommandServiceSource.includes("def list_relationships_command(") &&
      relationshipCommandServiceSource.includes("def normalize_relation_field_name(") &&
      relationshipCommandServiceSource.includes("def relation_candidate_fields(") &&
      relationshipCommandServiceSource.includes("def relationship_name_score(") &&
      relationshipCommandServiceSource.includes("def sample_field_values(") &&
      relationshipCommandServiceSource.includes("def saved_relationship_signatures(") &&
      relationshipCommandServiceSource.includes("def recommend_relationships_for_connection(") &&
      relationshipCommandServiceSource.includes("def recommend_relationships_command(") &&
      relationshipCommandServiceSource.includes("def resolve_relationship_query_inputs(") &&
      relationshipCommandServiceSource.includes("def parse_relationship_filter(") &&
      relationshipCommandServiceSource.includes("def relationship_rows_for_chart(") &&
      relationshipCommandServiceSource.includes("def query_relationship_command(") &&
      relationshipCommandServiceSource.includes("def remove_relationship_command(") &&
      relationshipCommandServiceSource.includes("def relationship_preview_command(") &&
      relationshipCommandServiceSource.includes("def build_relationship_save_plan(") &&
      relationshipCommandServiceSource.includes("def execute_relationship_save(") &&
      relationshipCommandServiceSource.includes("def relationship_save_command(") &&
      relationshipCommandServiceSource.includes("INSERT OR REPLACE INTO relationships(relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at)") &&
      relationshipCommandServiceSource.includes("DELETE FROM relationships WHERE relation_key = ? AND workspace_id = ?") &&
      relationshipCommandServiceSource.includes("relationship whitelist join") &&
      relationshipCommandServiceSource.includes("sample-overlap:") &&
      relationshipCommandServiceSource.includes("shared-business-token:") &&
      relationshipCommandServiceSource.includes("actual_confidence < 0.55") &&
      relationshipCommandServiceSource.includes("min_distinct_keys < 3") &&
      relationshipCommandServiceSource.includes("join_multiplier > 5") &&
      biCliSource.includes("recommend_relationships_for_connection_service(") &&
      biCliSource.includes("recommend_relationships_command_service(") &&
      !biCliSource.includes("INSERT OR REPLACE INTO relationships(relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at)") &&
      !biCliSource.includes("DELETE FROM relationships WHERE relation_key = ? AND workspace_id = ?") &&
      !biCliSource.includes("sample-overlap:") &&
      !biCliSource.includes("shared-business-token:") &&
      byLabel["cli-relationship-preview"].parsed?.relationshipPreview?.metrics?.confidence >= 0.8 &&
      byLabel["cli-relationship-save-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-list-relationships"].parsed?.relationships?.some((relationship) => relationship.relation_key === "orders_refunds_order_id_order_id") &&
      byLabel["cli-query-relationship"].parsed?.relationshipQuery?.joinType === "left" &&
      byLabel["cli-remove-relationship-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "source-evidence-engine-renamed",
    ok: existsSync(join(root, "tools", "evidence_profile_runtime", "table_reading.py")) &&
      existsSync(join(root, "tools", "source_evidence_engine.py")) &&
      !existsSync(join(root, "tools", "source_intelligence")) &&
      !existsSync(join(root, "tools", "profile_generic_sources_duckdb.py")),
  },
  {
    label: "semantic-inference-production-guards",
    ok: biCliSource.includes("field == \"__canonical_date\"") &&
      biCliSource.includes("field.startswith(\"__source_\")") &&
      biCliSource.includes("\"filterable,no-groupable\"") &&
      biCliSource.includes("\"联系方式\"") &&
      biCliSource.includes("\"流水号\"") &&
      biCliSource.includes("\"分成\"") &&
      biCliSource.includes('str(field["field_name"]).startswith("__")') &&
      biCliSource.includes("def cleanup_stale_auto_metrics(") &&
      biCliSource.includes("removedStaleAutoMetrics") &&
      biCliSource.includes("source = 'auto'") &&
      biCliSource.includes("substr(measure, 1, 2) = '__'") &&
      biCliSource.includes('not str(field["field_name"]).startswith("__")') &&
      biCliSource.includes("not str(field).startswith(\"__\")") &&
      semanticTextSource.includes("\"contact_phone\"") &&
      semanticTextSource.includes("\"source_metadata\"") &&
      semanticTextSource.includes("ATTRIBUTE_SEMANTICS") &&
      semanticTextSource.includes("semantic.startswith(\"field_\") and inferred_type == \"number\" and unique_ratio > 0.75"),
  },
  {
    label: "source-intelligence-receipts-boundary",
    ok: existsSync(join(root, "tools", "evidence_receipts.py")) &&
      biCliSource.includes("from evidence_receipts import (") &&
      !biCliSource.includes("def build_source_intelligence_dashboard_candidate(") &&
      !biCliSource.includes("def source_intelligence_file_coverage(") &&
      !biCliSource.includes("def dashboard_chart_type_for_result(") &&
      sourceIntelligenceReceiptsSource.includes("def build_source_intelligence_dashboard_candidate(") &&
      sourceIntelligenceReceiptsSource.includes("def source_intelligence_file_coverage(") &&
      sourceIntelligenceReceiptsSource.includes("source-intelligence-receipts") &&
      sourceIntelligenceReceiptsSource.includes("metric-query-results.json") &&
      sourceIntelligenceReceiptsSource.includes("metric-sql-compiler.json"),
  },
  {
    label: "source-intelligence-run-store-boundary",
    ok: existsSync(join(root, "tools", "evidence_run_store.py")) &&
      biCliSource.includes("from evidence_run_store import (") &&
      biCliSource.includes("save_source_intelligence_run(") &&
      biCliSource.includes("list_source_intelligence_runs(") &&
      biCliSource.includes("include_internal=args.all") &&
      biCliSource.includes('source_intelligence_runs.add_argument("--all", action="store_true")') &&
      biCliSource.includes("count_source_intelligence_runs(") &&
      biCliSource.includes("latest_source_intelligence_summary(") &&
      biCliSource.includes("latest_source_intelligence_run(") &&
      biCliSource.includes("source_intelligence_run_manifest(") &&
      !biCliSource.includes("INSERT INTO source_intelligence_runs(") &&
      !biCliSource.includes("FROM source_intelligence_runs\n") &&
      sourceIntelligenceRunStoreSource.includes("def save_source_intelligence_run(") &&
      sourceIntelligenceRunStoreSource.includes("def list_source_intelligence_runs(") &&
      sourceIntelligenceRunStoreSource.includes("include_internal: bool = False") &&
      sourceIntelligenceRunStoreSource.includes('item["isInternal"] = internal_source_intelligence_run(item)') &&
      sourceIntelligenceRunStoreSource.includes("business_runs = [item for item in runs if not item[\"isInternal\"]]") &&
      sourceIntelligenceRunStoreSource.includes("def get_source_intelligence_run(") &&
      sourceIntelligenceRunStoreSource.includes("def latest_source_intelligence_run(") &&
      sourceIntelligenceRunStoreSource.includes("def latest_source_intelligence_run(connection: sqlite3.Connection, *, workspace_id: str, include_internal: bool = False)") &&
      sourceIntelligenceRunStoreSource.includes("return next((row for row in rows if not internal_source_intelligence_run(dict(row))), rows[0])") &&
      sourceIntelligenceRunStoreSource.includes("def latest_source_intelligence_summary(") &&
      sourceIntelligenceRunStoreSource.includes("include_internal: bool = False") &&
      sourceIntelligenceRunStoreSource.includes("def internal_source_intelligence_run(") &&
      sourceIntelligenceRunStoreSource.includes("manifestInputRoots") &&
      sourceIntelligenceRunStoreSource.includes("LIMIT 200") &&
      sourceIntelligenceRunStoreSource.includes("def source_intelligence_run_manifest(") &&
      sourceIntelligenceRunStoreSource.includes("def count_source_intelligence_runs(") &&
      byLabel["cli-source-intelligence-validation-inputs"].parsed?.runKey &&
      byLabel["cli-source-intelligence-runs-after-validation-input"].parsed?.sourceIntelligenceRuns?.some((run) =>
        run.run_key === byLabel["cli-source-intelligence-validation-inputs"].parsed?.runKey &&
        run.fileCoverage?.dashboardCandidate?.source === "source-intelligence-receipts"
      ),
  },
  {
    label: "source-intelligence-dashboard-draft-action-boundary",
    ok: byLabel["cli-source-dashboard-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-source-dashboard-draft"].parsed?.actionDraft?.kind === "dashboard.create" &&
      byLabel["cli-source-dashboard-draft"].parsed?.source === "source-intelligence-dashboard-candidate" &&
      byLabel["cli-source-dashboard-draft"].parsed?.dashboardDraft?.source === "source-intelligence-dashboard-candidate" &&
      byLabel["cli-source-dashboard-draft"].parsed?.dashboardDraft?.widgets?.length >= 2 &&
      byLabel["cli-source-dashboard-draft"].parsed?.dashboardDraft?.widgets?.every((widget) =>
        widget.type === "text" &&
        widget.sourceRunKey &&
        widget.evidenceRefs?.some((ref) => String(ref).startsWith("source-intelligence:"))
      ) &&
      byLabel["cli-source-dashboard-confirm-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-source-dashboard-confirm-dry-run"].parsed?.dashboardDraft?.source === "source-intelligence-dashboard-candidate" &&
      byLabel["cli-source-dashboard-confirm"].parsed?.confirmed === true &&
      byLabel["cli-source-dashboard-after-confirm"].parsed?.dashboards?.some((dashboard) =>
        dashboard.dashboard_key === byLabel["cli-source-dashboard-confirm"].parsed?.createdDashboardKey &&
        dashboard.widgets?.some((widget) =>
          widget.widget_type === "text" &&
          widget.config?.sourceRunKey === byLabel["cli-source-dashboard-draft"].parsed?.sourceRunKey &&
          widget.config?.evidenceRefs?.some((ref) => String(ref).startsWith("source-intelligence:"))
        )
      ) &&
      !byLabel["cli-source-dashboard-action-drafts-after-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-source-dashboard-draft"].parsed?.actionDraft?.actionKey
      ) &&
      biCliSource.includes("def source_intelligence_dashboard_draft_command(") &&
      biCliSource.includes("from evidence_dashboard_drafts import build_source_intelligence_dashboard_draft") &&
      !biCliSource.includes("def build_source_intelligence_dashboard_draft(") &&
      !biCliSource.includes("def source_intelligence_dashboard_text(") &&
      sourceIntelligenceDashboardDraftsSource.includes("def build_source_intelligence_dashboard_draft(") &&
      sourceIntelligenceDashboardDraftsSource.includes("def source_intelligence_dashboard_text(") &&
      sourceIntelligenceDashboardDraftsSource.includes("preferred_table_key: Callable") &&
      sourceIntelligenceDashboardDraftsSource.includes("template_widget_layout: Callable") &&
      biCliSource.includes('source_dashboard_draft = sub.add_parser("source-dashboard-draft")') &&
      serverSourceRoutesSource.includes("/api/source-intelligence/dashboard-draft") &&
      apiSourceApiSource.includes("createSourceDashboardDraft") &&
      appSource.includes("handleSourceDashboardDraft") &&
      appDataActionsSource.includes("const handleSourceDashboardDraft = useCallback") &&
      !homeOverviewSource.includes("onSourceDashboardDraft({") &&
      dashboardWidgetContractsSource.includes('"sourceRunKey"') &&
      dashboardModuleOrchestrationSource.includes('("sourceRunKey", "sourceRunKey")'),
  },
  {
    label: "dashboard-widget-contract-boundary",
    ok: existsSync(join(root, "tools", "dashboard_widget_contracts.py")) &&
      biCliSource.includes("from dashboard_widget_contracts import (") &&
      !biCliSource.includes("def widget_config_from_options(") &&
      !biCliSource.includes("def widget_style_options_from_args(") &&
      !biCliSource.includes("B_DASHBOARD_WIDGET_CATALOG = [") &&
      dashboardWidgetContractsSource.includes("B_DASHBOARD_WIDGET_CATALOG = [") &&
      dashboardWidgetContractsSource.includes("def build_dashboard_widget_catalog_payload(") &&
      dashboardWidgetContractsSource.includes("def widget_config_from_options(") &&
      dashboardWidgetContractsSource.includes("def widget_style_options_from_args(") &&
      dashboardWidgetContractsSource.includes("B_WIDGET_TYPES") &&
      dashboardWidgetContractsSource.includes("B_DASHBOARD_FILTER_OPERATORS"),
  },
  {
    label: "dashboard-widget-write-primitive-boundary",
    ok: existsSync(join(root, "tools", "dashboard_widget_operations.py")) &&
      biCliSource.includes("from dashboard_widget_operations import (") &&
      !biCliSource.includes("def insert_dashboard_widget(") &&
      dashboardWidgetOperationsSource.includes("def dashboard_widget_key_exists(") &&
      dashboardWidgetOperationsSource.includes("def resolve_dashboard_widget_key(") &&
      dashboardWidgetOperationsSource.includes("def next_dashboard_widget_sort_order(") &&
      dashboardWidgetOperationsSource.includes("def insert_dashboard_widget(") &&
      dashboardWidgetOperationsSource.includes("Dashboard widget insert requires workspace_id") &&
      byLabel["cli-save-dashboard-modules-dry-run"].parsed?.proposedWidgets?.every((widget) => widget.workspace_id),
  },
  {
    label: "dashboard-widget-proposal-service-boundary",
    ok: existsSync(join(root, "tools", "dashboard_widget_proposal_service.py")) &&
      biCliSource.includes("from dashboard_widget_proposal_service import (") &&
      biCliSource.includes("build_dashboard_widget_proposal_service(") &&
      biCliSource.includes("build_dashboard_relationship_widget_proposal_service(") &&
      !biCliSource.includes("raise ValueError(f\"Unsupported widget type: {widget_type}\")") &&
      !biCliSource.includes("raise ValueError(f\"Unsupported relationship widget type: {widget_type}\")") &&
      !biCliSource.includes("Relationship references an unavailable table.") &&
      dashboardWidgetProposalServiceSource.includes("def build_dashboard_widget_proposal(") &&
      dashboardWidgetProposalServiceSource.includes("def build_dashboard_relationship_widget_proposal(") &&
      dashboardWidgetProposalServiceSource.includes("widget_config_from_options") &&
      dashboardWidgetProposalServiceSource.includes("resolve_dashboard_widget_key") &&
      dashboardWidgetProposalServiceSource.includes("next_dashboard_widget_sort_order") &&
      byLabel["cli-add-widget-view-dry-run"].parsed?.proposedWidget?.config?.dataMode === "view" &&
      byLabel["cli-add-relationship-widget-dry-run"].parsed?.proposedWidget?.config?.dataMode === "relationship",
  },
  {
    label: "dashboard-widget-command-service-boundary",
    ok: existsSync(join(root, "tools", "dashboard_widget_command_service.py")) &&
      biCliSource.includes("from dashboard_widget_command_service import (") &&
      biCliSource.includes("add_recommended_dashboard_widgets_service(") &&
      biCliSource.includes("add_dashboard_widget_service(") &&
      biCliSource.includes("add_dashboard_relationship_widget_service(") &&
      biCliSource.includes("set_dashboard_widget_service(") &&
      biCliSource.includes("copy_dashboard_widget_service(") &&
      biCliSource.includes("remove_dashboard_widget_service(") &&
      !biCliSource.includes("same type/title/source already exists") &&
      !biCliSource.includes("SELECT * FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?") &&
      dashboardWidgetCommandServiceSource.includes("def add_recommended_dashboard_widgets(") &&
      dashboardWidgetCommandServiceSource.includes("def add_dashboard_widget(") &&
      dashboardWidgetCommandServiceSource.includes("def add_dashboard_relationship_widget(") &&
      dashboardWidgetCommandServiceSource.includes("def set_dashboard_widget(") &&
      dashboardWidgetCommandServiceSource.includes("def copy_dashboard_widget(") &&
      dashboardWidgetCommandServiceSource.includes("def remove_dashboard_widget(") &&
      dashboardWidgetCommandServiceSource.includes("same type/title/source already exists") &&
      dashboardWidgetCommandServiceSource.includes("UPDATE dashboard_widgets") &&
      dashboardWidgetCommandServiceSource.includes("DELETE FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?") &&
      byLabel["cli-add-recommended-widgets-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-add-widget-view-confirm"].parsed?.confirmed === true &&
      byLabel["cli-set-widget-style-confirm"].parsed?.confirmed === true &&
      byLabel["cli-copy-widget-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-remove-widget-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "business-dashboard-service-boundary",
    ok: existsSync(join(root, "tools", "business_dashboard_service.py")) &&
      biCliSource.includes("from business_dashboard_service import (") &&
      biCliSource.includes("build_business_analysis_templates_service(") &&
      biCliSource.includes("build_business_dashboard_payload_service(") &&
      biCliSource.includes("write_business_dashboard_service(") &&
      biCliSource.includes("run_business_dashboard_command_service(") &&
      biCliSource.includes("build_agent_dashboard_create_draft_service(") &&
      !biCliSource.includes("def add_template(") &&
      !biCliSource.includes("经营复盘结论") &&
      !biCliSource.includes("No business dashboard templates are available for current sources.") &&
      businessDashboardServiceSource.includes("def template_widget_layout(") &&
      businessDashboardServiceSource.includes("def table_template_fields(") &&
      businessDashboardServiceSource.includes("def build_business_analysis_templates(") &&
      businessDashboardServiceSource.includes("def build_cost_monitor_templates(") &&
      businessDashboardServiceSource.includes("def build_business_dashboard_payload(") &&
      businessDashboardServiceSource.includes("def write_business_dashboard(") &&
      businessDashboardServiceSource.includes("def run_business_dashboard_command(") &&
      businessDashboardServiceSource.includes("def build_agent_dashboard_create_draft(") &&
      businessDashboardServiceSource.includes("COST_MONITOR_NET_FORMULA") &&
      businessDashboardServiceSource.includes("namespaced_dashboard_widget_id") &&
      businessDashboardServiceSource.includes("save_dashboard_with_widgets") &&
      byLabel["cli-business-dashboard-draft"].parsed?.templateCount >= 5 &&
      byLabel["cli-business-dashboard-create-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-business-dashboard-create-confirm"].parsed?.confirmed === true &&
      byLabel["cli-cost-monitor-dashboard-draft"].parsed?.draft?.templateKey === "cost-monitor" &&
      byLabel["cli-cost-monitor-dashboard-draft"].parsed?.templateCount >= 20 &&
      byLabel["cli-cost-monitor-dashboard-draft"].parsed?.draft?.widgets?.some((widget) => widget.title === "动账净额月度趋势") &&
      byLabel["cli-cost-monitor-dashboard-create-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-dashboard-dry-run"].parsed?.proposedDashboard?.source === "business-dashboard",
  },
  {
    label: "erp-dashboard-unit-library",
    ok: existsSync(join(root, "tools", "erp_dashboard_unit_library.py")) &&
      existsSync(join(root, "scripts", "verify-erp-unit-library.mjs")) &&
      packageJson.scripts["verify:erp-units"] === "node scripts/verify-erp-unit-library.mjs" &&
      biCliSource.includes("from erp_dashboard_unit_library import (") &&
      biCliSource.includes('sub.add_parser("erp-unit-library")') &&
      biCliSource.includes('choices=["business", "cost-monitor", ERP_UNIT_LIBRARY_TEMPLATE_KEY]') &&
      businessDashboardServiceSource.includes("prompt_prefers_erp_unit_library(prompt)") &&
      businessDashboardServiceSource.includes("build_erp_dashboard_unit_templates(") &&
      erpDashboardUnitLibrarySource.includes('ERP_UNIT_LIBRARY_TEMPLATE_KEY = "erp-units"') &&
      erpDashboardUnitLibrarySource.includes("PUBLIC_ERP_REFERENCES") &&
      erpDashboardUnitLibrarySource.includes("ERP_DASHBOARD_UNITS") &&
      erpDashboardUnitLibrarySource.includes("ERP_FIELD_GROUP_LABELS") &&
      erpDashboardUnitLibrarySource.includes("def _unavailable_unit_hints(") &&
      erpDashboardUnitLibrarySource.includes("prompt_prefers_erp_unit_library") &&
      erpDashboardUnitLibrarySource.includes("not a fixed ERP dashboard template") &&
      businessDashboardServiceSource.includes('"erpUnitLibrary": erp_unit_library') &&
      businessDashboardServiceSource.includes('"erp-unit-library"') &&
      byLabel["cli-dashboard-widget-catalog"].parsed?.erpUnitLibrary?.unitCount >= 150 &&
      byLabel["cli-dashboard-widget-catalog"].parsed?.erpUnitLibrary?.referenceCount >= 45 &&
      byLabel["cli-erp-unit-library-summary"].parsed?.catalog?.fieldAliasGroupCount >= 240 &&
      byLabel["cli-erp-unit-library-selection"].parsed?.selection?.erpUnitLibrary?.selectedUnitCount > 0 &&
      byLabel["cli-erp-unit-library-selection"].parsed?.selection?.erpUnitLibrary?.unavailableUnitCount >= 0 &&
      Array.isArray(byLabel["cli-erp-unit-library-selection"].parsed?.selection?.erpUnitLibrary?.omittedUnitHints) &&
      byLabel["cli-business-dashboard-erp-units-draft"].parsed?.draft?.templateKey === "erp-units" &&
      byLabel["cli-business-dashboard-erp-units-draft"].parsed?.draft?.erpUnitLibrary?.selectedUnitCount > 0 &&
      Array.isArray(byLabel["cli-business-dashboard-erp-units-draft"].parsed?.draft?.erpUnitLibrary?.categoryCoverage) &&
      byLabel["cli-business-dashboard-erp-units-draft"].parsed?.draft?.widgets?.some((widget) => widget.erpUnitKey && widget.matchedFields) &&
      byLabel["cli-agent-erp-dashboard-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-erp-dashboard-draft"].parsed?.actionDraft?.kind === "dashboard.create" &&
      byLabel["cli-agent-action-drafts-before-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-erp-dashboard-draft"].parsed?.actionDraft?.actionKey &&
        draft.payload?.dashboardDraft?.templateKey === "erp-units" &&
        draft.payload?.dashboardDraft?.erpUnitLibrary?.selectedUnitCount > 0 &&
        Array.isArray(draft.payload?.dashboardDraft?.erpUnitLibrary?.omittedUnitHints) &&
        Array.isArray(draft.payload?.dashboardDraft?.erpUnitLibrary?.categoryCoverage)
      ),
  },
  {
    label: "dashboard-module-orchestration-boundary",
    ok: existsSync(join(root, "tools", "dashboard_module_orchestration.py")) &&
      biCliSource.includes("from dashboard_module_orchestration import dashboard_module_widget_from_payload") &&
      !biCliSource.includes("def dashboard_module_widget_from_payload(") &&
      !biCliSource.includes("def namespaced_dashboard_widget_id(") &&
      dashboardModuleOrchestrationSource.includes("def dashboard_module_widget_from_payload(") &&
      dashboardModuleOrchestrationSource.includes("def namespaced_dashboard_widget_id(") &&
      dashboardModuleOrchestrationSource.includes("preferred_table_key: Callable") &&
      dashboardModuleOrchestrationSource.includes("table_display_name: Callable") &&
      dashboardModuleOrchestrationSource.includes("workspace_id: str") &&
      byLabel["cli-save-dashboard-modules-dry-run"].parsed?.proposedWidgets?.every((widget) =>
        widget.workspace_id && widget.config?.layout,
      ),
  },
  {
    label: "dashboard-save-transaction-boundary",
    ok: existsSync(join(root, "tools", "dashboard_save_transactions.py")) &&
      biCliSource.includes("from dashboard_save_transactions import dashboard_snapshot, save_dashboard_with_widgets") &&
      dashboardSaveTransactionsSource.includes("def upsert_dashboard_record(") &&
      dashboardSaveTransactionsSource.includes("def replace_dashboard_widgets(") &&
      dashboardSaveTransactionsSource.includes("def save_dashboard_with_widgets(") &&
      dashboardSaveTransactionsSource.includes("def dashboard_snapshot(") &&
      dashboardSaveTransactionsSource.includes("insert_dashboard_widget(connection, widget)") &&
      byLabel["cli-save-dashboard-modules-confirm"].parsed?.dashboard?.widgets?.every((widget) => widget.config),
  },
  {
    label: "bi-cli-core-boundary",
    ok: existsSync(join(root, "tools", "bi_cli_core.py")) &&
      biCliSource.includes("from bi_cli_core import (") &&
      !biCliSource.includes("def quote_identifier(name: str)") &&
      !biCliSource.includes("def source_label(path: Path | str)") &&
      biCliCoreSource.includes("def quote_identifier(name: str)") &&
      biCliCoreSource.includes("def source_label(path: Path | str)") &&
      biCliCoreSource.includes("A_PROJECT_ROOT") &&
      biCliCoreSource.includes("B_PROJECT_ROOT"),
  },
  {
    label: "verify-compact-output-default",
    ok: verifySource.includes('from "./verify/runtime.mjs"') &&
      verifySource.includes("finishVerify({") &&
      verifyRuntimeSource.includes("function compactReceipt(receipt)") &&
      verifyRuntimeSource.includes("const fullOutput = process.argv.includes(\"--full\") || process.env.AIBI_VERIFY_FULL === \"1\"") &&
      verifyRuntimeSource.includes("fullReceiptPath: verifyReceiptPath") &&
      verifyRuntimeSource.includes("write" + "FileSync(verifyReceiptPath") &&
      verifyRuntimeSource.includes("fullOutput ? receipt : compactReceipt(receipt)"),
  },
  {
    label: "verify-source-catalog-boundary",
    ok: verifySource.includes('from "./verify/sourceCatalog.mjs"') &&
      verifySource.includes("readVerifySourceCatalog(root)") &&
      !verifySource.includes("read" + "FileSync(") &&
      verifySourceCatalogSource.includes("const textSourceFiles = {") &&
      verifySourceCatalogSource.includes("export function readVerifySourceCatalog(root)") &&
      verifySourceCatalogSource.includes("read" + "FileSync(join(root, ...pathSegments), \"utf8\")"),
  },
  {
    label: "verify-fixture-writer-boundary",
    ok: verifySource.includes('from "./verify/fixtures.mjs"') &&
      verifySource.includes("writeCostMonitorFixtures(verifyDataDir)") &&
      !verifySource.includes("write" + "FileSync(") &&
      verifyFixturesSource.includes("export function writeCostMonitorFixtures(verifyDataDir)") &&
      verifyFixturesSource.includes("cost-monitor-funds.csv") &&
      verifyFixturesSource.includes("cost-monitor-policy.csv") &&
      verifyFixturesSource.includes("write" + "FileSync("),
  },
  {
    label: "source-pipeline-rich-contract",
    ok: Array.isArray(byLabel["cli-preview-import"].parsed?.sourcePipelineContract?.stages) &&
      byLabel["cli-preview-import"].parsed.sourcePipelineContract.stages.every((stage) => stage.id && stage.outputEvidence) &&
      Array.isArray(byLabel["cli-preview-import"].parsed.sourcePipelineContract.domainPackRuntime?.semanticHints),
  },
  {
    label: "import-preview-merge-plan",
    ok: Boolean(
      byLabel["cli-preview-import"].parsed?.uniqueKeyQuality?.totalRows &&
      byLabel["cli-preview-import"].parsed?.mergePolicyPreview?.mergePlan?.incomingRows,
    ),
  },
  {
    label: "b-import-policy-and-job-log",
    ok: byLabel["cli-set-import-policy-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-set-import-policy-confirm"].parsed?.confirmed === true &&
      byLabel["cli-set-import-policy-confirm"].parsed?.policy?.conflictRule === "fill-empty" &&
      byLabel["cli-list-import-jobs"].parsed?.importJobs?.some((job) => job.table_key === "orders" && job.status === "success") &&
      byLabel["cli-remove-import-job-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-preview-import"].parsed?.mergePolicyPreview?.savedPolicy?.conflictRule === "fill-empty",
  },
  {
    label: "b-source-management-write-boundary",
    ok: byLabel["cli-list-tables"].parsed?.tables?.some((table) => table.table_key === "orders") &&
      byLabel["cli-inspect-table"].parsed?.table?.table_key === "orders" &&
      byLabel["cli-inspect-table"].parsed?.fieldConfig?.length > 0 &&
      byLabel["cli-rename-source-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-rename-source-confirm"].parsed?.confirmed === true &&
      byLabel["cli-rename-source-confirm"].parsed?.renamedSource?.name === "验证退款表" &&
      byLabel["cli-import-delete-source-validation-input"].parsed?.result?.tableKey === "verify_delete_source" &&
      byLabel["cli-delete-source-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-delete-source-dry-run"].parsed?.impact?.fieldConfigs > 0 &&
      byLabel["cli-delete-source-confirm"].parsed?.confirmed === true &&
      byLabel["cli-delete-source-confirm"].parsed?.deletedSource === "verify_delete_source",
  },
  {
    label: "source-read-model-service-boundary",
    ok: existsSync(join(root, "tools", "source_read_model_service.py")) &&
      biCliSource.includes("from source_read_model_service import (") &&
      biCliSource.includes("list_tables_command_service(") &&
      biCliSource.includes("inspect_table_command_service(") &&
      sourceReadModelServiceSource.includes("def list_tables_command(") &&
      sourceReadModelServiceSource.includes("def inspect_table_command(") &&
      sourceReadModelServiceSource.includes("SELECT table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, created_at") &&
      sourceReadModelServiceSource.includes("SELECT field_name, role, usage, confidence") &&
      sourceReadModelServiceSource.includes("SELECT metric_key, label, measure, aggregation, dimension, time_field, value_format") &&
      sourceReadModelServiceSource.includes("SELECT view_key, name, tag_name, is_default, sort_order, created_by, agent_managed") &&
      sourceReadModelServiceSource.includes("SELECT relation_key, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence") &&
      sourceReadModelServiceSource.includes("SELECT job_key, workspace_id, source_file, mode, status, row_count, created_at") &&
      sourceReadModelServiceSource.includes("\"fieldConfig\"") &&
      sourceReadModelServiceSource.includes("\"importJobs\"") &&
      sourceReadModelServiceSource.includes("\"connectors\"") &&
      !biCliSource.includes("SELECT field_name, role, usage, confidence\n                FROM field_semantics") &&
      !biCliSource.includes("SELECT job_key, workspace_id, source_file, mode, status, row_count, created_at\n                FROM import_jobs") &&
      byLabel["cli-list-tables"].parsed?.count >= 2 &&
      byLabel["cli-inspect-table"].parsed?.columns?.includes("order_id") &&
      byLabel["cli-inspect-table"].parsed?.metrics?.some((metric) => metric.metric_key === "orders_row_count") &&
      byLabel["cli-inspect-table"].parsed?.views?.some((view) => view.view_key === "view_orders_default") &&
      byLabel["cli-inspect-table"].parsed?.relationships?.some((relation) => relation.relation_key.includes("orders_refunds")) &&
      byLabel["cli-inspect-table"].parsed?.importJobs?.length > 0,
  },
  {
    label: "source-management-command-service-boundary",
    ok: existsSync(join(root, "tools", "source_management_command_service.py")) &&
      biCliSource.includes("from source_management_command_service import (") &&
      biCliSource.includes("rename_source_command_service(") &&
      biCliSource.includes("remaining_table_key_after_delete_service(") &&
      biCliSource.includes("build_delete_source_plan_service(") &&
      biCliSource.includes("delete_source_command_service(") &&
      sourceManagementCommandServiceSource.includes("def rename_source_command(") &&
      sourceManagementCommandServiceSource.includes("def remaining_table_key_after_delete(") &&
      sourceManagementCommandServiceSource.includes("def build_delete_source_plan(") &&
      sourceManagementCommandServiceSource.includes("def delete_source_command(") &&
      sourceManagementCommandServiceSource.includes("UPDATE table_registry SET display_name = ? WHERE table_key = ? AND workspace_id = ?") &&
      sourceManagementCommandServiceSource.includes("DROP TABLE IF EXISTS") &&
      sourceManagementCommandServiceSource.includes("DELETE FROM table_registry WHERE table_key = ? AND workspace_id = ?") &&
      sourceManagementCommandServiceSource.includes("affectedWidgets") &&
      sourceManagementCommandServiceSource.includes("affectedConnectors") &&
      sourceManagementCommandServiceSource.includes("nextDefaultTableKey") &&
      !sourceManagementCommandServiceSource.includes("def source_was_seed_import(") &&
      !sourceManagementCommandServiceSource.includes("mode = 'seed'") &&
      !sourceManagementCommandServiceSource.includes("seed_repair_disabled") &&
      !sourceManagementCommandServiceSource.includes('"orders", "refunds"') &&
      !biCliSource.includes("\"affectedRelationshipKeys\": relation_keys") &&
      !biCliSource.includes("config[\"targetTableKey\"] = \"\"") &&
      byLabel["cli-rename-source-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-rename-source-confirm"].parsed?.confirmed === true &&
      byLabel["cli-delete-source-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-delete-source-dry-run"].parsed?.nextDefaultTableKey &&
      byLabel["cli-delete-source-confirm"].parsed?.confirmed === true,
  },
  {
    label: "production-empty-start-no-seed-boundary",
    ok: !existsSync(join(root, "tools", "seed_orchestration_service.py")) &&
      !existsSync(join(root, "tools", "seed_default_objects_service.py")) &&
      !biCliSource.includes("from seed_orchestration_service import (") &&
      !biCliSource.includes("from seed_default_objects_service import (") &&
      !biCliSource.includes("ensure_seed_data(") &&
      !biCliSource.includes("ensure_default_import_policies(") &&
      !biCliSource.includes("create_default_views(connection)") &&
      !biCliSource.includes(retiredSeedEnvName) &&
      !biCliCoreSource.includes("FIXTURE_DIR") &&
      !importTableWriterServiceSource.includes('mode == "seed"') &&
      !sourceManagementCommandServiceSource.includes("seed_repair_disabled") &&
      verifySource.includes("verify-bootstrap-import-orders") &&
      verifyBiCliAgentContractSource.includes("verify-contract-bootstrap-import-orders") &&
      (biCliSource.match(/def table_columns\(/g) ?? []).length === 1 &&
      byLabel["cli-status"].parsed?.health?.ok === true &&
      byLabel["cli-status"].parsed?.counts?.tables === 0 &&
      byLabel["verify-bootstrap-import-orders"].parsed?.result?.tableKey === "orders" &&
      byLabel["verify-bootstrap-import-refunds"].parsed?.result?.tableKey === "refunds" &&
      byLabel["cli-list-tables"].parsed?.tables?.some((table) => table.table_key === "orders") &&
      byLabel["cli-list-tables"].parsed?.tables?.some((table) => table.table_key === "refunds"),
  },
  {
    label: "validation-bootstrap-objects-boundary",
    ok: byLabel["verify-bootstrap-relationship"].parsed?.saved?.relation_key === "orders_refunds_order_id_order_id" &&
      byLabel["verify-bootstrap-orders-view"].parsed?.savedView?.view_key === "view_orders_default" &&
      byLabel["verify-bootstrap-refunds-view"].parsed?.savedView?.view_key === "view_refunds_default" &&
      byLabel["verify-bootstrap-dashboard"].parsed?.confirmed === true &&
      byLabel["verify-bootstrap-default-dashboard"].parsed?.confirmed === true &&
      byLabel["cli-default-dashboard-bootstrap"].parsed?.dashboards?.[0]?.widgets?.length >= 1 &&
      byLabel["cli-list-views"].parsed?.savedViews?.some((view) => view.view_key === "view_orders_default" && view.name === "订单明细视图") &&
      byLabel["cli-list-views"].parsed?.savedViews?.some((view) => view.view_key === "view_refunds_default" && view.name === "退款明细视图"),
  },
  {
    label: "b-connectors-file-sync-and-boundary",
    ok: byLabel["cli-save-connector-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-save-connector-confirm"].parsed?.confirmed === true &&
      byLabel["cli-list-connectors"].parsed?.connectors?.some((connector) => connector.connectorKey === "verify_file_connector") &&
      byLabel["cli-sync-connector-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-sync-connector-dry-run"].parsed?.proposedSync?.sourceExists === true &&
      byLabel["cli-sync-connector-confirm"].parsed?.confirmed === true &&
      byLabel["cli-sync-connector-confirm"].parsed?.connectorSync?.importResult?.tableKey === "orders" &&
      byLabel["cli-sync-external-connector-blocked"].parsed?.blocked === true &&
      byLabel["cli-remove-connector-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "b-preferences-theme-palettes",
    ok: byLabel["cli-preferences"].parsed?.preferences?.requireDeleteNameConfirmation === true &&
      byLabel["cli-preferences"].parsed?.preferences?.themeKey &&
      byLabel["cli-preferences-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-preferences-confirm"].parsed?.confirmed === true &&
      byLabel["cli-theme-palettes"].parsed?.themePalettes?.some((theme) => theme.themeKey === "L1") &&
      byLabel["cli-theme-save-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-theme-save-confirm"].parsed?.confirmed === true &&
      byLabel["cli-theme-save-confirm"].parsed?.savedThemePalette?.themeKey === "verify_custom" &&
      byLabel["cli-theme-delete-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "frontend-theme-no-flash-bootstrap",
    ok: indexHtmlSource.includes("aibiHybrid.themeSnapshot") &&
      indexHtmlSource.includes("readThemeFromWorkbench") &&
      indexHtmlSource.includes('request.open("GET", "/api/workbench?limit=1", false)') &&
      indexHtmlSource.includes("fallbackDarkTheme") &&
      indexHtmlSource.includes('window.matchMedia("(prefers-color-scheme: dark)")') &&
      indexHtmlSource.includes("root.dataset.themeMode = mode") &&
      indexHtmlSource.includes("root.style.colorScheme = mode") &&
      indexHtmlSource.includes('html[data-theme-mode="dark"]') &&
      appSource.includes("hasStoredThemeSnapshot") &&
      appSource.includes("if (!status.database && hasStoredThemeSnapshot())") &&
      themeSource.includes('const themeSnapshotStorageKey = "aibiHybrid.themeSnapshot"') &&
      themeSource.includes("export function hasStoredThemeSnapshot") &&
      themeSource.includes("window.localStorage.setItem(themeSnapshotStorageKey"),
  },
  {
    label: "preferences-theme-command-service-boundary",
    ok: existsSync(join(root, "tools", "preferences_theme_command_service.py")) &&
      biCliSource.includes("from preferences_theme_command_service import (") &&
      biCliSource.includes("normalize_user_preferences_service(") &&
      biCliSource.includes("normalize_theme_tokens_service(") &&
      biCliSource.includes("normalize_theme_palette_service(") &&
      biCliSource.includes("validate_theme_palette_payload_service(") &&
      biCliSource.includes("ensure_default_preferences_and_themes_service(") &&
      biCliSource.includes("load_user_preferences_service(") &&
      biCliSource.includes("save_user_preferences_service(") &&
      biCliSource.includes("list_theme_palettes_service(") &&
      biCliSource.includes("upsert_theme_palette_service(") &&
      biCliSource.includes("delete_theme_palette_service(") &&
      biCliSource.includes("preferences_payload_service(") &&
      biCliSource.includes("preferences_command_service(") &&
      biCliSource.includes("theme_palettes_command_service(") &&
      !biCliSource.includes("DEFAULT_USER_PREFERENCES =") &&
      !biCliSource.includes("DEFAULT_THEME_PALETTES =") &&
      preferencesThemeCommandServiceSource.includes("DEFAULT_USER_PREFERENCES =") &&
      preferencesThemeCommandServiceSource.includes("DEFAULT_THEME_PALETTES =") &&
      preferencesThemeCommandServiceSource.includes("REQUIRED_THEME_TOKENS =") &&
      preferencesThemeCommandServiceSource.includes("def ensure_default_preferences_and_themes(") &&
      preferencesThemeCommandServiceSource.includes("def preferences_command(") &&
      preferencesThemeCommandServiceSource.includes("def theme_palettes_command(") &&
      preferencesThemeCommandServiceSource.includes("Built-in themes cannot be overwritten") &&
      preferencesThemeCommandServiceSource.includes("Built-in themes cannot be deleted") &&
      !preferencesThemeCommandServiceSource.includes("return {\"themeKey\": row[\"theme_key\"], \"name\": row[\"name\"]}\n    connection.commit()") &&
      byLabel["cli-preferences"].parsed?.activeTheme?.themeKey === byLabel["cli-preferences"].parsed?.preferences?.themeKey &&
      byLabel["cli-preferences-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-preferences-confirm"].parsed?.confirmed === true &&
      byLabel["cli-theme-save-dry-run"].parsed?.proposedThemePalette?.themeKey === "verify_custom" &&
      byLabel["cli-theme-save-confirm"].parsed?.savedThemePalette?.createdBy === "manual" &&
      byLabel["cli-theme-delete-dry-run"].parsed?.operation === "delete-theme",
  },
  {
    label: "b-config-portability",
    ok: byLabel["cli-validate-config"].parsed?.ok === true &&
      Array.isArray(byLabel["cli-validate-config"].parsed?.errors) &&
      byLabel["cli-validate-config"].parsed?.errors.length === 0 &&
      byLabel["cli-export-config"].parsed?.businessDataIncluded === false &&
      byLabel["cli-export-config"].parsed?.tables?.dashboards >= 1 &&
      byLabel["cli-export-config"].parsed?.tables?.data_connectors >= 1 &&
      byLabel["cli-apply-config-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-apply-config-dry-run"].parsed?.restorePlan?.dashboards >= 1,
  },
  {
    label: "config-command-service-boundary",
    ok: existsSync(join(root, "tools", "config_command_service.py")) &&
      biCliSource.includes("from config_command_service import (") &&
      biCliSource.includes("redact_secret_value_service(") &&
      biCliSource.includes("restore_redacted_value_service(") &&
      biCliSource.includes("config_row_for_export_service(") &&
      biCliSource.includes("prepare_config_rows_for_restore_service(") &&
      biCliSource.includes("export_metadata_config_service(") &&
      biCliSource.includes("restore_config_rows_service(") &&
      biCliSource.includes("validate_metadata_config_service(") &&
      biCliSource.includes("validate_config_command_service(") &&
      biCliSource.includes("export_config_command_service(") &&
      biCliSource.includes("apply_config_command_service(") &&
      !biCliSource.includes("CONFIG_TABLES =") &&
      !biCliSource.includes("CONFIG_KIND =") &&
      configCommandServiceSource.includes("CONFIG_TABLES =") &&
      configCommandServiceSource.includes("CONFIG_KIND = \"aibi-hybrid-local-bi-config\"") &&
      configCommandServiceSource.includes("def redact_secret_value(") &&
      configCommandServiceSource.includes("def restore_redacted_value(") &&
      configCommandServiceSource.includes("def export_metadata_config(") &&
      configCommandServiceSource.includes("def restore_config_rows(") &&
      configCommandServiceSource.includes("def validate_metadata_config(") &&
      configCommandServiceSource.includes("def validate_config_command(") &&
      configCommandServiceSource.includes("def export_config_command(") &&
      configCommandServiceSource.includes("def apply_config_command(") &&
      configCommandServiceSource.includes("__AIBI_REDACTED__") &&
      configCommandServiceSource.includes("businessDataIncluded") &&
      configCommandServiceSource.includes("shutil.copy2(DB_PATH, backup_path)") &&
      configCommandServiceSource.includes("calculated_field_names_for_table=") &&
      configCommandServiceSource.includes("widget_types=") &&
      configCommandServiceSource.includes("safe_aggregations=") &&
      byLabel["cli-validate-config"].parsed?.ok === true &&
      byLabel["cli-export-config"].parsed?.kind === "aibi-hybrid-local-bi-config" &&
      byLabel["cli-export-config"].parsed?.businessDataIncluded === false &&
      byLabel["cli-export-config"].parsed?.redaction?.includes("__AIBI_REDACTED__") &&
      byLabel["cli-apply-config-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-apply-config-dry-run"].parsed?.message?.includes("business data tables are not imported"),
  },
  {
    label: "relationship-preview-coverage",
    ok: Boolean(
      byLabel["cli-relationship-preview"].parsed?.relationshipPreview?.metrics?.leftRows &&
      typeof byLabel["cli-relationship-preview"].parsed?.relationshipPreview?.metrics?.confidence === "number",
    ),
  },
  {
    label: "b-relationship-query-runtime",
    ok: byLabel["cli-list-relationships"].parsed?.relationships?.some((relationship) => relationship.relation_key === "orders_refunds_order_id_order_id") &&
      byLabel["cli-query-relationship"].parsed?.relationshipQuery?.joinType === "left" &&
      byLabel["cli-query-relationship"].parsed?.relationshipQuery?.rows?.[0]?.["左表.channel"] === "Douyin" &&
      byLabel["cli-query-relationship"].parsed?.rows?.[0]?.value === 3440 &&
      byLabel["cli-remove-relationship-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "duckdb-query-runtime",
    ok: byLabel["cli-status"].parsed?.queryRuntime?.available === true &&
      byLabel["cli-query"].parsed?.query?.runtime?.engine === "duckdb" &&
      byLabel["cli-query"].parsed?.query?.runtime?.compiledSql?.includes("TRY_CAST") &&
      byLabel["cli-query"].parsed?.query?.runtime?.syncedRows > 0,
  },
  {
    label: "workspace-create-default-dry-run",
    ok: byLabel["cli-workspace-create-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-workspace-create-dry-run"].parsed?.proposed?.name === "验证工作区",
  },
  {
    label: "workspace-create-select-active",
    ok: byLabel["cli-workspace-create-confirm"].parsed?.created?.id === "verify_workspace" &&
      byLabel["cli-workspace-select-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-workspace-select-confirm"].parsed?.workspace?.id === "verify_workspace" &&
      byLabel["cli-status-after-workspace-select"].parsed?.workspace?.id === "verify_workspace" &&
      byLabel["cli-status-after-workspace-select"].parsed?.workspaces?.some((workspace) => workspace.id === "verify_workspace" && workspace.isActive === true) &&
      byLabel["cli-workspace-select-default"].parsed?.workspace?.id === "default",
  },
  {
    label: "workspace-delete-safe-lifecycle",
    ok: byLabel["cli-workspace-delete-target-create"].parsed?.created?.id === "delete_workspace_target" &&
      byLabel["cli-workspace-delete-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-workspace-delete-dry-run"].parsed?.workspace?.id === "delete_workspace_target" &&
      typeof byLabel["cli-workspace-delete-dry-run"].parsed?.impact?.totalRows === "number" &&
      byLabel["cli-workspace-delete-confirm"].parsed?.deletedWorkspace?.id === "delete_workspace_target" &&
      byLabel["cli-workspace-delete-confirm"].parsed?.confirmed === true &&
      byLabel["cli-workspace-delete-default-blocked"].ok === true &&
      String(byLabel["cli-workspace-delete-default-blocked"].parsed?.error ?? "").includes("Default workspace cannot be deleted") &&
      byLabel["cli-workspace-active-delete-target-select"].parsed?.workspace?.id === "active_delete_workspace" &&
      byLabel["cli-workspace-delete-active-blocked"].ok === true &&
      String(byLabel["cli-workspace-delete-active-blocked"].parsed?.error ?? "").includes("Cannot delete the active workspace") &&
      byLabel["cli-workspace-select-default-after-delete-check"].parsed?.workspace?.id === "default",
  },
  {
    label: "workspace-command-service-boundary",
    ok: existsSync(join(root, "tools", "workspace_command_service.py")) &&
      biCliSource.includes("from workspace_command_service import (") &&
      biCliSource.includes("get_system_flag_service(") &&
      biCliSource.includes("set_system_flag_service(") &&
      biCliSource.includes("active_workspace_id_service(") &&
      biCliSource.includes("workspace_records_service(") &&
      biCliSource.includes("workspace_create_command_service(") &&
      biCliSource.includes("workspace_select_command_service(") &&
      workspaceCommandServiceSource.includes("def get_system_flag(") &&
      workspaceCommandServiceSource.includes("def set_system_flag(") &&
      workspaceCommandServiceSource.includes("def active_workspace_id(") &&
      workspaceCommandServiceSource.includes("def workspace_records(") &&
      workspaceCommandServiceSource.includes("def workspace_create_command(") &&
      workspaceCommandServiceSource.includes("def workspace_select_command(") &&
      workspaceCommandServiceSource.includes("def workspace_delete_command(") &&
      workspaceCommandServiceSource.includes("WORKSPACE_SCOPED_TABLES") &&
      workspaceCommandServiceSource.includes("DROP TABLE IF EXISTS") &&
      workspaceCommandServiceSource.includes("INSERT INTO workspaces") &&
      workspaceCommandServiceSource.includes("ON CONFLICT(key) DO UPDATE") &&
      biCliSource.includes("workspace_delete_command_service(") &&
      biCliSource.includes('workspace_delete = sub.add_parser("workspace-delete")') &&
      byLabel["cli-workspace-create-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-workspace-create-confirm"].parsed?.created?.id === "verify_workspace" &&
      byLabel["cli-workspace-select-dry-run"].parsed?.currentWorkspaceId === "default" &&
      byLabel["cli-workspace-select-confirm"].parsed?.workspace?.isActive === true &&
      byLabel["cli-workspace-delete-confirm"].parsed?.deletedWorkspace?.id === "delete_workspace_target" &&
      byLabel["cli-workspace-delete-default-blocked"].ok === true &&
      byLabel["cli-workspace-delete-active-blocked"].ok === true &&
      byLabel["cli-status-after-workspace-select"].parsed?.workspaces?.some((workspace) => workspace.id === "verify_workspace" && workspace.isActive === true) &&
      byLabel["workspace-source-intelligence-action-draft-isolation"].ok === true &&
      byLabel["workspace-bi-metadata-isolation"].ok === true &&
      byLabel["workspace-same-key-physical-isolation"].ok === true,
  },
  {
    label: "workspace-chinese-name-stable-id",
    ok: byLabel["cli-workspace-create-chinese-dry-run"].parsed?.proposed?.name === "验证中文工作区" &&
      typeof byLabel["cli-workspace-create-chinese-dry-run"].parsed?.proposed?.id === "string" &&
      byLabel["cli-workspace-create-chinese-dry-run"].parsed?.proposed?.id.startsWith("workspace_") &&
      byLabel["cli-workspace-create-chinese-dry-run"].parsed?.proposed?.id !== "source",
  },
  {
    label: "source-run-detail-complete",
    ok: byLabel["cli-source-run-detail"].parsed?.sourceRun?.profile?.rowCount > 0 &&
      byLabel["cli-source-run-detail"].parsed?.fields?.length > 0 &&
      byLabel["cli-source-run-detail"].parsed?.metrics?.length > 0 &&
      Array.isArray(byLabel["cli-source-run-detail"].parsed?.sourceRun?.evidence),
  },
  {
    label: "workbench-surface-complete",
    ok: Boolean(
      byLabel["cli-workbench"].parsed?.tables?.length &&
      byLabel["cli-workbench"].parsed?.fields?.length &&
      byLabel["cli-workbench"].parsed?.metrics?.length &&
      byLabel["cli-workbench"].parsed?.relationshipRecommendations?.some((recommendation) => recommendation.leftTableKey === "orders" && recommendation.rightTableKey === "refunds") &&
      byLabel["cli-workbench-after-connectors"].parsed?.connectors?.some((connector) => connector.connectorKey === "verify_file_connector") &&
      byLabel["cli-workbench-after-connectors"].parsed?.preferences?.themeKey &&
      byLabel["cli-workbench-after-connectors"].parsed?.themePalettes?.some((theme) => theme.themeKey === "L1") &&
      byLabel["cli-workbench"].parsed?.savedViews?.length &&
      byLabel["cli-workbench"].parsed?.navigation?.some((module) => module.moduleKey === "table:orders") &&
      Array.isArray(byLabel["cli-workbench"].parsed?.safeAggregations),
    ),
  },
  {
    label: "source-intelligence-file-coverage-contract",
    ok: sourceCoverageRuns.some((run) =>
      run.label === "verify-validation-inputs-source-intelligence" &&
      run.fileCoverage?.sourceFileCount === run.source_count &&
      run.fileCoverage?.manifestSourceCount === run.source_count &&
      run.fileCoverage?.filesBySourceGroup?.length >= 1 &&
      run.fileCoverage?.skippedTableCount === 0 &&
      run.fileCoverage?.complete === true,
    ) &&
      sourceCoverageAllRuns.some((run) => run.label === "verify-validation-inputs-source-intelligence" && run.isInternal === true) &&
      byLabel["cli-workbench"].parsed?.sourceIntelligenceRuns?.some((run) => run.fileCoverage?.sourceFileCount === run.source_count) &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-coverage-item"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-coverage-groups"') &&
      !sourceWorkbenchDataEntryPanelSource.includes("filesByMonth") &&
      sourceWorkbenchDataEntryPanelSource.includes("run.isInternal") &&
      sourceWorkbenchDataEntryPanelSource.includes("系统检查") &&
      sourceWorkbenchDataEntryPanelSource.includes("fileCoverage"),
  },
  {
    label: "source-workbench-folder-profile-entry",
    ok: sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-folder-entry"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-custom-run-button"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-open-import-button"') &&
      !sourceWorkbenchDataEntryPanelSource.includes("aTestdata") &&
      !sourceWorkbenchDataEntryPanelSource.includes("样例") &&
      !sourceWorkbenchDataEntryPanelSource.includes("sample data") &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-progress"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-result"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-error"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-recovery"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-recovery-steps"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-recovery-business-hint"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-business-impact"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-next-step"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-technical-details"') &&
      sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-result-technical-details"') &&
      sourceWorkbenchCommandModelSource.includes("splitInputPaths") &&
      sourceWorkbenchSource.includes("sourceProfileOptions") &&
      sourceWorkbenchSource.includes("runSourceProfile") &&
      sourceWorkbenchDataEntryPanelSource.includes("sourceProfileSummary") &&
      sourceWorkbenchDataEntryPanelSource.includes("sourceProfileBusinessStatus") &&
      sourceWorkbenchDataEntryPanelSource.includes("sourceProfileRecovery") &&
      sourceWorkbenchDataEntryPanelSource.includes("让 Agent 看看") &&
      sourceWorkbenchDataEntryPanelSource.includes("技术错误") &&
      stylesSource.includes(".sourceProfileRecovery") &&
      stylesSource.includes(".sourceProfileRecoveryActions") &&
      stylesSource.includes(".sourceProfileBusinessHint") &&
      stylesSource.includes(".sourceProfileSuccessBody") &&
      stylesSource.includes(".sourceProfileTechnicalError") &&
      sourceWorkbenchCommandModelSource.includes("inputs: splitInputPaths(sourceProfileInputs)") &&
      apiClientSource.includes("export async function fetchJsonStrict") &&
      apiClientSource.includes("export class ApiPayloadError extends Error") &&
      apiClientSource.includes("let lastError: unknown = null") &&
      apiClientSource.includes("throw lastError") &&
      apiClientSource.includes("throw new Error(`Local API request failed for ${path}: ${message}`)") &&
      apiSourceApiSource.includes("return fetchJsonStrict<Record<string, unknown>>(\"/api/source-intelligence/run\"") &&
      appDataActionsSource.includes("const { stayOnPage = false, ...sourceOptions }") &&
      appDataActionsSource.includes("const hasInputs = Array.isArray(sourceOptions.inputs) && sourceOptions.inputs.length > 0") &&
      appDataActionsSource.includes("请先在数据源工作台选择本地文件或文件夹") &&
      appDataActionsSource.includes("return result;") &&
      byLabel["cli-source-intelligence-validation-inputs"].parsed?.manifest?.sourceCount >= 2,
  },
  {
    label: "source-workbench-data-entry-panel-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchDataEntryPanel.tsx")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchDataEntryPanel } from "./SourceWorkbenchDataEntryPanel"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchDataEntryPanel") &&
      !sourceWorkbenchSource.includes('data-testid="source-intelligence-folder-entry"') &&
      !sourceWorkbenchSource.includes("const aTestdataMonths") &&
      !sourceWorkbenchSource.includes("sourceProfileBusinessStatus(sourceProfileResult)") &&
      sourceWorkbenchDataEntryPanelSource.includes("type SourceWorkbenchDataEntryPanelProps") &&
      sourceWorkbenchDataEntryPanelSource.includes('from "../sourceIntelligenceRunModel"') &&
      !sourceWorkbenchDataEntryPanelSource.includes("aTestdata0305SourceIntelligenceOptions()") &&
      !sourceWorkbenchDataEntryPanelSource.includes("type SourceIntelligenceRunOptions =") &&
      sourceWorkbenchDataEntryPanelSource.includes("sourceProfileOptions: () => SourceIntelligenceRunOptions") &&
      sourceWorkbenchDataEntryPanelSource.includes("runSourceProfile: (label: string, options: SourceIntelligenceRunOptions) => Promise<void>") &&
      sourceWorkbenchDataEntryPanelSource.includes("onAsk: (prompt: string) => Promise<void>") &&
      sourceWorkbenchDataEntryPanelSource.includes("SourceIntelligenceRunSummary") &&
      sourceWorkbenchDataEntryPanelSource.includes("sourceProfileRecovery(sourceProfileError, sourceProfileInputs)") &&
      sourceWorkbenchDataEntryPanelSource.includes("sourceIntelligenceRuns.slice(0, 4)") &&
      implementationStatusSource.includes("Source workbench data entry panel boundary"),
  },
  {
    label: "source-workbench-header-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchHeader.tsx")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchHeader } from "./SourceWorkbenchHeader"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchHeader") &&
      !sourceWorkbenchSource.includes('data-testid="import-preview-button"') &&
      !sourceWorkbenchSource.includes('data-testid="source-intelligence-run-button"') &&
      sourceWorkbenchHeaderSource.includes("type SourceWorkbenchHeaderProps") &&
      !sourceWorkbenchHeaderSource.includes('data-testid="import-preview-button"') &&
      !sourceWorkbenchHeaderSource.includes('data-testid="import-dry-run-button"') &&
      !sourceWorkbenchHeaderSource.includes('data-testid="import-confirm-button"') &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-preview-button"') &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-preview"') &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-confirm"') &&
      !sourceWorkbenchHeaderSource.includes('data-testid="source-intelligence-run-button"') &&
      !sourceWorkbenchHeaderSource.includes("SOURCE_INTELLIGENCE_A_TESTDATA_COMMAND") &&
      !sourceWorkbenchHeaderSource.includes("aTestdata0305SourceIntelligenceOptions()") &&
      sourceWorkbenchHeaderSource.includes("先导入或选择本地数据路径") &&
      implementationStatusSource.includes("Source workbench header boundary"),
  },
  {
    label: "source-workbench-model-boundary",
    ok: existsSync(join(root, "src", "sourceWorkbenchModel.ts")) &&
      sourceWorkbenchSource.includes('from "../sourceWorkbenchModel"') &&
      sourceWorkbenchSource.includes("useMemo(() => buildFieldSemanticReadiness(selectedFields)") &&
      !sourceWorkbenchSource.includes("function confidencePercent(") &&
      !sourceWorkbenchSource.includes("function sourceProfileRecovery(") &&
      !sourceWorkbenchSource.includes("function buildFieldSemanticReadiness(") &&
      !sourceWorkbenchSource.includes("function sourceProfileBusinessStatus(") &&
      sourceWorkbenchModelSource.includes("export function confidencePercent(") &&
      sourceWorkbenchModelSource.includes("export function splitInputPaths(") &&
      sourceWorkbenchModelSource.includes("export function sourceProfileSummary(") &&
      sourceWorkbenchModelSource.includes("export function sourceProfileBusinessStatus(") &&
      sourceWorkbenchModelSource.includes("export function sourceProfileRecovery(") &&
      sourceWorkbenchModelSource.includes("export function buildFieldSemanticReadiness(") &&
      sourceWorkbenchModelSource.includes("FieldConfig") &&
      sourceWorkbenchModelSource.includes('from "./components/Bilingual"') &&
      sourceWorkbenchModelSource.includes("external source folders remain untouched") &&
      sourceWorkbenchModelSource.includes("field.confidence >= 0.82"),
  },
  {
    label: "source-workbench-derived-model-boundary",
    ok: sourceWorkbenchSource.includes("buildSourceWorkbenchCollections(workbench, status, query)") &&
      sourceWorkbenchSource.includes("buildSourceWorkbenchSelection({") &&
      sourceWorkbenchSource.includes("buildSourceWorkbenchRuntimeSummary(workbench, status, query)") &&
      sourceWorkbenchImportControllerSource.includes("buildImportPreviewSummary({ preview, previewReadable, targetName })") &&
      !sourceWorkbenchSource.includes("const tables = Array.isArray(workbench.tables)") &&
      !sourceWorkbenchSource.includes("const selectedRowFormulas = rowFormulas.filter") &&
      !sourceWorkbenchSource.includes("const calculatedMeasureFields = selectedRowFormulas.map") &&
      !sourceWorkbenchSource.includes("const mergePlan = preview.mergePolicyPreview.mergePlan") &&
      sourceWorkbenchModelSource.includes("export function buildSourceWorkbenchCollections(") &&
      sourceWorkbenchModelSource.includes("export function buildSourceWorkbenchSelection(") &&
      sourceWorkbenchModelSource.includes("export function buildSourceWorkbenchRuntimeSummary(") &&
      sourceWorkbenchModelSource.includes("export function buildImportPreviewSummary(") &&
      implementationStatusSource.includes("Source workbench derived model boundary"),
  },
  {
    label: "frontend-business-first-copy-boundary",
    ok: appSource.includes('import { BusinessPathBar } from "./components/BusinessPathBar"') &&
      appSource.includes("<BusinessPathBar") &&
      appSource.includes("handleOpenBusinessStep") &&
      businessPathModelSource.includes('export type BusinessPathStepKey = "data" | "chart" | "evidence" | "confirm"') &&
      businessPathModelSource.includes("businessSectionForStep") &&
      businessPathModelSource.includes("businessStepForSection") &&
      businessPathBarSource.includes('data-testid="global-business-path"') &&
      businessPathBarSource.includes('data-testid={`business-path-${step.key}`}') &&
      businessPathBarSource.includes("每一步跳到唯一页面处理") &&
      homeOverviewSource.includes("从一条业务路径进入，不在首页重复配置") &&
      homeOverviewSource.includes("同一件事只保留一个承接页") &&
      homeActionDockSource.includes('onOpenStep("chart")') &&
      homeActionDockSource.includes("生成一个图表") &&
      homeOverviewSource.includes("<HomeOperatingSummaryPanel") &&
      homeOperatingSummaryPanelSource.includes("生成证据摘要") &&
      homeOperatingSummaryPanelSource.includes("这些问题会自动使用当前工作区和证据摘要") &&
      homeOperatingSummaryPanelSource.includes("常见问题不用配置") &&
      homeOperatingSummaryPanelSource.includes("动作边界") &&
      sourceWorkbenchHeaderSource.includes("数据入口") &&
      sourceWorkbenchHeaderSource.includes("先检查文件，再让系统生成证据摘要和看板建议") &&
      sourceWorkbenchDataEntryPanelSource.includes("证据摘要") &&
      !sourceWorkbenchDataEntryPanelSource.includes("生成样例摘要") &&
      sourceWorkbenchActionPanelSource.includes("展开字段、公式和关系设置") &&
      sidebarAssetSectionsSource.includes("生成证据摘要") &&
      sidebarAssetSectionsSource.includes("生成证据摘要") &&
      inspectorPanelModelSource.includes("生成摘要、创建看板") &&
      bWidgetKitSource.includes("sourceIntelligenceRuns") &&
      biDashboardWidgetFactorySource.includes("sourceIntelligenceRuns") &&
      bWidgetKitOverviewSource.includes("等待证据摘要") &&
      !sourceWorkbenchSource.includes("一键用 A 项目的 3-5 月全量表格生成画像") &&
      !sourceWorkbenchSource.includes("条可执行指标 SQL") &&
      agentPanelModelSource.includes("数据来源") &&
      agentPanelModelSource.includes("查询回执") &&
      agentPanelModelSource.includes("看板匹配") &&
      !agentPanelSource.includes("Query runtime") &&
      !agentPanelSource.includes("Ontology function") &&
      implementationStatusSource.includes("Global business path component boundary") &&
      implementationStatusSource.includes("Business path model boundary"),
  },
  {
    label: "source-workbench-dashboard-next-action",
    ok: sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-next-action"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-recipe"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-recipe-facts"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-recipe-cards"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-agent-draft"') &&
      sourceWorkbenchGuidanceModelSource.includes("dashboardRecipeCards") &&
      sourceWorkbenchGuidanceModelSource.includes("dashboardRecipeEvidenceCount") &&
      sourceWorkbenchActionPanelSource.includes("证据到看板配方") &&
      sourceWorkbenchActionPanelSource.includes("优先使用") &&
      sourceWorkbenchActionPanelSource.includes('data-testid="source-business-dashboard-preview"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="source-business-dashboard-create"') &&
      sourceWorkbenchActionPanelSource.includes('disabled={!dashboardRecipeReady || busy === "source-business-dashboard-preview"}') &&
      sourceWorkbenchActionPanelSource.includes('disabled={!dashboardRecipeReady || busy === "source-business-dashboard-create"}') &&
      sourceWorkbenchSource.includes("onBusinessDashboardOperation") &&
      sourceWorkbenchSource.includes("op: confirm ? \"create\" : \"draft\"") &&
      sourceWorkbenchSource.includes("onOpenDashboard()") &&
      stylesSource.includes(".sourceDashboardRecipe") &&
      stylesSource.includes(".sourceDashboardRecipeFacts") &&
      stylesSource.includes(".sourceDashboardRecipeCards") &&
      byLabel["cli-business-dashboard-draft"].parsed?.ok === true &&
      Boolean(byLabel["cli-business-dashboard-create-confirm"].parsed?.createdDashboardKey),
  },
  {
    label: "source-workbench-index-agent-draft-entry",
    ok: sourceWorkbenchActionPanelSource.includes('data-testid="source-index-suggestion"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="source-index-agent-draft"') &&
      sourceWorkbenchSource.includes("indexCandidateName") &&
      sourceWorkbenchModelSource.includes("const indexCandidateField = groupFields.find") &&
      sourceWorkbenchModelSource.includes("indexCandidateName: indexCandidateField?.field_name") &&
      sourceWorkbenchActionPanelSource.includes("让 Agent 起草索引") &&
      sourceWorkbenchActionPanelSource.includes("确认前不会创建 DuckDB 索引") &&
      sourceWorkbenchActionPanelSource.includes("onAsk(biText(`给 ${selectedTableKey} 的 ${indexCandidateName} 建索引来优化查询`") &&
      appSource.includes("onAsk={handleAgentCommandAsk}") &&
      stylesSource.includes(".sourceIndexSuggestion") &&
      stylesSource.includes(".sourceIndexFacts") &&
      byLabel["cli-agent-index-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-index-draft"].parsed?.actionDraft?.kind === "index.create",
  },
  {
    label: "source-workbench-agent-question-starter",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchAgentStarter.tsx")) &&
      sourceWorkbenchActionPanelSource.includes('import { SourceWorkbenchAgentStarter, type SourceAgentPrompt } from "./SourceWorkbenchAgentStarter"') &&
      sourceWorkbenchActionPanelSource.includes("<SourceWorkbenchAgentStarter") &&
      !sourceWorkbenchActionPanelSource.includes('data-testid="source-agent-question-starter"') &&
      !sourceWorkbenchActionPanelSource.includes("sourceAgentPrompts.map((item)") &&
      sourceWorkbenchAgentStarterSource.includes("export type SourceAgentPrompt") &&
      sourceWorkbenchAgentStarterSource.includes('import { AgentPromptGrid, type AgentPromptGridItem } from "./AgentPromptGrid"') &&
      sourceWorkbenchAgentStarterSource.includes("<AgentPromptGrid") &&
      sourceWorkbenchAgentStarterSource.includes('data-testid="source-agent-question-starter"') &&
      sourceWorkbenchAgentStarterSource.includes('testId="source-agent-prompt-grid"') &&
      sourceWorkbenchAgentStarterSource.includes('itemTestIdPrefix="source-agent-prompt"') &&
      sourceWorkbenchGuidanceModelSource.includes("const sourceAgentPrompts") &&
      sourceWorkbenchGuidanceModelSource.includes('"can-answer"') &&
      sourceWorkbenchGuidanceModelSource.includes('"find-gaps"') &&
      sourceWorkbenchGuidanceModelSource.includes('"draft-dashboard"') &&
      sourceWorkbenchGuidanceModelSource.includes("不要创建任何草案") &&
      sourceWorkbenchGuidanceModelSource.includes("先不要直接写入") &&
      agentPromptGridSource.includes("export type AgentPromptGridItem") &&
      agentPromptGridSource.includes("export function AgentPromptGrid") &&
      agentPromptGridSource.includes('data-testid={`${itemTestIdPrefix}-${item.key}`}') &&
      agentPromptGridSource.includes("onAsk(item.prompt)") &&
      stylesSource.includes(".sourceAgentStarter") &&
      stylesSource.includes(".agentPromptGrid") &&
      stylesSource.includes(".sourceAgentStarter .agentPromptGrid button"),
  },
  {
    label: "source-workbench-beginner-import-plan",
    ok: sourceWorkbenchActionPanelSource.includes('data-testid="beginner-import-plan"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid={`beginner-plan-${item.key}`}') &&
      !sourceWorkbenchActionPanelSource.includes('data-testid="beginner-plan-check-file"') &&
      !sourceWorkbenchActionPanelSource.includes('data-testid="beginner-plan-import-data"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="beginner-plan-refresh-profile"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="beginner-evidence-guard"') &&
      sourceWorkbenchActionPanelSource.includes('data-testid="source-guide-details"') &&
      sourceWorkbenchActionPanelSource.includes("更多引导和高级建议") &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-summary"') &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-impact"') &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-safety"') &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-confirm"') &&
      sourceWorkbenchImportPanelSource.includes("{previewReadable ? (") &&
      sourceWorkbenchImportPanelSource.includes('disabled={busy === "import-confirm"}') &&
      !sourceWorkbenchActionPanelSource.includes("不可读或未预检时不能确认导入") &&
      /\{hasData \? \(\s*<SourceWorkbenchActionPanel/.test(sourceWorkbenchSource) &&
      stylesSource.includes(".beginnerImportGuard") &&
      stylesSource.includes(".sourceGuideDetails") &&
      sourceWorkbenchImportControllerSource.includes("const previewSummary = buildImportPreviewSummary") &&
      sourceWorkbenchImportControllerSource.includes("...previewSummary") &&
      sourceWorkbenchGuidanceModelSource.includes("const recommendedPrimaryAction") &&
      sourceWorkbenchGuidanceModelSource.includes('"draft-dashboard"') &&
      sourceWorkbenchGuidanceModelSource.includes("sourceProfileComplete") &&
      sourceWorkbenchGuidanceModelSource.includes("previewReadable") &&
      sourceWorkbenchGuidanceModelSource.includes("hasImportedTables") &&
      sourceWorkbenchGuidanceModelSource.includes('measureFields[0]?.field_name ?? ""') &&
      sourceWorkbenchGuidanceModelSource.includes('groupFields[0]?.field_name ?? ""'),
  },
  {
    label: "source-workbench-guidance-model-boundary",
    ok: existsSync(join(root, "src", "sourceWorkbenchGuidanceModel.ts")) &&
      sourceWorkbenchSource.includes('import { buildSourceWorkbenchGuidance } from "../sourceWorkbenchGuidanceModel"') &&
      sourceWorkbenchSource.includes("buildSourceWorkbenchGuidance({") &&
      !sourceWorkbenchSource.includes("const dashboardRecipeCards = [") &&
      !sourceWorkbenchSource.includes("const beginnerPlan = [") &&
      !sourceWorkbenchSource.includes("const sourceAgentPrompts:") &&
      !sourceWorkbenchSource.includes("const hasImportedTables = tables.length > 0") &&
      sourceWorkbenchGuidanceModelSource.includes("export function buildSourceWorkbenchGuidance(") &&
      sourceWorkbenchGuidanceModelSource.includes("export type RecommendedPrimaryAction") &&
      sourceWorkbenchGuidanceModelSource.includes("export type BeginnerPlanItem") &&
      sourceWorkbenchGuidanceModelSource.includes("export type SourceAgentPrompt") &&
      sourceWorkbenchGuidanceModelSource.includes("export type DashboardRecipeCard") &&
      sourceWorkbenchGuidanceModelSource.includes("sourceProfileRunningLabel") &&
      sourceWorkbenchGuidanceModelSource.includes("dashboardRecipeCards") &&
      sourceWorkbenchGuidanceModelSource.includes("beginnerPlan") &&
      sourceWorkbenchGuidanceModelSource.includes("sourceAgentPrompts") &&
      implementationStatusSource.includes("Source workbench guidance model boundary"),
  },
  {
    label: "source-workbench-receipt-model-boundary",
    ok: existsSync(join(root, "src", "sourceWorkbenchReceiptModel.ts")) &&
      sourceWorkbenchImportControllerSource.includes('from "./sourceWorkbenchReceiptModel"') &&
      sourceWorkbenchImportControllerSource.includes("buildImportPreviewReceipt({") &&
      sourceWorkbenchImportControllerSource.includes("buildImportCommitReceipt({") &&
      sourceWorkbenchImportControllerSource.includes("buildImportPolicyReceipt({") &&
      sourceWorkbenchConnectorControllerSource.includes('from "./sourceWorkbenchReceiptModel"') &&
      sourceWorkbenchConnectorControllerSource.includes("buildConnectorSaveReceipt({") &&
      sourceWorkbenchConnectorControllerSource.includes("buildConnectorSyncReceipt(connector, confirm)") &&
      sourceWorkbenchConnectorControllerSource.includes("buildConnectorRemoveReceipt(connector)") &&
      !sourceWorkbenchSource.includes('title: biText("文件检查已完成"') &&
      !sourceWorkbenchSource.includes('title: confirm ? biText("导入已确认"') &&
      !sourceWorkbenchSource.includes('title: confirm ? biText("连接配置已保存"') &&
      !sourceWorkbenchSource.includes('title: confirm ? biText("同步已确认"') &&
      !sourceWorkbenchSource.includes('title: biText("连接删除已确认"') &&
      sourceWorkbenchReceiptModelSource.includes("export type WorkbenchOperationReceipt") &&
      sourceWorkbenchReceiptModelSource.includes("export function buildImportPreviewReceipt(") &&
      sourceWorkbenchReceiptModelSource.includes("export function buildImportCommitReceipt(") &&
      sourceWorkbenchReceiptModelSource.includes("export function buildImportPolicyReceipt(") &&
      sourceWorkbenchReceiptModelSource.includes("export function buildConnectorSaveReceipt(") &&
      sourceWorkbenchReceiptModelSource.includes("export function buildConnectorSyncReceipt(") &&
      sourceWorkbenchReceiptModelSource.includes("export function buildConnectorRemoveReceipt(") &&
      sourceWorkbenchReceiptModelSource.includes("外部源目录") &&
      implementationStatusSource.includes("Source workbench receipt model boundary"),
  },
  {
    label: "source-workbench-command-model-boundary",
    ok: existsSync(join(root, "src", "sourceWorkbenchCommandModel.ts")) &&
      sourceWorkbenchImportControllerSource.includes('from "./sourceWorkbenchCommandModel"') &&
      sourceWorkbenchImportControllerSource.includes("buildImportOptions({") &&
      sourceWorkbenchImportControllerSource.includes("buildImportPolicyOptions({") &&
      sourceWorkbenchSource.includes('from "../sourceWorkbenchCommandModel"') &&
      sourceWorkbenchSource.includes("buildSourceProfileOptions({") &&
      sourceWorkbenchConnectorControllerSource.includes("buildConnectorOptions({") &&
      sourceWorkbenchSource.includes("buildMetricDraft({") &&
      !sourceWorkbenchSource.includes("uniqueFields: splitCsv(uniqueFields)") &&
      !sourceWorkbenchSource.includes("inputs: splitInputPaths(sourceProfileInputs)") &&
      !sourceWorkbenchSource.includes("connector: connectorEditingKey || undefined") &&
      !sourceWorkbenchSource.includes("dimension: effectiveMetricDimension || undefined") &&
      sourceWorkbenchCommandModelSource.includes("export type ImportOptions") &&
      sourceWorkbenchCommandModelSource.includes("export type ImportPolicyOptions") &&
      sourceWorkbenchCommandModelSource.includes("export type ConnectorOptions") &&
      sourceWorkbenchCommandModelSource.includes("export type { SourceIntelligenceRunOptions }") &&
      sourceWorkbenchCommandModelSource.includes("export type MetricMutationOptions") &&
      sourceWorkbenchCommandModelSource.includes("export function buildImportOptions(") &&
      sourceWorkbenchCommandModelSource.includes("export function buildImportPolicyOptions(") &&
      sourceWorkbenchCommandModelSource.includes("export function buildSourceProfileOptions(") &&
      sourceWorkbenchCommandModelSource.includes("export function buildConnectorOptions(") &&
      sourceWorkbenchCommandModelSource.includes("export function buildMetricDraft(") &&
      sourceWorkbenchCommandModelSource.includes("splitCsv(uniqueFields)") &&
      sourceWorkbenchCommandModelSource.includes("splitCsv(connectorUniqueFields)") &&
      sourceWorkbenchCommandModelSource.includes("inputs: splitInputPaths(sourceProfileInputs)") &&
      sourceWorkbenchCommandModelSource.includes('label: sourceProfileLabel.trim() || "Source profile"') &&
      implementationStatusSource.includes("Source workbench command model boundary"),
  },
  {
    label: "source-intelligence-run-model-boundary",
    ok: existsSync(join(root, "src", "sourceIntelligenceRunModel.ts")) &&
      sourceIntelligenceRunModelSource.includes("export type SourceIntelligenceRunRequest") &&
      sourceIntelligenceRunModelSource.includes("export type SourceIntelligenceRunOptions") &&
      !sourceIntelligenceRunModelSource.includes("SOURCE_INTELLIGENCE_A_TESTDATA") &&
      !sourceIntelligenceRunModelSource.includes("aTestdata0305") &&
      apiSourceApiSource.includes('import type { SourceIntelligenceRunRequest } from "./sourceIntelligenceRunModel"') &&
      !appDataActionsSource.includes("aTestdata0305SourceIntelligenceRequest()") &&
      !homeOverviewSource.includes("aTestdata0305SourceIntelligenceOptions({") &&
      evidenceViewSource.includes("type { SourceIntelligenceRunOptions }") &&
      homeProductIntelligencePanelSource.includes("type { SourceIntelligenceRunOptions }") &&
      !metricSemanticRepairActionsSource.includes("aTestdata0305SourceIntelligenceOptions({") &&
      sourceWorkbenchActionPanelSource.includes('from "../sourceIntelligenceRunModel"') &&
      sourceWorkbenchDataEntryPanelSource.includes('from "../sourceIntelligenceRunModel"') &&
      !sourceWorkbenchHeaderSource.includes('from "../sourceIntelligenceRunModel"') &&
      !sourceWorkbenchGuidanceModelSource.includes("SOURCE_INTELLIGENCE_A_TESTDATA_COMMAND") &&
      !sourceWorkbenchActionPanelSource.includes("type SourceIntelligenceRunOptions =") &&
      !sourceWorkbenchDataEntryPanelSource.includes("type SourceIntelligenceRunOptions =") &&
      !metricSemanticRepairActionsSource.includes("type SourceIntelligenceOptions =") &&
      implementationStatusSource.includes("Source Intelligence run model boundary"),
  },
  {
    label: "source-workbench-contracts-boundary",
    ok: existsSync(join(root, "src", "sourceWorkbenchContracts.ts")) &&
      sourceWorkbenchSource.includes('from "../sourceWorkbenchContracts"') &&
      sourceWorkbenchSource.includes("type { QueryOptions, SourceWorkbenchProps }") &&
      !sourceWorkbenchSource.includes("type SourceWorkbenchProps =") &&
      !sourceWorkbenchSource.includes("type SemanticSetOptions =") &&
      !sourceWorkbenchSource.includes("type MetricQueryOptions =") &&
      sourceWorkbenchContractsSource.includes("export type SourceWorkbenchProps") &&
      sourceWorkbenchContractsSource.includes("export type QueryOptions") &&
      sourceWorkbenchContractsSource.includes("export type FieldUpdateOptions") &&
      sourceWorkbenchContractsSource.includes("export type SemanticInferOptions") &&
      sourceWorkbenchContractsSource.includes("export type SemanticSetOptions") &&
      sourceWorkbenchContractsSource.includes("export type MetricQueryOptions") &&
      sourceWorkbenchContractsSource.includes("onSourceIntelligenceRun: (options?: SourceIntelligenceRunOptions)") &&
      implementationStatusSource.includes("Source workbench contracts boundary"),
  },
  {
    label: "source-workbench-draft-model-boundary",
    ok: existsSync(join(root, "src", "sourceWorkbenchDraftModel.ts")) &&
      sourceWorkbenchSource.includes('from "../sourceWorkbenchDraftModel"') &&
      sourceWorkbenchSource.includes("readFieldDraft(fieldDrafts, field)") &&
      sourceWorkbenchSource.includes("applyFieldDraftPatch(current, field, patch)") &&
      sourceWorkbenchSource.includes("buildNavigationOperationOptions({") &&
      sourceWorkbenchSource.includes("managedSourceDisplayName(tables, tableKey)") &&
      !sourceWorkbenchSource.includes("fieldDrafts[`${field.table_key}.${field.field_name}`]") &&
      !sourceWorkbenchSource.includes("const key = `${field.table_key}.${field.field_name}`") &&
      !sourceWorkbenchSource.includes("moduleKey = activeNavigationModule?.moduleKey") &&
      !sourceWorkbenchSource.includes("Number(navigationSort || activeNavigationModule?.sort || 0)") &&
      !sourceWorkbenchSource.includes("tables.find((item) => item.table_key === tableKey)") &&
      sourceWorkbenchDraftModelSource.includes("export type FieldDraft") &&
      sourceWorkbenchDraftModelSource.includes("export type FieldDrafts") &&
      sourceWorkbenchDraftModelSource.includes("export type NavigationOperation") &&
      sourceWorkbenchDraftModelSource.includes("export function fieldDraftKey(") &&
      sourceWorkbenchDraftModelSource.includes("export function readFieldDraft(") &&
      sourceWorkbenchDraftModelSource.includes("export function applyFieldDraftPatch(") &&
      sourceWorkbenchDraftModelSource.includes("export function managedSourceDisplayName(") &&
      sourceWorkbenchDraftModelSource.includes("export function buildNavigationOperationOptions(") &&
      sourceWorkbenchDraftModelSource.includes("activeNavigationModule?.moduleKey ?? navigationModuleKey") &&
      sourceWorkbenchDraftModelSource.includes("Number(navigationSort || activeNavigationModule?.sort || 0)") &&
      implementationStatusSource.includes("Source workbench draft model boundary"),
  },
  {
    label: "source-workbench-action-panel-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchActionPanel.tsx")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchActionPanel } from "./SourceWorkbenchActionPanel"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchActionPanel") &&
      !sourceWorkbenchSource.includes('data-testid="source-agent-question-starter"') &&
      !sourceWorkbenchSource.includes('data-testid="source-dashboard-next-action"') &&
      !sourceWorkbenchSource.includes('data-testid="source-index-suggestion"') &&
      !sourceWorkbenchSource.includes('data-testid="beginner-import-plan"') &&
      sourceWorkbenchActionPanelSource.includes("type SourceWorkbenchActionPanelProps") &&
      sourceWorkbenchActionPanelSource.includes('type SourceAgentPrompt } from "./SourceWorkbenchAgentStarter"') &&
      sourceWorkbenchActionPanelSource.includes("type DashboardRecipeCard") &&
      sourceWorkbenchActionPanelSource.includes("RecommendedPrimaryAction") &&
      sourceWorkbenchActionPanelSource.includes("runBusinessDashboard: (confirm: boolean) => Promise<void>") &&
      sourceWorkbenchActionPanelSource.includes("runSourceProfile: (label: string, options: SourceIntelligenceRunOptions) => Promise<void>") &&
      sourceWorkbenchActionPanelSource.includes("<SourceWorkbenchAgentStarter") &&
      sourceWorkbenchActionPanelSource.includes("dashboardRecipeCards.map((card)") &&
      sourceWorkbenchActionPanelSource.includes("setShowAdvanced((current) => !current)") &&
      implementationStatusSource.includes("Source workbench action panel boundary"),
  },
  {
    label: "source-workbench-import-panel-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchImportPanel.tsx")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchImportPanel } from "./SourceWorkbenchImportPanel"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchImportPanel") &&
      !sourceWorkbenchSource.includes('data-testid="import-confirmation-summary"') &&
      !sourceWorkbenchSource.includes('data-testid="import-operation-receipt"') &&
      sourceWorkbenchImportPanelSource.includes("type SourceWorkbenchImportPanelProps") &&
      sourceWorkbenchImportPanelSource.includes("ReturnType<typeof useSourceWorkbenchImportController>") &&
      sourceWorkbenchImportControllerSource.includes("importPolicies: ImportPolicy[]") &&
      sourceWorkbenchImportControllerSource.includes("async function runImportPreviewAction()") &&
      sourceWorkbenchImportControllerSource.includes("async function runImportCommitAction(confirm: boolean)") &&
      sourceWorkbenchImportControllerSource.includes("async function runImportPolicyAction(confirm: boolean)") &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-policy-dry-run-button"') &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-policy-confirm-button"') &&
      sourceWorkbenchImportPanelSource.includes("确认后才写入工作区") &&
      sourceWorkbenchImportPanelSource.includes("当前只做检查，不写入") &&
      sourceWorkbenchImportPanelSource.includes("View import policy and receipt") &&
      sourceWorkbenchImportPanelSource.includes("countText(importInsertRows)") &&
      implementationStatusSource.includes("Source workbench import panel boundary"),
  },
  {
    label: "b-navigation-module-workflow",
    ok: byLabel["cli-list-navigation"].parsed?.navigation?.some((module) => module.moduleKey === "table:orders" && module.type === "table") &&
      byLabel["cli-list-navigation"].parsed?.navigation?.some((module) => module.moduleKey === "dashboard:default" && module.type === "dashboard") &&
      byLabel["cli-navigation-rename-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-navigation-rename-confirm"].parsed?.navigationModule?.name === "验证导航订单" &&
      byLabel["cli-navigation-move-dry-run"].parsed?.proposedModule?.sort === 88 &&
      byLabel["cli-navigation-move-confirm"].parsed?.navigationModule?.sort === 88 &&
      byLabel["cli-navigation-hide-dry-run"].parsed?.proposedModule?.enabled === false &&
      byLabel["cli-navigation-hide-confirm"].parsed?.navigationModule?.enabled === false &&
      byLabel["cli-navigation-show-dry-run"].parsed?.currentModule?.enabled === false &&
      byLabel["cli-navigation-show-dry-run"].parsed?.proposedModule?.enabled === true &&
      byLabel["cli-navigation-show-confirm"].parsed?.navigationModule?.enabled === true &&
      byLabel["cli-navigation-move-restore"].parsed?.navigationModule?.sort === 10 &&
      byLabel["cli-navigation-rename-restore"].parsed?.navigationModule?.name === "Orders" &&
      !biCliSource.includes("enabled = 1,\n                updated_at = ?"),
  },
  {
    label: "b-query-table-and-saved-views",
    ok: byLabel["cli-query-table-detail"].parsed?.tableQuery?.filteredRows === 4 &&
      byLabel["cli-query-table-detail"].parsed?.tableQuery?.rows?.[0]?.net_sales === "1280" &&
      byLabel["cli-query-table-view"].parsed?.tableQuery?.viewKey === "view_orders_default" &&
      byLabel["cli-list-views"].parsed?.savedViews?.length >= 2 &&
      byLabel["cli-save-view-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-save-view-confirm"].parsed?.confirmed === true,
  },
  {
    label: "b-dashboard-widget-catalog-complete",
    ok: ["metric", "bar", "line", "pie", "table", "text", "slicer"].every((type) => byLabel["cli-dashboard-widget-catalog"].parsed?.widgetTypes?.includes(type)) &&
      ["table", "view", "relationship"].every((mode) => byLabel["cli-dashboard-widget-catalog"].parsed?.dataModes?.includes(mode)) &&
      byLabel["cli-dashboard-widget-catalog"].parsed?.catalog?.length === 7 &&
      byLabel["cli-dashboard-widget-catalog"].parsed?.integration?.agentPolicy?.includes("action drafts"),
  },
  {
    label: "b-dashboard-widget-write-cycle",
    ok: byLabel["cli-recommend-widgets"].parsed?.recommendations?.length >= 6 &&
      byLabel["cli-add-recommended-widgets-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-add-recommended-widgets-dry-run"].parsed?.plannedCount >= 2 &&
      byLabel["cli-add-widget-view-dry-run"].parsed?.proposedWidget?.config?.dataMode === "view" &&
      byLabel["cli-add-widget-view-confirm"].parsed?.confirmed === true &&
      byLabel["cli-add-widget-view-confirm"].parsed?.addedWidget?.widget_key === "verify_view_widget" &&
      byLabel["cli-set-widget-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-set-widget-dry-run"].parsed?.proposedWidget?.title === "验证视图组件更新" &&
      byLabel["cli-set-widget-dry-run"].parsed?.proposedWidget?.config?.subtitle === "验证配置编辑" &&
      byLabel["cli-set-widget-dry-run"].parsed?.proposedWidget?.config?.topN === 20 &&
      byLabel["cli-set-widget-dry-run"].parsed?.proposedWidget?.config?.valueFormat === "currency" &&
      byLabel["cli-set-widget-filter-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-set-widget-filter-dry-run"].parsed?.proposedWidget?.config?.filters?.[0]?.field === "channel" &&
      byLabel["cli-set-widget-filter-confirm"].parsed?.confirmed === true &&
      byLabel["cli-set-widget-clear-filter-dry-run"].parsed?.requiresConfirmation === true &&
      Array.isArray(byLabel["cli-set-widget-clear-filter-dry-run"].parsed?.proposedWidget?.config?.filters) &&
      byLabel["cli-set-widget-clear-filter-dry-run"].parsed?.proposedWidget?.config?.filters.length === 0 &&
      byLabel["cli-copy-widget-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-remove-widget-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "b-dashboard-widget-style-controls",
    ok: byLabel["cli-set-widget-style-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.colorPalette === "contrast" &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.barOrientation === "horizontal" &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.rankingMode === "ranked" &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.showDataLabel === true &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.showLegend === false &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.showAxis === false &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.areaFill === true &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.pieShape === "pie" &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.slicerDisplay === "dropdown" &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.decimalPlaces === 1 &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.tableColumnLimit === 8 &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.xAxisTitle === "渠道" &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.yAxisTitle === "净销售额" &&
      byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.legendTitle === "渠道分类" &&
      byLabel["cli-set-widget-style-confirm"].parsed?.confirmed === true &&
      byLabel["cli-set-widget-style-confirm"].parsed?.updatedWidget?.config?.colorPalette === "contrast",
  },
  {
    label: "b-dashboard-modules-bulk-save-cycle",
    ok: byLabel["cli-save-dashboard-modules-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-save-dashboard-modules-dry-run"].parsed?.proposed?.widgetCount === 2 &&
      byLabel["cli-save-dashboard-modules-dry-run"].parsed?.proposed?.canvasWidthMode === "center" &&
      byLabel["cli-save-dashboard-modules-confirm"].parsed?.confirmed === true &&
      byLabel["cli-save-dashboard-modules-confirm"].parsed?.savedDashboardModules === 2 &&
      byLabel["cli-save-dashboard-modules-confirm"].parsed?.savedDashboardFilters === 1 &&
      byLabel["cli-save-dashboard-modules-confirm"].parsed?.dashboard?.layout?.canvasWidthMode === "center" &&
      byLabel["cli-save-dashboard-modules-confirm"].parsed?.dashboard?.widgets?.some((widget) => widget.widget_key === "verify_bulk_metric" && widget.config?.layout?.i === "verify_bulk_metric") &&
      byLabel["cli-dashboards-after-module-save"].parsed?.dashboards?.[0]?.widgets?.length === 2 &&
      byLabel["cli-dashboards-after-module-save"].parsed?.dashboards?.[0]?.layout?.globalFilters?.[0]?.field === "channel",
  },
  {
    label: "b-business-dashboard-template-cycle",
    ok: byLabel["cli-business-dashboard-draft"].parsed?.templateCount >= 5 &&
      byLabel["cli-business-dashboard-draft"].parsed?.draft?.templates?.some((template) => template.type === "slicer") &&
      byLabel["cli-business-dashboard-create-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-business-dashboard-create-dry-run"].parsed?.proposed?.widgetCount >= 5 &&
      byLabel["cli-business-dashboard-create-confirm"].parsed?.confirmed === true &&
      Boolean(byLabel["cli-business-dashboard-create-confirm"].parsed?.createdDashboardKey) &&
      byLabel["cli-business-dashboard-create-confirm"].parsed?.savedDashboardModules >= 5 &&
      byLabel["cli-business-dashboard-overwrite-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "b-dashboard-relationship-widget-write-cycle",
    ok: byLabel["cli-add-relationship-widget-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-add-relationship-widget-dry-run"].parsed?.proposedWidget?.config?.dataMode === "relationship" &&
      byLabel["cli-add-relationship-widget-dry-run"].parsed?.proposedWidget?.config?.relationship?.relationKey === "orders_refunds_order_id_order_id" &&
      byLabel["cli-add-relationship-widget-confirm"].parsed?.confirmed === true &&
      byLabel["cli-add-relationship-widget-confirm"].parsed?.addedWidget?.widget_key === "verify_relationship_widget" &&
      byLabel["cli-add-relationship-widget-confirm"].parsed?.addedWidget?.config?.relationship?.leftTableKey === "orders",
  },
  {
    label: "b-relationship-recommendation-cycle",
    ok: byLabel["cli-recommend-relationships"].parsed?.dryRun === true &&
      byLabel["cli-recommend-relationships"].parsed?.recommendations?.some((recommendation) =>
        recommendation.leftTableKey === "orders" &&
        recommendation.rightTableKey === "refunds" &&
        recommendation.fieldMappings?.some((mapping) => mapping.leftField === mapping.rightField) &&
        typeof recommendation.previewMetrics?.confidence === "number"
      ),
  },
  {
    label: "b-field-semantic-metric-management",
    ok: byLabel["cli-infer-semantics-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-infer-semantics-dry-run"].parsed?.proposed >= 8 &&
      byLabel["cli-set-semantic-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-set-semantic-confirm"].parsed?.confirmed === true &&
      byLabel["cli-set-semantic-confirm"].parsed?.semantic?.field === "sku" &&
      byLabel["cli-set-semantic-confirm"].parsed?.semantic?.tags?.includes("product") &&
      byLabel["cli-list-semantics"].parsed?.semantics?.some((semantic) => semantic.field === "sku" && semantic.source === "manual") &&
      byLabel["cli-infer-metrics-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-infer-metrics-confirm"].parsed?.saved >= 4 &&
      byLabel["cli-list-metrics"].parsed?.metrics?.some((metric) => metric.metricKey === "orders_net_sales_sum" && metric.dimension === "channel") &&
      byLabel["cli-add-metric-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-add-metric-confirm"].parsed?.confirmed === true &&
      byLabel["cli-add-metric-confirm"].parsed?.savedMetric?.metricKey === "verify_avg_net_sales" &&
      byLabel["cli-query-metric"].parsed?.tableQuery?.rows?.some((row) => row.channel === "Douyin" && Number(row.sum_net_sales) === 3440),
  },
  {
    label: "b-bi-cli-bridge-core-areas",
    ok: ["source-management", "query-runtime", "saved-views", "dashboard-pages", "dashboard-widgets", "filters", "performance-indexes", "relationships", "import", "field-metric-formula", "connectors-preferences", "config-portability"].every((area) =>
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === area && capability.status === "active")
    ) &&
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "dashboard-widgets" && capability.hybridCommands?.includes("add-relationship-widget") && capability.hybridCommands?.includes("save-dashboard-modules") && capability.hybridCommands?.includes("business-dashboard")) &&
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "filters" && capability.hybridCommands?.includes("remove-stale-filters")) &&
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "performance-indexes" && capability.hybridCommands?.includes("recommend-indexes") && capability.hybridCommands?.includes("create-index")) &&
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "relationships" && capability.hybridCommands?.includes("recommend-relationships") && capability.hybridCommands?.includes("query-relationship")) &&
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "import" && capability.hybridCommands?.includes("set-import-policy") && capability.hybridCommands?.includes("list-import-jobs")) &&
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "field-metric-formula" && capability.hybridCommands?.includes("infer-semantics") && capability.hybridCommands?.includes("set-semantic") && capability.hybridCommands?.includes("infer-metrics") && capability.hybridCommands?.includes("query-metric")) &&
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "connectors-preferences" && capability.hybridCommands?.includes("save-connector") && capability.hybridCommands?.includes("sync-connector") && capability.hybridCommands?.includes("preferences") && capability.hybridCommands?.includes("theme-palettes")) &&
      byLabel["cli-b-cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "config-portability" && capability.hybridCommands?.includes("validate-config") && capability.hybridCommands?.includes("export-config") && capability.hybridCommands?.includes("apply-config")) &&
      byLabel["cli-b-cli-capabilities"].parsed?.source?.executionPolicy?.includes("Do not execute external BI CLIs"),
  },
  {
    label: "frontend-field-semantic-readiness",
    ok: sourceWorkbenchSource.includes("buildFieldSemanticReadiness(selectedFields)") &&
      sourceWorkbenchModelSource.includes("export function buildFieldSemanticReadiness") &&
      sourceWorkbenchFieldMetricPanelSource.includes("<SourceWorkbenchFieldSemanticPanel") &&
      sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-readiness"') &&
      sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-readiness-cards"') &&
      sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-ready"') &&
      sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-relationship"') &&
      sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-review"') &&
      sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-agent-review"') &&
      sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-technical-details"') &&
      sourceWorkbenchFieldSemanticPanelSource.includes("检查字段用途") &&
      sourceWorkbenchFieldSemanticPanelSource.includes("逐字段调整") &&
      !sourceWorkbenchSource.includes("semantic.set 草案") &&
      stylesSource.includes(".fieldSemanticReadiness") &&
      stylesSource.includes(".fieldSemanticCards") &&
      stylesSource.includes(".fieldSemanticCard.review") &&
      stylesSource.includes(".fieldSemanticTechnical"),
  },
  {
    label: "b-dashboard-filters-write-boundary",
    ok: byLabel["cli-filter-add-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-filter-add-confirm"].parsed?.confirmed === true &&
      byLabel["cli-filter-list"].parsed?.filters?.some((filter) => filter.field === "channel" && filter.value === "Douyin") &&
      byLabel["cli-filter-remove-stale-dry-run"].parsed?.requiresConfirmation === true &&
      Array.isArray(byLabel["cli-filter-remove-stale-dry-run"].parsed?.staleFilters) &&
      byLabel["cli-filter-clear-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "b-performance-indexes-duckdb-boundary",
    ok: byLabel["cli-recommend-indexes"].parsed?.recommendations?.some((item) => item.field === "channel" && item.engine === "duckdb") &&
      byLabel["cli-create-index-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-create-index-dry-run"].parsed?.proposed?.engine === "duckdb" &&
      byLabel["cli-create-index-confirm"].parsed?.confirmed === true &&
      byLabel["cli-create-index-confirm"].parsed?.createdIndex?.field === "channel" &&
      byLabel["cli-create-index-confirm"].parsed?.syncedRows >= 1,
  },
  {
    label: "frontend-widget-filter-routing",
    ok: byLabel["frontend-widget-filter-model"].parsed?.ok === true &&
      byLabel["frontend-widget-filter-model"].parsed?.localRows?.[0]?.label === "Douyin" &&
      byLabel["frontend-widget-filter-model"].parsed?.globalRows?.[0]?.label === "JD",
  },
  {
    label: "frontend-slicer-cross-filter-routing",
    ok: byLabel["frontend-slicer-cross-filter-model"].parsed?.ok === true &&
      byLabel["frontend-slicer-cross-filter-model"].parsed?.slicer?.drillDown === false &&
      byLabel["frontend-slicer-cross-filter-model"].parsed?.slicer?.globalFilterTarget === true &&
      byLabel["frontend-slicer-cross-filter-model"].parsed?.filtered?.[0]?.label === "JD",
  },
  {
    label: "frontend-relationship-widget-hydration",
    ok: byLabel["frontend-relationship-widget-model"].parsed?.ok === true &&
      byLabel["frontend-relationship-widget-model"].parsed?.relationship?.relationKey === "orders_refunds_order_id_order_id",
  },
  {
    label: "frontend-b-widget-kit-all-types",
    ok: bWidgetKitSource.includes("<BiDashboardWidgetCard") &&
      !bWidgetKitSource.includes("data-testid={`b-widget-${widget.type}`}") &&
      bDashboardWidgetCardSource.includes("data-testid={`b-widget-${widget.type}`}") &&
      bWidgetKitSource.includes("<BiDashboardWidgetKitOverview") &&
      bWidgetKitOverviewSource.includes("data-testid=\"b-dashboard-read-path\"") &&
      bWidgetKitOverviewSource.includes("B_WIDGET_READING_PURPOSES") &&
      bWidgetKitModelSource.includes("export const B_WIDGET_READING_PURPOSES") &&
      bWidgetKitOverviewSource.includes("不用先学组件配置") &&
      bWidgetKitSource.includes("evidenceState") &&
      bDashboardWidgetCardSource.includes("queryRelationship") &&
      bDashboardWidgetCardSource.includes('from "../biDashboardPresentation"') &&
      biDashboardPresentationSource.includes("export function formatWidgetValue") &&
      biDashboardPresentationSource.includes("export function paletteColors") &&
      biDashboardPresentationSource.includes("export function catalogByType") &&
      biDashboardPresentationSource.includes("const paletteMap") &&
      existsSync(join(root, "src", "biDashboardValueModel.ts")) &&
      biDashboardValueModelSource.includes("export function toStringValue") &&
      biDashboardModelSource.includes('import { toStringValue } from "./biDashboardValueModel"') &&
      biDashboardWidgetFactorySource.includes('import { toStringValue } from "./biDashboardValueModel"') &&
      !biDashboardModelSource.includes("function toStringValue(") &&
      !biDashboardWidgetFactorySource.includes("function toStringValue(") &&
      !biDashboardModelSource.includes("export function formatWidgetValue") &&
      !biDashboardModelSource.includes("export function paletteColors") &&
      !biDashboardModelSource.includes("export function catalogByType") &&
      !biDashboardModelSource.includes("const paletteMap") &&
      bDashboardWidgetCardSource.includes('from "../biDashboardRuntime"') &&
      biDashboardModelSource.includes('export { buildBiDashboardWidgets } from "./biDashboardWidgetFactory"') &&
      biDashboardWidgetFactorySource.includes("export function buildBiDashboardWidgets") &&
      biDashboardWidgetFactorySource.includes("function hydrateStoredWidget") &&
      biDashboardWidgetFactorySource.includes("function relationshipForWidget") &&
      biDashboardWidgetFactorySource.includes("function baseWidget") &&
      biDashboardWidgetFactorySource.includes('import { safeQueryInfo } from "./biDashboardRuntime"') &&
      !biDashboardModelSource.includes('import { safeQueryInfo } from "./biDashboardRuntime"') &&
      !biDashboardModelSource.includes("function hydrateStoredWidget") &&
      !biDashboardModelSource.includes("function relationshipForWidget") &&
      !biDashboardModelSource.includes("function baseWidget") &&
      biDashboardRuntimeSource.includes("export function aggregateWidgetRows") &&
      biDashboardRuntimeSource.includes("export function calculateWidgetMetricValue") &&
      biDashboardRuntimeSource.includes("export function applyBiDashboardFilters") &&
      biDashboardRuntimeSource.includes("export function rowsFromQuery") &&
      !biDashboardModelSource.includes("export function aggregateWidgetRows") &&
      !biDashboardModelSource.includes("export function calculateWidgetMetricValue") &&
      !biDashboardModelSource.includes("export function applyBiDashboardFilters") &&
      !biDashboardModelSource.includes("export function rowsFromQuery") &&
      implementationStatusSource.includes("Dashboard value helper boundary") &&
      implementationStatusSource.includes("Dashboard runtime model boundary") &&
      implementationStatusSource.includes("Dashboard widget factory boundary") &&
      bWidgetKitSource.includes("data-testid=\"b-slicer-selection-bar\"") &&
      dashboardBusinessTemplatePanelSource.includes("data-testid=\"business-template-panel\"") &&
      dashboardRelationshipRecommendationPanelSource.includes("data-testid=\"relationship-recommendation-panel\"") &&
      ["metric", "bar", "line", "pie", "table", "text", "slicer"].every((type) => bWidgetKitOverviewSource.includes(`b-read-path-${type}`) || bWidgetKitOverviewSource.includes("data-testid={`b-read-path-${item.type}`}")) &&
      ["metric", "bar", "line", "pie", "table", "text", "slicer"].every((type) => bWidgetModelSource.includes(`"${type}"`)) &&
      bWidgetModelSource.includes("B_DASHBOARD_WIDGET_CATALOG") &&
      bWidgetModelSource.includes("B_DASHBOARD_DATA_MODES") &&
      stylesSource.includes(".bReadPath") &&
      stylesSource.includes(".bReadPathSteps") &&
      stylesSource.includes(".bReadPathStep.ready") &&
      stylesSource.includes(".bPieLegend button") &&
      stylesSource.includes("min-height: 30px") &&
      implementationStatusSource.includes("Dashboard widget card boundary"),
  },
  {
    label: "frontend-relationship-impact-panel",
    ok: sourceWorkbenchRelationshipPanelSource.includes("data-testid=\"relationship-impact-panel\"") &&
      sourceWorkbenchRelationshipPanelSource.includes("data-testid=\"relationship-recommendation-apply-card\"") &&
      sourceWorkbenchRelationshipPanelSource.includes("data-testid=\"relationship-apply-recommendation\"") &&
      sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-technical-details"') &&
      sourceWorkbenchRelationshipPanelSource.includes("applyRelationshipRecommendation") &&
      sourceWorkbenchRelationshipPanelSource.includes("relationshipDecisionState") &&
      sourceWorkbenchRelationshipPanelSource.includes("保存业务连接") &&
      sourceWorkbenchRelationshipPanelSource.includes("受控关联查询") &&
      sourceWorkbenchRelationshipPanelSource.includes("可连接键") &&
      sourceWorkbenchRelationshipPanelSource.includes("匹配度") &&
      sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-diagnostics-technical"') &&
      sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-warning-details"') &&
      stylesSource.includes(".relationshipImpactPanel") &&
      stylesSource.includes(".relationshipRecommendationCard") &&
      stylesSource.includes(".relationshipTechnicalDetails") &&
      stylesSource.includes(".relationshipDiagnosticsTechnical"),
  },
  {
    label: "frontend-source-advanced-business-controls",
    ok: sourceWorkbenchQueryFormulaPanelSource.includes("计算字段和指标") &&
      sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="formula-technical-details"') &&
      sourceWorkbenchQueryFormulaPanelSource.includes("查看编译后的查询") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("Preview save") &&
      !sourceWorkbenchSource.includes("Formula DSL") &&
      !sourceWorkbenchSource.includes("Dry-run save") &&
      !sourceWorkbenchSource.includes("Dry-run delete") &&
      stylesSource.includes(".formulaTechnicalDetails"),
  },
  {
    label: "frontend-relationship-auto-model-graph",
    ok: existsSync(join(root, "src", "components", "RelationshipAutoModelGraph.tsx")) &&
      existsSync(join(root, "src", "relationshipAutoModelGraphModel.ts")) &&
      sourceWorkbenchRelationshipPanelSource.includes('import { RelationshipAutoModelGraph } from "./RelationshipAutoModelGraph"') &&
      sourceWorkbenchRelationshipPanelSource.includes("<RelationshipAutoModelGraph") &&
      relationshipAutoModelGraphSource.includes("export function RelationshipAutoModelGraph") &&
      relationshipAutoModelGraphSource.includes('from "../relationshipAutoModelGraphModel"') &&
      relationshipAutoModelGraphSource.includes("buildRelationshipAutoModelGraphViewModel") &&
      relationshipAutoModelGraphSource.includes('data-testid="relationship-auto-graph"') &&
      relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-canvas"') &&
      relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-edge"') &&
      relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-best-apply"') &&
      relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-best-preview"') &&
      relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-best-confirm"') &&
      !relationshipAutoModelGraphSource.includes("function recommendationToEdge(") &&
      relationshipAutoModelGraphModelSource.includes("export function buildRelationshipAutoModelGraphViewModel") &&
      relationshipAutoModelGraphModelSource.includes("export function relationshipSaveOptions") &&
      relationshipAutoModelGraphModelSource.includes("export function topRelationshipNodeFields") &&
      relationshipAutoModelGraphModelSource.includes("buildRelationshipSavePayload") &&
      relationshipAutoModelGraphModelSource.includes("relationshipPrimaryMapping") &&
      relationshipAutoModelGraphSource.includes("AI 自动连线") &&
      relationshipAutoModelGraphSource.includes("手动选字段放在高级编辑里") &&
      relationshipAutoModelGraphSource.includes("runBusy(label, () => onRelationshipPreview(options))") &&
      relationshipAutoModelGraphSource.includes("runBusy(label, () => onRelationshipSave({ ...options, confirm }))") &&
      stylesSource.includes(".relationshipAutoGraph") &&
      stylesSource.includes(".relationshipGraphEdgeRow") &&
      stylesSource.includes(".relationshipGraphConnector") &&
      stylesSource.includes("container-name: relationship-model") &&
      stylesSource.includes("@container relationship-model (max-width: 820px)") &&
      implementationStatusSource.includes("Relationship auto model view-model boundary") &&
      implementationStatusSource.includes("Source visual relationship auto-modeling"),
  },
  {
    label: "frontend-source-operations-business-controls",
    ok: sourceWorkbenchOperationsPanelSource.includes("整理左侧入口") &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-technical-details"') &&
      sourceWorkbenchOperationsPanelSource.includes("页面显示和顺序") &&
      !sourceWorkbenchOperationsPanelSource.includes("调整顺序和技术目标") &&
      sourceWorkbenchOperationsPanelSource.includes("入口改动预览已生成") &&
      sourceWorkbenchConnectorPanelSource.includes("保存数据连接") &&
      sourceWorkbenchConnectorPanelSource.includes('data-testid="connector-business-lead"') &&
      sourceWorkbenchConnectorPanelSource.includes('data-testid="connector-technical-details"') &&
      sourceWorkbenchConnectorPanelSource.includes("清理导入记录") &&
      sourceWorkbenchConnectorPanelSource.includes("预览清理") &&
      sourceWorkbenchImportPanelSource.includes("Current state is preview") &&
      sourceWorkbenchConnectorControllerSource.includes("WorkbenchOperationReceipt") &&
      sourceWorkbenchImportControllerSource.includes("runImportPreviewAction") &&
      sourceWorkbenchImportControllerSource.includes("runImportCommitAction") &&
      sourceWorkbenchImportControllerSource.includes("runImportPolicyAction") &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-operation-receipt"') &&
      sourceWorkbenchImportPanelSource.includes('data-testid="import-operation-technical-details"') &&
      sourceWorkbenchImportPanelSource.includes("确认后才写入工作区") &&
      sourceWorkbenchImportPanelSource.includes("当前只做检查，不写入") &&
      sourceWorkbenchImportPanelSource.includes("View import policy and receipt") &&
      sourceWorkbenchConnectorControllerSource.includes("runConnectorSaveAction") &&
      sourceWorkbenchConnectorControllerSource.includes("runConnectorSyncAction") &&
      sourceWorkbenchConnectorControllerSource.includes("runConnectorRemoveAction") &&
      sourceWorkbenchConnectorPanelSource.includes('data-testid="connector-operation-receipt"') &&
      sourceWorkbenchConnectorPanelSource.includes('data-testid="connector-operation-technical-details"') &&
      sourceWorkbenchConnectorPanelSource.includes("同步数据仍然需要先预览，再确认") &&
      !sourceWorkbenchSource.includes("Dry-run rename") &&
      !sourceWorkbenchSource.includes("Dry-run move") &&
      !sourceWorkbenchSource.includes("Dry-run hide") &&
      !sourceWorkbenchSource.includes("Dry-run show") &&
      !sourceWorkbenchSource.includes("Navigation dry-run ready") &&
      !sourceWorkbenchSource.includes("Current state is dry-run") &&
      stylesSource.includes(".operationReceipt") &&
      stylesSource.includes(".connectorBusinessLead") &&
      stylesSource.includes(".connectorTechnicalDetails") &&
      stylesSource.includes(".navigationTechnicalDetails") &&
      stylesSource.includes(".navigationActionGrid"),
  },
  {
    label: "source-workbench-operations-panel-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchOperationsPanel.tsx")) &&
      existsSync(join(root, "src", "components", "SourceWorkbenchDataManagementPanel.tsx")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchOperationsPanel } from "./SourceWorkbenchOperationsPanel"') &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchDataManagementPanel } from "./SourceWorkbenchDataManagementPanel"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchOperationsPanel") &&
      sourceWorkbenchSource.includes("<SourceWorkbenchDataManagementPanel") &&
      !sourceWorkbenchSource.includes('data-testid="navigation-module-workbench"') &&
      !sourceWorkbenchSource.includes('data-testid={`source-inspect-${run.table_key}`}') &&
      !sourceWorkbenchSource.includes('data-testid="source-rename-dry-run-button"') &&
      sourceWorkbenchOperationsPanelSource.includes("type SourceWorkbenchOperationsPanelProps") &&
      !sourceWorkbenchOperationsPanelSource.includes("SourceRunSummary") &&
      !sourceWorkbenchOperationsPanelSource.includes("WorkbenchTable") &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-module-workbench"') &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-rename-dry-run"') &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-rename-confirm"') &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-move-dry-run"') &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-move-confirm"') &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-hide-dry-run"') &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-hide-confirm"') &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-show-dry-run"') &&
      sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-show-confirm"') &&
      sourceWorkbenchOperationsPanelSource.includes("runNavigationOperation(\"move\", true)") &&
      sourceWorkbenchOperationsPanelSource.includes("runNavigationOperation(\"hide\", true)") &&
      sourceWorkbenchOperationsPanelSource.includes("runNavigationOperation(\"show\", true)") &&
      stylesSource.includes("grid-template-columns: repeat(4, minmax(0, 1fr));") &&
      !sourceWorkbenchOperationsPanelSource.includes('data-testid={`source-inspect-${run.table_key}`}') &&
      !sourceWorkbenchOperationsPanelSource.includes('data-testid="source-delete-dry-run-button"') &&
      sourceWorkbenchDataManagementPanelSource.includes("SourceRunSummary") &&
      sourceWorkbenchDataManagementPanelSource.includes("WorkbenchTable") &&
      sourceWorkbenchDataManagementPanelSource.includes('data-testid="source-data-management-panel"') &&
      sourceWorkbenchDataManagementPanelSource.includes('data-testid={`source-inspect-${source.key}`}') &&
      sourceWorkbenchDataManagementPanelSource.includes('data-testid={`source-select-${source.key}`}') &&
      sourceWorkbenchDataManagementPanelSource.includes('data-testid="source-rename-dry-run-button"') &&
      sourceWorkbenchDataManagementPanelSource.includes('data-testid="source-delete-dry-run-button"') &&
      sourceWorkbenchDataManagementPanelSource.includes('data-testid="source-clear-button"') &&
      sourceWorkbenchDataManagementPanelSource.includes("runClearSandbox") &&
      sourceWorkbenchDataManagementPanelSource.includes("const seen = new Set<string>()") &&
      sourceWorkbenchDataManagementPanelSource.includes("sourceRuns.flatMap") &&
      sourceWorkbenchDataManagementPanelSource.includes("selectManagedSource(event.target.value)") &&
      sourceWorkbenchDataManagementPanelSource.includes("onDeleteSource({ source: selectedManagedSourceKey, confirm: true })") &&
      serverSourceRoutesSource.includes('url.pathname === "/api/sources/delete"') &&
      serverSourceRoutesSource.includes('url.pathname === "/api/sources/rename"') &&
      stylesSource.includes(".sourceLifecyclePanel") &&
      stylesSource.includes(".sourceDangerZone") &&
      implementationStatusSource.includes("Source workbench operations panel boundary"),
  },
  {
    label: "source-workbench-connector-panel-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchConnectorPanel.tsx")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchConnectorPanel } from "./SourceWorkbenchConnectorPanel"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchConnectorPanel") &&
      !sourceWorkbenchSource.includes('data-testid="connector-business-lead"') &&
      !sourceWorkbenchSource.includes('data-testid="connector-operation-receipt"') &&
      !sourceWorkbenchSource.includes('data-testid={`import-job-dry-remove-${job.job_key}`}') &&
      sourceWorkbenchConnectorPanelSource.includes("type SourceWorkbenchConnectorPanelProps") &&
      sourceWorkbenchConnectorPanelSource.includes("DataConnectorConfig") &&
      sourceWorkbenchConnectorPanelSource.includes("ImportJob") &&
      sourceWorkbenchConnectorPanelSource.includes("ReturnType<typeof useSourceWorkbenchConnectorController>") &&
      sourceWorkbenchConnectorControllerSource.includes("async function runConnectorSaveAction(confirm: boolean)") &&
      sourceWorkbenchConnectorControllerSource.includes("async function runConnectorSyncAction(connector: DataConnectorConfig, confirm: boolean)") &&
      sourceWorkbenchConnectorControllerSource.includes("async function runConnectorRemoveAction(connector: DataConnectorConfig)") &&
      sourceWorkbenchConnectorPanelSource.includes('data-testid="connector-save-dry-run-button"') &&
      sourceWorkbenchConnectorPanelSource.includes('data-testid={`connector-sync-dry-${connector.connectorKey}`}') &&
      sourceWorkbenchConnectorPanelSource.includes('data-testid={`connector-remove-${connector.connectorKey}`}') &&
      sourceWorkbenchConnectorPanelSource.includes('data-testid={`import-job-dry-remove-${job.job_key}`}') &&
      sourceWorkbenchConnectorPanelSource.includes("onRemoveImportJob({ jobKey: job.job_key, confirm: false })") &&
      sourceWorkbenchConnectorPanelSource.includes("This manages import receipts and records, not source business files") &&
      implementationStatusSource.includes("Source workbench connector panel boundary"),
  },
  {
    label: "source-workbench-field-metric-panel-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchFieldMetricPanel.tsx")) &&
      existsSync(join(root, "src", "components", "SourceWorkbenchFieldSemanticPanel.tsx")) &&
      existsSync(join(root, "src", "components", "SourceWorkbenchMetricDefinitionPanel.tsx")) &&
      existsSync(join(root, "src", "sourceWorkbenchFieldMetricTypes.ts")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchFieldMetricPanel } from "./SourceWorkbenchFieldMetricPanel"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchFieldMetricPanel") &&
      !sourceWorkbenchSource.includes('data-testid="field-semantic-readiness"') &&
      !sourceWorkbenchSource.includes('data-testid="infer-metrics-dry-run-button"') &&
      sourceWorkbenchFieldMetricPanelSource.includes("type SourceWorkbenchFieldMetricPanelProps") &&
      sourceWorkbenchFieldMetricPanelSource.includes('import { SourceWorkbenchFieldSemanticPanel } from "./SourceWorkbenchFieldSemanticPanel"') &&
      sourceWorkbenchFieldMetricPanelSource.includes('import { SourceWorkbenchMetricDefinitionPanel } from "./SourceWorkbenchMetricDefinitionPanel"') &&
      sourceWorkbenchFieldMetricPanelSource.includes("<SourceWorkbenchFieldSemanticPanel") &&
      sourceWorkbenchFieldMetricPanelSource.includes("<SourceWorkbenchMetricDefinitionPanel") &&
      !sourceWorkbenchFieldMetricPanelSource.includes('data-testid="field-semantic-readiness"') &&
      !sourceWorkbenchFieldMetricPanelSource.includes('data-testid="infer-metrics-dry-run-button"') &&
      sourceWorkbenchFieldMetricTypesSource.includes("export type FieldSemanticReadiness") &&
      sourceWorkbenchFieldMetricTypesSource.includes("export type MetricMutationOptions") &&
      sourceWorkbenchFieldMetricTypesSource.includes("export type QueryMetricOptions") &&
      sourceWorkbenchFieldMetricPanelSource.includes("fieldDraft: (field: FieldConfig)") &&
      sourceWorkbenchFieldMetricPanelSource.includes("metricDraft: (confirm?: boolean) => MetricMutationOptions") &&
      sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="infer-semantics-dry-run-button"') &&
      sourceWorkbenchMetricDefinitionPanelSource.includes('data-testid="infer-metrics-dry-run-button"') &&
      sourceWorkbenchMetricDefinitionPanelSource.includes('data-testid="add-metric-confirm-button"') &&
      sourceWorkbenchMetricDefinitionPanelSource.includes('data-testid="semantic-metric-result"') &&
      implementationStatusSource.includes("Source workbench field metric panel boundary"),
  },
  {
    label: "source-workbench-query-formula-panel-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchQueryFormulaPanel.tsx")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchQueryFormulaPanel } from "./SourceWorkbenchQueryFormulaPanel"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchQueryFormulaPanel") &&
      !sourceWorkbenchSource.includes('data-testid="query-run-button"') &&
      !sourceWorkbenchSource.includes('data-testid="formula-preview-button"') &&
      !sourceWorkbenchSource.includes("function formulaOptions(") &&
      !sourceWorkbenchSource.includes("function formulaAssetKey(") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("type SourceWorkbenchQueryFormulaPanelProps") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("type QueryOptions") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("type FormulaSaveOptions") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("function formulaOptions(") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("function formulaAssetKey(") &&
      sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="query-run-button"') &&
      sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="source-query-runtime-technical"') &&
      sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="formula-save-confirm-button"') &&
      sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="formula-asset-list"') &&
      implementationStatusSource.includes("Source workbench query formula panel boundary"),
  },
  {
    label: "source-workbench-relationship-panel-boundary",
    ok: existsSync(join(root, "src", "components", "SourceWorkbenchRelationshipPanel.tsx")) &&
      sourceWorkbenchSource.includes('import { SourceWorkbenchRelationshipPanel } from "./SourceWorkbenchRelationshipPanel"') &&
      sourceWorkbenchSource.includes("<SourceWorkbenchRelationshipPanel") &&
      !sourceWorkbenchSource.includes('data-testid="relationship-preview-button"') &&
      !sourceWorkbenchSource.includes('data-testid="relationship-impact-panel"') &&
      !sourceWorkbenchSource.includes("function applyRelationshipRecommendation(") &&
      !sourceWorkbenchSource.includes("relationshipDecisionState") &&
      sourceWorkbenchRelationshipPanelSource.includes("type SourceWorkbenchRelationshipPanelProps") &&
      sourceWorkbenchRelationshipPanelSource.includes('from "../dashboardCanvasContracts"') &&
      sourceWorkbenchRelationshipPanelSource.includes("relationshipForm: RelationshipSaveOptions") &&
      sourceWorkbenchRelationshipPanelSource.includes("setRelationshipForm: Dispatch<SetStateAction<RelationshipSaveOptions>>") &&
      sourceWorkbenchRelationshipPanelSource.includes("matchingRelationshipRecommendation") &&
      sourceWorkbenchRelationshipPanelSource.includes("relationshipAlreadySaved") &&
      sourceWorkbenchRelationshipPanelSource.includes("function applyRelationshipRecommendation(") &&
      sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-preview-button"') &&
      sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-confirm-button"') &&
      sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-impact-panel"') &&
      sourceWorkbenchRelationshipPanelSource.includes("已保存关系") &&
      implementationStatusSource.includes("Source workbench relationship panel boundary"),
  },
  {
    label: "frontend-b-widget-drilldown-workflow",
    ok: bWidgetKitSource.includes("runTableQuery") &&
      bWidgetKitSource.includes("saveView") &&
      bWidgetKitSource.includes("<BiDashboardDrilldownSheet") &&
      !bWidgetKitSource.includes("data-testid=\"b-drilldown-sheet\"") &&
      bDashboardDrilldownSheetSource.includes("export type DrilldownOperationReceipt") &&
      bDashboardDrilldownSheetSource.includes("data-testid=\"b-drilldown-sheet\"") &&
      bDashboardDrilldownSheetSource.includes("data-testid=\"b-drilldown-save-dry-run\"") &&
      bDashboardDrilldownSheetSource.includes("data-testid=\"b-drilldown-save-confirm\"") &&
      bDashboardDrilldownSheetSource.includes('data-testid="b-drilldown-operation-receipt"') &&
      bDashboardDrilldownSheetSource.includes('data-testid="b-drilldown-technical-details"') &&
      bDashboardDrilldownSheetSource.includes("可在视图页继续分析") &&
      bDashboardDrilldownSheetSource.includes("确认前不会创建视图") &&
      bDashboardDrilldownSheetSource.includes("View drilldown scope") &&
      stylesSource.includes(".bDrilldownReceipt") &&
      bDashboardWidgetCardSource.includes("onPointClick") &&
      bWidgetKitSource.includes("pointFilter"),
  },
  {
    label: "frontend-dashboard-widget-copy-remove-confirm-path",
    ok: dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-lifecycle-actions\"") &&
      dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-copy-preview-button\"") &&
      dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-copy-confirm-button\"") &&
      dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-remove-preview-button\"") &&
      dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-remove-confirm-button\"") &&
      dashboardWidgetLifecyclePanelSource.includes("复制或删除组件") &&
      dashboardWidgetManagePanelSource.includes("data-testid={`widget-copy-preview-${widget.widget_key}`}") &&
      dashboardWidgetManagePanelSource.includes("data-testid={`widget-remove-preview-${widget.widget_key}`}") &&
      dashboardWidgetLifecyclePanelSource.includes("confirm: false") &&
      dashboardWidgetLifecyclePanelSource.includes("confirm: true") &&
      !dashboardCanvasSource.includes("预演复制") &&
      !dashboardCanvasSource.includes("预演删除") &&
      dashboardWidgetManagePanelSource.includes("预览复制") &&
      dashboardWidgetManagePanelSource.includes("预览删除") &&
      serverDashboardRoutesSource.includes("op === \"copy\"") &&
      serverDashboardRoutesSource.includes("[\"copy-widget\", \"--widget\"") &&
      serverDashboardRoutesSource.includes("op === \"remove\"") &&
      serverDashboardRoutesSource.includes("[\"remove-widget\", \"--widget\""),
  },
  {
    label: "frontend-dashboard-widget-editor-business-controls",
    ok: dashboardWidgetEditorPanelSource.includes("调整组件呈现") &&
      dashboardWidgetBasicFormSource.includes("呈现方式") &&
      dashboardWidgetBasicFormSource.includes("数据范围") &&
      dashboardWidgetBasicFormSource.includes("分组字段") &&
      dashboardWidgetBasicFormSource.includes("计算字段") &&
      dashboardWidgetBasicFormSource.includes("计算方式") &&
      dashboardWidgetBasicFormSource.includes("显示数量") &&
      dashboardWidgetStylePanelSource.includes("外观和点击行为") &&
      dashboardWidgetLocalFilterPanelSource.includes("限定这个组件的数据") &&
      dashboardWidgetEditorPanelSource.includes("预览改动") &&
      dashboardWidgetEditorPanelSource.includes("应用改动") &&
      !dashboardCanvasSource.includes("组件配置") &&
      !dashboardCanvasSource.includes("预检配置") &&
      !dashboardCanvasSource.includes("Style and interaction") &&
      stylesSource.includes(".widgetLifecycleActions summary"),
  },
  {
    label: "dashboard-canvas-widget-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasWidgetModel.ts")) &&
      dashboardCanvasActionsSource.includes('from "./dashboardCanvasWidgetModel"') &&
      dashboardCanvasStateSource.includes('from "./dashboardCanvasWidgetModel"') &&
      dashboardCanvasStateSource.includes("useState<WidgetDraft>(() => defaultWidgetDraft())") &&
      dashboardCanvasStateSource.includes("setWidgetDraft(widgetDraftFromWidget(widget))") &&
      dashboardCanvasActionsSource.includes("buildDashboardModulePayload({") &&
      dashboardCanvasActionsSource.includes("buildWidgetSettingsPayload({") &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasWidgetModel"') &&
      !dashboardCanvasSource.includes("buildDashboardModulePayload({") &&
      !dashboardCanvasSource.includes("buildWidgetSettingsPayload({") &&
      !dashboardCanvasSource.includes("useState<WidgetDraft>(() => defaultWidgetDraft())") &&
      !dashboardCanvasSource.includes("setWidgetDraft(widgetDraftFromWidget(widget))") &&
      !dashboardCanvasSource.includes("type WidgetDraft = {") &&
      !dashboardCanvasSource.includes("type WidgetToggleKey =") &&
      !dashboardCanvasSource.includes("const parsedTopN =") &&
      !dashboardCanvasSource.includes("const parsedDecimalPlaces =") &&
      !dashboardCanvasSource.includes("const parsedTableColumnLimit =") &&
      !dashboardCanvasSource.includes("const fallbackWidth = widget.widget_type") &&
      !dashboardCanvasSource.includes("subtitle: typeof config.subtitle") &&
      dashboardCanvasWidgetModelSource.includes("export type DashboardCanvasWidthMode") &&
      dashboardCanvasWidgetModelSource.includes("export type WidgetDraft") &&
      dashboardCanvasWidgetModelSource.includes("export type WidgetToggleKey") &&
      dashboardCanvasWidgetModelSource.includes("export function defaultWidgetDraft(") &&
      dashboardCanvasWidgetModelSource.includes("export function widgetDraftFromWidget(") &&
      dashboardCanvasWidgetModelSource.includes("export function widgetDraftNumbers(") &&
      dashboardCanvasWidgetModelSource.includes("export function buildWidgetSettingsPayload(") &&
      dashboardCanvasWidgetModelSource.includes("export function moduleLayoutForWidget(") &&
      dashboardCanvasWidgetModelSource.includes("export function buildDashboardModulePayload(") &&
      dashboardCanvasSourceSwitchModelSource.includes("moduleLayoutForWidget(widget, index)") &&
      dashboardCanvasWidgetModelSource.includes("topN: boundedInteger(widgetDraft.topN, 12, 1, 500)") &&
      dashboardCanvasWidgetModelSource.includes("decimalPlaces: boundedInteger(widgetDraft.decimalPlaces, 0, 0, 4)") &&
      dashboardCanvasWidgetModelSource.includes("tableColumnLimit: boundedInteger(widgetDraft.tableColumnLimit, 6, 2, 24)") &&
      implementationStatusSource.includes("Dashboard canvas widget model boundary"),
  },
  {
    label: "dashboard-canvas-editor-options-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasEditorOptions.ts")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "../dashboardCanvasEditorOptions"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("buildWidgetToggleOptions(widgetDraft)") &&
      dashboardWidgetBasicFormSource.includes("widgetTypes.map") &&
      dashboardWidgetBasicFormSource.includes("valueFormats.map") &&
      dashboardWidgetStylePanelSource.includes("colorPalettes.map") &&
      dashboardWidgetStylePanelSource.includes("rankingModes.map") &&
      dashboardWidgetStylePanelSource.includes("slicerDisplays.map") &&
      dashboardOverviewStripSource.includes("dashboardAcceptanceItems.map") &&
      !dashboardCanvasSource.includes('const widgetTypes = ["metric"') &&
      !dashboardCanvasSource.includes('const valueFormats = ["auto"') &&
      !dashboardCanvasSource.includes('const colorPalettes = ["default"') &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasEditorOptions"') &&
      !dashboardCanvasSource.includes("buildWidgetToggleOptions(widgetDraft)") &&
      !dashboardCanvasSource.includes("dashboardAcceptanceItems.map") &&
      !dashboardCanvasSource.includes('const dashboardAcceptanceItems = [') &&
      !dashboardCanvasSource.includes('const widgetToggleOptions: Array<') &&
      !dashboardCanvasSource.includes('key: "showLegend", label: biText("图例"') &&
      dashboardCanvasEditorOptionsSource.includes('export const widgetTypes = ["metric", "bar", "line", "pie", "table", "text", "slicer"]') &&
      dashboardCanvasEditorOptionsSource.includes('export const valueFormats = ["auto", "plain", "compact", "currency", "percent"]') &&
      dashboardCanvasEditorOptionsSource.includes('export const colorPalettes = ["default", "fresh", "warm", "contrast", "mono"]') &&
      dashboardCanvasEditorOptionsSource.includes("export const dashboardAcceptanceItems") &&
      dashboardCanvasEditorOptionsSource.includes("export type WidgetToggleOption") &&
      dashboardCanvasEditorOptionsSource.includes("export function buildWidgetToggleOptions(") &&
      dashboardCanvasEditorOptionsSource.includes('key: "showLegend"') &&
      dashboardCanvasEditorOptionsSource.includes("多选切片") &&
      dashboardCanvasEditorOptionsSource.includes('key: "copy-delete"') &&
      implementationStatusSource.includes("Dashboard canvas editor options boundary"),
  },
  {
    label: "dashboard-canvas-summary-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasSummaryModel.ts")) &&
      dashboardCanvasViewModelSource.includes('from "./dashboardCanvasSummaryModel"') &&
      dashboardCanvasViewModelSource.includes("buildDashboardSummaryModel({") &&
      dashboardCanvasSource.includes("dashboardSummary={dashboardSummary}") &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasSummaryModel"') &&
      !dashboardCanvasSource.includes("buildDashboardSummaryModel({") &&
      dashboardOverviewStripSource.includes("dashboardSummary.topRow") &&
      dashboardOverviewStripSource.includes("dashboardSummary.currentScopeDetail") &&
      dashboardOverviewStripSource.includes("dashboardSummary.evidenceCoverageDetail") &&
      dashboardOverviewStripSource.includes("dashboardSummary.totalDetail") &&
      !dashboardCanvasSource.includes("const queryRows = Array.isArray(query.rows)") &&
      !dashboardCanvasSource.includes("const rankedRows = queryRows") &&
      !dashboardCanvasSource.includes("const totalValue = rankedRows.reduce") &&
      dashboardCanvasSummaryModelSource.includes("export type DashboardSummaryRow") &&
      dashboardCanvasSummaryModelSource.includes("export type DashboardSummaryModel") &&
      dashboardCanvasSummaryModelSource.includes("export function buildDashboardSummaryModel(") &&
      dashboardCanvasSummaryModelSource.includes("const rankedRows = queryRows") &&
      dashboardCanvasSummaryModelSource.includes(".map((row)") &&
      dashboardCanvasSummaryModelSource.includes("recommended group") &&
      dashboardCanvasSummaryModelSource.includes("evidenceCoverageDetail") &&
      implementationStatusSource.includes("Dashboard canvas summary model boundary"),
  },
  {
    label: "dashboard-canvas-view-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasViewModel.ts")) &&
      dashboardCanvasSource.includes('from "../dashboardCanvasViewModel"') &&
      dashboardCanvasSource.includes("buildDashboardCanvasViewModel({") &&
      dashboardCanvasSource.includes("dashboardEvidenceFocus") &&
      dashboardCanvasSource.includes("onOpenEvidence(dashboardEvidenceFocus)") &&
      !dashboardCanvasSource.includes("const sourceIntelligenceRuns =") &&
      !dashboardCanvasSource.includes("const latestRun = sourceIntelligenceRuns[0]") &&
      !dashboardCanvasSource.includes("const dashboardReadiness = buildDashboardReadinessModel") &&
      !dashboardCanvasSource.includes("const sourceSwitchView = buildDashboardSourceSwitchViewModel") &&
      !dashboardCanvasSource.includes("const { plannedWidgets, moduleSaveResult") &&
      dashboardCanvasViewModelSource.includes("export function buildDashboardCanvasViewModel(") &&
      dashboardCanvasViewModelSource.includes("type DashboardCanvasViewModelOptions") &&
      dashboardCanvasViewModelSource.includes("const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns)") &&
      dashboardCanvasViewModelSource.includes("const latestRun = sourceIntelligenceRuns[0]") &&
      dashboardCanvasViewModelSource.includes("const dashboardSummary = buildDashboardSummaryModel({") &&
      dashboardCanvasViewModelSource.includes("const widgetPlanSummary = summarizeDashboardWidgetPlan(widgetPlan)") &&
      dashboardCanvasViewModelSource.includes("const sourceSwitchAnalysis = analyzeDashboardSourceSwitch({") &&
      dashboardCanvasViewModelSource.includes("const sourceSwitchView = buildDashboardSourceSwitchViewModel(sourceSwitchAnalysis)") &&
      dashboardCanvasViewModelSource.includes("const nextWidgetFilters = buildNextWidgetFilters({") &&
      dashboardCanvasViewModelSource.includes("const dashboardReadiness = buildDashboardReadinessModel({") &&
      dashboardCanvasViewModelSource.includes("const dashboardEvidenceFocus = buildDashboardEvidenceFocus({") &&
      implementationStatusSource.includes("Dashboard canvas view model boundary"),
  },
  {
    label: "dashboard-canvas-contracts-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasContracts.ts")) &&
      dashboardCanvasContractsSource.includes("export type DashboardWidgetFilterInput") &&
      dashboardCanvasContractsSource.includes("export type DashboardOperationOptions") &&
      dashboardCanvasContractsSource.includes("export type DashboardFilterOperationOptions") &&
      dashboardCanvasContractsSource.includes("export type DashboardModuleSaveOptions") &&
      dashboardCanvasContractsSource.includes("export type BusinessDashboardOptions") &&
      dashboardCanvasContractsSource.includes("export type RelationshipSaveOptions") &&
      dashboardCanvasContractsSource.includes("export type DashboardWidgetOperationOptions") &&
      dashboardCanvasContractsSource.includes('op: "recommend" | "addRecommended" | "add" | "addRelationship" | "set" | "copy" | "remove"') &&
      dashboardCanvasContractsSource.includes("filters?: DashboardWidgetFilterInput[]") &&
      dashboardCanvasSource.includes('from "../dashboardCanvasContracts"') &&
      dashboardCanvasActionsSource.includes('from "./dashboardCanvasContracts"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "../dashboardCanvasContracts"') &&
      dashboardWidgetEditorPanelSource.includes('from "../dashboardCanvasContracts"') &&
      dashboardWidgetLocalFilterPanelSource.includes('from "../dashboardCanvasContracts"') &&
      dashboardWidgetLifecyclePanelSource.includes('from "../dashboardCanvasContracts"') &&
      dashboardPageAdminPanelSource.includes('from "../dashboardCanvasContracts"') &&
      dashboardBusinessTaskStripSource.includes('from "../dashboardCanvasContracts"') &&
      dashboardBusinessTemplatePanelSource.includes('from "../dashboardCanvasContracts"') &&
      dashboardFilterWorkbenchSource.includes('from "../dashboardCanvasContracts"') &&
      homeOverviewSource.includes('from "../dashboardCanvasContracts"') &&
      sourceWorkbenchSource.includes('from "../dashboardCanvasContracts"') &&
      sourceWorkbenchRelationshipPanelSource.includes('from "../dashboardCanvasContracts"') &&
      !dashboardCanvasSource.includes("op: \"recommend\" | \"addRecommended\" | \"add\" | \"addRelationship\" | \"set\" | \"copy\" | \"remove\"") &&
      !dashboardCanvasActionsSource.includes("type DashboardWidgetOperationOptions =") &&
      !dashboardCanvasActionsSource.includes("type DashboardOperationOptions =") &&
      !dashboardCanvasActionsSource.includes("type BusinessDashboardOptions =") &&
      !dashboardAdvancedWidgetWorkbenchSource.includes("type WidgetOperationOptions =") &&
      !dashboardAdvancedWidgetWorkbenchSource.includes("type BusinessDashboardOptions =") &&
      !dashboardWidgetEditorPanelSource.includes("type WidgetOperationOptions =") &&
      !dashboardWidgetLocalFilterPanelSource.includes("type WidgetFilterOperation =") &&
      !dashboardWidgetLifecyclePanelSource.includes("type WidgetLifecycleOperation") &&
      !dashboardPageAdminPanelSource.includes("type DashboardOperationOptions =") &&
      !dashboardBusinessTaskStripSource.includes("type BusinessDashboardOptions =") &&
      !dashboardBusinessTemplatePanelSource.includes("type BusinessDashboardOptions =") &&
      !dashboardFilterWorkbenchSource.includes("type DashboardFilterOperation =") &&
      !homeOverviewSource.includes('onBusinessDashboardOperation: (options: { op: "draft" | "create" | "overwrite"') &&
      !sourceWorkbenchSource.includes("type RelationshipOptions =") &&
      !sourceWorkbenchSource.includes('onBusinessDashboardOperation: (options: { op: "draft" | "create" | "overwrite"') &&
      !sourceWorkbenchRelationshipPanelSource.includes("type RelationshipOptions =") &&
      implementationStatusSource.includes("Dashboard canvas contracts boundary"),
  },
  {
    label: "frontend-dashboard-evidence-click-path",
    ok: bDashboardWidgetCardSource.includes("data-testid={`b-widget-evidence-${widget.id}`}") &&
      bDashboardWidgetCardSource.includes("Review evidence") &&
      bWidgetKitSource.includes("openWidgetEvidence") &&
      hasCssRule(stylesSource, ".bWidgetMeta button", "display: inline-flex;") &&
      stylesSource.includes("min-height: 32px;") &&
      dashboardCanvasSource.includes("onOpenEvidence={onOpenEvidence}") &&
      appSource.includes("const [evidenceFocus, setEvidenceFocus]") &&
      (appSource.includes("setSection(\"evidence\")") || appSource.includes("openSection(\"evidence\")")) &&
      evidenceViewSource.includes("data-testid=\"evidence-focus-card\"") &&
      evidenceViewSource.includes("data-testid=\"evidence-source-intelligence-summary\"") &&
      evidenceViewSource.includes('data-testid="evidence-technical-ref-details"') &&
      evidenceViewSource.includes('data-testid="evidence-receipt-technical-details"') &&
      evidenceViewSource.includes('data-testid="evidence-focus-technical-detail"') &&
      evidenceViewSource.includes("查看技术引用名") &&
      evidenceViewSource.includes("View technical reference names") &&
      evidenceViewSource.includes("查看原始本体合同") &&
      evidenceViewModelSource.includes("source-intelligence:"),
  },
  {
    label: "frontend-evidence-business-summary-first",
    ok: evidenceViewSource.includes("<EvidenceBusinessSummaryPanel") &&
      evidenceBusinessSummaryPanelSource.includes("data-testid=\"evidence-business-summary\"") &&
      evidenceBusinessSummaryPanelSource.includes("data-testid=\"evidence-business-summary-metrics\"") &&
      evidenceBusinessSummaryPanelSource.includes("data-testid=\"evidence-business-next-actions\"") &&
      evidenceViewSource.includes('from "../evidenceViewModel"') &&
      evidenceViewSource.includes("evidenceDecisionText") &&
      evidenceViewSource.includes("evidenceCoverageText") &&
      evidenceViewModelSource.includes("export function evidenceDecisionText") &&
      evidenceViewModelSource.includes("export function evidenceCoverageText") &&
      !evidenceViewSource.includes("function evidenceDecisionText") &&
      !evidenceViewSource.includes("function evidenceCoverageText") &&
      evidenceViewSource.includes("追溯依据") &&
      evidenceViewSource.includes("Trace basis"),
  },
  {
    label: "evidence-business-summary-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "EvidenceBusinessSummaryPanel.tsx")) &&
      evidenceViewSource.includes('import { EvidenceBusinessSummaryPanel } from "./EvidenceBusinessSummaryPanel"') &&
      evidenceViewSource.includes("<EvidenceBusinessSummaryPanel") &&
      !evidenceViewSource.includes('data-testid="evidence-business-summary"') &&
      evidenceBusinessSummaryPanelSource.includes("type EvidenceBusinessSummaryPanelProps") &&
      evidenceBusinessSummaryPanelSource.includes("businessMetrics: EvidenceBusinessMetric[]") &&
      evidenceBusinessSummaryPanelSource.includes("coverageText: string") &&
      evidenceBusinessSummaryPanelSource.includes("nextEvidenceActions.map") &&
      implementationStatusSource.includes("Evidence business summary panel component boundary"),
  },
  {
    label: "frontend-evidence-technical-details-collapsed",
    ok: evidenceViewSource.includes("证据摘要回执") &&
      evidenceViewSource.includes("可用问题") &&
      evidenceViewSource.includes("业务连接") &&
      evidenceViewSource.includes('data-testid="evidence-technical-ref-details"') &&
      evidenceViewSource.includes('data-testid="evidence-receipt-technical-details"') &&
      !evidenceViewSource.includes("<h3><Bilingual zh=\"Source Intelligence 回执\"") &&
      !evidenceViewSource.includes("可执行指标 SQL") &&
      sourceWorkbenchModelSource.includes("证据摘要生成失败") &&
      sourceWorkbenchModelSource.includes("证据摘要需要 CSV") &&
      sourceWorkbenchActionPanelSource.includes("当前证据摘要"),
  },
  {
    label: "frontend-evidence-agent-source-intelligence-business-first",
    ok: evidenceViewModelSource.includes("export function agentEvidenceBusinessLabel") &&
      evidenceViewModelSource.includes("export function agentEvidenceTechnicalText") &&
      evidenceViewModelSource.includes("export function actionBoundaryBusinessLabel") &&
      evidenceViewModelSource.includes("export function evidenceRunReadinessText") &&
      !evidenceViewSource.includes("function agentEvidenceBusinessLabel") &&
      !evidenceViewSource.includes("function agentEvidenceTechnicalText") &&
      !evidenceViewSource.includes("function actionBoundaryBusinessLabel") &&
      !evidenceViewSource.includes("function evidenceRunReadinessText") &&
      evidenceViewSource.includes('data-testid="evidence-agent-answer-business-refs"') &&
      evidenceViewSource.includes('data-testid="evidence-agent-answer-technical-refs"') &&
      evidenceViewSource.includes('data-testid={`evidence-action-boundary-technical-${action.id}`}') &&
      evidenceViewModelSource.includes("只读查询已完成") &&
      evidenceViewSource.includes("查看 Agent 证据原始引用") &&
      evidenceViewSource.includes("查看动作合同") &&
      evidenceViewModelSource.includes("可用于分析") &&
      !evidenceViewSource.includes('{String(ref.type ?? "evidence")} {String(ref.id ?? ref.metric_key ?? ref.engine ?? "")}') &&
      stylesSource.includes(".evidenceAgentTechnicalRefs") &&
      stylesSource.includes(".evidenceTechnicalList") &&
      stylesSource.includes(".evidenceActionBoundaryTechnical"),
  },
  {
    label: "frontend-evidence-action-receipt",
    ok: evidenceViewSource.includes("lastActionResult?: Record<string, unknown> | null") &&
      evidenceViewModelSource.includes("export function actionReceiptTitle") &&
      evidenceViewModelSource.includes("export function actionReceiptDetail") &&
      evidenceViewModelSource.includes("export function actionReceiptSubject") &&
      evidenceViewModelSource.includes("export function actionReceiptTechnical") &&
      !evidenceViewSource.includes("function actionReceiptTitle") &&
      !evidenceViewSource.includes("function actionReceiptDetail") &&
      !evidenceViewSource.includes("function actionReceiptSubject") &&
      !evidenceViewSource.includes("function actionReceiptTechnical") &&
      evidenceViewSource.includes('data-testid="evidence-action-receipt"') &&
      evidenceViewSource.includes('data-testid="evidence-action-receipt-title"') &&
      evidenceViewSource.includes('data-testid="evidence-action-receipt-detail"') &&
      evidenceViewSource.includes('data-testid="evidence-action-receipt-technical"') &&
      evidenceViewSource.includes("查看动作技术标识") &&
      evidenceViewSource.includes("最近动作回执") &&
      evidenceViewModelSource.includes("确认前不会写入") &&
      appSource.includes("lastActionResult={lastActionResult}") &&
      stylesSource.includes(".evidenceActionReceipt") &&
      stylesSource.includes(".evidenceActionTechnical"),
  },
  {
    label: "frontend-dashboard-beginner-editor",
    ok: dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-editor"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-recommend"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-preview-template"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-save"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-agent"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes('data-testid="dashboard-advanced-widget-workbench"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("Widget maintenance") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("组件维护") &&
      !dashboardCanvasSource.includes("高级组件工作台") &&
      dashboardCanvasSource.includes("onSaveDashboard={() => runModuleSave(true)}") &&
      dashboardCanvasSource.includes("runBusinessTemplate(\"business-template-preview\"") &&
      dashboardModuleSavePanelSource.includes("dashboardModuleSaveReceipt") &&
      dashboardModuleSavePanelSource.includes('data-testid="dashboard-modules-impact-summary"') &&
      dashboardModuleSavePanelSource.includes('data-testid="dashboard-modules-result-technical"') &&
      dashboardCanvasPlanModelSource.includes("确认前不会写入") &&
      dashboardCanvasPlanModelSource.includes("刷新后仍会保留") &&
      stylesSource.includes(".dashboardModuleSaveBusiness") &&
      stylesSource.includes(".dashboardModuleTechnicalDetails"),
  },
  {
    label: "frontend-dashboard-asset-source-strip",
    ok: dashboardOverviewStripSource.includes('data-testid="dashboard-asset-source-strip"') &&
      dashboardOverviewStripSource.includes('data-testid="dashboard-source-label"') &&
      dashboardOverviewStripSource.includes('data-testid="dashboard-source-facts"') &&
      dashboardCanvasSource.includes("dashboardCreatedBy={dashboardCreatedBy}") &&
      dashboardCanvasSource.includes("dashboardIsAgentManaged={dashboardIsAgentManaged}") &&
      dashboardCanvasReadinessModelSource.includes("Agent 生成") &&
      dashboardOverviewStripSource.includes("Editable asset, not a black-box result") &&
      dashboardCanvasReadinessModelSource.includes("agentManaged: readiness.isAgentManaged") &&
      dashboardCanvasReadinessModelSource.includes("可编辑；写入前确认") &&
      dashboardCanvasReadinessModelSource.includes("Editable; writes require approval") &&
      stylesSource.includes(".dashboardAssetSourceStrip") &&
      stylesSource.includes("width: fit-content") &&
      stylesSource.includes("justify-self: start") &&
      stylesSource.includes(".dashboardAssetSourceLead div > span") &&
      !stylesSource.includes(".dashboardAssetSourceLead span,") &&
      stylesSource.includes(".assetSourceBadge.agent"),
  },
  {
    label: "frontend-badge-fit-content-system",
    ok: dashboardBusinessTaskStripSource.includes('data-testid="dashboard-business-task-strip"') &&
      dashboardOverviewStripSource.includes('data-testid="dashboard-component-acceptance-strip"') &&
      stylesSource.includes("span.assetModeChip,") &&
      stylesSource.includes("span.storyMode,") &&
      stylesSource.includes("span.assetSourceBadge,") &&
      stylesSource.includes("span.statusBadge,") &&
      stylesSource.includes("span.settingsSandboxBadge,") &&
      stylesSource.includes("span.widgetCountBadge") &&
      stylesSource.includes("display: inline-flex;") &&
      stylesSource.includes("align-items: center;") &&
      stylesSource.includes("justify-content: center;") &&
      stylesSource.includes("justify-self: start;") &&
      stylesSource.includes("width: fit-content;") &&
      stylesSource.includes("white-space: nowrap;") &&
      implementationStatusSource.includes("Badge fit-content system"),
  },
  {
    label: "frontend-dashboard-business-task-strip",
    ok: dashboardBusinessTaskStripSource.includes('data-testid="dashboard-business-task-strip"') &&
      dashboardBusinessTaskStripSource.includes('data-testid="dashboard-task-explain"') &&
      dashboardBusinessTaskStripSource.includes('data-testid="dashboard-task-improve"') &&
      dashboardBusinessTaskStripSource.includes('data-testid="dashboard-task-evidence"') &&
      dashboardBusinessTaskStripSource.includes('data-testid="dashboard-task-template"') &&
      dashboardBusinessTaskStripSource.includes('data-testid="dashboard-beta-details"') &&
      dashboardCanvasSource.includes("function openDashboardEvidence") &&
      dashboardCanvasActionsSource.includes("async function runDashboardAsk") &&
      !dashboardCanvasSource.includes("function runDashboardAsk") &&
      dashboardBusinessTaskStripSource.includes("先说想看的一个图表") &&
      dashboardBusinessTaskStripSource.includes("高级：优化或行业看板 Beta") &&
      dashboardBusinessTaskStripSource.includes('className="advancedDetails compactAdvanced dashboardBetaDetails"') &&
      dashboardCanvasReadinessModelSource.includes("source: \"dashboard-summary\"") &&
      appSource.includes("onAsk={handleAgentCommandAsk}") &&
      stylesSource.includes(".dashboardBusinessTaskStrip") &&
      stylesSource.includes(".dashboardBusinessTasks") &&
      stylesSource.includes(".dashboardBetaDetails") &&
      stylesSource.includes("repeat(auto-fit, minmax(168px, 1fr))") &&
      !stylesSource.includes(".dashboardBusinessTasks span,\n.dashboardBusinessTasks strong,\n.dashboardBusinessTasks small {\n  display: block;\n  min-width: 0;\n  overflow-wrap: anywhere;"),
  },
  {
    label: "dashboard-business-task-strip-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardBusinessTaskStrip.tsx")) &&
      dashboardCanvasSource.includes('from "./DashboardBusinessTaskStrip"') &&
      dashboardCanvasSource.includes("<DashboardBusinessTaskStrip") &&
      dashboardCanvasSource.includes("onAsk={runDashboardAsk}") &&
      dashboardCanvasSource.includes("onBusinessTemplate={runBusinessTemplate}") &&
      dashboardCanvasSource.includes("onOpenEvidence={openDashboardEvidence}") &&
      !dashboardCanvasSource.includes('data-testid="dashboard-task-explain"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-task-improve"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-task-template"') &&
      dashboardBusinessTaskStripSource.includes("export function DashboardBusinessTaskStrip(") &&
      dashboardBusinessTaskStripSource.includes("type DashboardBusinessTaskStripProps") &&
      dashboardBusinessTaskStripSource.includes("dashboardName: string") &&
      dashboardBusinessTaskStripSource.includes("defaultTableKey: string") &&
      dashboardBusinessTaskStripSource.includes("onBusinessTemplate") &&
      dashboardBusinessTaskStripSource.includes("经营模板") &&
      dashboardBusinessTaskStripSource.includes("Preview impact") &&
      implementationStatusSource.includes("Dashboard business task strip component boundary"),
  },
  {
    label: "dashboard-beginner-editor-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardBeginnerEditor.tsx")) &&
      dashboardCanvasSource.includes('from "./DashboardBeginnerEditor"') &&
      dashboardCanvasSource.includes("<DashboardBeginnerEditor") &&
      dashboardCanvasSource.includes("healthItems={dashboardHealthItems}") &&
      dashboardCanvasSource.includes("sourceSwitchView={sourceSwitchView}") &&
      dashboardCanvasSource.includes("onSourceSwitch={runSourceSwitch}") &&
      dashboardCanvasSource.includes("onSourceSwitchTableChange={setSourceSwitchTableKey}") &&
      !dashboardCanvasSource.includes('data-testid="dashboard-beginner-editor"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-readiness-agent"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-source-switch-select"') &&
      !dashboardCanvasSource.includes("className=\"beginnerEditorActions\"") &&
      dashboardBeginnerEditorSource.includes("export function DashboardBeginnerEditor(") &&
      dashboardBeginnerEditorSource.includes("type DashboardBeginnerEditorProps") &&
      dashboardBeginnerEditorSource.includes("sourceSwitchView: DashboardSourceSwitchViewModel") &&
      dashboardBeginnerEditorSource.includes("healthItems: DashboardHealthItem[]") &&
      dashboardBeginnerEditorSource.includes("onSourceSwitchTableChange") &&
      dashboardBeginnerEditorSource.includes("Make the current dashboard usable first") &&
      dashboardBeginnerEditorSource.includes("Preview ready; writes still require confirmation") &&
      implementationStatusSource.includes("Dashboard beginner editor component boundary"),
  },
  {
    label: "dashboard-advanced-widget-workbench-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardAdvancedWidgetWorkbench.tsx")) &&
      dashboardCanvasSource.includes('from "./DashboardAdvancedWidgetWorkbench"') &&
      dashboardCanvasSource.includes("<DashboardAdvancedWidgetWorkbench") &&
      dashboardCanvasSource.includes("dashboardWidgets={dashboardWidgets}") &&
      dashboardCanvasSource.includes("onWidgetOperation={runWidgetOperation}") &&
      dashboardCanvasSource.includes("onModuleSave={runModuleSave}") &&
      dashboardCanvasSource.includes("widgetSettingsPayload={widgetSettingsPayload}") &&
      !dashboardCanvasSource.includes('data-testid="dashboard-advanced-widget-workbench"') &&
      !dashboardCanvasSource.includes("className=\"widgetWorkbenchGrid\"") &&
      !dashboardCanvasSource.includes("<DashboardModuleSavePanel") &&
      !dashboardCanvasSource.includes("<DashboardWidgetEditorPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("export function DashboardAdvancedWidgetWorkbench(") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("type DashboardAdvancedWidgetWorkbenchProps") &&
      dashboardAdvancedWidgetWorkbenchSource.includes('data-testid="dashboard-advanced-widget-workbench"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("className=\"widgetWorkbenchGrid\"") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardModuleSavePanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardBusinessTemplatePanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetRecommendationPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardSavedViewPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardRelationshipRecommendationPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardRelationshipWidgetPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetManagePanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetEditorPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("buildWidgetToggleOptions(widgetDraft)") &&
      implementationStatusSource.includes("Dashboard advanced widget workbench component boundary"),
  },
  {
    label: "dashboard-module-save-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardModuleSavePanel.tsx")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardModuleSavePanel"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardModuleSavePanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onSave={onModuleSave}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onCanvasWidthModeChange={onCanvasWidthModeChange}") &&
      !dashboardCanvasSource.includes('from "./DashboardModuleSavePanel"') &&
      !dashboardCanvasSource.includes("<DashboardModuleSavePanel") &&
      !dashboardCanvasSource.includes('data-testid="dashboard-module-save-panel"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-modules-dry-run"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-modules-result-technical"') &&
      !dashboardCanvasSource.includes("dashboardModuleSaveReceipt(moduleSaveResult") &&
      dashboardModuleSavePanelSource.includes("export function DashboardModuleSavePanel(") &&
      dashboardModuleSavePanelSource.includes("type DashboardModuleSavePanelProps") &&
      dashboardModuleSavePanelSource.includes("dashboardModuleSaveReceipt(moduleSaveResult") &&
      dashboardModuleSavePanelSource.includes("onSave(false)") &&
      dashboardModuleSavePanelSource.includes("onSave(true)") &&
      dashboardModuleSavePanelSource.includes("View module receipt") &&
      implementationStatusSource.includes("Dashboard module save panel component boundary"),
  },
  {
    label: "dashboard-business-template-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardBusinessTemplatePanel.tsx")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardBusinessTemplatePanel"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardBusinessTemplatePanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onBusinessTemplate={onBusinessTemplate}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("businessCategories={businessCategories}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("businessTemplateCount={businessTemplateCount}") &&
      !dashboardCanvasSource.includes('from "./DashboardBusinessTemplatePanel"') &&
      !dashboardCanvasSource.includes("<DashboardBusinessTemplatePanel") &&
      !dashboardCanvasSource.includes('data-testid="business-template-panel"') &&
      !dashboardCanvasSource.includes('data-testid="business-dashboard-preview"') &&
      !dashboardCanvasSource.includes('data-testid="business-dashboard-overwrite"') &&
      !dashboardCanvasSource.includes("businessCategories.map((category)") &&
      dashboardBusinessTemplatePanelSource.includes("export function DashboardBusinessTemplatePanel(") &&
      dashboardBusinessTemplatePanelSource.includes("type DashboardBusinessTemplatePanelProps") &&
      dashboardBusinessTemplatePanelSource.includes("onBusinessTemplate(\"business-template-preview\"") &&
      dashboardBusinessTemplatePanelSource.includes("onBusinessTemplate(\"erp-unit-template-preview\"") &&
      dashboardBusinessTemplatePanelSource.includes('template: "erp-units"') &&
      dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-dashboard-preview"') &&
      dashboardBusinessTemplatePanelSource.includes("onBusinessTemplate(\"business-template-create\"") &&
      dashboardBusinessTemplatePanelSource.includes("onBusinessTemplate(\"business-template-overwrite\"") &&
      dashboardBusinessTemplatePanelSource.includes("businessCategories.map((category)") &&
      dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-selection-evidence"') &&
      dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-selected-sources"') &&
      dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-widget-preview"') &&
      dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-omitted-hints"') &&
      dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-missing-field-chips"') &&
      dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-gap-unlocks"') &&
      dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-category-coverage"') &&
      dashboardBusinessTemplatePanelSource.includes("collectNeededFieldsFromErpHints(allOmittedUnitHints)") &&
      dashboardBusinessTemplatePanelSource.includes("buildErpGapUnlocks(allOmittedUnitHints)") &&
      dashboardBusinessTemplatePanelSource.includes("neededFieldsForErpHint(hint)") &&
      erpUnitLibraryViewModelSource.includes("export function buildErpGapUnlocks") &&
      erpUnitLibraryViewModelSource.includes("export function collectNeededFieldsFromErpHints") &&
      dashboardBusinessTemplatePanelSource.includes("summarizeMatchedFields(widget.matchedFields)") &&
      dashboardBusinessTemplatePanelSource.includes("Business dashboard generated") &&
      implementationStatusSource.includes("Dashboard business template panel component boundary"),
  },
  {
    label: "dashboard-widget-recommendation-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardWidgetRecommendationPanel.tsx")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardWidgetRecommendationPanel"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetRecommendationPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("plannedWidgets={plannedWidgets}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onRecommendWidgets={() => onWidgetOperation(\"recommend-widgets\"") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onAddRecommendedWidgets={() => onWidgetOperation(\"add-recommended\"") &&
      !dashboardCanvasSource.includes('from "./DashboardWidgetRecommendationPanel"') &&
      !dashboardCanvasSource.includes("<DashboardWidgetRecommendationPanel") &&
      !dashboardCanvasSource.includes('data-testid="widget-recommend-button"') &&
      !dashboardCanvasSource.includes('data-testid="widget-add-recommended-button"') &&
      !dashboardCanvasSource.includes("plannedWidgets.slice(0, 5).map") &&
      !dashboardCanvasSource.includes("点击推荐组件，系统会基于字段语义") &&
      dashboardWidgetRecommendationPanelSource.includes("export function DashboardWidgetRecommendationPanel(") &&
      dashboardWidgetRecommendationPanelSource.includes("type DashboardWidgetRecommendationPanelProps") &&
      dashboardWidgetRecommendationPanelSource.includes('data-testid="widget-recommendation-panel"') &&
      dashboardWidgetRecommendationPanelSource.includes('data-testid="widget-recommend-button"') &&
      dashboardWidgetRecommendationPanelSource.includes('data-testid="widget-add-recommended-button"') &&
      dashboardWidgetRecommendationPanelSource.includes("plannedWidgets.slice(0, 5).map") &&
      dashboardWidgetRecommendationPanelSource.includes("Use Recommend to generate widget candidates") &&
      implementationStatusSource.includes("Dashboard widget recommendation panel component boundary"),
  },
  {
    label: "dashboard-saved-view-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardSavedViewPanel.tsx")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardSavedViewPanel"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardSavedViewPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("views={usableViews}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("selectedViewKey={selectedViewKey}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onSelectedViewChange={onSelectedViewChange}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes('onWidgetOperation("add-view-widget"') &&
      !dashboardCanvasSource.includes('from "./DashboardSavedViewPanel"') &&
      !dashboardCanvasSource.includes("<DashboardSavedViewPanel") &&
      !dashboardCanvasSource.includes('runWidgetOperation("add-view-widget"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-saved-view-panel"') &&
      !dashboardCanvasSource.includes('data-testid="widget-add-view-button"') &&
      !dashboardCanvasSource.includes("usableViews.map((view)") &&
      !dashboardCanvasSource.includes("const selectedView = savedViews.find") &&
      dashboardSavedViewPanelSource.includes("export function DashboardSavedViewPanel(") &&
      dashboardSavedViewPanelSource.includes("type DashboardSavedViewPanelProps") &&
      dashboardSavedViewPanelSource.includes('data-testid="dashboard-saved-view-panel"') &&
      dashboardSavedViewPanelSource.includes('data-testid="widget-add-view-button"') &&
      dashboardSavedViewPanelSource.includes("views.map((view)") &&
      dashboardSavedViewPanelSource.includes("views.find((view)") &&
      dashboardSavedViewPanelSource.includes("Add view to dashboard") &&
      implementationStatusSource.includes("Dashboard saved view panel component boundary"),
  },
  {
    label: "dashboard-relationship-recommendation-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardRelationshipRecommendationPanel.tsx")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardRelationshipRecommendationPanel"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardRelationshipRecommendationPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("recommendations={relationshipRecommendations}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onRelationshipSave={onRelationshipSave}") &&
      !dashboardCanvasSource.includes('from "./DashboardRelationshipRecommendationPanel"') &&
      !dashboardCanvasSource.includes("<DashboardRelationshipRecommendationPanel") &&
      !dashboardCanvasSource.includes('data-testid="relationship-recommendation-panel"') &&
      !dashboardCanvasSource.includes("relationshipRecommendations.slice(0, 3).map") &&
      !dashboardCanvasSource.includes("relationshipPrimaryMapping(recommendation)") &&
      !dashboardCanvasSource.includes("relationshipRecommendationKey(recommendation)") &&
      !dashboardCanvasSource.includes("relationshipMappingLabel(recommendation)") &&
      dashboardRelationshipRecommendationPanelSource.includes("export function DashboardRelationshipRecommendationPanel(") &&
      dashboardRelationshipRecommendationPanelSource.includes("type DashboardRelationshipRecommendationPanelProps") &&
      dashboardRelationshipRecommendationPanelSource.includes('data-testid="relationship-recommendation-panel"') &&
      dashboardRelationshipRecommendationPanelSource.includes("recommendations.slice(0, 3).map") &&
      dashboardRelationshipRecommendationPanelSource.includes("relationshipPrimaryMapping(recommendation)") &&
      dashboardRelationshipRecommendationPanelSource.includes("relationshipRecommendationKey(recommendation)") &&
      dashboardRelationshipRecommendationPanelSource.includes("relationshipMappingLabel(recommendation)") &&
      dashboardRelationshipRecommendationPanelSource.includes("relationship-preview-${index}") &&
      dashboardRelationshipRecommendationPanelSource.includes("No recommended links yet") &&
      implementationStatusSource.includes("Dashboard relationship recommendation panel component boundary"),
  },
  {
    label: "dashboard-relationship-widget-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardRelationshipWidgetPanel.tsx")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardRelationshipWidgetPanel"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardRelationshipWidgetPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("relationships={savedRelationships}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("selectedRelationship={selectedRelationship}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onSelectedRelationshipChange={onSelectedRelationshipChange}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes('onWidgetOperation("add-relationship-widget"') &&
      !dashboardCanvasSource.includes('from "./DashboardRelationshipWidgetPanel"') &&
      !dashboardCanvasSource.includes("<DashboardRelationshipWidgetPanel") &&
      !dashboardCanvasSource.includes('runWidgetOperation("add-relationship-widget"') &&
      !dashboardCanvasSource.includes('data-testid="relationship-widget-panel"') &&
      !dashboardCanvasSource.includes('data-testid="widget-add-relationship-button"') &&
      !dashboardCanvasSource.includes("savedRelationships.map((relationship)") &&
      !dashboardCanvasSource.includes("selectedRelationship.left_table_key") &&
      dashboardRelationshipWidgetPanelSource.includes("export function DashboardRelationshipWidgetPanel(") &&
      dashboardRelationshipWidgetPanelSource.includes("type DashboardRelationshipWidgetPanelProps") &&
      dashboardRelationshipWidgetPanelSource.includes('data-testid="relationship-widget-panel"') &&
      dashboardRelationshipWidgetPanelSource.includes('data-testid="widget-add-relationship-button"') &&
      dashboardRelationshipWidgetPanelSource.includes("relationships.map((relationship)") &&
      dashboardRelationshipWidgetPanelSource.includes("onAddRelationshipWidget(selectedRelationship)") &&
      dashboardRelationshipWidgetPanelSource.includes("Create relation chart") &&
      implementationStatusSource.includes("Dashboard relationship widget panel component boundary"),
  },
  {
    label: "dashboard-widget-manage-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardWidgetManagePanel.tsx")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardWidgetManagePanel"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetManagePanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("widgets={dashboardWidgets}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("selectedWidgetKey={selectedWidget?.widget_key}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onSelectWidget={onSelectWidget}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onCopyPreview={(widget) => onWidgetOperation(`copy-preview-${widget.widget_key}`") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onRemovePreview={(widget) => onWidgetOperation(`remove-preview-${widget.widget_key}`") &&
      !dashboardCanvasSource.includes('from "./DashboardWidgetManagePanel"') &&
      !dashboardCanvasSource.includes("<DashboardWidgetManagePanel") &&
      !dashboardCanvasSource.includes('data-testid={`widget-edit-${widget.widget_key}`}') &&
      !dashboardCanvasSource.includes('className="widgetActionPanel widgetListActionPanel"') &&
      dashboardWidgetManagePanelSource.includes("export function DashboardWidgetManagePanel(") &&
      dashboardWidgetManagePanelSource.includes("type DashboardWidgetManagePanelProps") &&
      dashboardWidgetManagePanelSource.includes('data-testid="dashboard-widget-manage-panel"') &&
      dashboardWidgetManagePanelSource.includes("widgets.map((widget)") &&
      dashboardWidgetManagePanelSource.includes('data-testid={`widget-edit-${widget.widget_key}`}') &&
      dashboardWidgetManagePanelSource.includes('data-testid={`widget-copy-preview-${widget.widget_key}`}') &&
      dashboardWidgetManagePanelSource.includes('data-testid={`widget-remove-preview-${widget.widget_key}`}') &&
      dashboardWidgetManagePanelSource.includes("onSelectWidget(widget.widget_key)") &&
      dashboardWidgetManagePanelSource.includes("onCopyPreview(widget)") &&
      dashboardWidgetManagePanelSource.includes("onRemovePreview(widget)") &&
      implementationStatusSource.includes("Dashboard widget manage panel component boundary"),
  },
  {
    label: "dashboard-widget-editor-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardWidgetEditorPanel.tsx")) &&
      dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardWidgetEditorPanel"') &&
      dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetEditorPanel") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("selectedWidget={selectedWidget}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("widgetDraft={widgetDraft}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("setWidgetDraft={setWidgetDraft}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("onWidgetOperation={onWidgetOperation}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("widgetSettingsPayload={widgetSettingsPayload}") &&
      dashboardAdvancedWidgetWorkbenchSource.includes("nextWidgetFilters={nextWidgetFilters}") &&
      !dashboardCanvasSource.includes('from "./DashboardWidgetEditorPanel"') &&
      !dashboardCanvasSource.includes("<DashboardWidgetEditorPanel") &&
      !dashboardCanvasSource.includes('data-testid="widget-editor-panel"') &&
      !dashboardCanvasSource.includes('data-testid="widget-style-panel"') &&
      !dashboardCanvasSource.includes('data-testid="widget-local-filter-panel"') &&
      !dashboardCanvasSource.includes('data-testid="widget-lifecycle-actions"') &&
      !dashboardCanvasSource.includes("setWidgetDraft((draft) => ({ ...draft, title: event.target.value }))") &&
      !dashboardCanvasSource.includes("widgetToggleOptions.map(({ key, label, checked })") &&
      dashboardWidgetEditorPanelSource.includes("export function DashboardWidgetEditorPanel(") &&
      dashboardWidgetEditorPanelSource.includes("type DashboardWidgetEditorPanelProps") &&
      dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetBasicForm"') &&
      dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetLifecyclePanel"') &&
      dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetLocalFilterPanel"') &&
      dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetStylePanel"') &&
      dashboardWidgetEditorPanelSource.includes('data-testid="widget-editor-panel"') &&
      dashboardWidgetEditorPanelSource.includes("<DashboardWidgetBasicForm") &&
      dashboardWidgetEditorPanelSource.includes("<DashboardWidgetLocalFilterPanel") &&
      dashboardWidgetEditorPanelSource.includes("<DashboardWidgetLifecyclePanel") &&
      dashboardWidgetEditorPanelSource.includes("<DashboardWidgetStylePanel") &&
      !dashboardWidgetEditorPanelSource.includes('data-testid="widget-local-filter-panel"') &&
      !dashboardWidgetEditorPanelSource.includes('data-testid="widget-lifecycle-actions"') &&
      !dashboardWidgetEditorPanelSource.includes("setWidgetDraft((draft) => ({ ...draft, title: event.target.value }))") &&
      !dashboardWidgetEditorPanelSource.includes("widgetToggleOptions.map(({ key, label, checked })") &&
      dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"set-widget-dry\", widgetSettingsPayload(false))") &&
      !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"widget-filter-dry\"") &&
      !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"copy-widget-dry\"") &&
      implementationStatusSource.includes("Dashboard widget editor panel component boundary"),
  },
  {
    label: "dashboard-widget-basic-form-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardWidgetBasicForm.tsx")) &&
      dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetBasicForm"') &&
      dashboardWidgetEditorPanelSource.includes("<DashboardWidgetBasicForm") &&
      dashboardWidgetEditorPanelSource.includes("aggregations={aggregations}") &&
      dashboardWidgetEditorPanelSource.includes("draftDimensions={draftDimensions}") &&
      dashboardWidgetEditorPanelSource.includes("draftMeasures={draftMeasures}") &&
      dashboardWidgetEditorPanelSource.includes("draftViews={draftViews}") &&
      dashboardWidgetEditorPanelSource.includes("editableTables={editableTables}") &&
      dashboardWidgetEditorPanelSource.includes("valueFormats={valueFormats}") &&
      !dashboardWidgetEditorPanelSource.includes("widgetTypes.map((type)") &&
      !dashboardWidgetEditorPanelSource.includes("valueFormats.map((format)") &&
      !dashboardWidgetEditorPanelSource.includes("editableTables.map((table)") &&
      dashboardWidgetBasicFormSource.includes("export function DashboardWidgetBasicForm(") &&
      dashboardWidgetBasicFormSource.includes("type DashboardWidgetBasicFormProps") &&
      dashboardWidgetBasicFormSource.includes('data-testid="widget-basic-form"') &&
      dashboardWidgetBasicFormSource.includes("widgetTypes.map((type)") &&
      dashboardWidgetBasicFormSource.includes("editableTables.map((table)") &&
      dashboardWidgetBasicFormSource.includes("draftViews.map((view)") &&
      dashboardWidgetBasicFormSource.includes("draftDimensions.map((field)") &&
      dashboardWidgetBasicFormSource.includes("draftMeasures.map((field)") &&
      dashboardWidgetBasicFormSource.includes("valueFormats.map((format)") &&
      dashboardWidgetBasicFormSource.includes("widgetDraft.type === \"text\"") &&
      implementationStatusSource.includes("Dashboard widget basic form component boundary"),
  },
  {
    label: "dashboard-widget-style-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardWidgetStylePanel.tsx")) &&
      dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetStylePanel"') &&
      dashboardWidgetEditorPanelSource.includes("<DashboardWidgetStylePanel") &&
      dashboardWidgetEditorPanelSource.includes("colorPalettes={colorPalettes}") &&
      dashboardWidgetEditorPanelSource.includes("rankingModes={rankingModes}") &&
      dashboardWidgetEditorPanelSource.includes("slicerDisplays={slicerDisplays}") &&
      dashboardWidgetEditorPanelSource.includes("widgetToggleOptions={widgetToggleOptions}") &&
      !dashboardWidgetEditorPanelSource.includes("colorPalettes.map((palette)") &&
      !dashboardWidgetEditorPanelSource.includes("rankingModes.map((mode)") &&
      !dashboardWidgetEditorPanelSource.includes("slicerDisplays.map((display)") &&
      !dashboardWidgetEditorPanelSource.includes("widgetToggleOptions.map(({ key, label, checked })") &&
      dashboardWidgetStylePanelSource.includes("export function DashboardWidgetStylePanel(") &&
      dashboardWidgetStylePanelSource.includes("type DashboardWidgetStylePanelProps") &&
      dashboardWidgetStylePanelSource.includes('data-testid="widget-style-panel"') &&
      dashboardWidgetStylePanelSource.includes("colorPalettes.map((palette)") &&
      dashboardWidgetStylePanelSource.includes("rankingModes.map((mode)") &&
      dashboardWidgetStylePanelSource.includes("slicerDisplays.map((display)") &&
      dashboardWidgetStylePanelSource.includes("widgetToggleOptions.map(({ key, label, checked })") &&
      dashboardWidgetStylePanelSource.includes("Appearance and click behavior") &&
      implementationStatusSource.includes("Dashboard widget style panel component boundary"),
  },
  {
    label: "dashboard-widget-local-filter-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardWidgetLocalFilterPanel.tsx")) &&
      dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetLocalFilterPanel"') &&
      dashboardWidgetEditorPanelSource.includes("<DashboardWidgetLocalFilterPanel") &&
      dashboardWidgetEditorPanelSource.includes("draftFields={draftFields}") &&
      dashboardWidgetEditorPanelSource.includes("filterOperators={filterOperators}") &&
      dashboardWidgetEditorPanelSource.includes("nextWidgetFilters={nextWidgetFilters}") &&
      dashboardWidgetEditorPanelSource.includes("selectedWidgetKey={selectedWidget.widget_key}") &&
      dashboardWidgetEditorPanelSource.includes("widgetFilters={widgetFilters}") &&
      !dashboardWidgetEditorPanelSource.includes("widgetFilters.length ? widgetFilters.map") &&
      !dashboardWidgetEditorPanelSource.includes("filterOperators.map((operator)") &&
      !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"widget-filter-dry\"") &&
      dashboardWidgetLocalFilterPanelSource.includes("export function DashboardWidgetLocalFilterPanel(") &&
      dashboardWidgetLocalFilterPanelSource.includes("type DashboardWidgetLocalFilterPanelProps") &&
      dashboardWidgetLocalFilterPanelSource.includes('data-testid="widget-local-filter-panel"') &&
      dashboardWidgetLocalFilterPanelSource.includes('data-testid="widget-filter-preview-button"') &&
      dashboardWidgetLocalFilterPanelSource.includes('data-testid="widget-filter-apply-button"') &&
      dashboardWidgetLocalFilterPanelSource.includes('data-testid="widget-filter-clear-button"') &&
      dashboardWidgetLocalFilterPanelSource.includes("widgetFilters.length ? widgetFilters.map") &&
      dashboardWidgetLocalFilterPanelSource.includes("filterOperators.map((operator)") &&
      dashboardWidgetLocalFilterPanelSource.includes("onWidgetOperation(\"widget-filter-dry\"") &&
      dashboardWidgetLocalFilterPanelSource.includes("onWidgetOperation(\"widget-filter-clear\"") &&
      implementationStatusSource.includes("Dashboard widget local filter panel component boundary"),
  },
  {
    label: "dashboard-widget-lifecycle-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardWidgetLifecyclePanel.tsx")) &&
      dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetLifecyclePanel"') &&
      dashboardWidgetEditorPanelSource.includes("<DashboardWidgetLifecyclePanel") &&
      dashboardWidgetEditorPanelSource.includes("dashboardKey={dashboardKey}") &&
      dashboardWidgetEditorPanelSource.includes("selectedWidget={selectedWidget}") &&
      !dashboardWidgetEditorPanelSource.includes('data-testid="widget-copy-preview-button"') &&
      !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"copy-widget-dry\"") &&
      !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"remove-widget-dry\"") &&
      dashboardWidgetLifecyclePanelSource.includes("export function DashboardWidgetLifecyclePanel(") &&
      dashboardWidgetLifecyclePanelSource.includes("type DashboardWidgetLifecyclePanelProps") &&
      dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-lifecycle-actions"') &&
      dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-copy-preview-button"') &&
      dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-copy-confirm-button"') &&
      dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-remove-preview-button"') &&
      dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-remove-confirm-button"') &&
      dashboardWidgetLifecyclePanelSource.includes("onWidgetOperation(\"copy-widget-dry\"") &&
      dashboardWidgetLifecyclePanelSource.includes("onWidgetOperation(\"remove-widget-dry\"") &&
      dashboardWidgetLifecyclePanelSource.includes("Copy or delete widget") &&
      implementationStatusSource.includes("Dashboard widget lifecycle panel component boundary"),
  },
  {
    label: "dashboard-page-admin-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardPageAdminPanel.tsx")) &&
      dashboardCanvasSource.includes('from "./DashboardPageAdminPanel"') &&
      dashboardCanvasSource.includes("<DashboardPageAdminPanel") &&
      dashboardCanvasSource.includes("dashboardPages={dashboardPages}") &&
      dashboardCanvasSource.includes("draftName={draftName}") &&
      dashboardCanvasSource.includes("onDashboardOperation={runDashboardOperation}") &&
      dashboardCanvasSource.includes("onDashboardSelect={onDashboardSelect}") &&
      dashboardCanvasSource.includes("setDraftName={setDraftName}") &&
      !dashboardCanvasSource.includes('data-testid="dashboard-page-admin-panel"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-create-button"') &&
      !dashboardCanvasSource.includes("dashboardPages.map((item)") &&
      !dashboardCanvasSource.includes("setDraftName(event.target.value)") &&
      dashboardPageAdminPanelSource.includes("export function DashboardPageAdminPanel(") &&
      dashboardPageAdminPanelSource.includes("type DashboardPageAdminPanelProps") &&
      dashboardPageAdminPanelSource.includes('data-testid="dashboard-page-admin-panel"') &&
      dashboardPageAdminPanelSource.includes('data-testid="dashboard-create-button"') &&
      dashboardPageAdminPanelSource.includes('data-testid="dashboard-copy-button"') &&
      dashboardPageAdminPanelSource.includes('data-testid="dashboard-rename-button"') &&
      dashboardPageAdminPanelSource.includes('data-testid="dashboard-delete-button"') &&
      dashboardPageAdminPanelSource.includes("dashboardPages.map((item)") &&
      dashboardPageAdminPanelSource.includes("onDashboardSelect(item.dashboard_key)") &&
      dashboardPageAdminPanelSource.includes("onDashboardOperation(\"create\"") &&
      dashboardPageAdminPanelSource.includes("onDashboardOperation(\"delete\"") &&
      hasCssRule(stylesSource, ".dashboardOps", "display: grid;") &&
      stylesSource.includes("grid-template-columns: repeat(auto-fit, minmax(136px, 1fr));") &&
      stylesSource.includes(".dashboardOps > button") &&
      hasCssRule(stylesSource, ".businessTemplatePanel", "grid-column: span 2;") &&
      hasCssRule(stylesSource, ".businessTemplatePanel .dashboardOps", "grid-template-columns: repeat(3, minmax(0, 1fr));") &&
      hasCssRule(stylesSource, ".erpTemplateStats", "display: grid;", "grid-template-columns: repeat(auto-fit, minmax(104px, 1fr));") &&
      hasCssRule(stylesSource, ".erpOmittedUnitList", "display: grid;", "grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));") &&
      hasCssRule(stylesSource, ".erpUnitPreviewList", "display: grid;") &&
      hasCssRule(stylesSource, ".erpUnitPreviewList", "grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));") &&
      implementationStatusSource.includes("Dashboard page admin panel component boundary"),
  },
  {
    label: "dashboard-contract-boundary-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardContractBoundaryPanel.tsx")) &&
      dashboardCanvasSource.includes('from "./DashboardContractBoundaryPanel"') &&
      dashboardCanvasSource.includes("<DashboardContractBoundaryPanel") &&
      dashboardCanvasSource.includes("widgets={dashboardWidgets}") &&
      !dashboardCanvasSource.includes('data-testid="dashboard-contract-boundary-panel"') &&
      !dashboardCanvasSource.includes("查看组件合同和动作边界") &&
      !dashboardCanvasSource.includes("dashboardWidgets.map((widget)") &&
      !dashboardCanvasSource.includes("Object.entries(widget.config ?? {})") &&
      dashboardContractBoundaryPanelSource.includes("export function DashboardContractBoundaryPanel(") &&
      dashboardContractBoundaryPanelSource.includes("type DashboardContractBoundaryPanelProps") &&
      dashboardContractBoundaryPanelSource.includes('data-testid="dashboard-contract-boundary-panel"') &&
      dashboardContractBoundaryPanelSource.includes("Widget contract") &&
      dashboardContractBoundaryPanelSource.includes("Action boundary") &&
      dashboardContractBoundaryPanelSource.includes("widgets.map((widget)") &&
      dashboardContractBoundaryPanelSource.includes("Object.entries(widget.config ?? {})") &&
      dashboardContractBoundaryPanelSource.includes("Import commit, dashboard write, relationship save, index creation, external sync.") &&
      implementationStatusSource.includes("Dashboard contract boundary panel component boundary"),
  },
  {
    label: "dashboard-overview-strip-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardOverviewStrip.tsx")) &&
      dashboardCanvasSource.includes('from "./DashboardOverviewStrip"') &&
      dashboardCanvasSource.includes("<DashboardOverviewStrip") &&
      dashboardCanvasSource.includes("dashboardSummary={dashboardSummary}") &&
      dashboardCanvasSource.includes("dashboardWidgetsCount={dashboardWidgets.length}") &&
      dashboardCanvasSource.includes("dashboardFiltersCount={dashboardFilters.length}") &&
      dashboardCanvasSource.includes("onOpenEvidence={openDashboardEvidence}") &&
      !dashboardCanvasSource.includes('data-testid="dashboard-asset-source-strip"') &&
      !dashboardCanvasSource.includes('className="dashboardStoryStrip wide"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-component-acceptance-strip"') &&
      !dashboardCanvasSource.includes("dashboardAcceptanceItems.map") &&
      dashboardOverviewStripSource.includes("export function DashboardOverviewStrip(") &&
      dashboardOverviewStripSource.includes("type DashboardOverviewStripProps") &&
      dashboardOverviewStripSource.includes('data-testid="dashboard-asset-source-strip"') &&
      dashboardOverviewStripSource.includes('className="dashboardStoryStrip wide"') &&
      dashboardOverviewStripSource.includes('data-testid="dashboard-component-acceptance-strip"') &&
      dashboardOverviewStripSource.includes("dashboardAcceptanceItems.map") &&
      dashboardOverviewStripSource.includes("dashboardSummary.topRow") &&
      dashboardOverviewStripSource.includes("dashboardWidgetsCount") &&
      dashboardOverviewStripSource.includes("dashboardFiltersCount") &&
      implementationStatusSource.includes("Dashboard overview strip component boundary"),
  },
  {
    label: "dashboard-filter-workbench-component-boundary",
    ok: existsSync(join(root, "src", "components", "DashboardFilterWorkbench.tsx")) &&
      dashboardCanvasSource.includes('from "./DashboardFilterWorkbench"') &&
      dashboardCanvasSource.includes("<DashboardFilterWorkbench") &&
      dashboardCanvasSource.includes("dashboardFilters={dashboardFilters}") &&
      dashboardCanvasSource.includes("availableFilterFields={availableFilterFields}") &&
      dashboardCanvasSource.includes("onFilterOperation={runFilterOperation}") &&
      dashboardCanvasSource.includes("operatorLabel={operatorLabel}") &&
      !dashboardCanvasSource.includes('className="dashboardFilterWorkbench wide"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-filter-preview"') &&
      !dashboardCanvasSource.includes("dashboardFilters.length ? dashboardFilters.map") &&
      !dashboardCanvasSource.includes("runFilterOperation(`remove-${filter.id}`") &&
      dashboardFilterWorkbenchSource.includes("export function DashboardFilterWorkbench(") &&
      dashboardFilterWorkbenchSource.includes("type DashboardFilterWorkbenchProps") &&
      dashboardFilterWorkbenchSource.includes('className="dashboardFilterWorkbench wide"') &&
      dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-preview"') &&
      dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-apply"') &&
      dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-clear"') &&
      dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-stale-preview"') &&
      dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-stale-remove"') &&
      dashboardFilterWorkbenchSource.includes("dashboardFilters.length ? dashboardFilters.map") &&
      dashboardFilterWorkbenchSource.includes("filterOperators.map((operator)") &&
      dashboardFilterWorkbenchSource.includes("onFilterOperation(`remove-${filter.id}`") &&
      implementationStatusSource.includes("Dashboard filter workbench component boundary"),
  },
  {
    label: "frontend-dashboard-source-switch-preview",
    ok: dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-panel"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-select"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-preview"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-confirm"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-impact"') &&
      dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-stale-list"') &&
      dashboardCanvasViewModelSource.includes("sourceSwitchAnalysis") &&
      dashboardBeginnerEditorSource.includes("sourceSwitchView.impactItems.map") &&
      dashboardBeginnerEditorSource.includes("sourceSwitchView.staleItems.map") &&
      dashboardCanvasActionsSource.includes("sourceSwitchModulePayload") &&
      dashboardCanvasActionsSource.includes("buildSourceSwitchModulePayload({") &&
      dashboardBeginnerEditorSource.includes("onSourceSwitch(false)") &&
      byLabel["cli-dashboard-source-switch-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-dashboard-source-switch-dry-run"].parsed?.proposed?.defaultTableKey === "refunds",
  },
  {
    label: "dashboard-canvas-source-switch-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasSourceSwitchModel.ts")) &&
      dashboardCanvasViewModelSource.includes('from "./dashboardCanvasSourceSwitchModel"') &&
      dashboardCanvasActionsSource.includes('from "./dashboardCanvasSourceSwitchModel"') &&
      dashboardCanvasViewModelSource.includes("analyzeDashboardSourceSwitch({") &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasSourceSwitchModel"') &&
      !dashboardCanvasSource.includes("analyzeDashboardSourceSwitch({") &&
      dashboardCanvasActionsSource.includes("buildSourceSwitchModulePayload({") &&
      !dashboardCanvasSource.includes("buildSourceSwitchModulePayload({") &&
      !dashboardCanvasSource.includes("sourceSwitchTargetFields") &&
      !dashboardCanvasSource.includes("sourceSwitchTargetFieldNames") &&
      !dashboardCanvasSource.includes("sourceSwitchValidFilters") &&
      !dashboardCanvasSource.includes("function cleanedWidgetForSourceSwitch(") &&
      !dashboardCanvasSource.includes("const localFilters = normalizeDashboardFilters({ globalFilters: Array.isArray(config.filters)") &&
      dashboardCanvasSourceSwitchModelSource.includes("export type SourceSwitchStaleWidgetRef") &&
      dashboardCanvasSourceSwitchModelSource.includes("export type SourceSwitchAnalysis") &&
      dashboardCanvasSourceSwitchModelSource.includes('import { normalizeWidgetFilters } from "./dashboardCanvasFilterModel"') &&
      dashboardCanvasSourceSwitchModelSource.includes("normalizeWidgetFilters(config.filters)") &&
      !dashboardCanvasSourceSwitchModelSource.includes("function normalizeWidgetConfigFilters(") &&
      dashboardCanvasSourceSwitchModelSource.includes("export function analyzeDashboardSourceSwitch(") &&
      dashboardCanvasSourceSwitchModelSource.includes("export function cleanedWidgetForSourceSwitch(") &&
      dashboardCanvasSourceSwitchModelSource.includes("export function buildSourceSwitchModulePayload(") &&
      dashboardCanvasSourceSwitchModelSource.includes('["dimension", "group", "measure", "timeField"]') &&
      dashboardCanvasSourceSwitchModelSource.includes("filterCleanup.length + staleWidgetRefs.length") &&
      dashboardCanvasSourceSwitchModelSource.includes("defaultTableKey: sourceSwitchTableKey") &&
      implementationStatusSource.includes("Dashboard canvas source switch model boundary"),
  },
  {
    label: "dashboard-canvas-source-switch-view-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasSourceSwitchViewModel.ts")) &&
      dashboardCanvasViewModelSource.includes('from "./dashboardCanvasSourceSwitchViewModel"') &&
      dashboardCanvasViewModelSource.includes("buildDashboardSourceSwitchViewModel(sourceSwitchAnalysis)") &&
      dashboardCanvasViewModelSource.includes("sourceSwitchView.changed") &&
      dashboardCanvasViewModelSource.includes("sourceSwitchView.cleanupCount") &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasSourceSwitchViewModel"') &&
      !dashboardCanvasSource.includes("buildDashboardSourceSwitchViewModel(sourceSwitchAnalysis)") &&
      dashboardBeginnerEditorSource.includes("sourceSwitchView.impactItems.map") &&
      dashboardBeginnerEditorSource.includes("sourceSwitchView.showStaleList") &&
      dashboardBeginnerEditorSource.includes("sourceSwitchView.staleItems.map") &&
      !dashboardCanvasSource.includes("const sourceSwitchImpactedWidgets =") &&
      !dashboardCanvasSource.includes("const sourceSwitchFilterCleanup =") &&
      !dashboardCanvasSource.includes("const sourceSwitchStaleWidgetRefs =") &&
      !dashboardCanvasSource.includes("sourceSwitchFilterCleanup.slice(") &&
      !dashboardCanvasSource.includes("sourceSwitchStaleWidgetRefs.slice(") &&
      !dashboardCanvasSource.includes("widgets follow default source") &&
      !dashboardCanvasSource.includes("全局筛选需清理") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("export type SourceSwitchViewItem") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("export type DashboardSourceSwitchViewModel") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("export function buildDashboardSourceSwitchViewModel(") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("showStaleList: analysis.changed && analysis.cleanupCount > 0") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("impactItems: [") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("staleItems: [") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("analysis.filterCleanup.slice(0, 3)") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("analysis.staleWidgetRefs.slice(0, 4)") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("widgets follow default source") &&
      dashboardCanvasSourceSwitchViewModelSource.includes("全局筛选需清理") &&
      implementationStatusSource.includes("Dashboard canvas source switch view model boundary"),
  },
  {
    label: "dashboard-canvas-readiness-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasReadinessModel.ts")) &&
      dashboardCanvasViewModelSource.includes('from "./dashboardCanvasReadinessModel"') &&
      dashboardCanvasViewModelSource.includes("buildDashboardReadinessModel({") &&
      dashboardCanvasViewModelSource.includes("buildDashboardEvidenceFocus({") &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasReadinessModel"') &&
      !dashboardCanvasSource.includes("buildDashboardReadinessModel({") &&
      !dashboardCanvasSource.includes("buildDashboardEvidenceFocus({") &&
      !dashboardCanvasSource.includes('const dashboardCreatedBy = String(dashboard.created_by || "manual")') &&
      !dashboardCanvasSource.includes("const dashboardHealthItems = [") &&
      !dashboardCanvasSource.includes('source: "dashboard-summary",') &&
      dashboardCanvasReadinessModelSource.includes("export type DashboardHealthTone") &&
      dashboardCanvasReadinessModelSource.includes("export function buildDashboardReadinessModel(") &&
      dashboardCanvasReadinessModelSource.includes("export function buildDashboardEvidenceFocus(") &&
      dashboardCanvasReadinessModelSource.includes("Agent 生成") &&
      dashboardOverviewStripSource.includes("Editable asset, not a black-box result") &&
      dashboardCanvasReadinessModelSource.includes("source-intelligence:") &&
      implementationStatusSource.includes("Dashboard canvas readiness model boundary"),
  },
  {
    label: "dashboard-canvas-plan-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasPlanModel.ts")) &&
      dashboardCanvasViewModelSource.includes('from "./dashboardCanvasPlanModel"') &&
      dashboardCanvasViewModelSource.includes("summarizeDashboardWidgetPlan(widgetPlan)") &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasPlanModel"') &&
      !dashboardCanvasSource.includes("summarizeDashboardWidgetPlan(widgetPlan)") &&
      dashboardModuleSavePanelSource.includes("dashboardModuleSaveReceipt(moduleSaveResult") &&
      !dashboardCanvasSource.includes("function moduleResultNumber(") &&
      !dashboardCanvasSource.includes("const plannedWidgets = Array.isArray(widgetPlan?.plannedWidgets)") &&
      !dashboardCanvasSource.includes("const businessTemplateCount = typeof widgetPlan?.templateCount") &&
      !dashboardCanvasSource.includes("预演完成，确认前不会写入") &&
      dashboardCanvasPlanModelSource.includes("export type DashboardWidgetPlanSummary") &&
      dashboardCanvasPlanModelSource.includes("export type DashboardModuleSaveReceipt") &&
      dashboardCanvasPlanModelSource.includes("function moduleResultNumber(") &&
      dashboardCanvasPlanModelSource.includes("export function summarizeDashboardWidgetPlan(") &&
      dashboardCanvasPlanModelSource.includes("export function dashboardModuleSaveReceipt(") &&
      dashboardCanvasPlanModelSource.includes("savedDashboardModules") &&
      dashboardCanvasPlanModelSource.includes("确认前不会写入") &&
      dashboardCanvasPlanModelSource.includes("刷新后仍会保留") &&
      implementationStatusSource.includes("Dashboard canvas plan model boundary"),
  },
  {
    label: "dashboard-canvas-filter-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasFilterModel.ts")) &&
      dashboardCanvasSource.includes('from "../dashboardCanvasFilterModel"') &&
      dashboardCanvasStateSource.includes('from "./dashboardCanvasFilterModel"') &&
      dashboardCanvasSource.includes("normalizeDashboardFilters(dashboard.layout)") &&
      dashboardCanvasStateSource.includes("normalizeWidgetFilters(selectedWidget.config?.filters)") &&
      dashboardCanvasViewModelSource.includes("buildNextWidgetFilters({") &&
      !dashboardCanvasSource.includes("buildNextWidgetFilters({") &&
      dashboardCanvasSource.includes("filterOperators={filterOperators}") &&
      dashboardCanvasSource.includes("operatorLabel={operatorLabel}") &&
      !dashboardCanvasSource.includes("function normalizeDashboardFilters(") &&
      !dashboardCanvasSource.includes("function operatorLabel(") &&
      !dashboardCanvasSource.includes('const filterOperators = ["contains"') &&
      !dashboardCanvasSource.includes("...widgetFilters.map((filter) => ({ field: filter.field") &&
      dashboardFilterWorkbenchSource.includes("filterOperators.map") &&
      dashboardFilterWorkbenchSource.includes("operatorLabel(filter.operator)") &&
      dashboardCanvasFilterModelSource.includes("export const filterOperators") &&
      dashboardCanvasFilterModelSource.includes("export function normalizeDashboardFilterList(") &&
      dashboardCanvasFilterModelSource.includes("export function normalizeDashboardFilters(") &&
      dashboardCanvasFilterModelSource.includes("export function normalizeWidgetFilters(") &&
      dashboardCanvasFilterModelSource.includes("export function buildNextWidgetFilters(") &&
      dashboardCanvasFilterModelSource.includes("export function operatorLabel(") &&
      dashboardCanvasFilterModelSource.includes("scope = \"dashboard\"") &&
      dashboardCanvasFilterModelSource.includes("normalizeDashboardFilterList(value, \"widget\")") &&
      dashboardCanvasSourceSwitchModelSource.includes("normalizeWidgetFilters(config.filters)") &&
      implementationStatusSource.includes("Dashboard canvas filter model boundary"),
  },
  {
    label: "dashboard-canvas-field-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasFieldModel.ts")) &&
      dashboardCanvasStateSource.includes('from "./dashboardCanvasFieldModel"') &&
      dashboardCanvasStateSource.includes("buildDashboardCanvasFieldModel({") &&
      dashboardCanvasSource.includes("availableFilterFields") &&
      dashboardCanvasSource.includes("usableViews") &&
      dashboardCanvasSource.includes("draftDimensions") &&
      dashboardCanvasSource.includes("draftMeasures") &&
      dashboardCanvasSource.includes("draftViews") &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasFieldModel"') &&
      !dashboardCanvasSource.includes("buildDashboardCanvasFieldModel({") &&
      !dashboardCanvasSource.includes("const tableFields = workbench.fields.filter(") &&
      !dashboardCanvasSource.includes("const filterableFields = tableFields.filter(") &&
      !dashboardCanvasSource.includes("const currentTableViews = savedViews.filter(") &&
      !dashboardCanvasSource.includes("const draftFields = workbench.fields.filter(") &&
      !dashboardCanvasSource.includes("const draftDimensions = draftFields.filter((field)") &&
      !dashboardCanvasSource.includes("const draftMeasures = draftFields.filter((field)") &&
      !dashboardCanvasSource.includes("const draftViews = savedViews.filter(") &&
      dashboardCanvasFieldModelSource.includes("export type DashboardCanvasFieldModel") &&
      dashboardCanvasFieldModelSource.includes("export function isDashboardDimensionField(") &&
      dashboardCanvasFieldModelSource.includes("export function isDashboardMeasureField(") &&
      dashboardCanvasFieldModelSource.includes("export function buildDashboardCanvasFieldModel(") &&
      dashboardCanvasFieldModelSource.includes("availableFilterFields = filterableFields.length ? filterableFields : tableFields") &&
      dashboardCanvasFieldModelSource.includes("usableViews = currentTableViews.length ? currentTableViews : savedViews") &&
      dashboardCanvasFieldModelSource.includes("draftFields.filter(isDashboardDimensionField)") &&
      dashboardCanvasFieldModelSource.includes("draftFields.filter(isDashboardMeasureField)") &&
      implementationStatusSource.includes("Dashboard canvas field model boundary"),
  },
  {
    label: "dashboard-canvas-state-hook-boundary",
    ok: existsSync(join(root, "src", "useDashboardCanvasState.ts")) &&
      dashboardCanvasSource.includes('from "../useDashboardCanvasState"') &&
      dashboardCanvasSource.includes("useDashboardCanvasState({") &&
      dashboardCanvasSource.includes("savedRelationships,") &&
      !dashboardCanvasSource.includes('from "react"') &&
      !dashboardCanvasSource.includes("useEffect(() =>") &&
      !dashboardCanvasSource.includes("const [draftName, setDraftName]") &&
      !dashboardCanvasSource.includes("const [selectedWidgetKey, setSelectedWidgetKey]") &&
      !dashboardCanvasSource.includes("const selectedWidget = dashboardWidgets.find") &&
      dashboardCanvasStateSource.includes("export function useDashboardCanvasState(") &&
      dashboardCanvasStateSource.includes("type DashboardCanvasStateOptions") &&
      dashboardCanvasStateSource.includes("const [draftName, setDraftName] = useState") &&
      dashboardCanvasStateSource.includes("const [selectedWidgetKey, setSelectedWidgetKey] = useState") &&
      dashboardCanvasStateSource.includes("const selectedWidget = useMemo(") &&
      dashboardCanvasStateSource.includes("dashboardWidgets.find((widget) => widget.widget_key === selectedWidgetKey)") &&
      dashboardCanvasStateSource.includes("const fieldModel = useMemo(() => buildDashboardCanvasFieldModel({") &&
      dashboardCanvasStateSource.includes("setDraftName(dashboard?.name ?? \"\")") &&
      dashboardCanvasStateSource.includes("setCanvasWidthMode(dashboard.layout?.canvasWidthMode === \"center\" ? \"center\" : \"stretch\")") &&
      dashboardCanvasStateSource.includes("setSourceSwitchTableKey(dashboard.default_table_key)") &&
      dashboardCanvasStateSource.includes("setFilterField((current)") &&
      dashboardCanvasStateSource.includes("setSelectedViewKey((current)") &&
      dashboardCanvasStateSource.includes("setSelectedRelationshipKey((current)") &&
      dashboardCanvasStateSource.includes("setSelectedWidgetKey((current)") &&
      dashboardCanvasStateSource.includes("setWidgetDraft(widgetDraftFromWidget(widget))") &&
      dashboardCanvasStateSource.includes("setWidgetFilterField((current)") &&
      implementationStatusSource.includes("Dashboard canvas state hook boundary"),
  },
  {
    label: "dashboard-canvas-actions-hook-boundary",
    ok: existsSync(join(root, "src", "useDashboardCanvasActions.ts")) &&
      dashboardCanvasSource.includes('from "../useDashboardCanvasActions"') &&
      dashboardCanvasSource.includes("useDashboardCanvasActions({") &&
      dashboardCanvasSource.includes("onDashboardWidgetOperation,") &&
      dashboardCanvasSource.includes("selectedWidgetKey: selectedWidget?.widget_key") &&
      !dashboardCanvasSource.includes("async function runDashboardOperation") &&
      !dashboardCanvasSource.includes("function dashboardModulePayload") &&
      !dashboardCanvasSource.includes("function sourceSwitchModulePayload") &&
      !dashboardCanvasSource.includes("const widgetSettingsPayload = (confirm: boolean)") &&
      !dashboardCanvasSource.includes("buildRelationshipSavePayload(recommendation, confirm)") &&
      dashboardCanvasActionsSource.includes("export function useDashboardCanvasActions(") &&
      dashboardCanvasActionsSource.includes("type DashboardCanvasActionsOptions") &&
      dashboardCanvasActionsSource.includes("async function runDashboardOperation(") &&
      dashboardCanvasActionsSource.includes("async function runFilterOperation(") &&
      dashboardCanvasActionsSource.includes("async function runWidgetOperation(") &&
      dashboardCanvasActionsSource.includes("function dashboardModulePayload(") &&
      dashboardCanvasActionsSource.includes("function sourceSwitchModulePayload(") &&
      dashboardCanvasActionsSource.includes("async function runModuleSave(") &&
      dashboardCanvasActionsSource.includes("async function runSourceSwitch(") &&
      dashboardCanvasActionsSource.includes("async function runBusinessTemplate(") &&
      dashboardCanvasActionsSource.includes("async function runDashboardAsk(") &&
      dashboardCanvasActionsSource.includes("async function runRelationshipSave(") &&
      dashboardCanvasActionsSource.includes("const widgetSettingsPayload = (confirm: boolean)") &&
      dashboardCanvasActionsSource.includes("return {") &&
      implementationStatusSource.includes("Dashboard canvas actions hook boundary"),
  },
  {
    label: "dashboard-canvas-action-runner-boundary",
    ok: existsSync(join(root, "src", "useDashboardCanvasActionRunner.ts")) &&
      dashboardCanvasActionsSource.includes('from "./useDashboardCanvasActionRunner"') &&
      dashboardCanvasActionsSource.includes("useDashboardCanvasActionRunner()") &&
      dashboardCanvasActionsSource.includes("runVoidAction(label, () => onDashboardOperation(options))") &&
      dashboardCanvasActionsSource.includes("runVoidAction(label, () => onDashboardFilterOperation(options))") &&
      dashboardCanvasActionsSource.includes("runPlanAction(label, () => onDashboardWidgetOperation(options))") &&
      dashboardCanvasActionsSource.includes("runPlanAction(label, () => onDashboardModulesSave(dashboardModulePayload(confirm)))") &&
      dashboardCanvasActionsSource.includes("runPlanAction(label, () => onDashboardModulesSave(sourceSwitchModulePayload(confirm)))") &&
      dashboardCanvasActionsSource.includes("runPlanAction(label, () => onBusinessDashboardOperation(options))") &&
      dashboardCanvasActionsSource.includes("runVoidAction(label, () => onAsk(prompt))") &&
      dashboardCanvasActionsSource.includes("runPlanAction(label, () => onRelationshipSave(payload))") &&
      !dashboardCanvasSource.includes('from "../useDashboardCanvasActionRunner"') &&
      !dashboardCanvasSource.includes("useDashboardCanvasActionRunner()") &&
      !dashboardCanvasSource.includes("runVoidAction(label") &&
      !dashboardCanvasSource.includes("runPlanAction(label") &&
      !dashboardCanvasSource.includes("const [busy, setBusy] = useState") &&
      !dashboardCanvasSource.includes("const [widgetPlan, setWidgetPlan] = useState") &&
      !dashboardCanvasSource.includes("setBusy(label);") &&
      !dashboardCanvasSource.includes("setWidgetPlan(result);") &&
      dashboardCanvasActionRunnerSource.includes("export function useDashboardCanvasActionRunner(") &&
      dashboardCanvasActionRunnerSource.includes("const [busy, setBusy] = useState<string | null>(null)") &&
      dashboardCanvasActionRunnerSource.includes("const [widgetPlan, setWidgetPlan] = useState<PlanResult | null>(null)") &&
      dashboardCanvasActionRunnerSource.includes("async function runVoidAction(") &&
      dashboardCanvasActionRunnerSource.includes("async function runPlanAction(") &&
      dashboardCanvasActionRunnerSource.includes("setWidgetPlan(result)") &&
      dashboardCanvasActionRunnerSource.includes("setBusy(null)") &&
      implementationStatusSource.includes("Dashboard canvas action runner boundary"),
  },
  {
    label: "dashboard-canvas-relationship-model-boundary",
    ok: existsSync(join(root, "src", "dashboardCanvasRelationshipModel.ts")) &&
      dashboardCanvasActionsSource.includes('from "./dashboardCanvasRelationshipModel"') &&
      dashboardCanvasActionsSource.includes("buildRelationshipSavePayload(recommendation, confirm)") &&
      dashboardCanvasActionsSource.includes("if (!payload) return") &&
      !dashboardCanvasSource.includes('from "../dashboardCanvasRelationshipModel"') &&
      !dashboardCanvasSource.includes("buildRelationshipSavePayload(recommendation, confirm)") &&
      !dashboardCanvasSource.includes("if (!payload) return") &&
      !dashboardCanvasSource.includes("relationshipPrimaryMapping(recommendation)") &&
      !dashboardCanvasSource.includes("relationshipRecommendationKey(recommendation)") &&
      !dashboardCanvasSource.includes("relationshipMappingLabel(recommendation)") &&
      dashboardRelationshipRecommendationPanelSource.includes("relationshipPrimaryMapping(recommendation)") &&
      dashboardRelationshipRecommendationPanelSource.includes("relationshipRecommendationKey(recommendation)") &&
      dashboardRelationshipRecommendationPanelSource.includes("relationshipMappingLabel(recommendation)") &&
      !dashboardCanvasSource.includes("const mapping = recommendation.fieldMappings?.[0]") &&
      !dashboardCanvasSource.includes("leftTable: recommendation.leftTableKey") &&
      !dashboardCanvasSource.includes("joinType: recommendation.joinType || \"left\"") &&
      !dashboardCanvasSource.includes("limit: 20") &&
      dashboardCanvasRelationshipModelSource.includes("export type RelationshipSavePayload") &&
      dashboardCanvasRelationshipModelSource.includes("export function relationshipPrimaryMapping(") &&
      dashboardCanvasRelationshipModelSource.includes("export function relationshipRecommendationKey(") &&
      dashboardCanvasRelationshipModelSource.includes("export function relationshipMappingLabel(") &&
      dashboardCanvasRelationshipModelSource.includes("export function buildRelationshipSavePayload(") &&
      dashboardCanvasRelationshipModelSource.includes("recommendation.fieldMappings?.[0] ?? null") &&
      dashboardCanvasRelationshipModelSource.includes("joinType: recommendation.joinType || \"left\"") &&
      dashboardCanvasRelationshipModelSource.includes("limit: 20") &&
      implementationStatusSource.includes("Dashboard canvas relationship model boundary"),
  },
  {
    label: "frontend-saved-view-evidence-click-path",
    ok: viewWorkspaceSource.includes('data-testid="view-evidence-button"') &&
      viewWorkspaceSource.includes('source: "saved-view"') &&
      viewWorkspaceSource.includes('"saved-view-config"') &&
      viewWorkspaceSource.includes('"table-query-contract"') &&
      viewWorkspaceSource.includes("source-intelligence:") &&
      appSource.includes("onOpenEvidence={handleOpenEvidence}") &&
      evidenceViewSource.includes("focus?.viewKey") &&
      evidenceViewSource.includes("data-testid=\"evidence-focus-detail\"") &&
      evidenceViewModelSource.includes("保存视图口径") &&
      evidenceViewModelSource.includes("Detail query receipt"),
  },
  {
    label: "frontend-view-agent-task-strip",
    ok: viewAgentTaskStripSource.includes('data-testid="view-agent-task-strip"') &&
      viewAgentTaskStripSource.includes('import { AgentPromptGrid } from "./AgentPromptGrid"') &&
      viewAgentTaskStripSource.includes("<AgentPromptGrid") &&
      viewAgentTaskStripSource.includes('testId="view-agent-prompt-grid"') &&
      viewAgentTaskStripSource.includes('itemTestIdPrefix="view-agent-prompt"') &&
      viewWorkspaceSource.includes("buildViewAgentPrompts") &&
      viewWorkspaceModelSource.includes("export function buildViewAgentPrompts") &&
      viewWorkspaceModelSource.includes('"explain"') &&
      viewWorkspaceModelSource.includes('"find-anomaly"') &&
      viewWorkspaceModelSource.includes('"dashboard-widget"') &&
      viewWorkspaceModelSource.includes("不要创建待确认修改") &&
      viewWorkspaceModelSource.includes("不要直接修改数据") &&
      viewWorkspaceModelSource.includes("先不要直接写入") &&
      agentPromptGridSource.includes("onAsk(item.prompt)") &&
      appSource.includes("onAsk={handleAgentCommandAsk}") &&
      stylesSource.includes(".viewAgentTaskStrip") &&
      stylesSource.includes(".agentPromptGrid") &&
      stylesSource.includes(".viewAgentTaskStrip .agentPromptGrid button"),
  },
  {
    label: "view-agent-task-strip-component-boundary",
    ok: existsSync(join(root, "src", "components", "ViewAgentTaskStrip.tsx")) &&
      viewWorkspaceSource.includes('import { ViewAgentTaskStrip } from "./ViewAgentTaskStrip"') &&
      viewWorkspaceSource.includes("<ViewAgentTaskStrip") &&
      !viewWorkspaceSource.includes('data-testid="view-agent-task-strip"') &&
      viewAgentTaskStripSource.includes("type ViewAgentTaskStripProps") &&
      viewAgentTaskStripSource.includes("viewAgentPrompts: ViewAgentPrompt[]") &&
      viewAgentTaskStripSource.includes("不用导出表格，直接问当前视图") &&
      viewAgentTaskStripSource.includes('itemTestIdPrefix="view-agent-prompt"') &&
      implementationStatusSource.includes("View Agent task strip component boundary"),
  },
  {
    label: "frontend-saved-view-dashboard-bridge",
    ok: viewWorkspaceSource.includes("<ViewDashboardBridgePanel") &&
      viewDashboardBridgePanelSource.includes('data-testid="view-dashboard-bridge"') &&
      viewDashboardBridgePanelSource.includes('data-testid="view-dashboard-bridge-facts"') &&
      viewDashboardBridgePanelSource.includes('data-testid="view-dashboard-bridge-steps"') &&
      viewDashboardBridgePanelSource.includes('data-testid={`view-bridge-step-${step.key}`}') &&
      viewDashboardBridgePanelSource.includes('data-testid="view-bridge-evidence"') &&
      viewDashboardBridgePanelSource.includes('data-testid="view-bridge-agent-widget"') &&
      viewWorkspaceSource.includes("viewCanFeedDashboard") &&
      viewWorkspaceSource.includes("bridgeEvidenceCount") &&
      viewWorkspaceSource.includes("bridgeFilterScopeCount") &&
      viewWorkspaceSource.includes("viewReadinessLabel") &&
      viewWorkspaceSource.includes("viewScopeScore") &&
      viewWorkspaceSource.includes("ViewOperationReceipt") &&
      viewWorkspaceSource.includes('from "../viewWorkspaceModel"') &&
      viewWorkspaceSource.includes("buildViewBridgeSteps") &&
      viewWorkspaceModelSource.includes("export type ViewOperationReceipt") &&
      viewWorkspaceModelSource.includes("export function viewColumns") &&
      viewWorkspaceModelSource.includes("export function viewFilters") &&
      viewWorkspaceModelSource.includes("export function viewSort") &&
      viewWorkspaceModelSource.includes("export function viewSearch") &&
      viewWorkspaceModelSource.includes("export function viewName") &&
      viewWorkspaceModelSource.includes("export function buildViewBridgeSteps") &&
      !viewWorkspaceSource.includes("function viewColumns(") &&
      !viewWorkspaceSource.includes("function viewFilters(") &&
      !viewWorkspaceSource.includes("function viewSort(") &&
      !viewWorkspaceSource.includes("function viewSearch(") &&
      !viewWorkspaceSource.includes("function viewName(") &&
      viewWorkspaceSource.includes("runViewQueryAction") &&
      viewWorkspaceSource.includes("runSaveCurrentSearch") &&
      viewWorkspaceSource.includes("runCopyView") &&
      viewWorkspaceSource.includes("runDeleteView") &&
      viewWorkspaceSource.includes('data-testid="view-operation-receipt"') &&
      viewWorkspaceSource.includes('data-testid="view-operation-technical-details"') &&
      viewWorkspaceSource.includes("View scope and paging") &&
      viewWorkspaceSource.includes("视图已切换并刷新") &&
      viewWorkspaceSource.includes("当前搜索已保存到视图") &&
      viewWorkspaceModelSource.includes("固定视图口径") &&
      viewWorkspaceModelSource.includes("Refresh rows") &&
      viewWorkspaceModelSource.includes("Agent creates a pending change only") &&
      viewDashboardBridgePanelSource.includes("生成一个待确认的看板组件") &&
      viewDashboardBridgePanelSource.includes("不要直接写入") &&
      viewWorkspaceSource.includes('data-testid="view-query-diagnostics"') &&
      viewWorkspaceSource.includes('data-testid="view-query-technical-details"') &&
      stylesSource.includes(".viewOperationReceipt") &&
      viewWorkspaceSource.includes("看板来源") &&
      !viewWorkspaceSource.includes('<span>{biText("执行", "runtime")}</span>') &&
      stylesSource.includes(".viewBridgePanel") &&
      stylesSource.includes(".viewBridgeFacts") &&
      stylesSource.includes(".viewBridgeSteps") &&
      stylesSource.includes(".viewBridgeStep.ready") &&
      stylesSource.includes(".viewBridgeActions"),
  },
  {
    label: "view-dashboard-bridge-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "ViewDashboardBridgePanel.tsx")) &&
      viewWorkspaceSource.includes('import { ViewDashboardBridgePanel } from "./ViewDashboardBridgePanel"') &&
      viewWorkspaceSource.includes("<ViewDashboardBridgePanel") &&
      !viewWorkspaceSource.includes('data-testid="view-dashboard-bridge"') &&
      viewDashboardBridgePanelSource.includes("type ViewDashboardBridgePanelProps") &&
      viewDashboardBridgePanelSource.includes("bridgeSteps: ViewBridgeStep[]") &&
      viewDashboardBridgePanelSource.includes("openViewEvidence: () => void") &&
      viewDashboardBridgePanelSource.includes("viewCanFeedDashboard: boolean") &&
      viewDashboardBridgePanelSource.includes('data-testid="view-bridge-agent-widget"') &&
      implementationStatusSource.includes("View dashboard bridge panel component boundary"),
  },
  {
    label: "view-saved-list-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "ViewSavedListPanel.tsx")) &&
      viewWorkspaceSource.includes('import { ViewSavedListPanel } from "./ViewSavedListPanel"') &&
      viewWorkspaceSource.includes("<ViewSavedListPanel") &&
      !viewWorkspaceSource.includes('<aside className="viewListPanel">') &&
      viewSavedListPanelSource.includes("type ViewSavedListPanelProps") &&
      viewSavedListPanelSource.includes('className="viewListPanel"') &&
      viewSavedListPanelSource.includes('className={view.view_key === activeView?.view_key ? "viewRow active" : "viewRow"}') &&
      viewSavedListPanelSource.includes("view.columnCount ?? viewColumns(view).length") &&
      viewSavedListPanelSource.includes("view.filterCount ?? viewFilters(view).length") &&
      implementationStatusSource.includes("View saved list panel component boundary"),
  },
  {
    label: "frontend-query-workbench-diagnostics-simplified",
    ok: sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="source-query-runtime-technical"') &&
      sourceWorkbenchQueryFormulaPanelSource.includes("结果可刷新") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("等待连接") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("查看取数诊断") &&
      sourceWorkbenchQueryFormulaPanelSource.includes("已切换到备用查询") &&
      !sourceWorkbenchSource.includes("Fell back to SQLite") &&
      viewWorkspaceSource.includes('data-testid="view-query-diagnostics"') &&
      viewWorkspaceSource.includes("查看分页、执行引擎和查询口径") &&
      viewWorkspaceSource.includes("查看生成查询"),
  },
  {
    label: "frontend-loading-state-not-fallback-sample",
    ok: appSource.includes('type ApiMode') &&
      appSource.includes('from "./appWorkspaceModel"') &&
      appWorkspaceModelSource.includes('export type ApiMode = "loading" | "live" | "fallback"') &&
      appWorkspaceModelSource.includes("export const connectingStatus: WorkspaceStatus") &&
      appWorkspaceModelSource.includes('notes: ["Connecting to local data service..."]') &&
      appSource.includes('apiMode === "loading" ? connectingStatus : status') &&
      topBarSource.includes('apiMode === "loading"') &&
      topBarSource.includes('biText("正在连接", "Connecting")'),
  },
  {
    label: "app-workspace-model-boundary",
    ok: existsSync(join(root, "src", "appWorkspaceModel.ts")) &&
      appSource.includes('from "./appWorkspaceModel"') &&
      appWorkspaceModelSource.includes("export function preferredLandingSection(") &&
      appWorkspaceModelSource.includes("export function normalizeStatus(") &&
      appWorkspaceModelSource.includes("export function normalizeQuery(") &&
      appWorkspaceModelSource.includes("export function normalizeWorkbench(") &&
      appWorkspaceModelSource.includes("export function normalizeDashboards(") &&
      appWorkspaceModelSource.includes("export function actionErrorResult(") &&
      appWorkspaceModelSource.includes("buildActionRecovery(action, error)") &&
      actionRecoveryModelSource.includes("no-sample-fallback-for-core-action") &&
      appWorkspaceModelSource.includes('from "./emptyWorkspaceData"') &&
      appWorkspaceModelSource.includes("emptyWorkbenchPayload.formulaDsl") &&
      appWorkspaceModelSource.includes("return \"dashboards\"") &&
      appWorkspaceModelSource.includes("return \"sources\"") &&
      !appSource.includes("function normalizeStatus(") &&
      !appSource.includes("function normalizeQuery(") &&
      !appSource.includes("function normalizeWorkbench(") &&
      !appSource.includes("function normalizeDashboards(") &&
      !appSource.includes("function actionErrorResult(") &&
      !appSource.includes("const connectingStatus: WorkspaceStatus") &&
      implementationStatusSource.includes("App workspace model boundary"),
  },
  {
    label: "empty-workspace-data-boundary",
    ok: existsSync(join(root, "src", "emptyWorkspaceData.ts")) &&
      emptyWorkspaceDataSource.includes("export const emptyWorkspaceStatus") &&
      emptyWorkspaceDataSource.includes("export const emptyImportPreview") &&
      emptyWorkspaceDataSource.includes("export const emptyQueryResult") &&
      emptyWorkspaceDataSource.includes("export const emptyTableQuery") &&
      emptyWorkspaceDataSource.includes("export const emptyWorkbenchPayload") &&
      emptyWorkspaceDataSource.includes("export const emptyDashboardPayload") &&
      emptyWorkspaceDataSource.includes("export const emptyAgentResult") &&
      emptyWorkspaceDataSource.includes("export const emptyActionDrafts") &&
      emptyWorkspaceDataSource.includes('tables: 0') &&
      emptyWorkspaceDataSource.includes('dashboards: 0') &&
      appSource.includes('from "./emptyWorkspaceData"') &&
      apiAgentSource.includes('emptyActionDrafts') &&
      apiWorkspaceSource.includes('emptyWorkspaceStatus') &&
      apiWorkspaceSource.includes('emptyWorkbenchPayload') &&
      apiWorkspaceSource.includes('emptyDashboardPayload') &&
      apiSourceApiSource.includes('emptyImportPreview') &&
      apiModelSource.includes('emptyFormulaPreview') &&
      apiModelSource.includes('emptyRelationshipPreview') &&
      !appWorkspaceModelSource.includes('from "./sampleData"') &&
      !apiWorkspaceSource.includes('from "./sampleData"') &&
      !apiAgentSource.includes('sampleActionDrafts') &&
      implementationStatusSource.includes("Empty workspace data boundary"),
  },
  {
    label: "types-workspace-contract-boundary",
    ok: existsSync(join(root, "src", "typesWorkspace.ts")) &&
      typesSource.includes('from "./typesWorkspace"') &&
      typesSource.includes("export type { QueryRuntimeStatus, SelectionConfidence, SourceRunSummary, WorkspaceRecord, WorkspaceStatus }") &&
      typesWorkspaceSource.includes("export interface WorkspaceStatus") &&
      typesWorkspaceSource.includes("export interface WorkspaceRecord") &&
      typesWorkspaceSource.includes("export interface QueryRuntimeStatus") &&
      typesWorkspaceSource.includes("export interface SourceRunSummary") &&
      typesWorkspaceSource.includes('export type SelectionConfidence = "explicit"') &&
      !typesSource.includes("export interface WorkspaceStatus") &&
      !typesSource.includes("export interface WorkspaceRecord") &&
      !typesSource.includes("export interface QueryRuntimeStatus") &&
      !typesSource.includes("export interface SourceRunSummary") &&
      implementationStatusSource.includes("Types workspace contract boundary"),
  },
  {
    label: "types-dashboard-contract-boundary",
    ok: existsSync(join(root, "src", "typesDashboard.ts")) &&
      typesSource.includes('from "./typesDashboard"') &&
      typesSource.includes("export type { DashboardFilterPayload, DashboardFilterRule, DashboardPage, DashboardPayload, DashboardWidget, NavigationModule }") &&
      typesDashboardSource.includes("export interface DashboardWidget") &&
      typesDashboardSource.includes("export interface DashboardFilterRule") &&
      typesDashboardSource.includes("export interface DashboardPage") &&
      typesDashboardSource.includes("export interface DashboardPayload") &&
      typesDashboardSource.includes("export interface NavigationModule") &&
      typesDashboardSource.includes("export interface DashboardFilterPayload") &&
      !typesSource.includes("export interface DashboardWidget") &&
      !typesSource.includes("export interface DashboardFilterRule") &&
      !typesSource.includes("export interface DashboardPage") &&
      !typesSource.includes("export interface DashboardPayload") &&
      !typesSource.includes("export interface NavigationModule") &&
      !typesSource.includes("export interface DashboardFilterPayload") &&
      implementationStatusSource.includes("Types dashboard contract boundary"),
  },
  {
    label: "types-source-contract-boundary",
    ok: existsSync(join(root, "src", "typesSource.ts")) &&
      existsSync(join(root, "src", "typesSourceIntelligence.ts")) &&
      typesSource.includes('from "./typesSource"') &&
      typesSource.includes("SourceIntelligenceDashboardCandidate") &&
      typesSource.includes("WorkbenchPayload") &&
      typesSourceContractsSource.includes("export interface SourceFieldProfile") &&
      typesSourceContractsSource.includes("export interface ImportPreview") &&
      typesSourceContractsSource.includes('from "./typesDomain"') &&
      typesSourceContractsSource.includes("export interface WorkbenchTable") &&
      typesSourceContractsSource.includes("export interface FieldConfig") &&
      typesSourceContractsSource.includes("export interface MetricDefinition") &&
      typesSourceContractsSource.includes("export interface FormulaDefinition") &&
      typesSourceContractsSource.includes("export interface RelationshipRecord") &&
      typesSourceContractsSource.includes("export interface SavedView") &&
      typesSourceContractsSource.includes("export interface TableQueryPayload") &&
      typesSourceContractsSource.includes('from "./typesSourceIntelligence"') &&
      typesSourceContractsSource.includes("SourceIntelligenceRunSummary") &&
      typesSourceContractsSource.includes("EvidenceFocus") &&
      typesSourceIntelligenceSource.includes("export interface SourceIntelligenceRunSummary") &&
      typesSourceIntelligenceSource.includes("export interface SourceIntelligenceDashboardCandidate") &&
      typesSourceIntelligenceSource.includes("export interface EvidenceFocus") &&
      typesSourceContractsSource.includes("export interface WorkbenchPayload") &&
      typesSourceContractsSource.includes("export interface RelationshipPreviewPayload") &&
      typesSourceContractsSource.includes("export interface FormulaPreviewPayload") &&
      typesSourceContractsSource.includes("export interface FormulaMutationPayload") &&
      !typesSource.includes("export interface SourceFieldProfile") &&
      !typesSource.includes("export interface WorkbenchPayload") &&
      !typesSource.includes("export interface ImportPreview") &&
      !typesSource.includes("export interface DomainPackRuntime") &&
      !typesSourceContractsSource.includes("export interface SourceIntelligenceRunSummary") &&
      !typesSourceContractsSource.includes("export interface EvidenceFocus") &&
      !typesSourceContractsSource.includes("export interface DomainPackRuntime") &&
      implementationStatusSource.includes("Types source contract boundary"),
  },
  {
    label: "types-domain-contract-boundary",
    ok: existsSync(join(root, "src", "typesDomain.ts")) &&
      typesSourceContractsSource.includes('import type { SourcePipelineContract } from "./typesDomain"') &&
      typesSourceContractsSource.includes('} from "./typesDomain"') &&
      typesDomainSource.includes("export interface SourcePipelineStageContract") &&
      typesDomainSource.includes("export interface SourcePipelineContract") &&
      typesDomainSource.includes("export interface DomainSemanticHint") &&
      typesDomainSource.includes("export interface DomainLinkHint") &&
      typesDomainSource.includes("export interface DomainFunctionHint") &&
      typesDomainSource.includes("export interface DomainActionHint") &&
      typesDomainSource.includes("export interface DomainPackRuntime") &&
      implementationStatusSource.includes("Types domain contract boundary"),
  },
  {
    label: "types-query-agent-facade-boundary",
    ok: existsSync(join(root, "src", "typesQuery.ts")) &&
      existsSync(join(root, "src", "typesAgent.ts")) &&
      typesSource.includes('from "./typesQuery"') &&
      typesSource.includes('from "./typesAgent"') &&
      typesQuerySource.includes("export interface QueryResult") &&
      typesAgentSource.includes("export interface AgentAskResult") &&
      typesAgentSource.includes("export interface ActionDraft") &&
      typesAgentSource.includes("export interface ActionDraftPayload") &&
      typesAgentSource.includes('from "./typesSource"') &&
      typesAgentSource.includes('from "./typesWorkspace"') &&
      !typesSource.includes("export interface QueryResult") &&
      !typesSource.includes("export interface AgentAskResult") &&
      !typesSource.includes("export interface ActionDraft") &&
      !typesSource.includes("export interface ActionDraftPayload") &&
      implementationStatusSource.includes("Types query and Agent contract boundary"),
  },
  {
    label: "app-data-actions-hook-boundary",
    ok: existsSync(join(root, "src", "useAppDataActions.ts")) &&
      appSource.includes('from "./useAppDataActions"') &&
      appSource.includes("useAppDataActions({") &&
      appSource.includes("setRelationshipPreview,") &&
      appSource.includes("setFormulaPreview,") &&
      appSource.includes("setActionDrafts,") &&
      appSource.includes("handleSourceIntelligenceRun,") &&
      appDataActionsSource.includes("export function useAppDataActions(") &&
      appDataActionsSource.includes("type AppDataActionsOptions") &&
      appDataActionsSource.includes("const handleCommitImport = useCallback") &&
      appDataActionsSource.includes("const handleSourceIntelligenceRun = useCallback") &&
      appDataActionsSource.includes("const handleSourceDashboardDraft = useCallback") &&
      appDataActionsSource.includes("const handleDashboardRelationshipSave = useCallback") &&
      appDataActionsSource.includes("const handleSaveConnector = useCallback") &&
      appDataActionsSource.includes("const handleSaveView = useCallback") &&
      appDataActionsSource.includes("const { stayOnPage = false, ...sourceOptions }") &&
      appDataActionsSource.includes("const hasInputs = Array.isArray(sourceOptions.inputs) && sourceOptions.inputs.length > 0") &&
      appDataActionsSource.includes("setSection(\"sources\")") &&
      appDataActionsSource.includes("setSection(\"views\")") &&
      appDataActionsSource.includes("setSection(\"agent\")") &&
      !appSource.includes("const handleCommitImport = useCallback") &&
      !appSource.includes("const handleSourceIntelligenceRun = useCallback") &&
      !appSource.includes("const handleSourceDashboardDraft = useCallback") &&
      !appSource.includes("const handleSaveConnector = useCallback") &&
      !appSource.includes("const handleSaveView = useCallback") &&
      !appSource.includes("commitImport(options)") &&
      !appSource.includes("runSourceIntelligence(request)") &&
      implementationStatusSource.includes("App data actions hook boundary"),
  },
  {
    label: "frontend-section-lazy-split-boundary",
    ok: appSource.includes("import { Suspense") &&
      appSource.includes('from "./appLazyModules"') &&
      appLazyModulesSource.includes("import { lazy } from \"react\"") &&
      appLazyModulesSource.includes('const loadAgentPanel = () => import("./components/AgentPanel")') &&
      appLazyModulesSource.includes('const loadDashboardCanvas = () => import("./components/DashboardCanvas")') &&
      appLazyModulesSource.includes('const loadEvidenceView = () => import("./components/EvidenceView")') &&
      appLazyModulesSource.includes('const loadHomeOverview = () => import("./components/HomeOverview")') &&
      appLazyModulesSource.includes('const loadInspectorPanel = () => import("./components/InspectorPanel")') &&
      appLazyModulesSource.includes('const loadSettingsPanel = () => import("./components/SettingsPanel")') &&
      appLazyModulesSource.includes('const loadSourceWorkbench = () => import("./components/SourceWorkbench")') &&
      appLazyModulesSource.includes('const loadViewWorkspace = () => import("./components/ViewWorkspace")') &&
      appLazyModulesSource.includes("export const AgentPanel = lazy(loadAgentPanel)") &&
      appLazyModulesSource.includes("export const DashboardCanvas = lazy(loadDashboardCanvas)") &&
      appLazyModulesSource.includes("export const EvidenceView = lazy(loadEvidenceView)") &&
      appLazyModulesSource.includes("export const HomeOverview = lazy(loadHomeOverview)") &&
      appLazyModulesSource.includes("export const InspectorPanel = lazy(loadInspectorPanel)") &&
      appLazyModulesSource.includes("export const SettingsPanel = lazy(loadSettingsPanel)") &&
      appLazyModulesSource.includes("export const SourceWorkbench = lazy(loadSourceWorkbench)") &&
      appLazyModulesSource.includes("export const ViewWorkspace = lazy(loadViewWorkspace)") &&
      appLazyModulesSource.includes("export const sectionPreloaders: Record<AppSection") &&
      appLazyModulesSource.includes("export function scheduleIdlePreload") &&
      appLazyModulesSource.includes("requestIdleCallback") &&
      appLazyModulesSource.includes("export function ModuleLoadingPanel") &&
      appLazyModulesSource.includes("export function InspectorLoadingPanel") &&
      appSource.includes("preloadModules(sectionPreloaders[section])") &&
      appSource.includes("preloadModules([...allSectionPreloaders, inspectorPreloader])") &&
      appLazyModulesSource.includes('import { getAppSection } from "./appSections"') &&
      appLazyModulesSource.includes('function sectionText(section: AppSection, language: "zh" | "en", field: "loading" | "loadingDetail")') &&
      !appSource.includes("lazy(loadAgentPanel)") &&
      !appSource.includes("function ModuleLoadingPanel") &&
      !appSource.includes('import { AgentPanel } from "./components/AgentPanel"') &&
      !appSource.includes('import { DashboardCanvas } from "./components/DashboardCanvas"') &&
      !appSource.includes('import { EvidenceView } from "./components/EvidenceView"') &&
      !appSource.includes('import { HomeOverview } from "./components/HomeOverview"') &&
      !appSource.includes('import { InspectorPanel } from "./components/InspectorPanel"') &&
      !appSource.includes('import { SettingsPanel } from "./components/SettingsPanel"') &&
      !appSource.includes('import { SourceWorkbench } from "./components/SourceWorkbench"') &&
      !appSource.includes('import { ViewWorkspace } from "./components/ViewWorkspace"') &&
      appLazyModulesSource.includes("function ModuleLoadingPanel") &&
      appLazyModulesSource.includes('data-testid="lazy-section-loading"') &&
      appLazyModulesSource.includes("const loadingFlow: AppSection[]") &&
      appLazyModulesSource.includes("function LoadingFlowRail") &&
      appLazyModulesSource.includes('data-testid={index === currentIndex ? "lazy-section-current-step" : undefined}') &&
      appLazyModulesSource.includes('data-testid="lazy-section-loading-support"') &&
      appLazyModulesSource.includes("dashboardModuleLoadingPanel") &&
      appLazyModulesSource.includes("dashboardLoadingFrame") &&
      appSectionsSource.includes("Preparing metrics, filters, widgets, and evidence entry points.") &&
      appLazyModulesSource.includes("function InspectorLoadingPanel") &&
      appLazyModulesSource.includes('data-testid="lazy-inspector-loading"') &&
      appLazyModulesSource.includes("inspectorLoadingStack") &&
      appSource.includes("<Suspense fallback={<ModuleLoadingPanel section={section} language={resolvedLanguage} />}>") &&
      appSource.includes("<Suspense fallback={<InspectorLoadingPanel language={resolvedLanguage} />}>") &&
      stylesSource.includes(".moduleLoadingPanel") &&
      stylesSource.includes(".moduleLoadingFlow") &&
      stylesSource.includes(".moduleLoadingSupport") &&
      stylesSource.includes(".dashboardLoadingGrid") &&
      stylesSource.includes(".dashboardLoadingMetric") &&
      stylesSource.includes(".dashboardLoadingChart") &&
      stylesSource.includes(".inspectorLoadingPanel") &&
      stylesSource.includes(".inspectorLoadingStack"),
  },
  {
    label: "frontend-core-api-strict-no-sample-fallback",
    ok: apiSource.includes('from "./apiClient"') &&
      apiClientSource.includes("export class ApiPayloadError extends Error") &&
      apiClientSource.includes("payload: Record<string, unknown>") &&
      apiClientSource.includes("Local API request failed for") &&
      apiClientSource.includes("Local API returned invalid JSON") &&
      apiClientSource.includes("export function localApiCandidates(") &&
      apiClientSource.includes('window.location.port === "8686"') &&
      apiClientSource.includes("http://127.0.0.1:8787") &&
      apiViewsSource.includes('return fetchJsonStrict<QueryResult>("/api/query"') &&
      apiViewsSource.includes('return fetchJsonStrict<TableQueryPayload>("/api/query-table"') &&
      apiDashboardSource.includes('return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/business-template"') &&
      apiDashboardSource.includes('return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/widgets"') &&
      apiDashboardSource.includes('return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/modules"') &&
      apiDashboardSource.includes('return fetchJsonStrict<Record<string, unknown>>("/api/dashboards/operation"') &&
      apiDashboardSource.includes('return fetchJsonStrict<DashboardFilterPayload>("/api/dashboards/filters"') &&
      apiAgentSource.includes('return fetchJsonStrict<AgentAskResult>("/api/agent/ask"') &&
      apiAgentSource.includes('return fetchJsonStrict<AgentAskResult>("/api/agent/explain"') &&
      appSource.includes('from "./appWorkspaceModel"') &&
      appWorkspaceModelSource.includes("export function actionErrorResult") &&
      actionRecoveryModelSource.includes("no-sample-fallback-for-core-action") &&
      appWorkspaceModelSource.includes("actionRecoveryFromError(error) ?? buildActionRecovery(action, error)") &&
      appSource.includes('setLastActionResult(actionErrorResult("initial-load", error))') &&
      appDataActionsSource.includes('setLastActionResult(actionErrorResult("query", error))') &&
      appDataActionsSource.includes('setLastActionResult(actionErrorResult("query-table", error))') &&
      appAgentActionsSource.includes('setLastActionResult(actionErrorResult("agent-ask", error))') &&
      appAgentActionsSource.includes('setLastActionResult(actionErrorResult("agent-explain", error))') &&
      appDashboardActionsSource.includes('actionErrorResult("business-dashboard", error)') &&
      appDashboardActionsSource.includes('actionErrorResult("dashboard-widget", error)') &&
      appDashboardActionsSource.includes('actionErrorResult("dashboard-modules", error)'),
  },
  {
    label: "api-domain-boundary",
    ok: apiSource.includes('export { askAgent, askAgentReadOnly, confirmAction, getActionDrafts } from "./apiAgent"') &&
      apiSource.includes('from "./apiDashboard"') &&
      apiSource.includes('from "./apiSettings"') &&
      apiSource.includes('from "./apiSource"') &&
      apiSource.includes('from "./apiViews"') &&
      apiSource.includes('export { createWorkspace, deleteWorkspace, getDashboards, getWorkbenchData, getWorkspaceStatus, renameWorkspace, selectWorkspace } from "./apiWorkspace"') &&
      apiAgentSource.includes('from "./apiClient"') &&
      apiAgentSource.includes('emptyActionDrafts') &&
      apiDashboardSource.includes('from "./apiClient"') &&
      apiDashboardSource.includes('getDashboardWidgetCatalog') &&
      apiDashboardSource.includes('dashboardWidgetOperation') &&
      apiDashboardSource.includes('dashboardFilterOperation') &&
      apiModelSource.includes('from "./apiClient"') &&
      apiModelSource.includes('updateFieldConfig') &&
      apiModelSource.includes('queryRelationship') &&
      apiModelSource.includes('previewFormula') &&
      apiModelSource.includes('recommendIndexes') &&
      apiModelSource.includes('"/api/relationships/query"') &&
      apiModelSource.includes('"/api/formulas/save"') &&
      apiSourceApiSource.includes('from "./apiClient"') &&
      apiSourceApiSource.includes('previewImportWithOptions') &&
      apiSourceApiSource.includes('runSourceIntelligence') &&
      apiSourceApiSource.includes('createSourceDashboardDraft') &&
      apiSourceApiSource.includes('"/api/import/preview"') &&
      apiSourceApiSource.includes('"/api/source-intelligence/dashboard-draft"') &&
      apiSettingsSource.includes('from "./apiClient"') &&
      apiSettingsSource.includes('"/api/preferences"') &&
      apiSettingsSource.includes('"/api/theme-palettes"') &&
      apiSettingsSource.includes('"/api/config/validate"') &&
      apiSettingsSource.includes('"/api/config/export"') &&
      apiSettingsSource.includes('"/api/config/apply"') &&
      apiViewsSource.includes('from "./apiClient"') &&
      apiViewsSource.includes('runTableQuery') &&
      apiViewsSource.includes('saveView') &&
      apiViewsSource.includes('"/api/views/save"') &&
      apiViewsSource.includes('"/api/views/delete"') &&
      apiWorkspaceSource.includes('from "./apiClient"') &&
      apiWorkspaceSource.includes("type WorkspaceEnvelope") &&
      apiWorkspaceSource.includes("export function deleteWorkspace") &&
      apiWorkspaceSource.includes("export function renameWorkspace") &&
      apiWorkspaceSource.includes('"/api/workspaces"') &&
      apiWorkspaceSource.includes('"/api/dashboards"') &&
      apiWorkspaceSource.includes('"/api/workbench?limit=12"') &&
      implementationStatusSource.includes("API workspace, source, dashboard, settings, views, model, and Agent domain boundary"),
  },
  {
    label: "frontend-service-diagnostics",
    ok: topBarSource.includes("const showServiceDiagnostics = apiMode !== \"live\"") &&
      (topBarSource.includes('className="topBarStack"') || topBarSource.includes("topBarStack workbenchTopBar")) &&
      topBarSource.includes('data-testid="service-diagnostics"') &&
      topBarSource.includes('data-testid="service-diagnostics-title"') &&
      topBarSource.includes('data-testid="service-diagnostics-technical"') &&
      topBarSource.includes('data-testid="service-diagnostics-commands"') &&
      topBarSource.includes('data-testid="service-diagnostics-notes"') &&
      topBarSource.includes("查看启动命令和端口") &&
      topBarSource.includes("npm run dev") &&
      topBarSource.includes("npm run api") &&
      topBarSource.includes("前端 8686 · API 8787") &&
      topBarSource.includes("等待导入数据") &&
      topBarSource.includes("没有可用数据表") &&
      packageJson.scripts?.dev === "node scripts/dev.mjs" &&
      packageJson.scripts?.["dev:ui"]?.includes("--port 8686") &&
      devScriptSource.includes("portIsOpen(8787)") &&
      devScriptSource.includes("portIsOpen(8686)") &&
      devScriptSource.includes("async function apiIsCompatible()") &&
      devScriptSource.includes('payload?.service === "aibi-hybrid-api"') &&
      devScriptSource.includes("async function uiIsCompatible()") &&
      devScriptSource.includes("<title>AIBI Hybrid</title>") &&
      devScriptSource.includes("async function stopOwnedPortProcess") &&
      devScriptSource.includes("compatible existing service detected; reusing it.") &&
      devScriptSource.includes("port is occupied by an incompatible service") &&
      devScriptSource.includes('start("api:8787", ["run", "api"])') &&
      devScriptSource.includes('start("ui:8686", ["run", "dev:ui"])') &&
      stylesSource.includes(".topBarStack") &&
      stylesSource.includes(".serviceDiagnostics.fallback") &&
      stylesSource.includes(".serviceDiagnosticsTechnical") &&
      stylesSource.includes(".serviceDiagnosticsCommands code"),
  },
  {
    label: "frontend-home-workspace-start-guide",
    ok: homeOverviewSource.includes("<HomeWorkspaceStartGuide") &&
      homeWorkspaceStartGuideSource.includes("data-testid=\"workspace-start-guide\"") &&
      homeWorkspaceStartGuideSource.includes("data-testid=\"workspace-start-guide-primary\"") &&
      homeWorkspaceStartGuideSource.includes("data-testid={`workspace-guide-step-${step.key}`}") &&
      homeWorkspaceStartGuideSource.includes("data-testid=\"workspace-start-guide-boundary\"") &&
      homeWorkspaceStartGuideSource.includes("Follow the business path before learning configuration") &&
      homeOverviewSource.includes("buildHomeGuideSteps({") &&
      ["source", "profile", "dashboard", "ask"].every((key) => homeOverviewModelSource.includes(`key: "${key}"`)) &&
      homeWorkspaceStartGuideSource.includes("Imports, deletes, overwrites, relationship saves, and dashboard writes become drafts or previews before execution.") &&
      implementationStatusSource.includes("Home workspace start guide component boundary"),
  },
  {
    label: "frontend-home-overview-model-boundary",
    ok: homeOverviewSource.includes('from "../homeOverviewModel"') &&
      homeOverviewModelSource.includes("export const starterQuestions") &&
      homeOverviewModelSource.includes("export type GuideStep") &&
      homeOverviewModelSource.includes("export function buildHomeReadiness") &&
      homeOverviewModelSource.includes("export function buildHomeGuideSteps") &&
      homeOverviewModelSource.includes("export function sourceDashboardCandidate") &&
      homeOverviewModelSource.includes('from "./safeValue"') &&
      homeOverviewModelSource.includes("export { numberValue, objectRecord, recordArray, stringValue }") &&
      homeOverviewModelSource.includes("SourceIntelligenceDashboardCandidate") &&
      homeOverviewSource.includes("buildHomeReadiness({") &&
      homeOverviewSource.includes("buildHomeGuideSteps({") &&
      !homeOverviewSource.includes("function sourceDashboardCandidate(") &&
      !homeOverviewSource.includes("const starterQuestions = [") &&
      !homeOverviewSource.includes("const guideSteps = useMemo<GuideStep[]>") &&
      implementationStatusSource.includes("Home overview model boundary"),
  },
  {
    label: "safe-value-helper-boundary",
    ok: safeValueSource.includes("export function numberValue") &&
      safeValueSource.includes("export function objectRecord") &&
      safeValueSource.includes("export function recordArray") &&
      safeValueSource.includes("export function stringValue") &&
      homeOverviewModelSource.includes('from "./safeValue"') &&
      agentPanelModelSource.includes('from "./safeValue"') &&
      agentPanelModelSource.includes("export { objectRecord }") &&
      sourceWorkbenchModelSource.includes('from "./safeValue"') &&
      sourceWorkbenchModelSource.includes("export { numberValue }") &&
      metricRepairModelSource.includes('from "./safeValue"') &&
      !homeOverviewModelSource.includes("export function numberValue(value: unknown)") &&
      !homeOverviewModelSource.includes("export function objectRecord(value: unknown)") &&
      !agentPanelModelSource.includes("export function objectRecord(value: unknown)") &&
      !metricRepairModelSource.includes("function numberValue(value: unknown)") &&
      !metricRepairModelSource.includes("function objectRecord(value: unknown)") &&
      !sourceWorkbenchModelSource.includes("export function numberValue(value: unknown)") &&
      implementationStatusSource.includes("Safe value helper boundary"),
  },
  {
    label: "b-cost-monitor-comparison-artifact",
    ok: bCostMonitorComparison === null ||
      (bCostMonitorComparison?.dashboard?.key === "xlsx_cost_monitor_20260609" &&
        bCostMonitorComparison?.dashboard?.widgetCount === 23 &&
        bCostMonitorComparison?.sources?.length === 10 &&
        Object.values(bCostMonitorComparison?.rowCounts ?? {}).length === 4 &&
        Object.values(bCostMonitorComparison?.rowCounts ?? {}).every((row) => row.dbRows === row.sourceRows && row.dbColumns === row.sourceColumns) &&
        bCostMonitorComparison?.widgets?.filter((widget) => widget.chartType !== "text").length === 22 &&
        bCostMonitorComparison?.widgets?.filter((widget) => widget.chartType !== "text").every((widget) => widget.matches === true) &&
        bCostMonitorComparison?.formulaDefinitions?.["动账净额"]?.includes("出账") &&
        bCostMonitorComparison?.formulaDefinitions?.["收入"]?.includes("订单实付应结")),
  },
  {
    label: "api-b-cost-monitor-validation-route",
    ok: serverDashboardRoutesSource.includes('url.pathname === "/api/validation/b-cost-monitor"') &&
      serverDashboardRoutesSource.includes("readBCostMonitorValidation(root)") &&
      serverRuntimeSource.includes("b-cost-monitor-comparison.json") &&
      serverRuntimeSource.includes("matchedNonTextWidgets") &&
      apiSource.includes("getBCostMonitorValidation") &&
      apiDashboardSource.includes('"/api/validation/b-cost-monitor"'),
  },
  {
    label: "server-runtime-boundary",
    ok: existsSync(join(root, "server", "serverRuntime.ts")) &&
      serverIndexSource.includes('from "./serverRuntime"') &&
      serverIndexSource.includes("const cli = (args: string[]) => runCli(root, args)") &&
      !serverIndexSource.includes('spawn("python"') &&
      !serverIndexSource.includes("function pushDashboardWidgetStyleArgs(") &&
      !serverIndexSource.includes("function numberValue(") &&
      serverRuntimeSource.includes("export function sendJson(") &&
      serverRuntimeSource.includes("function enrichedErrorBody(") &&
      serverRuntimeSource.includes("buildActionRecovery(action, error)") &&
      serverRuntimeSource.includes("response.end(JSON.stringify(enrichedErrorBody(body), null, 2))") &&
      serverIndexSource.includes("function actionForApiPath(url: URL)") &&
      serverIndexSource.includes("action: url.pathname.startsWith(\"/api/\") ? actionForApiPath(url) : \"static\"") &&
      serverRuntimeSource.includes("export function readBody(") &&
      serverRuntimeSource.includes("export function runCli(") &&
      serverRuntimeSource.includes("export function pushDashboardWidgetStyleArgs(") &&
      serverRuntimeSource.includes("export async function readBCostMonitorValidation(") &&
      implementationStatusSource.includes("Server runtime boundary"),
  },
  {
    label: "server-static-boundary",
    ok: existsSync(join(root, "server", "staticServer.ts")) &&
      serverIndexSource.includes('import { handleStatic } from "./staticServer"') &&
      serverIndexSource.includes("await handleStatic(response, url.pathname, root)") &&
      !serverIndexSource.includes("readFile(path)") &&
      !serverIndexSource.includes("extname(path)") &&
      serverStaticSource.includes("export async function handleStatic(") &&
      serverStaticSource.includes('join(root, "dist")') &&
      serverStaticSource.includes('join(dist, "index.html")') &&
      serverStaticSource.includes("readFile(path)") &&
      serverStaticSource.includes("extname(path)") &&
      implementationStatusSource.includes("Server static boundary"),
  },
  {
    label: "server-dashboard-routes-boundary",
    ok: existsSync(join(root, "server", "dashboardRoutes.ts")) &&
      serverIndexSource.includes('import { handleDashboardApi } from "./dashboardRoutes"') &&
      serverIndexSource.includes("await handleDashboardApi({ cli, request, response, root, url })") &&
      !serverIndexSource.includes('url.pathname === "/api/dashboard/widget-catalog"') &&
      !serverIndexSource.includes('url.pathname === "/api/dashboards"') &&
      !serverIndexSource.includes('url.pathname === "/api/validation/b-cost-monitor"') &&
      serverDashboardRoutesSource.includes("export async function handleDashboardApi(") &&
      serverDashboardRoutesSource.includes('url.pathname === "/api/dashboard/widget-catalog"') &&
      serverDashboardRoutesSource.includes('url.pathname === "/api/dashboard/widgets"') &&
      serverDashboardRoutesSource.includes('url.pathname === "/api/dashboards/filters"') &&
      serverDashboardRoutesSource.includes('url.pathname === "/api/b-cli/capabilities"') &&
      implementationStatusSource.includes("Server dashboard routes boundary"),
  },
  {
    label: "server-source-routes-boundary",
    ok: existsSync(join(root, "server", "sourceRoutes.ts")) &&
      serverIndexSource.includes('import { handleSourceApi } from "./sourceRoutes"') &&
      serverIndexSource.includes("await handleSourceApi({ cli, request, response, url })") &&
      !serverIndexSource.includes('url.pathname === "/api/source-intelligence/run"') &&
      !serverIndexSource.includes('url.pathname === "/api/import/preview"') &&
      !serverIndexSource.includes('url.pathname === "/api/import/commit"') &&
      !serverIndexSource.includes('url.pathname === "/api/connectors"') &&
      !serverIndexSource.includes('url.pathname.startsWith("/api/source-runs/")') &&
      serverSourceRoutesSource.includes("export async function handleSourceApi(") &&
      serverSourceRoutesSource.includes('url.pathname === "/api/source-intelligence/run"') &&
      serverSourceRoutesSource.includes('url.pathname === "/api/import/commit"') &&
      serverSourceRoutesSource.includes('url.pathname === "/api/connectors"') &&
      serverSourceRoutesSource.includes('url.pathname.startsWith("/api/source-runs/")') &&
      implementationStatusSource.includes("Server source routes boundary"),
  },
  {
    label: "server-settings-routes-boundary",
    ok: existsSync(join(root, "server", "settingsRoutes.ts")) &&
      serverIndexSource.includes('import { handleSettingsApi } from "./settingsRoutes"') &&
      serverIndexSource.includes("await handleSettingsApi({ cli, request, response, url })") &&
      !serverIndexSource.includes('url.pathname === "/api/preferences"') &&
      !serverIndexSource.includes('url.pathname === "/api/theme-palettes"') &&
      !serverIndexSource.includes('url.pathname === "/api/config/validate"') &&
      serverSettingsRoutesSource.includes("export async function handleSettingsApi(") &&
      serverSettingsRoutesSource.includes('url.pathname === "/api/preferences"') &&
      serverSettingsRoutesSource.includes('url.pathname === "/api/theme-palettes"') &&
      serverSettingsRoutesSource.includes('url.pathname === "/api/config/validate"') &&
      serverSettingsRoutesSource.includes('url.pathname === "/api/config/apply"') &&
      implementationStatusSource.includes("Server settings routes boundary"),
  },
  {
    label: "server-model-routes-boundary",
    ok: existsSync(join(root, "server", "modelRoutes.ts")) &&
      serverIndexSource.includes('import { handleModelApi } from "./modelRoutes"') &&
      serverIndexSource.includes("await handleModelApi({ cli, request, response, url })") &&
      !serverIndexSource.includes('url.pathname === "/api/relationships/preview"') &&
      !serverIndexSource.includes('url.pathname === "/api/formulas/preview"') &&
      !serverIndexSource.includes('url.pathname === "/api/indexes/recommend"') &&
      !serverIndexSource.includes('url.pathname === "/api/semantics"') &&
      !serverIndexSource.includes('url.pathname === "/api/metrics"') &&
      serverModelRoutesSource.includes("export async function handleModelApi(") &&
      serverModelRoutesSource.includes('url.pathname === "/api/relationships/query"') &&
      serverModelRoutesSource.includes('url.pathname === "/api/formulas/save"') &&
      serverModelRoutesSource.includes('url.pathname === "/api/indexes/create"') &&
      serverModelRoutesSource.includes('url.pathname === "/api/fields/update"') &&
      serverModelRoutesSource.includes('url.pathname === "/api/metrics/query"') &&
      implementationStatusSource.includes("Server model routes boundary"),
  },
  {
    label: "server-query-routes-boundary",
    ok: existsSync(join(root, "server", "queryRoutes.ts")) &&
      serverIndexSource.includes('import { handleQueryApi } from "./queryRoutes"') &&
      serverIndexSource.includes("await handleQueryApi({ cli, request, response, url })") &&
      !serverIndexSource.includes('url.pathname === "/api/query"') &&
      !serverIndexSource.includes('url.pathname === "/api/query-table"') &&
      !serverIndexSource.includes('url.pathname === "/api/views/save"') &&
      serverQueryRoutesSource.includes("export async function handleQueryApi(") &&
      serverQueryRoutesSource.includes('url.pathname === "/api/query"') &&
      serverQueryRoutesSource.includes('url.pathname === "/api/query-table"') &&
      serverQueryRoutesSource.includes('url.pathname === "/api/views/save"') &&
      serverQueryRoutesSource.includes('url.pathname === "/api/views/delete"') &&
      implementationStatusSource.includes("Server query routes boundary"),
  },
  {
    label: "server-agent-routes-boundary",
    ok: existsSync(join(root, "server", "agentRoutes.ts")) &&
      serverIndexSource.includes('import { handleAgentApi } from "./agentRoutes"') &&
      serverIndexSource.includes("await handleAgentApi({ cli, request, response, url })") &&
      !serverIndexSource.includes('url.pathname === "/api/agent/ask"') &&
      !serverIndexSource.includes('url.pathname === "/api/actions/confirm"') &&
      serverAgentRoutesSource.includes("export async function handleAgentApi(") &&
      serverAgentRoutesSource.includes('url.pathname === "/api/agent/ask"') &&
      serverAgentRoutesSource.includes('url.pathname === "/api/agent/explain"') &&
      serverAgentRoutesSource.includes('url.pathname === "/api/actions/confirm"') &&
      serverAgentRoutesSource.includes('url.pathname === "/api/actions"') &&
      implementationStatusSource.includes("Server agent routes boundary"),
  },
  {
    label: "api-health-status-routes",
    ok: serverWorkspaceRoutesSource.includes('url.pathname === "/api/health"') &&
      serverWorkspaceRoutesSource.includes('service: "aibi-hybrid-api"') &&
      serverWorkspaceRoutesSource.includes('url.pathname === "/api/status"') &&
      serverWorkspaceRoutesSource.includes('const status = await cli(["status"])'),
  },
  {
    label: "server-workspace-routes-boundary",
    ok: existsSync(join(root, "server", "workspaceRoutes.ts")) &&
      serverIndexSource.includes('import { handleWorkspaceApi } from "./workspaceRoutes"') &&
      serverIndexSource.includes("await handleWorkspaceApi({ cli, port, request, response, url })") &&
      !serverIndexSource.includes('url.pathname === "/api/workspaces"') &&
      !serverIndexSource.includes('url.pathname === "/api/sources"') &&
      serverWorkspaceRoutesSource.includes("export async function handleWorkspaceApi(") &&
      serverWorkspaceRoutesSource.includes('url.pathname === "/api/workspaces"') &&
      serverWorkspaceRoutesSource.includes('op === "delete"') &&
      serverWorkspaceRoutesSource.includes('"workspace-delete"') &&
      serverWorkspaceRoutesSource.includes('url.pathname === "/api/workbench"') &&
      serverWorkspaceRoutesSource.includes('url.pathname === "/api/navigation"') &&
      serverWorkspaceRoutesSource.includes('url.pathname === "/api/sources"') &&
      implementationStatusSource.includes("Server workspace routes boundary"),
  },
  {
    label: "frontend-home-four-action-import-proof",
    ok: homeOverviewSource.includes("<ProductActivationPanel") &&
      homeOverviewSource.includes('data-testid="home-shortcut-details"') &&
      homeOverviewSource.includes("<HomeActionDock") &&
      homeOverviewSource.includes("<HomeOperatingSummaryPanel") &&
      homeOperatingSummaryPanelSource.includes('className="quickQuestionBox"') &&
      homeOperatingSummaryPanelSource.includes('className="operatingSummaryGrid"') &&
      homeOperatingSummaryPanelSource.includes('className="trustGrid"') &&
      homeOperatingSummaryPanelSource.includes("starterQuestions") &&
      !homeOverviewSource.includes('className="quickQuestionBox"') &&
      !homeOverviewSource.includes('className="operatingSummaryGrid"') &&
      homeActionDockSource.includes('data-testid="home-action-dock"') &&
      homeActionDockSource.includes('data-testid="home-action-import"') &&
      homeActionDockSource.includes('data-testid="home-action-cost-monitor"') &&
      homeActionDockSource.includes('data-testid="home-action-ask"') &&
      homeActionDockSource.includes('data-testid="home-action-confirm"') &&
      !homeOverviewSource.includes("HomeRealDataValidationPanel") &&
      !homeOverviewSource.includes("getBCostMonitorValidation") &&
      !homeOverviewSource.includes("matchedNonTextWidgets") &&
      productActivationPanelSource.includes('testId = "product-activation-panel"') &&
      productActivationPanelSource.includes('data-testid="product-activation-primary"') &&
      productActivationModelSource.includes("export function buildProductActivation") &&
      stylesSource.includes(".homeActionDock") &&
      stylesSource.includes(".productActivationPanel") &&
      stylesSource.includes(".homeActionCard.primary") &&
      implementationStatusSource.includes("Home action dock component boundary") &&
      implementationStatusSource.includes("Product activation model and panel boundary") &&
      homeOverviewSource.includes("<HomeDetailedPathPanel") &&
      homeDetailedPathPanelSource.includes('data-testid="home-detailed-path"'),
  },
  {
    label: "frontend-no-data-onboarding-ux-boundary",
    ok: homeOverviewSource.includes("<ProductActivationPanel") &&
      homeOverviewSource.includes("buildProductActivation({") &&
      homeOverviewSource.includes("useQualityDoctor(hasData, workbench)") &&
      /if \(!enabled\) \{\s*setResult\(null\);\s*return;\s*\}/.test(useQualityDoctorSource) &&
      /\{hasData \? \(\s*<>/.test(homeOverviewSource) &&
      !homeOverviewSource.includes('data-testid="home-first-run-focus"') &&
      homeOverviewSource.includes("homeBetaDetails") &&
      homeOverviewSource.includes('data-testid="home-secondary-path-details"') &&
      homeOverviewSource.includes('data-testid="home-detailed-path-details"') &&
      homeOverviewSource.includes('data-testid="home-operating-summary-details"') &&
      homeActionDockSource.includes('className={hasData ? "homeActionDock" : "homeActionDock firstRun"}') &&
      homeActionDockSource.includes('disabled={!hasData}') &&
      productActivationModelSource.includes('ProductActivationStepKey = "connect" | "profile" | "chart" | "evidence" | "confirm"') &&
      productActivationModelSource.includes("const activeStepKey: ProductActivationStepKey = flow.activeStage") &&
      workspaceFlowModelSource.includes("export function buildWorkspaceFlow") &&
      workspaceFlowModelSource.includes("export function isBusinessStepLockedByFlow") &&
      workspaceFlowModelSource.includes("export function resolveSectionForFlow") &&
      appSource.includes("const workspaceFlow = useMemo(() => buildWorkspaceFlow") &&
      appSource.includes("resolveSectionForFlow(section, workspaceFlow)") &&
      sidebarSource.includes("isSectionLockedByFlow") &&
      businessPathBarSource.includes("isBusinessStepLockedByFlow") &&
      productActivationModelSource.includes("Charts and evidence appear only after a real import") &&
      productActivationModelSource.includes("full industry boards remain beta") &&
      productActivationPanelSource.includes('data-testid={`product-activation-step-${step.key}`}') &&
      sourceWorkbenchSource.includes("const hasData = tables.length > 0 || status.counts.tables > 0") &&
      sourceWorkbenchSource.includes("const showExpertWorkbench = showAdvanced") &&
      sourceWorkbenchSource.includes('testId="source-product-activation"') &&
      sourceWorkbenchSource.includes("onOpenBusinessStep") &&
      !sourceWorkbenchSource.includes('data-testid="source-no-data-guide"') &&
      sourceWorkbenchSource.includes('data-testid="source-expert-details"') &&
      dashboardCanvasSource.includes("onOpenBusinessStep: (step: BusinessPathStepKey) => void") &&
      dashboardCanvasSource.includes('testId="dashboard-product-activation"') &&
      !dashboardCanvasSource.includes('data-testid="dashboard-no-data-route"') &&
      dashboardCanvasSource.includes('data-testid="dashboard-guided-edit-details"') &&
      dashboardCanvasSource.includes('data-testid="dashboard-advanced-edit-details"') &&
      dashboardCanvasSource.includes('data-testid="dashboard-contract-details"') &&
      agentPanelSource.includes("onOpenSources: () => void") &&
      agentPanelSource.includes('data-testid="agent-no-data-route"') &&
      agentPanelSource.includes('data-testid="agent-suggestion-details"') &&
      agentPanelSource.includes('data-testid="agent-evidence-audit-details"') &&
      agentPanelSource.includes('data-testid="agent-task-packet-details"') &&
      evidenceViewSource.includes("onOpenBusinessStep: (step: BusinessPathStepKey) => void") &&
      evidenceViewSource.includes("useQualityDoctor(hasData, workbench)") &&
      /if \(!enabled\) \{\s*setResult\(null\);\s*return;\s*\}/.test(useQualityDoctorSource) &&
      evidenceViewSource.includes('testId="evidence-product-activation"') &&
      !evidenceViewSource.includes('data-testid="evidence-no-data-route"') &&
      evidenceViewSource.includes('data-testid="evidence-explanation-details"') &&
      evidenceViewSource.includes('data-testid="evidence-receipts-details"') &&
      viewWorkspaceSource.includes('data-testid="view-dashboard-bridge-details"') &&
      viewWorkspaceSource.includes('data-testid="view-agent-task-details"') &&
      viewWorkspaceSource.includes('data-testid="view-manage-details"') &&
      settingsPanelSource.includes('data-testid="settings-sandbox-details"') &&
      settingsPanelSource.includes('data-testid="settings-acceptance-details"') &&
      settingsPanelSource.includes('data-testid="settings-config-portability-details"') &&
      sidebarWorkspaceCardSource.includes('<details className="workspaceManageDetails">') &&
      sidebarAssetSectionsSource.includes('data-testid="sidebar-source-asset-details"') &&
      sidebarAssetSectionsSource.includes('data-testid="sidebar-dashboard-asset-details"') &&
      sidebarAssetSectionsSource.includes('data-testid="sidebar-evidence-asset-details"') &&
      businessPathBarSource.includes('className={compact ? "businessPathBar compact" : "businessPathBar"}') &&
      agentCommandDockSource.includes("const shouldMinimize = !hasTables && !assistantOpen && activeSection !== \"agent\"") &&
      agentCommandDockSource.includes("onboardingMinimized") &&
      !stylesSource.includes(".firstRunFocusPanel") &&
      !stylesSource.includes(".sourceNoDataGuide") &&
      stylesSource.includes(".productActivationSteps") &&
      stylesSource.includes(".productActivationFactGrid") &&
      stylesSource.includes(".sourceBeginnerMode .workbenchGrid") &&
      stylesSource.includes(".noDataRoutePanel") &&
      stylesSource.includes(".workspaceManageDetails") &&
      stylesSource.includes(".workspaceManageDetails:not([open]) > :not(summary)") &&
      stylesSource.includes(".progressiveDetails") &&
      stylesSource.includes(".dashboardProgressiveGrid") &&
      stylesSource.includes(".evidenceProgressiveGrid") &&
      stylesSource.includes(".sidebarAssetDetails") &&
      stylesSource.includes(".homeIntelligenceGrid") &&
      stylesSource.includes(".sandboxCompareFacts") &&
      stylesSource.includes(".sandboxVersionHints") &&
      stylesSource.includes(".businessPathBar.compact") &&
      stylesSource.includes(".agentCommandDock.onboardingMinimized"),
  },
  {
    label: "product-ux-acceptance-documentation-boundary",
    ok: productUxStandardDocSource.includes("## First Success Flow Standard") &&
      productUxStandardDocSource.includes("## Object Ownership Matrix") &&
      productUxStandardDocSource.includes("## Delete And Rollback Standard") &&
      productUxStandardDocSource.includes("docs/product-acceptance-matrix.md") &&
      productAcceptanceMatrixDocSource.includes("Empty workspace") &&
      productAcceptanceMatrixDocSource.includes("Create one chart") &&
      productAcceptanceMatrixDocSource.includes("Delete source or object") &&
      productAcceptanceMatrixDocSource.includes("Production no-demo boundary") &&
      productAcceptanceMatrixDocSource.includes("validation-inputs") &&
      docsReadmeSource.includes("product-acceptance-matrix.md") &&
      prdDocSource.includes("validation-inputs") &&
      !prdDocSource.includes("source-intelligence fixtures") &&
      implementationStatusSource.includes("Product activation model and panel boundary"),
  },
  {
    label: "frontend-production-copy-no-example-placeholders",
    ok: productAcceptanceMatrixDocSource.includes("- `npm run preflight`") &&
      dashboardCanvasSource.includes('name: biText("未命名看板", "Untitled dashboard")') &&
      !dashboardCanvasSource.includes("临时看板") &&
      !dashboardCanvasSource.includes("Temporary dashboard") &&
      dashboardBusinessTaskStripSource.includes("描述指标、维度、时间范围或想比较的对象") &&
      dashboardBusinessTaskStripSource.includes("Describe the metric, dimension, time range, or comparison") &&
      !dashboardBusinessTaskStripSource.includes("例如：") &&
      !dashboardBusinessTaskStripSource.includes("Example:") &&
      agentCommandDockSource.includes("输入你想分析的问题或要生成的图表") &&
      agentCommandDockSource.includes("Enter the question to analyze or chart to create") &&
      !agentCommandDockSource.includes("直接问：") &&
      !agentCommandDockSource.includes("Ask: which channel") &&
      docsReadmeSource.includes("development-roadmap.md") &&
      docsReadmeSource.includes("`npm run preflight` 是本地交付前总入口") &&
      prdDocSource.includes("`npm run preflight` 通过，作为本地交付前总入口") &&
      developmentRoadmapDocSource.includes("## Development Order") &&
      developmentRoadmapDocSource.includes("## Current Release Status") &&
      developmentRoadmapDocSource.includes("Production copy and no-demo boundary") &&
      developmentRoadmapDocSource.includes("AI one-chart path") &&
      developmentRoadmapDocSource.includes("Complete for this baseline") &&
      developmentRoadmapDocSource.includes("Use `npm run preflight` as the final local acceptance gate"),
  },
  {
    label: "home-detailed-path-panel-boundary",
    ok: existsSync(join(root, "src", "components", "HomeDetailedPathPanel.tsx")) &&
      homeOverviewSource.includes('import { HomeDetailedPathPanel } from "./HomeDetailedPathPanel"') &&
      homeOverviewSource.includes("<HomeDetailedPathPanel") &&
      !homeOverviewSource.includes('data-testid="home-detailed-path"') &&
      homeDetailedPathPanelSource.includes("type HomeDetailedPathPanelProps") &&
      homeDetailedPathPanelSource.includes("runDashboardTemplate: (confirm: boolean) => Promise<void>") &&
      homeDetailedPathPanelSource.includes("onSourceIntelligenceRun: () => Promise<Record<string, unknown> | void>") &&
      homeDetailedPathPanelSource.includes("查看更多数据源、通用看板和 Agent 路径") &&
      homeDetailedPathPanelSource.includes("预览看板草案") &&
      homeDetailedPathPanelSource.includes("帮我生成经营看板并说明证据") &&
      implementationStatusSource.includes("Home detailed path panel boundary"),
  },
  {
    label: "frontend-state-driven-landing",
    ok: appSource.includes("function sectionFromUrl(): AppSection | null") &&
      appSource.includes('import { isAppSection } from "./appSections"') &&
      appSectionsSource.includes("export function isAppSection") &&
      appSource.includes("return isAppSection(section) ? section : null") &&
      appSource.includes("return sectionFromUrl() ?? \"home\"") &&
      appSource.includes('from "./appWorkspaceModel"') &&
      appWorkspaceModelSource.includes("export function preferredLandingSection") &&
      appWorkspaceModelSource.includes("if (hasDashboard) return \"dashboards\"") &&
      appWorkspaceModelSource.includes("if (hasSource) return \"sources\"") &&
      appSource.includes("explicitInitialSectionRef") &&
      appSource.includes("autoLandingAppliedRef") &&
      appSource.includes('import { refreshStatusDashboardsWorkbenchDrafts } from "./appRefreshModel"') &&
      appRefreshModelSource.includes("export async function refreshStatusDashboardsWorkbenchDrafts") &&
      appSource.includes("setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards))") &&
      !appSource.includes("setSection(\"home\");"),
  },
  {
    label: "app-agent-actions-hook-boundary",
    ok: existsSync(join(root, "src", "useAppAgentActions.ts")) &&
      appSource.includes('from "./useAppAgentActions"') &&
      appSource.includes("useAppAgentActions({") &&
      appSource.includes("setAgent,") &&
      appSource.includes("handleAgentCommandAsk,") &&
      appSource.includes("handleConfirmAction,") &&
      appAgentActionsSource.includes("export function useAppAgentActions(") &&
      appAgentActionsSource.includes("type AppAgentActionsOptions") &&
      appAgentActionsSource.includes("const handleAsk = useCallback") &&
      appAgentActionsSource.includes("const handleAskReadOnly = useCallback") &&
      appAgentActionsSource.includes("const handleConfirmAction = useCallback") &&
      appAgentActionsSource.includes("const handleRejectAction = useCallback") &&
      appAgentActionsSource.includes("confirmAction(actionKey, true, true)") &&
      appAgentActionsSource.includes("setSection(\"dashboards\")") &&
      appAgentActionsSource.includes("setSection(\"agent\")") &&
      !appSource.includes("const handleAsk = useCallback") &&
      !appSource.includes("const handleConfirmAction = useCallback") &&
      !appSource.includes("const handleRejectAction = useCallback"),
  },
  {
    label: "app-settings-actions-hook-boundary",
    ok: existsSync(join(root, "src", "useAppSettingsActions.ts")) &&
      appSource.includes('from "./useAppSettingsActions"') &&
      appSource.includes("useAppSettingsActions({") &&
      appSource.includes("handleSavePreferences,") &&
      appSource.includes("handleApplyConfig,") &&
      appSettingsActionsSource.includes("export function useAppSettingsActions") &&
      appSettingsActionsSource.includes("type AppSettingsActionsOptions") &&
      appSettingsActionsSource.includes("const handleSavePreferences = useCallback") &&
      appSettingsActionsSource.includes("const handleSaveThemePalette = useCallback") &&
      appSettingsActionsSource.includes("const handleValidateConfig = useCallback") &&
      appSettingsActionsSource.includes("const handleExportConfig = useCallback") &&
      appSettingsActionsSource.includes("const handleApplyConfig = useCallback") &&
      appSettingsActionsSource.includes("setSection(\"settings\")") &&
      appSettingsActionsSource.includes("refreshStatusWorkbenchDashboards()") &&
      appRefreshModelSource.includes("export async function refreshStatusWorkbenchDashboards") &&
      !appSource.includes("const handleSavePreferences = useCallback") &&
      !appSource.includes("const handleApplyConfig = useCallback"),
  },
  {
    label: "no-sample-runtime-domain-boundary",
    ok: !existsSync(join(root, "src", "sampleAgentData.ts")) &&
      !existsSync(join(root, "src", "sampleThemeData.ts")) &&
      existsSync(join(root, "src", "defaultThemeData.ts")) &&
      !existsSync(join(root, "src", "sampleData.ts")) &&
      !existsSync(join(root, "src", "sampleWorkspaceData.ts")) &&
      !existsSync(join(root, "src", "sampleWorkspaceQueryData.ts")) &&
      defaultThemeDataSource.includes("export const defaultUserPreferences") &&
      defaultThemeDataSource.includes("export const defaultThemePalettes") &&
      themeSource.includes('from "./defaultThemeData"') &&
      !biCliSource.includes(retiredSeedEnvName) &&
      !verifySource.includes(retiredSeedEnvName) &&
      !verifyBiCliAgentContractSource.includes(retiredSeedEnvName) &&
      !existsSync(join(root, "tools", "seed_orchestration_service.py")) &&
      !existsSync(join(root, "tools", "seed_default_objects_service.py")) &&
      emptyWorkspaceDataSource.includes("export const emptyWorkspaceStatus") &&
      !("verify:a-testdata" in packageJson.scripts) &&
      !existsSync(join(root, "scripts", "verify-a-testdata-source-intelligence.mjs")) &&
      !biCliSource.includes("A_TESTDATA_03_05_DIRS") &&
      !biCliSource.includes("--a-testdata-03-05") &&
      /elif op == "create":\s*resolved_table_key = ""/.test(biCliSource) &&
      biCliSource.includes('table_key = str(proposed.get("defaultTableKey") or "")') &&
      biCliSource.includes('layout = {"version": 1, "grid": "12-col", "widgets": [], "globalFilters": []}') &&
      !biCliSource.includes('("bar", "渠道净销售"') &&
      !biCliSource.includes('("table", "订单明细"') &&
      productUxStandardDocSource.includes("Creating an empty dashboard creates only the dashboard container") &&
      byLabel["cli-source-intelligence-no-input-blocked"].ok === true &&
      String(byLabel["cli-source-intelligence-no-input-blocked"].parsed?.error ?? "").includes("requires imported source paths") &&
      implementationStatusSource.includes("Empty workspace data boundary"),
  },
  {
    label: "frontend-dashboard-status-refresh-after-writes",
    ok: appSource.includes('from "./useAppDashboardActions"') &&
      appSource.includes("useAppDashboardActions({") &&
      appSource.includes("setActiveDashboardKey,") &&
      appSource.includes("handleBusinessDashboardOperation") &&
      appSource.includes("handleDashboardModulesSave") &&
      appSource.includes("handleDashboardOperation") &&
      !appSource.includes("const handleDashboardOperation = useCallback") &&
      !appSource.includes("const handleDashboardModulesSave = useCallback") &&
      appDashboardActionsSource.includes("export function useAppDashboardActions") &&
      appDashboardActionsSource.includes("type AppDashboardActionsOptions") &&
      appDashboardActionsSource.includes("refreshStatusAndDashboards()") &&
      appDashboardActionsSource.includes("refreshStatusWorkbenchDashboards()") &&
      appRefreshModelSource.includes("export async function refreshStatusAndDashboards") &&
      appRefreshModelSource.includes("export async function refreshStatusWorkbenchDashboards") &&
      appRefreshModelSource.includes("normalizeStatus(status)") &&
      appRefreshModelSource.includes("normalizeDashboards(dashboards)") &&
      appRefreshModelSource.includes("normalizeWorkbench(workbench)") &&
      appDashboardActionsSource.includes("actionErrorResult(\"business-dashboard\", error)"),
  },
  {
    label: "frontend-workspace-switcher",
    ok: sidebarWorkspaceCardSource.includes('data-testid="workspace-switcher"') &&
      sidebarSource.includes("onWorkspaceCreate") &&
      sidebarSource.includes("onWorkspaceSelect") &&
      sidebarSource.includes("onWorkspaceDelete") &&
      sidebarSource.includes("selectWorkspaceFromInput") &&
      sidebarSource.includes("createWorkspaceFromInput") &&
      sidebarSource.includes("deleteWorkspaceFromInput") &&
      appSource.includes("createWorkspace(name, false)") &&
      appSource.includes("selectWorkspace(workspaceId, true)") &&
      appSource.includes("deleteWorkspace(workspaceId, false)") &&
      appSource.includes("const handleWorkspaceDelete = useCallback") &&
      appSource.includes("reloadWorkspaceSurface"),
  },
  {
    label: "sidebar-workspace-card-component-boundary",
    ok: existsSync(join(root, "src", "components", "SidebarWorkspaceCard.tsx")) &&
      sidebarSource.includes('import { SidebarWorkspaceCard } from "./SidebarWorkspaceCard"') &&
      sidebarSource.includes("<SidebarWorkspaceCard") &&
      !sidebarSource.includes('data-testid="workspace-switcher"') &&
      sidebarWorkspaceCardSource.includes("type SidebarWorkspaceCardProps") &&
      sidebarWorkspaceCardSource.includes("createWorkspaceFromInput: () => Promise<void>") &&
      sidebarWorkspaceCardSource.includes("selectWorkspaceFromInput: (workspaceId: string) => Promise<void>") &&
      sidebarWorkspaceCardSource.includes("deleteWorkspaceFromInput: (workspaceId: string) => Promise<void>") &&
      sidebarWorkspaceCardSource.includes('data-testid="workspace-delete-list"') &&
      sidebarWorkspaceCardSource.includes("deletableWorkspaces") &&
      sidebarWorkspaceCardSource.includes("window.confirm") &&
      sidebarWorkspaceCardSource.includes("工作区沙盒") &&
      sidebarWorkspaceCardSource.includes("写入类动作仍必须先生成草案并确认") &&
      implementationStatusSource.includes("Sidebar workspace card component boundary"),
  },
  {
    label: "sidebar-asset-sections-component-boundary",
    ok: existsSync(join(root, "src", "components", "SidebarAssetSections.tsx")) &&
      sidebarSource.includes('import { SidebarAssetSections } from "./SidebarAssetSections"') &&
      sidebarSource.includes("<SidebarAssetSections") &&
      !sidebarSource.includes('aria-labelledby="source-assets-title"') &&
      !sidebarSource.includes('aria-labelledby="dashboard-assets-title"') &&
      sidebarAssetSectionsSource.includes("type SidebarAssetSectionsProps") &&
      sidebarAssetSectionsSource.includes('aria-labelledby="source-assets-title"') &&
      sidebarAssetSectionsSource.includes('aria-labelledby="dashboard-assets-title"') &&
      sidebarAssetSectionsSource.includes('aria-labelledby="agent-assets-title"') &&
      sidebarAssetSectionsSource.includes('aria-labelledby="evidence-assets-title"') &&
      sidebarAssetSectionsSource.includes("全局提问与确认") &&
      sidebarAssetSectionsSource.includes("右下角都可以直接提问") &&
      !sidebarAssetSectionsSource.includes("promptStack") &&
      !sidebarAssetSectionsSource.includes("用自然语言改看板") &&
      sidebarAssetSectionsSource.includes('aria-labelledby="settings-assets-title"') &&
      implementationStatusSource.includes("Sidebar asset sections component boundary"),
  },
  {
    label: "frontend-app-section-model-boundary",
    ok: existsSync(join(root, "src", "appSections.ts")) &&
      appSectionsSource.includes('export type AppSection = "home" | "sources" | "views" | "dashboards" | "agent" | "evidence" | "settings"') &&
      appSectionsSource.includes("export const appSections: Record<AppSection, AppSectionMeta>") &&
      appSectionsSource.includes("export const primaryAppSections") &&
      appSectionsSource.includes("export function getAppSection") &&
      appSectionsSource.includes("export function isAppSection") &&
      sidebarSource.includes('from "../appSections"') &&
      sidebarSource.includes("primaryAppSections.map") &&
      sidebarSource.includes("utilityAppSections.map") &&
      topBarSource.includes("getAppSection(activeSection)") &&
      appLazyModulesSource.includes("getAppSection(section)") &&
      appSource.includes("isAppSection(section) ? section : null") &&
      implementationStatusSource.includes("App section model boundary"),
  },
  {
    label: "frontend-desktop-shell-fluid-width",
    ok: stylesSource.includes("--shell-asset-width: clamp(280px, 17vw, 324px)") &&
      stylesSource.includes("--shell-inspector-width: clamp(300px, 18vw, 340px)") &&
      stylesSource.includes("grid-template-columns: var(--shell-rail-width) var(--shell-asset-width) minmax(0, 1fr) var(--shell-inspector-width)") &&
      stylesSource.includes("grid-template-columns: var(--shell-rail-width) var(--shell-asset-width) minmax(0, 1fr) var(--shell-inspector-collapsed-width)") &&
      stylesSource.includes("height: 100dvh") &&
      stylesSource.includes("overflow: hidden") &&
      !stylesSource.includes("--desktop-width") &&
      !stylesSource.includes("min-width: var(--desktop-width)") &&
      !stylesSource.includes("width: max(100vw") &&
      implementationStatusSource.includes("Desktop shell fluid width"),
  },
  {
    label: "frontend-sidebar-dashboard-asset-typing",
    ok: sidebarAssetSectionsSource.includes("resolveDashboardAsset(item: NavigationModule | DashboardPage") &&
      sidebarAssetSectionsSource.includes("type DashboardAsset") &&
      sidebarAssetSectionsSource.includes('import type { ActionDraft, AgentAskResult, DashboardPage, DashboardPayload, NavigationModule') &&
      sidebarAssetSectionsSource.includes("const asset = resolveDashboardAsset(item, dashboardPages)") &&
      !sidebarAssetSectionsSource.includes("as any") &&
      !sidebarSource.includes("as any"),
  },
  {
    label: "frontend-home-draft-state-requires-confirmation",
    ok: homeOverviewSource.includes('agent.requiresConfirmation && agent.actionDraft?.status === "draft"'),
  },
  {
    label: "frontend-home-dashboard-preview-visible",
    ok: homeOverviewSource.includes("const [dashboardPlan, setDashboardPlan]") &&
      homeOverviewSource.includes("setDashboardPlan(result)") &&
      homeDetailedPathPanelSource.includes('data-testid="home-dashboard-preview-result"') &&
      homeDetailedPathPanelSource.includes('data-testid="home-dashboard-preview-confirm"') &&
      homeDetailedPathPanelSource.includes('data-testid="home-dashboard-preview-open"') &&
      homeDetailedPathPanelSource.includes("runDashboardTemplate(false)") &&
      homeDetailedPathPanelSource.includes("runDashboardTemplate(true)") &&
      homeOverviewSource.includes("op: confirm ? \"create\" : \"draft\"") &&
      !homeOverviewSource.includes("runBusinessDashboardOperation({ op: \"create\""),
  },
  {
    label: "frontend-product-intelligence-model",
    ok: productIntelligenceModelSource.includes("export function buildScenarioPacks") &&
      productIntelligenceModelSource.includes("export function buildDataQualityDoctor") &&
      productIntelligenceModelSource.includes("export function buildObjectInspectorModel") &&
      productIntelligenceModelSource.includes("export function buildEvidenceNarrative") &&
      productIntelligenceModelSource.includes("export function buildSandboxComparison") &&
      productIntelligenceModelSource.includes("费用监控") &&
      productIntelligenceModelSource.includes("销售经营") &&
      productIntelligenceModelSource.includes("退款与异常") &&
      productIntelligenceModelSource.includes("现金流与动账"),
  },
  {
    label: "frontend-home-scenario-quality-sandbox-panels",
    ok: homeOverviewSource.includes("buildScenarioPacks(status, workbench)") &&
      homeOverviewSource.includes("buildDataQualityDoctor(status, workbench") &&
      homeOverviewSource.includes("buildSandboxComparison(status, workbench)") &&
      homeOverviewSource.includes("buildMetricRepairPlan(qualityDoctorResult, workbench)") &&
      homeOverviewSource.includes("<HomeScenarioPacksPanel") &&
      homeOverviewSource.includes("<HomeProductIntelligencePanel") &&
      homeScenarioPacksPanelSource.includes('data-testid="home-scenario-packs"') &&
      homeScenarioPacksPanelSource.includes('data-testid={`scenario-pack-${pack.key}`}') &&
      homeProductIntelligencePanelSource.includes('data-testid="home-product-intelligence"') &&
      homeProductIntelligencePanelSource.includes('data-testid="home-data-quality-doctor"') &&
      homeProductIntelligencePanelSource.includes('data-testid="home-quality-metric-sql"') &&
      homeProductIntelligencePanelSource.includes('data-testid="home-quality-missing-semantics"') &&
      homeProductIntelligencePanelSource.includes('data-testid="home-quality-repair-draft"') &&
      homeProductIntelligencePanelSource.includes('data-testid="home-quality-failed-metrics"') &&
      homeProductIntelligencePanelSource.includes('data-testid="home-metric-repair-wizard"') &&
      homeProductIntelligencePanelSource.includes('actionsTestId="home-semantic-binding-drafts"') &&
      homeProductIntelligencePanelSource.includes('loopTestId="home-semantic-confirm-loop"') &&
      homeProductIntelligencePanelSource.includes("onSetSemantic={onSetSemantic}") &&
      homeProductIntelligencePanelSource.includes("onSourceIntelligenceRun={onSourceIntelligenceRun}") &&
      homeOverviewSource.includes("useQualityDoctor(hasData, workbench)") &&
      useQualityDoctorSource.includes("getQualityDoctor()") &&
      homeProductIntelligencePanelSource.includes('data-testid="home-sandbox-compare"') &&
      homeOverviewSource.includes("runScenarioPrompt") &&
      homeOverviewSource.includes("previewScenarioTemplate") &&
      implementationStatusSource.includes("Home scenario packs component boundary") &&
      implementationStatusSource.includes("Home product intelligence component boundary") &&
      stylesSource.includes(".scenarioPackPanel") &&
      stylesSource.includes(".qualityDoctorPanel") &&
      stylesSource.includes(".qualityDoctorMetricSql") &&
      stylesSource.includes(".metricSemanticChips") &&
      stylesSource.includes(".metricRepairDraft") &&
      stylesSource.includes(".metricRepairWizard") &&
      stylesSource.includes(".semanticBindingDrafts") &&
      stylesSource.includes(".semanticRepairLoop") &&
      stylesSource.includes(".semanticBindingActions") &&
      stylesSource.includes(".semanticRepairResult") &&
      stylesSource.includes(".metricFailureSamples") &&
      stylesSource.includes(".sandboxComparePanel"),
  },
  {
    label: "frontend-semantic-confirm-loop-component",
    ok: metricSemanticRepairActionsSource.includes("export function MetricSemanticRepairActions") &&
      metricSemanticRepairActionsSource.includes("runSemanticAction") &&
      metricSemanticRepairActionsSource.includes("rerunSourceIntelligence") &&
      metricSemanticRepairActionsSource.includes("confirm,") &&
      metricSemanticRepairActionsSource.includes("stayOnPage: true") &&
      metricSemanticRepairActionsSource.includes("onSetSemantic({") &&
      metricSemanticRepairActionsSource.includes("if (!plan.rerunInputs.length)") &&
      metricSemanticRepairActionsSource.includes("请先在数据源工作台导入本地文件或文件夹") &&
      metricSemanticRepairActionsSource.includes("onSourceIntelligenceRun({ inputs: plan.rerunInputs") &&
      metricSemanticRepairActionsSource.includes("data-testid={loopTestId}") &&
      metricSemanticRepairActionsSource.includes("data-testid={actionsTestId}") &&
      metricSemanticRepairActionsSource.includes("semanticBindingActions") &&
      metricSemanticRepairActionsSource.includes("semanticRepairFooter") &&
      metricSemanticRepairActionsSource.includes("snapshotFromResult") &&
      !metricSemanticRepairActionsSource.includes("debug sample") &&
      metricSemanticRepairActionsSource.includes("previewedSemantics") &&
      metricSemanticRepairActionsSource.includes("draft.requiresPreview") &&
      metricSemanticRepairActionsSource.includes('data-testid={`${loopTestId}-benefit`}') &&
      metricSemanticRepairActionsSource.includes('data-testid={`${loopTestId}-comparison`}') &&
      metricSemanticRepairActionsSource.includes("semanticBindingRisk") &&
      metricSemanticRepairActionsSource.includes("预演") &&
      metricSemanticRepairActionsSource.includes("先预演") &&
      metricSemanticRepairActionsSource.includes("确认") &&
      metricSemanticRepairActionsSource.includes("重跑画像"),
  },
  {
    label: "frontend-semantic-confirm-app-wiring",
    ok: appSource.includes("onSetSemantic={handleSetSemantic}") &&
      appSource.includes("onSourceIntelligenceRun={handleSourceIntelligenceRun}") &&
      evidenceViewSource.includes("onSetSemantic:") &&
      evidenceViewSource.includes("onSourceIntelligenceRun:") &&
      evidenceViewSource.includes('loopTestId="evidence-semantic-confirm-loop"') &&
      appDataActionsSource.includes("stayOnPage = false") &&
      appDataActionsSource.includes("const { stayOnPage = false, ...semanticOptions } = options") &&
      appDataActionsSource.includes("setSemantic(semanticOptions)") &&
      appDataActionsSource.includes('if (!stayOnPage) setSection("sources")'),
  },
  {
    label: "frontend-metric-repair-model",
    ok: metricRepairModelSource.includes("export function buildMetricRepairPlan") &&
      metricRepairModelSource.includes("const semanticAliases") &&
      metricRepairModelSource.includes("SemanticBindingDraft") &&
      metricRepairModelSource.includes("EvidenceGapItem") &&
      metricRepairModelSource.includes("rerunInputs") &&
      metricRepairModelSource.includes("benefitSummary") &&
      metricRepairModelSource.includes("manifestInputRoots") &&
      metricRepairModelSource.includes("semanticRiskTerms") &&
      metricRepairModelSource.includes("riskForSemantic") &&
      metricRepairModelSource.includes("riskConfidenceCap") &&
      metricRepairModelSource.includes("preview-required") &&
      metricRepairModelSource.includes("needs-human-confirmation") &&
      metricRepairModelSource.includes("待选择字段"),
  },
  {
    label: "frontend-evidence-gap-panel",
    ok: evidenceViewSource.includes("buildMetricRepairPlan(qualityDoctorResult, workbench)") &&
      evidenceViewSource.includes("useQualityDoctor(hasData, workbench)") &&
      useQualityDoctorSource.includes("getQualityDoctor()") &&
      evidenceViewSource.includes('data-testid="evidence-gap-panel"') &&
      evidenceViewSource.includes('actionsTestId="evidence-gap-semantic-actions"') &&
      evidenceViewSource.includes('data-testid="evidence-gap-items"') &&
      evidenceViewSource.includes("MetricSemanticRepairActions") &&
      stylesSource.includes(".evidenceGapPanel") &&
      stylesSource.includes(".evidenceGapItems"),
  },
  {
    label: "quality-doctor-cli-api",
    ok: biCliSource.includes("def quality_doctor_command(") &&
      biCliSource.includes("def metric_sql_doctor_from_run(") &&
      biCliSource.includes("metric-sql-compiler.json") &&
      biCliSource.includes("metric-query-results.json") &&
      biCliSource.includes('sub.add_parser("quality-doctor")') &&
      biCliSource.includes('elif args.command == "quality-doctor"') &&
      serverWorkspaceRoutesSource.includes('url.pathname === "/api/quality/doctor"') &&
      serverWorkspaceRoutesSource.includes('cli(["quality-doctor"])') &&
      apiSource.includes("export function getQualityDoctor()") &&
      apiSource.includes('"/api/quality/doctor"') &&
      byLabel["cli-quality-doctor"].parsed?.source === "hybrid-quality-doctor" &&
      Array.isArray(byLabel["cli-quality-doctor"].parsed?.issues) &&
      byLabel["cli-quality-doctor"].parsed?.metricSql?.planned >= 0 &&
      byLabel["cli-quality-doctor"].parsed?.metricSql?.blocked >= 0 &&
      Array.isArray(byLabel["cli-quality-doctor"].parsed?.latestSourceIntelligenceRun?.inputRoots) &&
      Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.missingSemantics) &&
      Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.failedSamples) &&
      Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.semanticBindingDrafts) &&
      byLabel["cli-quality-doctor"].parsed?.metricSql?.repairDraft?.kind === "metric-sql.repair" &&
      Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.repairDraft?.semanticBindingDrafts),
  },
  {
    label: "frontend-initial-agent-readonly",
    ok: appSource.includes("setAgent(emptyAgentResult)") &&
      appSource.includes("setPreview(emptyImportPreview)") &&
      appSource.includes("setQuery(emptyQueryResult)") &&
      appSource.includes("setTableQuery(emptyTableQuery)") &&
      !appSource.includes("askAgent(\"先告诉我当前工作区能回答什么，不要创建任何草案\")") &&
      !appSource.includes("askAgent(\"生成经营分析计划\")"),
  },
  {
    label: "frontend-inspector-selected-context",
    ok: inspectorPanelSource.includes("activeSection: AppSection") &&
      inspectorPanelSource.includes("evidenceFocus?: EvidenceFocus | null") &&
      inspectorPanelSource.includes("data-testid=\"inspector-selected-context\"") &&
      inspectorPanelSource.includes("data-testid=\"inspector-selected-context-chips\"") &&
      inspectorPanelSource.includes("data-testid=\"inspector-open-evidence\"") &&
      inspectorPanelSource.includes("sectionContext(activeSection") &&
      inspectorPanelModelSource.includes("export function drawerActionsForSection") &&
      inspectorPanelModelSource.includes("export function sectionContext") &&
      inspectorPanelSource.includes("drawerActionsForSection(activeSection)") &&
      inspectorPanelModelSource.includes("检查摘要") &&
      inspectorPanelModelSource.includes("改看板") &&
      appSource.includes("activeSection={section}") &&
      appSource.includes("evidenceFocus={evidenceFocus}") &&
      appSource.includes("activeDashboardName={activeDashboardName}") &&
      appSource.includes("activeViewName={activeViewName}") &&
      appSource.includes("onOpenEvidence={handleInspectorOpenEvidence}") &&
      appSource.includes("const activeDashboardName ="),
  },
  {
    label: "frontend-collapsible-inspector",
    ok: appSource.includes("inspectorPreferenceStorageKey") &&
      appSource.includes("initialInspectorPreference") &&
      appSource.includes("data-inspector-state={inspectorExpanded ? \"expanded\" : \"collapsed\"}") &&
      appSource.includes("inspectorCollapsed={!inspectorExpanded}") &&
      appSource.includes("onCollapseInspector={handleInspectorCollapse}") &&
      appSource.includes("onExpandInspector={handleInspectorExpand}") &&
      appSource.includes("onPinInspectorToggle={handleInspectorPinToggle}") &&
      inspectorPanelSource.includes("inspectorCollapsed: boolean") &&
      inspectorPanelSource.includes("inspectorPinned: boolean") &&
      inspectorPanelSource.includes("data-testid=\"inspector-expand\"") &&
      inspectorPanelSource.includes("data-testid=\"inspector-collapse\"") &&
      inspectorPanelSource.includes("data-testid=\"inspector-pin\"") &&
      inspectorPanelSource.includes("data-testid=\"inspector-mini-evidence\"") &&
      inspectorPanelSource.includes("data-testid=\"inspector-mini-tasks\"") &&
      inspectorPanelSource.includes("data-testid=\"inspector-mini-safety\"") &&
      stylesSource.includes('.appShell[data-inspector-state="collapsed"]') &&
      stylesSource.includes(".inspectorCollapsed") &&
      stylesSource.includes(".inspectorMiniButton"),
  },
  {
    label: "frontend-inspector-friendly-action-error",
    ok: inspectorPanelSource.includes("actionResultSummary(lastActionResult)") &&
      inspectorPanelSource.includes("import { actionKindLabel, actionNextStep, actionResultSummary, drawerActionsForSection, payloadTarget, sectionContext }") &&
      actionRecoveryModelSource.includes("export function buildActionRecovery") &&
      actionRecoveryModelSource.includes("query-table") &&
      actionRecoveryModelSource.includes("dashboard-recovery") &&
      actionRecoveryModelSource.includes("source-recovery") &&
      actionRecoveryModelSource.includes("export function actionRecoveryFromError") &&
      appWorkspaceModelSource.includes('import { actionRecoveryFromError, buildActionRecovery } from "./actionRecoveryModel"') &&
      appWorkspaceModelSource.includes("actionRecoveryFromError(error) ?? buildActionRecovery(action, error)") &&
      appWorkspaceModelSource.includes("targetSection: recovery.targetSection") &&
      appWorkspaceModelSource.includes("recovery,") &&
      inspectorPanelModelSource.includes('import { actionRecoveryFromResult } from "./actionRecoveryModel"') &&
      inspectorPanelModelSource.includes("const recovery = actionRecoveryFromResult(result)") &&
      inspectorPanelModelSource.includes("steps: recovery.steps") &&
      inspectorPanelModelSource.includes("targetSection: recovery.targetSection") &&
      inspectorPanelModelSource.includes("function friendlyActionError") &&
      inspectorPanelModelSource.includes("No analyzable CSV/XLSX spreadsheet was found") &&
      inspectorPanelModelSource.includes("证据摘要没有完成") &&
      inspectorPanelSource.includes('data-testid="last-action-recovery-steps"') &&
      inspectorPanelSource.includes('data-testid="last-action-recovery-open-section"') &&
      inspectorPanelSource.includes("getAppSection(latestSummary.targetSection)") &&
      inspectorPanelSource.includes("onOpenSection(latestSummary.targetSection!)") &&
      inspectorPanelSource.includes("visibleActionSafeState") &&
      appSource.includes("const handleInspectorOpenSection = useCallback") &&
      appSource.includes("onOpenSection={handleInspectorOpenSection}") &&
      inspectorPanelSource.includes("data-testid=\"last-action-technical\"") &&
      inspectorPanelSource.includes("visibleActionSummary ${latestSummary.tone}") &&
      inspectorPanelSource.includes("查看错误原文") &&
      appDataActionsSource.includes('action: "source-intelligence"') &&
      appDataActionsSource.includes("throw error") &&
      stylesSource.includes(".visibleActionSummary.failed") &&
      stylesSource.includes(".visibleActionSummaryBody") &&
      stylesSource.includes(".visibleActionSafeState") &&
      stylesSource.includes(".visibleActionRecoverySteps") &&
      stylesSource.includes(".visibleActionRecoveryAction") &&
      stylesSource.includes(".visibleActionTechnical"),
  },
  {
    label: "frontend-inspector-action-queue-business-first",
    ok: inspectorPanelModelSource.includes("export function actionNextStep") &&
      inspectorPanelModelSource.includes("export function payloadTarget") &&
      inspectorPanelModelSource.includes("export function actionKindLabel") &&
      inspectorPanelSource.includes("actionNextStep(draft)") &&
      inspectorPanelSource.includes("payloadTarget(draft)") &&
      inspectorPanelSource.includes("actionKindLabel(draft.kind)") &&
      inspectorPanelSource.includes('data-testid="action-queue-next-step"') &&
      inspectorPanelSource.includes('data-testid={`action-queue-technical-${draft.action_key}`}') &&
      inspectorPanelSource.includes("查看证据和编号") &&
      inspectorPanelSource.includes("查看错误原文") &&
      inspectorPanelSource.includes("证据线索") &&
      !inspectorPanelSource.includes("evidence refs`)") &&
      stylesSource.includes(".taskNextStep") &&
      stylesSource.includes(".taskEvidenceRow summary"),
  },
  {
    label: "frontend-object-inspector-v2",
    ok: inspectorPanelSource.includes("buildObjectInspectorModel({ activeSection") &&
      inspectorPanelSource.includes('data-testid="object-inspector-lens"') &&
      inspectorPanelSource.includes('data-testid="object-inspector-facts"') &&
      inspectorPanelSource.includes('data-testid="object-inspector-editor-slots"') &&
      inspectorPanelSource.includes("objectModel.primaryAction") &&
      inspectorPanelSource.includes('<details className="contextReservePanel">') &&
      inspectorPanelSource.includes("扩展能力") &&
      stylesSource.includes(".objectInspectorLens") &&
      stylesSource.includes(".objectInspectorFacts") &&
      stylesSource.includes(".objectInspectorSlots") &&
      stylesSource.includes(".contextReservePanel summary"),
  },
  {
    label: "frontend-evidence-number-explainer",
    ok: evidenceViewSource.includes("buildEvidenceNarrative(focus, agent, workbench)") &&
      evidenceViewSource.includes("<EvidenceNumberExplainerPanel") &&
      evidenceNumberExplainerPanelSource.includes('data-testid="evidence-number-explainer"') &&
      evidenceNumberExplainerPanelSource.includes('data-testid="evidence-calculation-steps"') &&
      evidenceNumberExplainerPanelSource.includes('data-testid="evidence-trust-checks"') &&
      evidenceNumberExplainerPanelSource.includes("数字说明书") &&
      stylesSource.includes(".evidenceNarrativeCard") &&
      stylesSource.includes(".evidenceNarrativeSteps") &&
      stylesSource.includes(".evidenceTrustChecks"),
  },
  {
    label: "evidence-number-explainer-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "EvidenceNumberExplainerPanel.tsx")) &&
      evidenceViewSource.includes('import { EvidenceNumberExplainerPanel } from "./EvidenceNumberExplainerPanel"') &&
      evidenceViewSource.includes("<EvidenceNumberExplainerPanel") &&
      !evidenceViewSource.includes('data-testid="evidence-number-explainer"') &&
      evidenceNumberExplainerPanelSource.includes('import type { EvidenceNarrative } from "../productIntelligenceModel"') &&
      evidenceNumberExplainerPanelSource.includes("type EvidenceNumberExplainerPanelProps") &&
      !evidenceNumberExplainerPanelSource.includes("type EvidenceNarrativeStep") &&
      !evidenceNumberExplainerPanelSource.includes("type EvidenceNarrative =") &&
      evidenceNumberExplainerPanelSource.includes("evidenceNarrative.calculationSteps.map") &&
      implementationStatusSource.includes("Evidence number explainer panel component boundary"),
  },
  {
    label: "frontend-agent-dock-beginner-task-entry",
    ok: agentCommandDockSource.includes("data-testid=\"agent-command-dock\"") &&
      !appSource.includes('section !== "agent"') &&
      appSource.includes("<AgentCommandDock") &&
      agentCommandDockSource.includes('data-testid="floating-agent-button"') &&
      agentCommandDockSource.includes('data-testid="floating-agent-panel"') &&
      agentCommandDockSource.includes('setAssistantOpen(true)') &&
      agentCommandDockSource.includes('setAssistantOpen(false)') &&
      agentCommandDockSource.includes('aria-label={biText("全局 AI 助手"') &&
      agentCommandDockSource.includes('getAppSection(activeSection)') &&
      agentCommandDockSource.includes('import { resolveAgentPromptRoute, type AgentPromptRoute } from "../agentPromptRouting"') &&
      agentCommandDockSource.includes("const [routeHint, setRouteHint] = useState<AgentPromptRoute | null>(null)") &&
      agentCommandDockSource.includes("const route = resolveAgentPromptRoute(normalizedPrompt, status)") &&
      agentCommandDockSource.includes("onOpenSection(route.section)") &&
      agentCommandDockSource.includes("await onAsk(normalizedPrompt, route.section)") &&
      agentCommandDockSource.includes('data-testid="agent-route-hint"') &&
      agentPromptRoutingSource.includes("export function resolveAgentPromptRoute") &&
      agentPromptRoutingSource.includes('section: "sources"') &&
      agentPromptRoutingSource.includes('section: "views"') &&
      agentPromptRoutingSource.includes('section: "dashboards"') &&
      agentPromptRoutingSource.includes('section: "evidence"') &&
      agentPromptRoutingSource.includes('section: "settings"') &&
      appAgentActionsSource.includes("targetSection?: AppSection") &&
      appAgentActionsSource.includes("if (nextAgent?.requiresConfirmation)") &&
      appAgentActionsSource.includes('setSection(targetSection ?? "agent")') &&
      agentCommandDockSource.includes("aria-busy={busy}") &&
      agentCommandDockSource.includes("data-testid=\"agent-task-strip\"") &&
      agentCommandDockSource.includes("data-testid=\"agent-task-sources\"") &&
      agentCommandDockSource.includes("data-testid=\"agent-task-dashboard\"") &&
      /data-testid="agent-task-dashboard"\s+disabled=\{busy\}/.test(agentCommandDockSource) &&
      agentCommandDockSource.includes("data-testid=\"agent-task-evidence\"") &&
      /data-testid="agent-task-ask"\s+disabled=\{busy\}/.test(agentCommandDockSource) &&
      agentCommandDockSource.includes("data-testid=\"agent-decision-lane\"") &&
      agentCommandDockSource.includes("data-testid={`agent-decision-${item.key}`}") &&
      agentCommandDockSource.includes("data-testid={`agent-decision-${item.key}`} disabled={busy}") &&
      /disabled=\{busy\}\s+key=\{item\.(key|zh)\}/.test(agentCommandDockSource) &&
      agentCommandDockSource.includes("Can answer") &&
      agentCommandDockSource.includes("Review needed") &&
      agentCommandDockSource.includes("Missing data") &&
      agentCommandDockSource.includes("sourceIntelligenceCount") &&
      agentCommandDockSource.includes("hasEvidenceProfile") &&
      agentCommandDockSource.includes("onOpenSection(\"sources\")") &&
      agentCommandDockSource.includes("onOpenSection(\"evidence\")") &&
      agentCommandDockSource.includes("生成一个经营看板待确认修改，先不要直接写入") &&
      stylesSource.includes(".agentCommandDock.floating") &&
      stylesSource.includes(".agentFloatButton") &&
      stylesSource.includes(".agentFloatPanel") &&
      stylesSource.includes(".agentRouteHint") &&
      stylesSource.includes('.appShell[data-inspector-state="expanded"] .agentCommandDock.floating') &&
      stylesSource.includes(".agentDockDecisionLane") &&
      stylesSource.includes(".agentDockShortcuts button") &&
      stylesSource.includes("min-height: 34px") &&
      implementationStatusSource.includes("Global floating Agent assistant"),
  },
  {
    label: "frontend-dashboard-readiness-panel",
    ok: dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-panel\"") &&
      dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-facts\"") &&
      !dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-agent\"") &&
      !dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-recommend\"") &&
      !dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-evidence\"") &&
      dashboardCanvasSource.includes("dashboardHealthTitle") &&
      dashboardCanvasSource.includes("dashboardHealthItems") &&
      dashboardCanvasReadinessModelSource.includes("Add evidence profiling") &&
      stylesSource.includes(".dashboardReadinessPanel") &&
      stylesSource.includes(".dashboardReadinessFacts") &&
      !stylesSource.includes(".dashboardReadinessActions"),
  },
  {
    label: "frontend-import-to-dashboard-wizard",
    ok: sourceWorkbenchActionPanelSource.includes('data-testid="import-to-dashboard-wizard"') &&
      sourceWorkbenchActionPanelSource.includes('<details className="sourceGuideDetails"') &&
      sourceWorkbenchActionPanelSource.includes("这些文件是什么业务？") &&
      sourceWorkbenchActionPanelSource.includes("证据摘要是否完整？") &&
      sourceWorkbenchActionPanelSource.includes("先看什么问题？") &&
      sourceWorkbenchActionPanelSource.includes("source-agent-import-guide") &&
      !sourceWorkbenchActionPanelSource.includes("beginner-plan-import-data") &&
      sourceWorkbenchActionPanelSource.includes('disabled={!dashboardRecipeReady || busy === "source-business-dashboard-create"}') &&
      stylesSource.includes(".importToDashboardWizard") &&
      stylesSource.includes(".wizardQuestionGrid") &&
      stylesSource.includes(".wizardActions"),
  },
  {
    label: "frontend-settings-sandbox-boundary",
    ok: settingsSandboxBoundaryPanelSource.includes("const settingsSandboxItems") &&
      settingsSandboxBoundaryPanelSource.includes("data-testid=\"settings-sandbox-boundary\"") &&
      settingsSandboxBoundaryPanelSource.includes("data-testid=\"settings-sandbox-grid\"") &&
      settingsSandboxBoundaryPanelSource.includes("data-testid={`settings-sandbox-${item.key}`}") &&
      settingsSandboxBoundaryPanelSource.includes("外部源目录只读") &&
      settingsSandboxBoundaryPanelSource.includes("业务数据不导出") &&
      settingsSandboxBoundaryPanelSource.includes("写入先预演，再确认") &&
      settingsSandboxBoundaryPanelSource.includes("手动资产默认受保护") &&
      settingsSandboxBoundaryPanelSource.includes("onRunConfigAction(\"validate-config\", onValidateConfig)") &&
      settingsSandboxBoundaryPanelSource.includes("onRunConfigAction(\"export-config\", onExportConfig)") &&
      stylesSource.includes(".settingsSandboxCard") &&
      stylesSource.includes(".settingsSandboxGrid") &&
      stylesSource.includes(".settingsSandboxBadge.warn"),
  },
  {
    label: "settings-sandbox-boundary-panel-component",
    ok: existsSync(join(root, "src", "components", "SettingsSandboxBoundaryPanel.tsx")) &&
      settingsPanelSource.includes('import { SettingsSandboxBoundaryPanel } from "./SettingsSandboxBoundaryPanel"') &&
      settingsPanelSource.includes("<SettingsSandboxBoundaryPanel") &&
      !settingsPanelSource.includes("const settingsSandboxItems") &&
      !settingsPanelSource.includes('data-testid="settings-sandbox-boundary"') &&
      settingsSandboxBoundaryPanelSource.includes("type SettingsSandboxBoundaryPanelProps") &&
      settingsSandboxBoundaryPanelSource.includes("draftPreferences: UserPreferencesConfig") &&
      implementationStatusSource.includes("Settings sandbox boundary panel component"),
  },
  {
    label: "settings-theme-preference-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "SettingsThemePreferencePanel.tsx")) &&
      settingsPanelSource.includes('import { SettingsThemePreferencePanel, ThemeSwatches } from "./SettingsThemePreferencePanel"') &&
      settingsPanelSource.includes("<SettingsThemePreferencePanel") &&
      !settingsPanelSource.includes('className="themePaletteGrid"') &&
      !settingsPanelSource.includes('className="preferenceList"') &&
      settingsThemePreferencePanelSource.includes("type SettingsThemePreferencePanelProps") &&
      settingsThemePreferencePanelSource.includes("export function ThemeSwatches") &&
      settingsThemePreferencePanelSource.includes('data-testid="settings-theme-palette-panel"') &&
      settingsThemePreferencePanelSource.includes('data-testid="settings-preference-switch-panel"') &&
      settingsThemePreferencePanelSource.includes("onPreferenceToggle(row.key, event.target.checked)") &&
      settingsThemePreferencePanelSource.includes("themeIsSystem(theme)") &&
      implementationStatusSource.includes("Settings theme preference panel component boundary"),
  },
  {
    label: "frontend-settings-friendly-config-result",
    ok: settingsPanelSource.includes("import { SettingsConfigPortabilityPanel }") &&
      settingsPanelSource.includes("<SettingsConfigPortabilityPanel") &&
      settingsPanelSource.includes("onRunConfigAction={runConfigAction}") &&
      settingsConfigPortabilityPanelSource.includes("function configResultMessage") &&
      settingsConfigPortabilityPanelSource.includes("function friendlyConfigWarning") &&
      settingsConfigPortabilityPanelSource.includes("const configMigrationSteps") &&
      settingsConfigPortabilityPanelSource.includes("const configMigrationScopes") &&
      settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-safety-plan\"") &&
      settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-migration-steps\"") &&
      settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-migration-scope\"") &&
      settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-friendly-result\"") &&
      settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-result-facts\"") &&
      settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-result-technical\"") &&
      settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-restore-guard\"") &&
      settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-restore-actions\"") &&
      settingsConfigPortabilityPanelSource.includes("配置可以迁移，业务数据和密钥不跟着走") &&
      settingsConfigPortabilityPanelSource.includes("恢复配置时必须先预览影响") &&
      settingsConfigPortabilityPanelSource.includes("检查当前设置") &&
      settingsConfigPortabilityPanelSource.includes("备份工作区设置") &&
      settingsConfigPortabilityPanelSource.includes("检查恢复影响") &&
      settingsConfigPortabilityPanelSource.includes("可以继续使用，有待同步项") &&
      settingsConfigPortabilityPanelSource.includes("连接器 ${connectorMatch[1]} 还没有同步成数据表 ${connectorMatch[2]}") &&
      settingsConfigPortabilityPanelSource.includes("查看配置检查明细") &&
      !settingsConfigPortabilityPanelSource.includes("Dry-run restore") &&
      stylesSource.includes(".configSafetyPlan") &&
      stylesSource.includes(".configMigrationSteps") &&
      stylesSource.includes(".configMigrationScope") &&
      stylesSource.includes(".configResultHeader") &&
      stylesSource.includes(".configResultFacts") &&
      stylesSource.includes(".configResultDetails"),
  },
  {
    label: "frontend-settings-closure-workbench",
    ok: settingsAcceptanceEvidencePanelSource.includes("const closureItems") &&
      settingsAcceptanceEvidencePanelSource.includes('data-testid="settings-closure-workbench"') &&
      settingsAcceptanceEvidencePanelSource.includes('data-testid="settings-closure-lead"') &&
      settingsAcceptanceEvidencePanelSource.includes('data-testid="settings-closure-grid"') &&
      settingsAcceptanceEvidencePanelSource.includes('data-testid={`settings-closure-${item.key}`}') &&
      settingsAcceptanceEvidencePanelSource.includes("刷新不白屏") &&
      settingsAcceptanceEvidencePanelSource.includes("本地 BI 操作已并入当前工作区") &&
      settingsAcceptanceEvidencePanelSource.includes("空工作区只引导导入") &&
      settingsAcceptanceEvidencePanelSource.includes("看板阅读和编辑动作集中可验收") &&
      settingsAcceptanceEvidencePanelSource.includes("新手路径已收敛") &&
      settingsAcceptanceEvidencePanelSource.includes("docs/implementation-status.md") &&
      settingsAcceptanceEvidencePanelSource.includes("python tools/bi_cli.py --json b-cli-capabilities") &&
      settingsAcceptanceEvidencePanelSource.includes('data-testid={`settings-closure-technical-${item.key}`}') &&
      settingsAcceptanceEvidencePanelSource.includes("empty-workspace-data-boundary") &&
      settingsAcceptanceEvidencePanelSource.includes("frontend-b-widget-acceptance-gallery") &&
      stylesSource.includes(".closureWorkbenchCard") &&
      stylesSource.includes(".closureGrid") &&
      stylesSource.includes(".closureItem.ok") &&
      stylesSource.includes(".closureTechnical"),
  },
  {
    label: "settings-acceptance-evidence-panel-component-boundary",
    ok: existsSync(join(root, "src", "components", "SettingsAcceptanceEvidencePanel.tsx")) &&
      settingsPanelSource.includes('import { SettingsAcceptanceEvidencePanel } from "./SettingsAcceptanceEvidencePanel"') &&
      settingsPanelSource.includes("<SettingsAcceptanceEvidencePanel") &&
      !settingsPanelSource.includes("const closureItems") &&
      !settingsPanelSource.includes('data-testid="settings-closure-workbench"') &&
      !settingsPanelSource.includes('className="settingsEvidenceList"') &&
      settingsAcceptanceEvidencePanelSource.includes("export function SettingsAcceptanceEvidencePanel") &&
      settingsAcceptanceEvidencePanelSource.includes('className="settingsEvidenceList"') &&
      settingsAcceptanceEvidencePanelSource.includes('data-testid="settings-closure-workbench"') &&
      implementationStatusSource.includes("Settings acceptance evidence panel component boundary"),
  },
  {
    label: "frontend-no-sample-debug-entry",
    ok: !existsSync(join(root, "src", "components", "HomeRealDataValidationPanel.tsx")) &&
      !homeOverviewSource.includes("runATestdataDebugChain") &&
      !homeOverviewSource.includes("HomeRealDataValidationPanel") &&
      !homeOverviewSource.includes("A testdata") &&
      !homeOverviewSource.includes("onSourceDashboardDraft({") &&
      !appDataActionsSource.includes("aTestdata0305") &&
      !sourceIntelligenceRunModelSource.includes("aTestdata0305") &&
      !metricSemanticRepairActionsSource.includes("debug sample") &&
      appDataActionsSource.includes("请先在数据源工作台选择本地文件或文件夹"),
  },
  {
    label: "a-adversarial-source-intelligence-harness",
    ok: packageJson.scripts["verify:a-adversarial"] === "node scripts/verify-a-adversarial-source-intelligence.mjs" &&
      existsSync(join(root, "scripts", "verify-a-adversarial-source-intelligence.mjs")) &&
      verifyAAdversarialSource.includes("AIBI-skills") &&
      verifyAAdversarialSource.includes("source-intelligence-experience.md") &&
      verifyAAdversarialSource.includes("ADV-CN-012-二手车") &&
      verifyAAdversarialSource.includes("ADV-CN-011-教培课包") &&
      verifyAAdversarialSource.includes("ADV-CN-013-跨境仓配") &&
      verifyAAdversarialSource.includes("ADV-LONG-021-私域会员储值履约") &&
      verifyAAdversarialSource.includes("ADV-ERP-072-旺店通订单明细利润物流差异") &&
      verifyAAdversarialSource.includes("ADV-ERP-072-聚水潭订单出库售后对账") &&
      verifyAAdversarialSource.includes("ADV-ERP-072-金蝶销售出库应收勾稽") &&
      verifyAAdversarialSource.includes("ADV-ERP-072-采购库存周转供应商履约") &&
      verifyAAdversarialSource.includes("batch-072-cn-erp-adversarial") &&
      verifyAAdversarialSource.includes("erp-adversarial-2026-07-05-b072") &&
      verifyAAdversarialSource.includes("erp-batch-manifest-available") &&
      verifyAAdversarialSource.includes("erp-long-cycle-summary-available") &&
      verifyAAdversarialSource.includes("experience-keeps-workspace-boundary") &&
      verifyAAdversarialSource.includes("adversarial-gap-boundary") &&
      verifyAAdversarialSource.includes("metricSqlExecutableCount < manifest?.metricSqlPlanCount") &&
      verifyAAdversarialSource.includes("output-stays-outside-project-a") &&
      readmeSource.includes("npm run verify") &&
      implementationStatusSource.includes("Source evidence regression harness"),
  },
  {
    label: "frontend-b-widget-acceptance-gallery",
    ok: bWidgetKitOverviewSource.includes('from "../biDashboardWidgetKitModel"') &&
      bWidgetKitModelSource.includes("export const B_WIDGET_ACCEPTANCE_ITEMS") &&
      dashboardCanvasEditorOptionsSource.includes("export const dashboardAcceptanceItems") &&
      dashboardOverviewStripSource.includes('data-testid="dashboard-component-acceptance-strip"') &&
      dashboardOverviewStripSource.includes('data-testid="dashboard-component-acceptance-items"') &&
      dashboardOverviewStripSource.includes("data-testid={`dashboard-component-acceptance-${item.key}`}") &&
      dashboardOverviewStripSource.includes("dashboardComponentAcceptanceDetails") &&
      dashboardOverviewStripSource.includes("expand when needed") &&
      stylesSource.includes(".dashboardComponentAcceptanceStrip.compactAcceptance") &&
      stylesSource.includes(".dashboardComponentAcceptanceDetails summary") &&
      stylesSource.includes(".dashboardComponentAcceptanceDetails:not([open]) .dashboardComponentAcceptanceItems") &&
      bWidgetKitSource.includes("<BiDashboardWidgetKitOverview") &&
      bWidgetKitOverviewSource.includes('data-testid="b-widget-acceptance-gallery"') &&
      bWidgetKitOverviewSource.includes('data-testid="b-widget-acceptance-grid"') &&
      bWidgetKitOverviewSource.includes("data-testid={`b-widget-acceptance-${item.key}`}") &&
      bWidgetKitOverviewSource.includes("data-testid={`b-widget-acceptance-technical-${item.key}`}") &&
      bWidgetKitOverviewSource.includes('data-testid="b-widget-catalog-technical-details"') &&
      ["看总量", "看排行", "看趋势", "查明细", "快速筛选", "跨表分析", "追到原始记录", "维护组件", "调整呈现"].every((label) => bWidgetKitModelSource.includes(label)) &&
      bWidgetKitOverviewSource.includes("用户会做的事都集中可测") &&
      bWidgetKitOverviewSource.includes("查看组件目录和命令证据") &&
      ["metric", "bar", "line", "pie", "table", "text", "slicer", "relationship", "filter", "drilldown", "copy-delete", "style"].every((key) => bWidgetKitModelSource.includes(`key: "${key}"`)) &&
      bWidgetKitOverviewSource.includes("dashboard-widget-gallery") &&
      bWidgetKitOverviewSource.includes("dashboardSelectionConfidence") &&
      stylesSource.includes(".dashboardComponentAcceptanceStrip") &&
      stylesSource.includes(".dashboardComponentAcceptanceItems") &&
      stylesSource.includes(".bWidgetAcceptanceGallery") &&
      stylesSource.includes(".bWidgetAcceptanceGrid") &&
      stylesSource.includes(".bWidgetAcceptanceItem.ready") &&
      stylesSource.includes(".bWidgetAcceptanceTechnical"),
  },
  {
    label: "implementation-status-handoff",
    ok: implementationStatusSource.includes("# AI BI Workbench Implementation Status") &&
      implementationStatusSource.includes("Project boundary: this repository is the product boundary.") &&
      implementationStatusSource.includes("BI CLI bridge") &&
      implementationStatusSource.includes("Source evidence profiling") &&
      implementationStatusSource.includes("Dashboard widget set") &&
      implementationStatusSource.includes("npm run verify") &&
      implementationStatusSource.includes("python tools/bi_cli.py --json status") &&
      implementationStatusSource.includes("Users should start from business actions"),
  },
  {
    label: "frontend-agent-panel-action-draft-lifecycle",
    ok: agentPanelSource.includes("actionDrafts: ActionDraft[]") &&
      agentPanelSource.includes('from "../agentPanelModel"') &&
      agentPanelModelSource.includes("export function actionKindText") &&
      agentPanelModelSource.includes("export function actionTarget") &&
      agentPanelSource.includes("lastActionResult: Record<string, unknown> | null") &&
      agentPanelSource.includes("onRejectAction") &&
      agentPanelSource.includes("<AgentPendingChangesPanel") &&
      agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-queue\"") &&
      agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-queue-item\"") &&
      agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-queue-empty\"") &&
      agentPendingChangesPanelSource.includes("data-testid=\"agent-current-draft-reject\"") &&
      agentPendingChangesPanelSource.includes("data-testid={`agent-draft-reject-${draft.action_key}`}") &&
      agentPendingChangesPanelSource.includes("onConfirmDryRun(draft.action_key)") &&
      agentPendingChangesPanelSource.includes("onConfirmAction(draft.action_key)") &&
      agentPendingChangesPanelSource.includes("onRejectAction(draft.action_key)") &&
      agentPanelSource.includes("currentDraftIsPending") &&
      agentPanelModelSource.includes("dashboard.copy") &&
      agentPanelModelSource.includes("dashboard.rename") &&
      agentPanelModelSource.includes("dashboard.delete") &&
      agentPanelModelSource.includes("dashboard.widget.add") &&
      agentPanelModelSource.includes("dashboard.filter.add") &&
      agentPanelModelSource.includes("index.create") &&
      agentPanelModelSource.includes("relationship.save") &&
      agentPanelModelSource.includes("import.commit") &&
      agentPanelModelSource.includes("formula.save") &&
      agentPanelModelSource.includes("view.save") &&
      agentPanelModelSource.includes("metric.add") &&
      agentPanelModelSource.includes("semantic.set") &&
      agentPanelModelSource.includes("filePath") &&
      agentPanelModelSource.includes("formulaText") &&
      agentPanelModelSource.includes("Add metric") &&
      agentPanelModelSource.includes("Add dashboard widget") &&
      agentPanelModelSource.includes("Add dashboard filter") &&
      agentPanelModelSource.includes("leftTable") &&
      agentPanelModelSource.includes("Create query index") &&
      implementationStatusSource.includes("Agent panel model boundary") &&
      appSource.includes("lastActionResult={lastActionResult}"),
  },
  {
    label: "frontend-agent-dry-run-result-feedback",
    ok: agentPanelModelSource.includes("export function resultActionKey") &&
      agentPanelModelSource.includes("export function actionResultHeadline") &&
      agentPanelModelSource.includes("export function actionResultDetail") &&
      agentPanelSource.includes("const activeActionResult = activeActionKey && resultActionKey(lastActionResult) === activeActionKey ? lastActionResult : null") &&
      agentPendingChangesPanelSource.includes('data-testid="agent-action-result"') &&
      agentPendingChangesPanelSource.includes('data-testid="agent-action-result-headline"') &&
      agentPendingChangesPanelSource.includes('data-testid="agent-action-result-detail"') &&
      agentPanelModelSource.includes("预演完成") &&
      agentPanelModelSource.includes("确认前不会写入") &&
      stylesSource.includes(".agentActionResult") &&
      appSource.includes("lastActionResult={lastActionResult}"),
  },
  {
    label: "frontend-agent-draft-impact-summary",
    ok: agentPanelModelSource.includes("export function actionImpactGroup") &&
      agentPanelSource.includes("const draftImpactItems") &&
      agentPanelSource.includes("const riskyDraftCount") &&
      agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-impact-summary\"") &&
      agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-impact-grid\"") &&
      agentPendingChangesPanelSource.includes("data-testid={`agent-draft-impact-${item.key}`}") &&
      agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-next-review\"") &&
      ["data", "dashboard", "model", "workspace"].every((key) => agentPanelSource.includes(`key: "${key}"`)) &&
      agentPendingChangesPanelSource.includes("Review impact before approval") &&
      stylesSource.includes(".agentDraftImpactSummary") &&
      stylesSource.includes(".agentDraftImpactGrid") &&
      stylesSource.includes(".agentDraftNextReview"),
  },
  {
    label: "frontend-agent-task-packet-business-summary",
    ok: agentPanelSource.includes("<AgentTaskPacket") &&
      agentTaskPacketSource.includes("data-testid=\"agent-task-packet\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-task-packet-target\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-task-packet-risk\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-task-packet-evidence\"") &&
      agentPanelModelSource.includes("export function actionRiskText") &&
      agentPanelModelSource.includes("export function actionEvidenceChips") &&
      agentPanelModelSource.includes("export function dashboardCreateDraft") &&
      agentPanelModelSource.includes("export function draftDashboardLabel") &&
      agentTaskPacketSource.includes("data-testid=\"agent-dashboard-draft-preview\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-dashboard-draft-widget\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-erp-unit-summary\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-erp-gap-list\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-erp-missing-field-chips\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-erp-gap-unlocks\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-erp-category-coverage\"") &&
      agentTaskPacketSource.includes("data-testid=\"agent-erp-source-list\"") &&
      agentTaskPacketSource.includes("collectNeededFieldsFromErpHints(allErpGaps, 8)") &&
      agentTaskPacketSource.includes("buildErpGapUnlocks(allErpGaps, 3)") &&
      agentTaskPacketSource.includes("neededFieldsForErpHint(gap)") &&
      agentPanelModelSource.includes('"erp-unit-library": biText("ERP 单元", "ERP units")') &&
      agentPanelModelSource.includes("previewWidgets") &&
      agentPanelSource.includes("const currentDraft = pendingDrafts.find") &&
      agentPanelSource.includes("?? pendingDrafts[0]") &&
      agentPanelSource.includes("activeDashboardConfidence") &&
      agentPanelSource.includes("activeBoundaryBlocked") &&
      agentContextPlanPanelSource.includes("Change queued") &&
      agentContextPlanPanelSource.includes("current task packet has a change awaiting approval") &&
      agentTaskPacketSource.includes("actionTarget(currentDraft)") &&
      agentPanelModelSource.includes("dashboardSelectionConfidence") &&
      agentPanelModelSource.includes("Model change: affects future analysis only after confirmation.") &&
      agentPendingChangesPanelSource.includes('data-testid="agent-current-draft-next-step"') &&
      agentPendingChangesPanelSource.includes("actionNextStepText(currentDraft)") &&
      byLabel["cli-agent-widget-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-widget-draft"].parsed?.actionDraft?.kind === "dashboard.widget.add" &&
      byLabel["cli-agent-widget-draft"].parsed?.matched?.dashboardSelectionConfidence === "explicit",
  },
  {
    label: "frontend-agent-panel-pending-change-language",
    ok: agentPendingChangesPanelSource.includes("待确认修改") &&
      agentContextPlanPanelSource.includes("有待确认修改") &&
      agentContextPlanPanelSource.includes("Change requires approval") &&
      agentPendingChangesPanelSource.includes('data-testid="agent-action-technical-details"') &&
      agentPanelSource.includes('data-testid="agent-recommended-command-details"') &&
      agentPendingChangesPanelSource.includes('data-testid={`agent-draft-queue-technical-${draft.action_key}`}') &&
      agentPendingChangesPanelSource.includes("查看动作技术详情") &&
      agentPanelSource.includes("查看技术命令") &&
      agentPendingChangesPanelSource.includes("查看证据和编号") &&
      !agentPanelSource.includes("<h3><Bilingual zh=\"动作草案\"") &&
      !agentPanelSource.includes("<h3><Bilingual zh=\"推荐命令\"") &&
      stylesSource.includes(".agentActionTechnical") &&
      stylesSource.includes(".agentRecommendedCommands") &&
      stylesSource.includes(".agentDraftQueueTechnical"),
  },
  {
    label: "frontend-agent-answer-card",
    ok: agentPanelSource.includes("<AgentAnswerCard") &&
      agentAnswerCardSource.includes("data-testid=\"agent-answer-card\"") &&
      agentAnswerCardSource.includes("data-testid=\"agent-answer-rows\"") &&
      agentAnswerCardSource.includes("data-testid=\"agent-clarification-choices\"") &&
      agentAnswerCardSource.includes("data-testid=\"agent-clarification-measure\"") &&
      agentAnswerCardSource.includes("data-testid=\"agent-clarification-dimension\"") &&
      agentAnswerCardSource.includes("candidatePrompt(\"measure\", field)") &&
      agentPanelSource.includes("onAskCandidate={(candidatePrompt)") &&
      typesAgentSource.includes("clarification?:") &&
      biCliSource.includes("\"clarification\": {") &&
      agentAnswerCardSource.includes("answerCard: NonNullable<AgentAskResult") &&
      agentPanelSource.includes("type AnswerEvidenceStep") &&
      agentPanelSource.includes("const answerEvidenceSteps: AnswerEvidenceStep[]") &&
      agentAnswerCardSource.includes("data-testid=\"agent-answer-evidence-route\"") &&
      agentAnswerCardSource.includes("data-testid=\"agent-answer-evidence-steps\"") &&
      agentAnswerCardSource.includes("data-testid={`agent-answer-evidence-route-${item.key}`}") &&
      agentPanelSource.includes('key: "source"') &&
      agentPanelSource.includes('key: "metric"') &&
      agentPanelSource.includes('key: "runtime"') &&
      agentPanelSource.includes('key: "boundary"') &&
      agentAnswerCardSource.includes("先看结论，再追到数据、口径和查询回执") &&
      agentAnswerCardSource.includes("Read the answer first, then trace source, metric, and query receipt") &&
      agentAnswerCardSource.includes('data-testid="agent-answer-runtime-technical"') &&
      agentPanelModelSource.includes("只读查询已完成") &&
      agentAnswerCardSource.includes("查看查询回执技术信息") &&
      agentPanelSource.includes("受控查询") &&
      agentAnswerCardSource.includes("Business answer") &&
      agentAnswerCardSource.includes("evidenceRefText") &&
      agentPanelModelSource.includes("Query receipt") &&
      agentPanelModelSource.includes("Business rule") &&
      stylesSource.includes(".agentAnswerEvidenceRoute") &&
      stylesSource.includes(".agentAnswerEvidenceSteps") &&
      stylesSource.includes(".agentAnswerRuntimeTechnical") &&
      stylesSource.includes(".agentClarificationChoices") &&
      stylesSource.includes(".agentClarificationChipGrid"),
  },
  {
    label: "frontend-agent-can-answer-suggestions",
    ok: agentPanelSource.includes("workbench: WorkbenchPayload") &&
      agentPanelSource.includes("<AgentCanAnswerPanel") &&
      agentCanAnswerPanelSource.includes("data-testid=\"agent-can-answer-panel\"") &&
      agentCanAnswerPanelSource.includes("data-testid=\"agent-can-answer-suggestions\"") &&
      agentCanAnswerPanelSource.includes("data-testid={`agent-can-answer-${item.key}`}") &&
      agentPanelSource.includes("sourceRunPrompt(latestRun)") &&
      agentPanelSource.includes("metricPrompt(topMetric)") &&
      agentPanelSource.includes("viewPrompt(topView)") &&
      agentPanelSource.includes("topRelationship") &&
      agentCanAnswerPanelSource.includes("onAskSuggestion(item.prompt)") &&
      agentCanAnswerPanelSource.includes("Start from evidence, not configuration") &&
      appSource.includes("workbench={workbench}") &&
      byLabel["cli-agent-ask"].parsed?.ok === true,
  },
  {
    label: "frontend-agent-checked-evidence-summary",
    ok: agentPanelSource.includes("type CheckedItem") &&
      agentPanelModelSource.includes("export type CheckedItem") &&
      agentPanelSource.includes("const checkedItems: CheckedItem[]") &&
      agentPanelSource.includes("<AgentEvidenceAuditPanels") &&
      agentEvidenceAuditPanelsSource.includes('data-testid="agent-checked-panel"') &&
      agentEvidenceAuditPanelsSource.includes('data-testid="agent-checked-grid"') &&
      agentEvidenceAuditPanelsSource.includes('data-testid={`agent-checked-${item.key}`}') &&
      agentPanelSource.includes('key: "source-intelligence"') &&
      agentPanelSource.includes('key: "metric"') &&
      agentPanelSource.includes('key: "runtime"') &&
      agentPanelSource.includes('key: "dashboard"') &&
      agentPanelSource.includes("queryRuntimeRef") &&
      agentEvidenceAuditPanelsSource.includes("What this response checked") &&
      stylesSource.includes(".agentCheckedPanel") &&
      stylesSource.includes(".agentCheckedGrid"),
  },
  {
    label: "agent-llm-provider-audit",
    ok: byLabel["cli-agent-ask"].parsed?.llm?.audit?.serverSideOnly === true &&
      byLabel["cli-agent-ask"].parsed?.llm?.audit?.secretExposed === false &&
      byLabel["cli-agent-ask"].parsed?.llm?.audit?.contextBoundary === "active-workspace-sourceRun-workbench" &&
      ["provider", "deterministic-fallback"].includes(byLabel["cli-agent-ask"].parsed?.llm?.audit?.mode) &&
      !JSON.stringify(byLabel["cli-agent-ask"].parsed?.llm ?? {}).includes("DEEPSEEK_API_KEY=") &&
      biCliSource.includes('"secretExposed": False') &&
      biCliSource.includes('"serverSideOnly": True') &&
      typesAgentSource.includes("audit?: {") &&
      agentPanelSource.includes("<AgentEvidenceAuditPanels") &&
      agentEvidenceAuditPanelsSource.includes('data-testid="agent-llm-audit-panel"') &&
      agentEvidenceAuditPanelsSource.includes('data-testid="agent-llm-audit-technical"') &&
      agentEvidenceAuditPanelsSource.includes('data-testid="agent-llm-audit-grid"') &&
      agentEvidenceAuditPanelsSource.includes('data-testid={`agent-llm-audit-${item.key}`}') &&
      agentPanelSource.includes("llmAuditItems") &&
      agentPanelSource.includes("secretExposed") &&
      agentEvidenceAuditPanelsSource.includes("当前由本地规则和工作区证据生成回答") &&
      agentEvidenceAuditPanelsSource.includes("View model runtime detail") &&
      agentEvidenceAuditPanelsSource.includes("The DeepSeek key is used only server-side") &&
      stylesSource.includes(".agentLlmAuditPanel") &&
      stylesSource.includes(".agentLlmAuditTechnical") &&
      stylesSource.includes(".agentLlmAuditGrid"),
  },
  {
    label: "frontend-agent-target-boundary-confidence",
    ok: agentContextPlanPanelSource.includes("data-testid=\"agent-target-boundary\"") &&
      agentContextPlanPanelSource.includes("data-testid=\"agent-dashboard-confidence\"") &&
      agentContextPlanPanelSource.includes("confidenceText") &&
      agentPanelSource.includes("blockedDashboardWrite") &&
      agentContextPlanPanelSource.includes("没有明确命中目标看板") &&
      agentContextPlanPanelSource.includes("No target dashboard was matched") &&
      byLabel["cli-agent-missing-dashboard"].parsed?.matched?.dashboardSelectionConfidence === "missing" &&
      byLabel["cli-agent-missing-dashboard"].parsed?.requiresConfirmation === false &&
      byLabel["cli-agent-missing-dashboard"].parsed?.actionDraft?.actionKey === "read_only_plan" &&
      byLabel["cli-agent-widget-draft"].parsed?.matched?.dashboardSelectionConfidence === "explicit" &&
      byLabel["cli-agent-widget-draft"].parsed?.requiresConfirmation === true,
  },
  {
    label: "agent-context-plan-panel-boundary",
    ok: existsSync(join(root, "src", "components", "AgentContextPlanPanel.tsx")) &&
      agentPanelSource.includes('import { AgentContextPlanPanel } from "./AgentContextPlanPanel"') &&
      agentPanelSource.includes("<AgentContextPlanPanel") &&
      !agentPanelSource.includes('data-testid="agent-target-boundary"') &&
      agentContextPlanPanelSource.includes("type AgentContextPlanPanelProps") &&
      agentContextPlanPanelSource.includes("activeDashboardConfidence: SelectionConfidence | \"draft\"") &&
      agentContextPlanPanelSource.includes("匹配上下文") &&
      agentContextPlanPanelSource.includes("计划") &&
      implementationStatusSource.includes("Agent context plan panel boundary"),
  },
  {
    label: "agent-prompt-composer-component-boundary",
    ok: existsSync(join(root, "src", "components", "AgentPromptComposer.tsx")) &&
      agentPanelSource.includes('import { AgentPromptComposer } from "./AgentPromptComposer"') &&
      agentPanelSource.includes("<AgentPromptComposer") &&
      !agentPanelSource.includes('className="agentComposer"') &&
      !agentPanelSource.includes('aria-label={biText("Agent 提问", "Agent prompt")}') &&
      agentPromptComposerSource.includes("type AgentPromptComposerProps") &&
      agentPromptComposerSource.includes('data-testid="agent-prompt-composer"') &&
      agentPromptComposerSource.includes('aria-label={biText("Agent 提问", "Agent prompt")}') &&
      agentPromptComposerSource.includes("setPromptTouched(true)") &&
      agentPromptComposerSource.includes("isAsking ? biText(\"规划中\", \"Planning\") : biText(\"提问\", \"Ask\")") &&
      implementationStatusSource.includes("Agent prompt composer component boundary"),
  },
  {
    label: "write-ops-default-dry-run",
    ok: byLabel["cli-field-update-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-relationship-save-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-dashboard-op-dry-run"].parsed?.requiresConfirmation === true,
  },
  {
    label: "formula-preview-ast-sql",
    ok: Boolean(
      byLabel["cli-formula-preview"].parsed?.formulaAst &&
      byLabel["cli-formula-preview"].parsed?.compiledSql?.includes("CASE WHEN") &&
      byLabel["cli-formula-preview"].parsed?.dependencies?.includes("net_sales"),
    ),
  },
  {
    label: "b-formula-save-query-delete-workflow",
    ok: byLabel["cli-save-formula-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-save-formula-confirm"].parsed?.savedFormula?.metricType === "formula" &&
      byLabel["cli-query-formula-metric"].parsed?.tableQuery?.runtime?.engine === "sqlite-formula-metric" &&
      byLabel["cli-query-formula-metric"].parsed?.rows?.some((row) => row.channel === "Douyin" && Number(row.formula_value) > 0) &&
      byLabel["cli-list-formulas"].parsed?.metricFormulas?.some((formula) => formula.metricKey === "verify_formula_metric") &&
      byLabel["cli-delete-formula-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-delete-formula-confirm"].parsed?.deletedFormula?.metricKey === "verify_formula_metric",
  },
  {
    label: "b-row-calculated-field-query-workflow",
    ok: byLabel["cli-save-row-formula-confirm"].parsed?.savedFormula?.mode === "row" &&
      byLabel["cli-query-row-formula-detail"].parsed?.tableQuery?.columns?.includes("net_sales_per_unit") &&
      byLabel["cli-query-row-formula-detail"].parsed?.tableQuery?.rows?.[0]?.net_sales_per_unit > 300 &&
      byLabel["cli-query-row-formula-aggregate"].parsed?.tableQuery?.measure === "net_sales_per_unit" &&
      byLabel["cli-query-row-formula-aggregate"].parsed?.tableQuery?.rows?.some((row) => row.channel === "Douyin" && Number(row.avg_net_sales_per_unit) > 0) &&
      byLabel["cli-delete-row-formula-confirm"].parsed?.deletedFormula?.fieldKey === "verify_row_formula",
  },
  {
    label: "b-calculated-field-reference-delete-guard",
    ok: byLabel["cli-save-row-formula-view"].parsed?.savedView?.view_key === "verify_row_formula_view" &&
      byLabel["cli-delete-row-formula-dry-blocked"].parsed?.blockedByReferences === true &&
      byLabel["cli-delete-row-formula-dry-blocked"].parsed?.references?.some((reference) => reference.kind === "saved_view" && reference.key === "verify_row_formula_view") &&
      byLabel["cli-delete-row-formula-confirm-blocked"].status === 1 &&
      byLabel["cli-delete-row-formula-confirm-blocked"].parsed?.ok === false &&
      byLabel["cli-delete-row-formula-confirm-blocked"].parsed?.blockedByReferences === true &&
      byLabel["cli-delete-row-formula-view-confirm"].parsed?.deletedViewKey === "verify_row_formula_view" &&
      byLabel["cli-delete-row-formula-confirm"].parsed?.deletedFormula?.fieldKey === "verify_row_formula",
  },
  {
    label: "agent-dashboard-explicit-missing-safety",
    ok: byLabel["cli-agent-missing-dashboard"].parsed?.matched?.dashboardSelectionConfidence === "missing" &&
      byLabel["cli-agent-missing-dashboard"].parsed?.matched?.dashboard === null &&
      byLabel["cli-agent-missing-dashboard"].parsed?.requiresConfirmation === false,
  },
  {
    label: "agent-answer-card-query-runtime",
    ok: Boolean(
      byLabel["cli-agent-ask"].parsed?.answerCard?.confidence === "query-runtime" &&
      byLabel["cli-agent-ask"].parsed?.answerCard?.query?.sqlIntent === "whitelist aggregate query; no user SQL accepted" &&
      byLabel["cli-agent-ask"].parsed?.answerCard?.rows?.length > 0 &&
      byLabel["cli-agent-ask"].parsed?.answerCard?.evidenceRefs?.some((ref) => ref.type === "sourceRun") &&
      byLabel["cli-agent-ask"].parsed?.answerCard?.evidenceRefs?.some((ref) => ref.type === "queryRuntime") &&
      byLabel["cli-agent-ask"].parsed?.answerCard?.title?.zh &&
      byLabel["cli-agent-ask"].parsed?.answerCard?.title?.en
    ),
  },
  {
    label: "agent-english-generic-dashboard-create-intent",
    ok: byLabel["cli-agent-english-generic-dashboard-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-english-generic-dashboard-draft"].parsed?.actionDraft?.kind === "dashboard.create" &&
      byLabel["cli-agent-english-generic-dashboard-draft"].parsed?.matched?.dashboardSelectionConfidence !== "missing",
  },
  {
    label: "agent-ambiguous-chart-requires-clarification",
    ok: byLabel["cli-agent-ambiguous-chart-clarification"].parsed?.requiresConfirmation === false &&
      byLabel["cli-agent-ambiguous-chart-clarification"].parsed?.actionDraft?.status === "read-only" &&
      byLabel["cli-agent-ambiguous-chart-clarification"].parsed?.answerCard?.kind === "clarification" &&
      byLabel["cli-agent-ambiguous-chart-clarification"].parsed?.matched?.widget?.needsClarification === true &&
      byLabel["cli-agent-ambiguous-chart-clarification"].parsed?.matched?.widgetSelectionConfidence === "missing",
  },
  {
    label: "agent-action-draft-confirm-navigation-cycle",
    ok: Boolean(
      byLabel["cli-agent-dashboard-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-dashboard-draft"].parsed?.actionDraft?.kind === "dashboard.create" &&
      byLabel["cli-agent-action-drafts-before-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-dashboard-draft"].parsed?.actionDraft?.actionKey &&
        draft.status === "draft"
      ) &&
      byLabel["cli-agent-confirm-dashboard-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-dashboard-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-dashboard-dry-run"].parsed?.proposedDashboard?.source === "business-dashboard" &&
      byLabel["cli-agent-confirm-dashboard-dry-run"].parsed?.proposedDashboard?.widgetCount >= 5 &&
      byLabel["cli-agent-confirm-dashboard-dry-run"].parsed?.dashboardDraft?.previewWidgets?.length >= 5 &&
      byLabel["cli-agent-confirm-dashboard"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard"].parsed?.createdDashboardKey &&
      byLabel["cli-agent-confirm-dashboard"].parsed?.savedDashboardModules >= 5 &&
      byLabel["cli-navigation-after-agent-confirm"].parsed?.navigation?.some((module) =>
        module.moduleKey === `dashboard:${byLabel["cli-agent-confirm-dashboard"].parsed?.createdDashboardKey}` &&
        module.type === "dashboard" &&
        module.dashboardKey === byLabel["cli-agent-confirm-dashboard"].parsed?.createdDashboardKey &&
        module.createdBy === "agent"
      ) &&
      !byLabel["cli-agent-action-drafts-after-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-dashboard-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-dashboard-crud-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-dashboard-copy-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-dashboard-copy-draft"].parsed?.actionDraft?.kind === "dashboard.copy" &&
      byLabel["cli-agent-dashboard-copy-draft"].parsed?.matched?.dashboardSelectionConfidence === "explicit" &&
      byLabel["cli-agent-dashboard-copy-draft"].parsed?.matched?.dashboardOperation?.name === "Agent复制验证看板" &&
      byLabel["cli-agent-confirm-dashboard-copy-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-dashboard-copy-dry-run"].parsed?.proposedDashboardOperation?.op === "copy" &&
      byLabel["cli-agent-confirm-dashboard-copy"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-copy"].parsed?.operation === "copy" &&
      byLabel["cli-agent-dashboard-rename-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-dashboard-rename-draft"].parsed?.actionDraft?.kind === "dashboard.rename" &&
      byLabel["cli-agent-dashboard-rename-draft"].parsed?.matched?.dashboardOperation?.name === "Agent重命名验证看板" &&
      byLabel["cli-agent-confirm-dashboard-rename-dry-run"].parsed?.proposedDashboardOperation?.op === "rename" &&
      byLabel["cli-agent-confirm-dashboard-rename"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-rename"].parsed?.operation === "rename" &&
      byLabel["cli-agent-dashboard-delete-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-dashboard-delete-draft"].parsed?.actionDraft?.kind === "dashboard.delete" &&
      byLabel["cli-agent-confirm-dashboard-delete-dry-run"].parsed?.proposedDashboardOperation?.op === "delete" &&
      byLabel["cli-agent-confirm-dashboard-delete"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-delete"].parsed?.operation === "delete" &&
      !byLabel["cli-agent-dashboards-after-crud"].parsed?.dashboards?.some((dashboard) =>
        dashboard.dashboard_key === byLabel["cli-agent-confirm-dashboard-delete"].parsed?.dashboardKey ||
        dashboard.name === "Agent重命名验证看板"
      ) &&
      !byLabel["cli-agent-action-drafts-after-dashboard-crud"].parsed?.actionDrafts?.some((draft) =>
        [
          byLabel["cli-agent-dashboard-copy-draft"].parsed?.actionDraft?.actionKey,
          byLabel["cli-agent-dashboard-rename-draft"].parsed?.actionDraft?.actionKey,
          byLabel["cli-agent-dashboard-delete-draft"].parsed?.actionDraft?.actionKey,
        ].includes(draft.action_key)
      )
    ),
  },
  {
    label: "agent-index-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-index-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-index-draft"].parsed?.actionDraft?.kind === "index.create" &&
      byLabel["cli-agent-index-draft"].parsed?.matched?.indexField === "channel" &&
      byLabel["cli-agent-confirm-index-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-index-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-index-dry-run"].parsed?.proposedExecution?.engine === "duckdb" &&
      byLabel["cli-agent-confirm-index-dry-run"].parsed?.proposedExecution?.field === "channel" &&
      byLabel["cli-agent-confirm-index"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-index"].parsed?.createdIndex?.field === "channel" &&
      byLabel["cli-agent-confirm-index"].parsed?.syncedRows >= 1 &&
      !byLabel["cli-agent-action-drafts-after-index-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-index-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-relationship-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-relationship-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-relationship-draft"].parsed?.actionDraft?.kind === "relationship.save" &&
      byLabel["cli-agent-relationship-draft"].parsed?.matched?.relationship?.leftField === "order_id" &&
      byLabel["cli-agent-confirm-relationship-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-relationship-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-relationship-dry-run"].parsed?.relationshipPreview?.metrics?.confidence >= 0.8 &&
      byLabel["cli-agent-confirm-relationship"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-relationship"].parsed?.savedRelationship?.left_field === "order_id" &&
      byLabel["cli-agent-confirm-relationship"].parsed?.savedRelationship?.right_field === "order_id" &&
      byLabel["cli-agent-relationships-after-confirm"].parsed?.relationships?.some((relationship) =>
        relationship.relation_key === byLabel["cli-agent-confirm-relationship"].parsed?.savedRelationship?.relation_key
      ) &&
      !byLabel["cli-agent-action-drafts-after-relationship-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-relationship-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-import-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-import-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-import-draft"].parsed?.actionDraft?.kind === "import.commit" &&
      byLabel["cli-agent-import-draft"].parsed?.matched?.importFile?.includes("refunds.csv") &&
      byLabel["cli-agent-confirm-import-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-import-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-import-dry-run"].parsed?.importPreview?.profile?.rowCount === 3 &&
      byLabel["cli-agent-confirm-import"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-import"].parsed?.importResult?.tableKey === "refunds" &&
      byLabel["cli-agent-confirm-import"].parsed?.importResult?.sourceRunId &&
      byLabel["cli-agent-import-jobs-after-confirm"].parsed?.importJobs?.some((job) =>
        job.table_key === "refunds" &&
        job.source_file?.includes("refunds.csv")
      ) &&
      !byLabel["cli-agent-action-drafts-after-import-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-import-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-formula-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-formula-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-formula-draft"].parsed?.actionDraft?.kind === "formula.save" &&
      byLabel["cli-agent-formula-draft"].parsed?.matched?.formula?.name === "客单价" &&
      byLabel["cli-agent-formula-draft"].parsed?.matched?.formula?.formulaText?.includes("COUNT_DISTINCT") &&
      byLabel["cli-agent-confirm-formula-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-formula-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-formula-dry-run"].parsed?.proposedFormula?.dependencies?.includes("net_sales") &&
      byLabel["cli-agent-confirm-formula"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-formula"].parsed?.savedFormula?.metricType === "formula" &&
      byLabel["cli-agent-formulas-after-confirm"].parsed?.metricFormulas?.some((formula) =>
        formula.metricKey === byLabel["cli-agent-formula-draft"].parsed?.matched?.formula?.formulaKey
      ) &&
      byLabel["cli-agent-query-formula-after-confirm"].parsed?.rows?.length > 0 &&
      byLabel["cli-agent-delete-formula-confirm"].parsed?.confirmed === true &&
      !byLabel["cli-agent-action-drafts-after-formula-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-formula-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-view-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-view-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-view-draft"].parsed?.actionDraft?.kind === "view.save" &&
      byLabel["cli-agent-view-draft"].parsed?.matched?.view?.name === "Douyin订单视图" &&
      byLabel["cli-agent-view-draft"].parsed?.matched?.view?.config?.filters?.some((filter) =>
        filter.field === "channel" &&
        filter.operator === "equals" &&
        filter.value === "Douyin"
      ) &&
      byLabel["cli-agent-confirm-view-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-view-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-view-dry-run"].parsed?.proposedView?.preview?.rowCount >= 1 &&
      byLabel["cli-agent-confirm-view"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-view"].parsed?.savedView?.name === "Douyin订单视图" &&
      byLabel["cli-agent-views-after-confirm"].parsed?.savedViews?.some((view) =>
        view.view_key === byLabel["cli-agent-confirm-view"].parsed?.savedView?.view_key &&
        view.filterCount === 1
      ) &&
      byLabel["cli-agent-navigation-after-view-confirm"].parsed?.navigation?.some((module) =>
        module.moduleKey === `view:${byLabel["cli-agent-confirm-view"].parsed?.savedView?.view_key}` &&
        module.type === "view" &&
        module.tableKey === "orders"
      ) &&
      byLabel["cli-agent-query-view-after-confirm"].parsed?.tableQuery?.rows?.length >= 1 &&
      byLabel["cli-agent-query-view-after-confirm"].parsed?.tableQuery?.rows?.every((row) => row.channel === "Douyin") &&
      !byLabel["cli-agent-action-drafts-after-view-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-view-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-metric-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-metric-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-metric-draft"].parsed?.actionDraft?.kind === "metric.add" &&
      byLabel["cli-agent-metric-draft"].parsed?.matched?.metric?.measure === "net_sales" &&
      byLabel["cli-agent-metric-draft"].parsed?.matched?.metric?.aggregation === "sum" &&
      byLabel["cli-agent-metric-draft"].parsed?.matched?.metric?.dimension === "channel" &&
      byLabel["cli-agent-confirm-metric-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-metric-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-metric-dry-run"].parsed?.proposedMetric?.measure === "net_sales" &&
      byLabel["cli-agent-confirm-metric-dry-run"].parsed?.proposedMetric?.dimension === "channel" &&
      byLabel["cli-agent-confirm-metric"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-metric"].parsed?.savedMetric?.source === "manual" &&
      byLabel["cli-agent-metrics-after-confirm"].parsed?.metrics?.some((metric) =>
        metric.metricKey === byLabel["cli-agent-confirm-metric"].parsed?.savedMetric?.metricKey &&
        metric.measure === "net_sales" &&
        metric.dimension === "channel"
      ) &&
      !byLabel["cli-agent-action-drafts-after-metric-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-metric-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-dashboard-widget-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-widget-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-widget-draft"].parsed?.actionDraft?.kind === "dashboard.widget.add" &&
      byLabel["cli-agent-widget-draft"].parsed?.matched?.dashboardSelectionConfidence === "explicit" &&
      byLabel["cli-agent-widget-draft"].parsed?.matched?.widget?.widgetType === "metric" &&
      byLabel["cli-agent-widget-draft"].parsed?.matched?.widget?.proposedWidget?.config?.measure === "net_sales" &&
      byLabel["cli-agent-confirm-widget-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-widget-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-widget-dry-run"].parsed?.proposedWidget?.widget_type === "metric" &&
      byLabel["cli-agent-confirm-widget-dry-run"].parsed?.proposedWidget?.config?.measure === "net_sales" &&
      byLabel["cli-agent-confirm-widget"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-widget"].parsed?.addedWidget?.widget_type === "metric" &&
      byLabel["cli-agent-dashboard-after-widget-confirm"].parsed?.dashboards?.some((dashboard) =>
        dashboard.dashboard_key === "default" &&
        dashboard.widgets?.some((widget) =>
          widget.widget_key === byLabel["cli-agent-confirm-widget"].parsed?.addedWidget?.widget_key &&
          widget.config?.measure === "net_sales"
        )
      ) &&
      !byLabel["cli-agent-action-drafts-after-widget-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-widget-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-view-bridge-widget-action-draft",
    ok: Boolean(
      byLabel["cli-agent-view-bridge-widget-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-view-bridge-widget-draft"].parsed?.actionDraft?.kind === "dashboard.widget.add" &&
      byLabel["cli-agent-view-bridge-widget-draft"].parsed?.matched?.dashboardSelectionConfidence === "fallback" &&
      byLabel["cli-agent-view-bridge-widget-draft"].parsed?.matched?.widget?.proposedWidget?.widget_type
    ),
  },
  {
    label: "agent-dashboard-filter-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-dashboard-filter-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-dashboard-filter-draft"].parsed?.actionDraft?.kind === "dashboard.filter.add" &&
      byLabel["cli-agent-dashboard-filter-draft"].parsed?.matched?.dashboardSelectionConfidence === "explicit" &&
      byLabel["cli-agent-dashboard-filter-draft"].parsed?.matched?.dashboardFilter?.field === "channel" &&
      byLabel["cli-agent-dashboard-filter-draft"].parsed?.matched?.dashboardFilter?.operator === "equals" &&
      byLabel["cli-agent-dashboard-filter-draft"].parsed?.matched?.dashboardFilter?.value === "Douyin" &&
      byLabel["cli-agent-confirm-dashboard-filter-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-dashboard-filter-dry-run"].parsed?.decision === "confirm" &&
      byLabel["cli-agent-confirm-dashboard-filter-dry-run"].parsed?.proposedFilter?.field === "channel" &&
      byLabel["cli-agent-confirm-dashboard-filter-dry-run"].parsed?.proposedFilter?.value === "Douyin" &&
      byLabel["cli-agent-confirm-dashboard-filter"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-dashboard-filter"].parsed?.filter?.field === "channel" &&
      byLabel["cli-agent-dashboard-filters-after-confirm"].parsed?.filters?.some((filter) =>
        filter.id === byLabel["cli-agent-confirm-dashboard-filter"].parsed?.filter?.id &&
        filter.field === "channel" &&
        filter.operator === "equals" &&
        filter.value === "Douyin"
      ) &&
      !byLabel["cli-agent-action-drafts-after-dashboard-filter-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-dashboard-filter-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-semantic-action-draft-confirm-cycle",
    ok: Boolean(
      byLabel["cli-agent-semantic-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-semantic-draft"].parsed?.actionDraft?.kind === "semantic.set" &&
      byLabel["cli-agent-semantic-draft"].parsed?.matched?.semantic?.field === "channel" &&
      byLabel["cli-agent-semantic-draft"].parsed?.matched?.semantic?.role === "dimension" &&
      byLabel["cli-agent-confirm-semantic-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-confirm-semantic-dry-run"].parsed?.current?.field === "channel" &&
      byLabel["cli-agent-confirm-semantic-dry-run"].parsed?.proposedSemantic?.source === "manual" &&
      byLabel["cli-agent-confirm-semantic"].parsed?.confirmed === true &&
      byLabel["cli-agent-confirm-semantic"].parsed?.semantic?.primaryUsage === "groupable" &&
      byLabel["cli-agent-semantics-after-confirm"].parsed?.semantics?.some((semantic) =>
        semantic.field === "channel" &&
        semantic.role === "dimension" &&
        semantic.source === "manual"
      ) &&
      !byLabel["cli-agent-action-drafts-after-semantic-confirm"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-semantic-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
  {
    label: "agent-action-draft-reject-cycle",
    ok: Boolean(
      byLabel["cli-agent-dashboard-reject-draft"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-reject-dashboard-dry-run"].parsed?.requiresConfirmation === true &&
      byLabel["cli-agent-reject-dashboard-dry-run"].parsed?.decision === "reject" &&
      byLabel["cli-agent-reject-dashboard"].parsed?.confirmed === true &&
      byLabel["cli-agent-reject-dashboard"].parsed?.decision === "reject" &&
      !byLabel["cli-agent-action-drafts-after-reject"].parsed?.actionDrafts?.some((draft) =>
        draft.action_key === byLabel["cli-agent-dashboard-reject-draft"].parsed?.actionDraft?.actionKey
      )
    ),
  },
);

finishVerify({
  checks,
  fullOutput,
  generatedBy: "scripts/verify.mjs",
  verifyReceiptPath,
});
