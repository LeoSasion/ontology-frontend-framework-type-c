from __future__ import annotations

BI_CLI_CAPABILITY_MAP = [
    {
        "area": "source-management",
        "compatibilityCommands": ["list-tables", "inspect-table", "rename-source", "delete-source"],
        "commands": ["list-tables", "inspect-table", "rename-source", "delete-source", "list-navigation", "navigation-op", "workbench"],
        "integration": "mapped-to-hybrid-table-registry-source-run-and-config-cleanup",
        "status": "active",
    },
    {
        "area": "query-runtime",
        "compatibilityCommands": ["query", "query-table"],
        "commands": ["query", "query-table"],
        "integration": "mapped-to-duckdb-whitelist-table-query",
        "status": "active",
    },
    {
        "area": "saved-views",
        "compatibilityCommands": ["list-views", "copy-view", "create-table-view", "update-table-view", "delete-table-view"],
        "commands": ["list-views", "save-view", "copy-view", "delete-view"],
        "integration": "mapped-to-hybrid-sqlite-saved-views-and-query-table",
        "status": "active",
    },
    {
        "area": "dashboard-pages",
        "compatibilityCommands": ["list-dashboards", "add-dashboard", "copy-dashboard", "rename-dashboard", "remove-dashboard", "set-dashboard-source"],
        "commands": ["dashboards", "dashboard-op"],
        "integration": "mapped-to-hybrid-sqlite-metadata",
        "status": "active",
    },
    {
        "area": "dashboard-widgets",
        "compatibilityCommands": ["recommend-widgets", "add-recommended-widgets", "add-widget", "add-relationship-widget", "set-widget", "copy-widget", "remove-widget", "saveDashboardModules", "businessDashboardTemplates"],
        "commands": ["dashboard-widget-catalog", "recommend-widgets", "add-recommended-widgets", "add-widget", "add-relationship-widget", "set-widget", "copy-widget", "remove-widget", "save-dashboard-modules", "business-dashboard", "dashboard-op", "ask"],
        "integration": "mapped-to-hybrid-sqlite-dashboard-widgets-layout-bulk-module-save-analysis-templates-and-domain-pack-registry-with-dry-run-boundary",
        "status": "active",
    },
    {
        "area": "filters",
        "compatibilityCommands": ["list-filters", "add-filter", "set-filter", "remove-filter", "remove-stale-filters", "clear-filters"],
        "commands": ["list-filters", "add-filter", "set-filter", "remove-filter", "remove-stale-filters", "clear-filters", "dashboard-widget-catalog"],
        "integration": "mapped-to-dashboard-layout-global-filters-with-confirmed-writes",
        "status": "active",
    },
    {
        "area": "performance-indexes",
        "compatibilityCommands": ["recommend-indexes", "create-index"],
        "commands": ["recommend-indexes", "create-index", "query", "query-table"],
        "integration": "mapped-to-duckdb-local-index-suggestions-and-confirmed-create-index",
        "status": "active",
    },
    {
        "area": "relationships",
        "compatibilityCommands": ["recommend-relationships", "list-relationships", "add-relationship", "remove-relationship", "preview-relationship", "query-relationship"],
        "commands": ["recommend-relationships", "list-relationships", "relationship-preview", "relationship-save", "remove-relationship", "query-relationship"],
        "integration": "mapped-to-hybrid-relationship-recommend-preview-save-query-and-confirmed-remove",
        "status": "active",
    },
    {
        "area": "import",
        "compatibilityCommands": ["set-import-policy", "preview-import", "list-import-jobs", "remove-import-job", "import-file"],
        "commands": ["set-import-policy", "preview-import", "import-commit", "preview-import-folder", "import-folder", "list-import-jobs", "remove-import-job"],
        "integration": "mapped-to-import-policy-folder-plan-job-log-and-confirmed-commit",
        "status": "active",
    },
    {
        "area": "field-metric-formula",
        "compatibilityCommands": ["set-field-config", "infer-semantics", "list-semantics", "set-semantic", "infer-metrics", "list-metrics", "add-metric", "query-metric", "ensure-calculated-fields"],
        "commands": ["field-update", "infer-semantics", "list-semantics", "set-semantic", "infer-metrics", "list-metrics", "add-metric", "query-metric", "formula-preview", "save-formula", "list-formulas", "delete-formula", "workbench"],
        "integration": "mapped-to-field-semantics-tags-usage-metric-definitions-saved-metric-query-and-formula-dsl",
        "status": "active",
    },
    {
        "area": "connectors-preferences",
        "compatibilityCommands": ["list-connectors", "save-connector", "sync-connector", "delete-connector", "preferences", "theme-palettes"],
        "commands": ["list-connectors", "save-connector", "list-connector-adapters", "discover-connector", "preview-connector", "plan-connector-sync", "federation-proof", "sync-connector", "remove-connector", "preferences", "theme-palettes", "workbench"],
        "integration": "mapped-to-read-only-connector-adapters-bounded-preview-controlled-sync-plan-federation-proof-preferences-theme-palettes-and-confirmed-delete",
        "status": "active",
    },
    {
        "area": "config-portability",
        "compatibilityCommands": ["validate-config", "export-config", "apply-config"],
        "commands": ["validate-config", "export-config", "apply-config"],
        "integration": "mapped-to-redacted-metadata-config-export-dry-run-apply-and-sqlite-backup",
        "status": "active",
    },
]

