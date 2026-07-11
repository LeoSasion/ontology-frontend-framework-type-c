from __future__ import annotations

B_BI_CLI_CAPABILITY_MAP = [
    {
        "area": "source-management",
        "bCommands": ["list-tables", "inspect-table", "rename-source", "delete-source"],
        "hybridCommands": ["list-tables", "inspect-table", "rename-source", "delete-source", "list-navigation", "navigation-op", "workbench"],
        "integration": "mapped-to-hybrid-table-registry-source-run-and-config-cleanup",
        "status": "active",
    },
    {
        "area": "query-runtime",
        "bCommands": ["query", "query-table"],
        "hybridCommands": ["query", "query-table"],
        "integration": "mapped-to-duckdb-whitelist-and-b-style-table-query",
        "status": "active",
    },
    {
        "area": "saved-views",
        "bCommands": ["list-views", "copy-view", "create-table-view", "update-table-view", "delete-table-view"],
        "hybridCommands": ["list-views", "save-view", "copy-view", "delete-view"],
        "integration": "mapped-to-hybrid-sqlite-saved-views-and-query-table",
        "status": "active",
    },
    {
        "area": "dashboard-pages",
        "bCommands": ["list-dashboards", "add-dashboard", "copy-dashboard", "rename-dashboard", "remove-dashboard", "set-dashboard-source"],
        "hybridCommands": ["dashboards", "dashboard-op"],
        "integration": "mapped-to-hybrid-sqlite-metadata",
        "status": "active",
    },
    {
        "area": "dashboard-widgets",
        "bCommands": ["recommend-widgets", "add-recommended-widgets", "add-widget", "add-relationship-widget", "set-widget", "copy-widget", "remove-widget", "saveDashboardModules", "businessDashboardTemplates"],
        "hybridCommands": ["dashboard-widget-catalog", "recommend-widgets", "add-recommended-widgets", "add-widget", "add-relationship-widget", "set-widget", "copy-widget", "remove-widget", "save-dashboard-modules", "business-dashboard", "dashboard-op", "ask"],
        "integration": "mapped-to-hybrid-sqlite-dashboard-widgets-layout-bulk-module-save-business-dashboard-templates-and-erp-unit-library-with-dry-run-boundary",
        "status": "active",
    },
    {
        "area": "filters",
        "bCommands": ["list-filters", "add-filter", "set-filter", "remove-filter", "remove-stale-filters", "clear-filters"],
        "hybridCommands": ["list-filters", "add-filter", "set-filter", "remove-filter", "remove-stale-filters", "clear-filters", "dashboard-widget-catalog"],
        "integration": "mapped-to-dashboard-layout-global-filters-with-confirmed-writes",
        "status": "active",
    },
    {
        "area": "performance-indexes",
        "bCommands": ["recommend-indexes", "create-index"],
        "hybridCommands": ["recommend-indexes", "create-index", "query", "query-table"],
        "integration": "mapped-to-duckdb-local-index-suggestions-and-confirmed-create-index",
        "status": "active",
    },
    {
        "area": "relationships",
        "bCommands": ["recommend-relationships", "list-relationships", "add-relationship", "remove-relationship", "preview-relationship", "query-relationship"],
        "hybridCommands": ["recommend-relationships", "list-relationships", "relationship-preview", "relationship-save", "remove-relationship", "query-relationship"],
        "integration": "mapped-to-hybrid-relationship-recommend-preview-save-query-and-confirmed-remove",
        "status": "active",
    },
    {
        "area": "import",
        "bCommands": ["set-import-policy", "preview-import", "list-import-jobs", "remove-import-job", "import-file"],
        "hybridCommands": ["set-import-policy", "preview-import", "import-commit", "preview-import-folder", "import-folder", "list-import-jobs", "remove-import-job"],
        "integration": "mapped-to-import-policy-folder-plan-job-log-and-confirmed-commit",
        "status": "active",
    },
    {
        "area": "field-metric-formula",
        "bCommands": ["set-field-config", "infer-semantics", "list-semantics", "set-semantic", "infer-metrics", "list-metrics", "add-metric", "query-metric", "ensure-calculated-fields"],
        "hybridCommands": ["field-update", "infer-semantics", "list-semantics", "set-semantic", "infer-metrics", "list-metrics", "add-metric", "query-metric", "formula-preview", "save-formula", "list-formulas", "delete-formula", "workbench"],
        "integration": "mapped-to-field-semantics-tags-usage-metric-definitions-saved-metric-query-and-formula-dsl",
        "status": "active",
    },
    {
        "area": "connectors-preferences",
        "bCommands": ["list-connectors", "save-connector", "sync-connector", "delete-connector", "preferences", "theme-palettes"],
        "hybridCommands": ["list-connectors", "save-connector", "sync-connector", "remove-connector", "preferences", "theme-palettes", "workbench"],
        "integration": "mapped-to-hybrid-connector-registry-file-sync-preferences-theme-palettes-and-confirmed-delete",
        "status": "active",
    },
    {
        "area": "config-portability",
        "bCommands": ["validate-config", "export-config", "apply-config"],
        "hybridCommands": ["validate-config", "export-config", "apply-config"],
        "integration": "mapped-to-redacted-metadata-config-export-dry-run-apply-and-sqlite-backup",
        "status": "active",
    },
]
