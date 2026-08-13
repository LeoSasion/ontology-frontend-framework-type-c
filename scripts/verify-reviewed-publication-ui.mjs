import { readFileSync } from "node:fs";

function source(relativePath) {
  return readFileSync(new URL(`../${relativePath}`, import.meta.url), "utf8");
}

const view = source("src/components/EvidenceView.tsx");
const panel = source("src/components/EvidenceReviewedPublicationsPanel.tsx");
const api = source("src/apiReviewedPublications.ts");
const routes = source("server/reviewedPublicationRoutes.ts");
const css = source("src/components/evidenceReviewedPublications.css");

const checks = [
  {
    label: "reviewed-publications-load-only-inside-evidence-advanced-details",
    ok: view.includes('lazyWithRetry(() => import("./EvidenceReviewedPublicationsPanel"))')
      && view.includes("showWorkspaceManifest ? <Suspense")
      && view.includes("<EvidenceReviewedPublicationsPanel workspaceId={workspaceId}"),
  },
  {
    label: "workspace-switch-aborts-and-clears-list-detail-and-mutation-state",
    ok: panel.includes("listRequestRef.current?.abort()")
      && panel.includes("detailRequestRef.current?.abort()")
      && panel.includes("actionRequestRef.current?.abort()")
      && panel.includes("setPublications([])")
      && panel.includes("setSelected(null)")
      && panel.includes("}, [loadList, workspaceId]);"),
  },
  {
    label: "all-four-effective-statuses-and-ledger-drift-blockers-are-visible",
    ok: panel.includes('key: "drifted"')
      && panel.includes('key: "integrity_failed"')
      && panel.includes('key: "deprecated"')
      && panel.includes('key: "current"')
      && panel.includes("selected.ledger.blockers")
      && panel.includes("selected.ledger.evidenceBlockers")
      && panel.includes("selected.drift.reasonCodes")
      && panel.includes("selected.ledgerHeadHash"),
  },
  {
    label: "deprecation-has-one-preview-and-exact-head-confirmation-boundary",
    ok: panel.includes("previewDeprecation")
      && panel.includes("confirmDeprecation")
      && panel.includes("pending.expectedHeadHash")
      && api.includes("expectedHeadHash: input.expectedHeadHash")
      && routes.includes('"--expected-head", expectedHeadHash'),
  },
  {
    label: "confirmed-deprecation-immediately-replaces-selected-and-list-state",
    ok: panel.includes("payload.publication.publicationKey !== pending.publicationKey")
      && panel.includes("setSelected(payload.publication)")
      && panel.includes("item.publicationKey === payload.publication?.publicationKey ? payload.publication : item")
      && panel.indexOf("setSelected(payload.publication)") < panel.indexOf("await loadList(pending.publicationKey"),
  },
  {
    label: "safe-export-has-no-forensic-or-publish-surface",
    ok: panel.includes("exportReviewedPublication")
      && panel.includes("Safe JSON export")
      && !/forensic|publishReviewed|publication-publish|createReviewedPublication/i.test(`${panel}\n${api}`),
  },
  {
    label: "native-controls-and-live-feedback-remain-keyboard-accessible",
    ok: panel.includes("<select")
      && panel.includes("<textarea")
      && panel.includes('type="button"')
      && panel.includes('role="status"')
      && panel.includes('role="alert"'),
  },
  {
    label: "layout-honors-720-short-edge-and-long-ledger-identifiers",
    ok: css.includes("@container viewport-stage (max-width: 720px)")
      && css.includes("@container viewport-stage (max-height: 720px) and (min-width: 721px)")
      && css.includes("content-visibility: auto")
      && css.includes("overflow-wrap: anywhere")
      && css.includes("min-height: 44px")
      && !/(?:^|[;{]\s*)width:\s*\d{3,}px/m.test(css),
  },
  {
    label: "api-is-workspace-and-publication-key-scoped-without-publication-content-input",
    ok: api.includes("encodeURIComponent(publicationKey)")
      && api.includes("workspaceId")
      && !/content:|inputContract|ledgerEntries|businessRows|rawRows/.test(api),
  },
];

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-reviewed-publication-ui-verify/v1",
  generatedBy: "scripts/verify-reviewed-publication-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
