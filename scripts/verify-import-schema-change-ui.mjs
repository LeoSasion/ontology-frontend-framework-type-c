import { readFileSync } from "node:fs";

function source(relativePath) {
  return readFileSync(new URL(`../${relativePath}`, import.meta.url), "utf8");
}

const panel = source("src/components/SourceWorkbenchImportPanel.tsx");
const report = source("src/components/ImportSchemaChangeReport.tsx");
const controller = source("src/useSourceWorkbenchImportController.ts");
const api = source("src/apiSource.ts");
const jobApi = source("src/apiImportJobs.ts");
const routes = source("server/sourceRoutes.ts");
const jobRoutes = source("server/importJobRoutes.ts");
const runtime = source("server/durableJobRuntime.ts");
const styles = source("src/components/importSchemaChangeReport.css");
const sourceCoreStyles = source("src/components/sourceWorkbenchCore.css");
const schemaChangeService = source("tools/import_schema_change_service.py");

const checks = [
  {
    label: "preview-mode-reaches-the-cli-instead-of-being-silently-reset",
    ok: api.includes("mode?: string")
      && routes.includes('if (body.mode) args.push("--mode", String(body.mode))')
      && controller.includes("result.commitOptions?.mode || result.mergePolicyPreview.mode")
      && panel.includes('<option value="replace">'),
  },
  {
    label: "schema-change-report-is-lazy-and-only-shown-for-a-required-confirmation",
    ok: panel.includes('lazyWithRetry(() => import("./ImportSchemaChangeReport"))')
      && panel.includes("preview.schemaChange?.confirmationRequired")
      && panel.includes("<Suspense")
      && report.includes('data-testid="import-schema-change-report"'),
  },
  {
    label: "ui-blocks-confirmation-until-the-exact-schema-preview-is-acknowledged",
    ok: panel.includes("schemaChangeConfirmationRequired && !schemaChangeAcknowledged")
      && controller.includes("setSchemaChangeAcknowledged(false)")
      && controller.includes("targetName.trim() === previewCommitOptions.name")
      && controller.includes("[conflictRule, filePath, importMode, targetName, targetTable, uniqueFields]")
      && controller.includes(":schema=${schemaChangeAcknowledged}")
      && controller.includes("confirmSchemaChange: schemaChangeAcknowledged"),
  },
  {
    label: "backend-confirmation-flag-is-forwarded-through-the-owned-runtime",
    ok: jobApi.includes("confirmSchemaChange?: boolean")
      && jobRoutes.includes("confirmSchemaChange: body.confirmSchemaChange === true")
      && runtime.includes('args.push("--confirm-schema-change")'),
  },
  {
    label: "report-exposes-complete-expandable-and-downloadable-impact-without-raw-business-rows",
    ok: report.includes("change.addedFields")
      && report.includes("change.removedFields")
      && report.includes("change.impact.totalDependencies")
      && report.includes("impactGroups")
      && report.includes('data-testid="schema-change-impact-download"')
      && report.includes("aria-expanded={expanded}")
      && report.includes("View all ${items.length} items")
      && schemaChangeService.includes('"truncated": False')
      && schemaChangeService.includes("**impacts")
      && !schemaChangeService.includes("IMPACT_ITEM_LIMIT")
      && !/(sampleValues|businessRows|rawRows|recordRows)/.test(report),
  },
  {
    label: "merge-schema-mismatch-opens-rules-offers-adjacent-recovery-and-cannot-enable-confirm",
    ok: panel.includes('preview.blockers?.includes("merge-schema-mismatch")')
      && panel.includes("preview.readyToCommit === false")
      && panel.includes("字段不同，不能合并")
      && panel.includes("if (mergeSchemaBlocked) setRulesOpen(true)")
      && panel.includes('data-testid="import-switch-replace-and-recheck"')
      && panel.includes('runImportPreviewAction("replace")')
      && controller.includes("preview.readyToCommit !== false"),
  },
  {
    label: "import-failures-render-inline-stage-aware-recovery-without-raw-error-details",
    ok: panel.includes("function buildImportActionError(")
      && panel.includes('testId="import-action-error"')
      && panel.includes('role="alert"')
      && panel.includes("系统会复用同一请求边界")
      && panel.includes("category=${category}")
      && !panel.includes("technical: error instanceof Error ? error.message"),
  },
  {
    label: "completed-preview-has-one-confirmation-summary-and-a-secondary-recheck-action",
    ok: panel.includes('sourceChecked ? "secondaryButton" : "primaryButton"')
      && panel.includes("重新检查来源")
      && panel.split('data-testid="import-confirmation-summary"').length === 2
      && !panel.includes('<div className="policyStrip">'),
  },
  {
    label: "path-entry-gives-concrete-examples-and-workspace-scoped-recent-sources",
    ok: panel.includes("支持 CSV、XLSX、XLSM")
      && panel.includes('data-testid="recent-import-paths"')
      && panel.includes("recentImportPaths.map")
      && controller.includes("aibi-c:recent-import-paths:v1:${workspaceId}")
      && controller.includes("rememberImportPath(filePath)")
      && controller.includes("slice(0, 5)"),
  },
  {
    label: "schema-change-layout-honors-the-720-short-edge-and-touch-target",
    ok: styles.includes("@container viewport-stage (max-width: 720px)")
      && styles.includes("@container viewport-stage (max-height: 720px) and (min-width: 721px)")
      && styles.includes("min-height: 44px")
      && styles.includes("overflow-wrap: anywhere")
      && sourceCoreStyles.includes(".sourceImportPanel .formGrid:not(.oneCol)")
      && sourceCoreStyles.includes('input:not([type="checkbox"])')
      && sourceCoreStyles.includes("min-height: 44px")
      && sourceCoreStyles.includes(".workbenchGrid > .workbenchPanel,")
      && sourceCoreStyles.includes(".sourceSecondaryGrid {\n    grid-template-columns: minmax(0, 1fr);")
      && !/(?:^|[;{]\s*)width:\s*\d{3,}px/m.test(styles),
  },
];

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-import-schema-change-ui-verify/v1",
  generatedBy: "scripts/verify-import-schema-change-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
