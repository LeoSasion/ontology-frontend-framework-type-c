import assert from "node:assert/strict";
import { emptyDashboardPayload, emptyWorkspaceStatus, emptyWorkbenchPayload } from "../src/emptyWorkspaceData";
import { preferredLandingSection } from "../src/appWorkspaceModel";
import { mergeNavigationContext, navigationContextForSection } from "../src/appNavigationModel";
import type { DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "../src/types";

function statusWith(counts: Partial<WorkspaceStatus["counts"]>): WorkspaceStatus {
  return {
    ...emptyWorkspaceStatus,
    counts: { ...emptyWorkspaceStatus.counts, ...counts },
  };
}

function workbenchWith(sourceProfileCount = 0): WorkbenchPayload {
  return {
    ...emptyWorkbenchPayload,
    sourceIntelligenceRuns: Array.from({ length: sourceProfileCount }, (_, index) => ({ run_key: `profile-${index}` } as WorkbenchPayload["sourceIntelligenceRuns"][number])),
  };
}

function dashboardsWith(count = 0): DashboardPayload {
  return {
    ...emptyDashboardPayload,
    dashboards: Array.from({ length: count }, (_, index) => ({ dashboard_key: `dashboard-${index}` } as DashboardPayload["dashboards"][number])),
  };
}

assert.equal(preferredLandingSection(statusWith({}), workbenchWith(), dashboardsWith()), "home");
assert.equal(preferredLandingSection(statusWith({ tables: 1 }), workbenchWith(), dashboardsWith()), "home");
assert.equal(preferredLandingSection(statusWith({ tables: 1 }), workbenchWith(1), dashboardsWith()), "home");
assert.equal(preferredLandingSection(statusWith({ tables: 1, dashboards: 1 }), workbenchWith(1), dashboardsWith(1)), "home");
assert.equal(preferredLandingSection(statusWith({ tables: 1, actionDrafts: 1 }), workbenchWith(1), dashboardsWith(1), 1), "agent");
assert.deepEqual(navigationContextForSection("home", { tableKey: "orders", dashboardKey: "sales" }), {});
assert.deepEqual(navigationContextForSection("sources", { tableKey: "orders", dashboardKey: "sales", viewKey: "detail", sourceRunKey: "run-1" }), { tableKey: "orders", sourceRunKey: "run-1" });
assert.deepEqual(navigationContextForSection("dashboards", { tableKey: "orders", dashboardKey: "sales", viewKey: "detail" }), { tableKey: "orders", dashboardKey: "sales" });
assert.deepEqual(mergeNavigationContext({ tableKey: "orders" }, { dashboardKey: "sales" }), { tableKey: "orders", dashboardKey: "sales", viewKey: undefined, sourceRunKey: undefined, actionKey: undefined, origin: undefined });

console.log(JSON.stringify({
  ok: true,
  checks: [
    "empty workspace opens Home",
    "stable workspaces open the single Workspace landing",
    "pending writes open Agent",
    "navigation context is scoped to the owning page",
  ],
}));
