import { readFileSync } from "node:fs";

function source(relativePath) {
  return readFileSync(new URL(`../${relativePath}`, import.meta.url), "utf8");
}

function routeBlock(routeSource, pathname) {
  const marker = `if (url.pathname === "${pathname}"`;
  const start = routeSource.indexOf(marker);
  if (start < 0) return "";
  const next = routeSource.indexOf("\n  if (url.pathname === ", start + marker.length);
  return routeSource.slice(start, next < 0 ? routeSource.length : next);
}

const api = source("src/apiWorkspaceContext.ts");
const types = source("src/typesWorkspaceContext.ts");
const settings = source("src/components/SettingsAgentRuntimeProfilePanel.tsx");
const sourcePanel = source("src/components/SourceWorkbenchBusinessFieldProfilePanel.tsx");
const sourceView = source("src/components/SourceWorkbenchView.tsx");
const sourceAdvancedModules = source("src/sourceWorkbenchAdvancedModules.tsx");
const evidencePanel = source("src/components/EvidenceWorkspaceManifestPanel.tsx");
const evidenceView = source("src/components/EvidenceView.tsx");
const workspaceRoutes = source("server/workspaceRoutes.ts");
const workspaceManifestService = source("tools/workspace_manifest_service.py");

const manifestRoute = routeBlock(workspaceRoutes, "/api/workspace/manifest");
const runtimeCatalogRoute = routeBlock(workspaceRoutes, "/api/runtime/catalog");
const fieldProfilesRoute = routeBlock(workspaceRoutes, "/api/business-field-profiles");
const workspaceContextRoutes = [manifestRoute, runtimeCatalogRoute, fieldProfilesRoute];
const workspaceContextUi = [settings, sourcePanel, evidencePanel].join("\n");

const checks = [
  {
    label: "business-field-profiles-client-is-typed-and-bounded",
    ok: api.includes("export function getBusinessFieldProfiles(table: string, signal?: AbortSignal)")
      && api.includes("fetchJsonStrict<BusinessFieldProfileCollection>")
      && api.includes("/api/business-field-profiles?table=${encodeURIComponent(table)}")
      && types.includes('schema: "aibi-business-field-profile/v1"')
      && types.includes('schema: "aibi-business-field-profile-collection/v1"'),
  },
  {
    label: "runtime-catalog-client-is-typed",
    ok: api.includes("export function getRuntimeCatalog(signal?: AbortSignal)")
      && api.includes("fetchJsonStrict<{ ok: boolean; runtimeCatalog: RuntimeCatalogSummary }>")
      && api.includes('"/api/runtime/catalog"')
      && types.includes('schema: "aibi-runtime-catalog/v1"'),
  },
  {
    label: "workspace-manifest-client-is-typed",
    ok: api.includes("export function getWorkspaceManifest(signal?: AbortSignal)")
      && api.includes("fetchJsonStrict<{ ok: boolean; workspaceManifest: WorkspaceManifestSummary }>")
      && api.includes('"/api/workspace/manifest"')
      && types.includes('schema: "aibi-workspace-manifest/v1"'),
  },
  {
    label: "workspace-context-routes-use-active-workspace-only",
    ok: workspaceContextRoutes.every((block) => block.length > 0)
      && workspaceContextRoutes.every((block) => !/workspaceId|searchParams\.get\(["']workspace["']\)|--workspace/.test(block))
      && !api.includes("workspaceId"),
  },
  {
    label: "source-field-profile-has-stable-testid-and-progressive-rows",
    ok: sourcePanel.includes('data-testid="source-business-field-profile"')
      && sourcePanel.includes('<details className="businessFieldProfileRow"')
      && sourcePanel.includes("profile.semantic.authority === \"manual-confirmed\"")
      && sourcePanel.includes('biText("仅候选", "Candidate")'),
  },
  {
    label: "source-field-profile-loads-only-with-expert-workbench",
    ok: sourceView.indexOf("{showExpertWorkbench ? (") >= 0
      && sourceView.indexOf("<SourceWorkbenchBusinessFieldProfilePanel", sourceView.indexOf("{showExpertWorkbench ? (")) > sourceView.indexOf("{showExpertWorkbench ? (")
      && sourceAdvancedModules.includes('lazy(() => import("./components/SourceWorkbenchBusinessFieldProfilePanel"))')
      && !sourceView.includes('from "../apiWorkspaceContext"'),
  },
  {
    label: "source-field-profile-rejects-late-or-cross-scope-responses",
    ok: sourcePanel.includes("requestRef.current?.controller.abort()")
      && sourcePanel.includes("requestRef.current?.id !== requestId")
      && sourcePanel.includes("result.workspaceId === workspaceId")
      && sourcePanel.includes("result.requestScope.tableKey === tableKey")
      && sourcePanel.includes("profile.fieldRef.tableKey === tableKey")
      && sourcePanel.includes('reason.name === "AbortError"'),
  },
  {
    label: "evidence-manifest-has-stable-testid-and-technical-disclosure",
    ok: evidencePanel.includes('data-testid="evidence-workspace-manifest"')
      && evidencePanel.includes('data-testid="evidence-workspace-manifest-technical"')
      && evidencePanel.includes('<details className="advancedDetails compactAdvanced"'),
  },
  {
    label: "evidence-manifest-loads-only-after-receipts-open",
    ok: evidenceView.includes("const [showWorkspaceManifest, setShowWorkspaceManifest] = useState(false)")
      && evidenceView.includes('data-testid="evidence-receipts-details"')
      && evidenceView.includes("onToggle={(event) => setShowWorkspaceManifest(event.currentTarget.open)}")
      && evidenceView.includes("showWorkspaceManifest ? <Suspense fallback={null}><EvidenceWorkspaceManifestPanel /></Suspense> : null")
      && evidenceView.includes('lazyWithRetry(() => import("./EvidenceWorkspaceManifestPanel"))'),
  },
  {
    label: "settings-runtime-catalog-is-a-summary-with-progressive-boundaries",
    ok: settings.includes('data-testid="settings-runtime-catalog"')
      && settings.includes("getRuntimeCatalog(controller.signal)")
      && settings.includes("requestRef.current?.controller.abort()")
      && [
        "runtimeCatalog.tables.length",
        "runtimeCatalog.metrics.length",
        "runtimeCatalog.relationships.length",
        "runtimeCatalog.analyticalSkills.enabled.length",
        "runtimeCatalog.domainPacks.enabled.length",
        "runtimeCatalog.capabilities.length",
      ].every((token) => settings.includes(token))
      && settings.includes('<details className="runtimeCatalogDetails">'),
  },
  {
    label: "workspace-context-ui-does-not-render-raw-samples",
    ok: !/\b(?:sampleValues|rawSampleValues|rawValues|sampleRows|rawRows)\b/.test(workspaceContextUi)
      && !workspaceContextUi.includes("JSON.stringify")
      && types.includes("rawValuesExposed: false")
      && types.includes("rawSampleValuesExposed: false")
      && types.includes("rawValuesWithheld: true")
      && workspaceManifestService.includes('"rawValuesExposed": False')
      && workspaceManifestService.includes('"rawValuesWithheld": True')
      && workspaceManifestService.includes('"rawSampleValuesExposed": False'),
  },
];

const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-workspace-context-ui-verify/v1",
  generatedBy: "scripts/verify-workspace-context-ui.mjs",
  checks,
  failedChecks,
}, null, 2));

if (failedChecks.length) process.exitCode = 1;
