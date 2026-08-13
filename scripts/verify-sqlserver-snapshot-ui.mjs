import { readFileSync } from "node:fs";

function source(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

const types = source("src/typesSqlServerSnapshot.ts");
const api = source("src/apiSqlServerSnapshot.ts");
const panel = source("src/components/SqlServerAdapterCapabilityPanel.tsx");
const loader = source("src/components/sqlServerAdapterLoader.ts");
const host = source("src/components/SourceWorkbenchSqlServerCapability.tsx");
const connectorPanel = source("src/components/SourceWorkbenchConnectorPanel.tsx");
const styles = source("src/components/sqlServerAdapterCapabilityPanel.css");
const routes = source("server/sqlServerSnapshotRoutes.ts");

const checks = [
  {
    label: "four-capability-levels-are-typed-and-rendered",
    ok: ["unavailable", "ready_for_test", "ready_for_snapshot", "active"].every((value) => (
      types.includes(`\"${value}\"`) && panel.includes(`${value}:`)
    )),
  },
  {
    label: "client-surface-has-no-secret-or-arbitrary-sql-input",
    ok: !/(credentialRef|password|connectionString|\bsql\b|\bquery\b)/i.test(api)
      && api.includes("expectedPlanFingerprint")
      && api.includes('"x-idempotency-key"'),
  },
  {
    label: "server-authorizes-before-reading-request-body",
    ok: routes.indexOf("if (!await authorized(options, capability))") < routes.indexOf("const body = await readBody(request)")
      && routes.includes("SQLSERVER_CAPABILITY_DENIED"),
  },
  {
    label: "server-rejects-sql-credentials-and-connection-strings",
    ok: routes.includes("rejectForbiddenSurface")
      && routes.includes("SQLSERVER_FORBIDDEN_INPUT_SURFACE")
      && routes.includes("connectionString")
      && routes.includes("credentialRef"),
  },
  {
    label: "snapshot-api-requires-confirmation-plan-and-idempotency",
    ok: routes.includes("body.confirm !== true")
      && routes.includes("expectedPlanFingerprint")
      && routes.includes("--expected-plan")
      && routes.includes("--request-key")
      && routes.includes("--yes"),
  },
  {
    label: "ui-does-not-present-unavailable-adapter-as-actionable",
    ok: panel.includes('const canTest = contract.capability === "ready_for_test"')
      && panel.includes('const canSnapshot = contract.capability === "ready_for_snapshot"')
      && panel.includes("disabled={!canSnapshot || busy !== null}")
      && panel.includes("任意 SQL")
      && panel.includes("fallback are disabled"),
  },
  {
    label: "advanced-panel-is-dynamic-and-responsive",
    ok: loader.includes('return import("./SqlServerAdapterCapabilityPanel")')
      && host.includes("lazy(() =>")
      && host.includes("loadSqlServerAdapterCapabilityPanel().then")
      && host.includes("<Suspense")
      && styles.includes("container-type: inline-size")
      && styles.includes("repeat(auto-fit, minmax(min(100%, 10rem), 1fr))")
      && styles.includes("@container (max-width: 34rem)")
      && !/width:\s*\d{3,}px/.test(styles),
  },
  {
    label: "public-types-do-not-expose-secret-reference-or-path",
    ok: !/(credentialRef|connectionString|password|absolutePath|stagingPath)/.test(types)
      && types.includes("credentialConfigured")
      && types.includes("artifactKey"),
  },
  {
    label: "production-workbench-mount-is-advanced-and-sqlserver-only",
    ok: connectorPanel.includes("showAdvanced && selectedSqlServerConnector")
      && connectorPanel.includes('connector.type === "sqlserver"')
      && connectorPanel.includes("<SourceWorkbenchSqlServerCapability")
      && !connectorPanel.includes("<SqlServerAdapterCapabilityPanel"),
  },
  {
    label: "capability-host-runs-the-reviewed-snapshot-and-durable-activation-flow",
    ok: [
      "probeSqlServerAdapter",
      "testSqlServerConnection",
      "discoverSqlServerCatalog",
      "planSqlServerSnapshot",
      "createSqlServerSnapshot",
      "activateSqlServerSnapshot",
      "fetchImportJob",
      "fetchSqlServerActivationStatus",
    ].every((value) => host.includes(value))
      && host.includes("expectedPlanFingerprint")
      && host.includes("expectedManifestFingerprint")
      && host.includes("confirm: true")
      && host.includes("onSnapshot=")
      && host.includes("onActivate="),
  },
  {
    label: "ui-active-state-requires-authoritative-finalized-journal-status",
    ok: host.includes('activation.capability === "active"')
      && host.includes('capability: "active"')
      && panel.includes('activation?.activation.status === "committed"')
      && panel.includes('activation.activation.phase === "finalized"')
      && panel.includes("<ImportJobStatusCard")
      && panel.includes('data-testid="sqlserver-activation-status"'),
  },
  {
    label: "snapshot-and-activation-actions-stay-confirmed-and-state-gated",
    ok: panel.includes('data-testid="sqlserver-snapshot-button"')
      && panel.includes('disabled={!canSnapshot || busy !== null}')
      && panel.includes('data-testid="sqlserver-activate-button"')
      && panel.includes('disabled={!canActivate || busy !== null}')
      && panel.includes('Boolean(snapshot?.manifestFingerprint)')
      && panel.includes('["failed", "canceled"].includes(job.status)'),
  },
  {
    label: "capability-host-aborts-and-rejects-stale-connector-responses",
    ok: host.includes("new AbortController()")
      && host.includes("requestRef.current?.controller.abort()")
      && host.includes("requestRef.current?.id === request.id")
      && host.includes("connectorKeyRef.current === request.connectorKey")
      && host.includes("}, [connectorKey]);"),
  },
  {
    label: "capability-host-exposes-bounded-errors-and-row-free-results",
    ok: host.includes('role="alert"')
      && host.includes('aria-live="polite"')
      && host.includes("slice(0, 320)")
      && host.includes("no business rows were returned")
      && !/(credentialRef|connectionString|password|absolutePath|stagingPath)/.test(host),
  },
];

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-sqlserver-snapshot-ui-verify/v1",
  generatedBy: "scripts/verify-sqlserver-snapshot-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
