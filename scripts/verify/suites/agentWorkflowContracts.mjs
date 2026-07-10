export function appendAgentWorkflowContractChecks(context) {
  const {
    byLabel,
    checks,
  } = context;
  checks.push(
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
      }
  );
}
