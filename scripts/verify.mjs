import { existsSync } from "node:fs";
import { join } from "node:path";
import { writeCostMonitorFixtures } from "./verify/fixtures.mjs";
import { createVerifyRuntime, finishVerify, hasCssRule } from "./verify/runtime.mjs";
import { readProjectJsonIfExists, readVerifySourceCatalog } from "./verify/sourceCatalog.mjs";
import { appendCoreContractChecks } from "./verify/suites/coreContracts.mjs";
import { appendSourceContractChecks } from "./verify/suites/sourceContracts.mjs";
import { appendDashboardViewContractChecks } from "./verify/suites/dashboardViewContracts.mjs";
import { appendAppArchitectureContractChecks } from "./verify/suites/appArchitectureContracts.mjs";
import { appendProductUxContractChecks } from "./verify/suites/productUxContracts.mjs";
import { appendAgentWorkflowContractChecks } from "./verify/suites/agentWorkflowContracts.mjs";

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
const sourceCatalog = readVerifySourceCatalog(root);
const {
  stylesSource: globalStylesSource,
  dashboardDeferredStylesSource,
  sourceWorkbenchAdvancedStylesSource,
  viewWorkspaceStylesSource,
  settingsPanelStylesSource,
  agentEvidenceStylesSource,
} = sourceCatalog;
const stylesSource = `${globalStylesSource}\n${dashboardDeferredStylesSource}\n${sourceWorkbenchAdvancedStylesSource}\n${viewWorkspaceStylesSource}\n${settingsPanelStylesSource}\n${agentEvidenceStylesSource}`;
const sourceCoverageRuns = byLabel["cli-source-intelligence-runs-after-validation-input"].parsed?.sourceIntelligenceRuns ?? [];
const sourceCoverageAllRuns = byLabel["cli-source-intelligence-runs-after-validation-input-all"].parsed?.sourceIntelligenceRuns ?? [];
const contractCheckContext = {
  ...sourceCatalog,
  globalStylesSource,
  bCostMonitorComparison,
  byLabel,
  checks,
  existsSync,
  hasCssRule,
  join,
  readOnlyAgentCheck,
  retiredSeedEnvName,
  root,
  run,
  sourceCoverageAllRuns,
  sourceCoverageRuns,
  stylesSource,
};
appendCoreContractChecks(contractCheckContext);
appendSourceContractChecks(contractCheckContext);
appendDashboardViewContractChecks(contractCheckContext);
appendAppArchitectureContractChecks(contractCheckContext);
appendProductUxContractChecks(contractCheckContext);
appendAgentWorkflowContractChecks(contractCheckContext);

finishVerify({
  checks,
  fullOutput,
  generatedBy: "scripts/verify.mjs",
  verifyReceiptPath,
});
