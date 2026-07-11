import assert from "node:assert/strict";
import { emptyDashboardPayload, emptyWorkspaceStatus, emptyWorkbenchPayload } from "../src/emptyWorkspaceData";
import { preferredLandingSection } from "../src/appWorkspaceModel";
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
assert.equal(preferredLandingSection(statusWith({ tables: 1 }), workbenchWith(), dashboardsWith()), "sources");
assert.equal(preferredLandingSection(statusWith({ tables: 1 }), workbenchWith(1), dashboardsWith()), "dashboards");
assert.equal(preferredLandingSection(statusWith({ tables: 1, dashboards: 1 }), workbenchWith(1), dashboardsWith(1)), "dashboards");
assert.equal(preferredLandingSection(statusWith({ tables: 1, actionDrafts: 1 }), workbenchWith(1), dashboardsWith(1), 1), "agent");

console.log(JSON.stringify({
  ok: true,
  checks: [
    "empty workspace opens Home",
    "unprofiled data opens Sources",
    "profiled data without a chart opens Dashboards",
    "existing chart stays on Dashboards",
    "pending writes open Agent",
  ],
}));
