import { readFileSync } from "node:fs";

const read = (path) => readFileSync(path, "utf8");
const panel = read("src/components/SettingsWorkspaceRecoveryPanel.tsx");
const api = read("src/apiWorkspaceRecovery.ts");
const types = read("src/typesWorkspaceRecovery.ts");
const css = read("src/components/workspaceRecoveryPanel.css");
const loader = read("src/components/workspaceRecoveryLoader.ts");

const checks = [
  {
    label: "workspace-recovery-chunk-has-a-dedicated-dynamic-loader",
    ok: loader.includes('import("./SettingsWorkspaceRecoveryPanel")')
      && !loader.includes("SettingsWorkspaceRecoveryPanel from"),
  },
  {
    label: "panel-guards-workspace-and-request-order",
    ok: panel.includes("workspaceRef.current !== expectedWorkspace")
      && panel.includes("requestRef.current?.controller.abort()")
      && panel.includes("payload.workspaceId !== expectedWorkspace"),
  },
  {
    label: "all-mutations-preview-before-exact-confirmation",
    ok: ['preview("create")', 'preview("restore"', 'preview("delete"'].every((needle) => panel.includes(needle))
      && panel.includes("expectedPlanFingerprint: pending.plan.planFingerprint")
      && panel.includes('data-testid="workspace-recovery-confirmation"'),
  },
  {
    label: "restore-invalidates-only-returned-resource-keys",
    ok: panel.includes("onInvalidated?.(payload.invalidationKeys ?? pending.plan.invalidationKeys)")
      && !panel.includes("window.location.reload")
      && !panel.includes("location.reload"),
  },
  {
    label: "typed-api-has-no-read-fallback-and-carries-idempotency-key",
    ok: api.includes("fetchJsonStrict")
      && api.includes('"x-idempotency-key": input.requestKey')
      && api.includes("/api/workspace-recovery/${input.operation}")
      && types.includes('"aibi-workspace-recovery-point/v1"'),
  },
  {
    label: "restore-impact-is-compared-before-operator-confirmation",
    ok: panel.includes("compareWorkspaceRecoveryPoint")
      && panel.includes('data-testid="workspace-recovery-comparison"')
      && panel.includes("exposesBusinessRows !== false")
      && panel.includes("current?.recoveryPointKey === payload.recoveryPlan!.recoveryPointKey")
      && panel.includes("comparison.recoveryPointKey")
      && api.includes("compareWorkspaceRecoveryPoint")
      && types.includes('"aibi-workspace-recovery-comparison/v1"'),
  },
  {
    label: "advanced-list-is-bounded-and-content-virtualized",
    ok: panel.includes("points.slice(0, 1)")
      && panel.includes("limit: 50")
      && css.includes("content-visibility: auto")
      && css.includes("repeat(auto-fit")
      && !/(?:^|[;{]\s*)width:\s*\d+px/m.test(css),
  },
  {
    label: "public-ui-does-not-render-paths-or-business-rows",
    ok: panel.includes("响应不展示本地绝对路径、源文件或业务行")
      && !/\.path\b|absolutePath|sourceFile|businessRows/.test(panel),
  },
];

const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-workspace-recovery-ui-verify/v1",
  generatedBy: "scripts/verify-workspace-recovery-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
