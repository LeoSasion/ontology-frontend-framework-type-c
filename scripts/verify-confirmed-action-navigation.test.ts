import assert from "node:assert/strict";
import test from "node:test";
import { confirmedActionNavigationTarget } from "../src/agentActionNavigationModel";
import type { ActionDraft } from "../src/types";

function draft(kind: string, payload: Record<string, unknown> = {}): ActionDraft {
  return {
    action_key: `draft-${kind}`,
    kind,
    label: kind,
    status: "draft",
    payload,
    evidence: [],
    created_at: "2026-07-15T00:00:00Z",
  };
}

test("confirmed Agent actions return to their owning product surface", () => {
  assert.deepEqual(
    confirmedActionNavigationTarget("dashboard-action", { confirmed: true }, draft("dashboard.widget.add", { dashboardKey: "board-1", tableKey: "orders" })),
    { section: "dashboards", actionKey: "dashboard-action", dashboardKey: "board-1", viewKey: undefined, tableKey: "orders" },
  );
  assert.equal(confirmedActionNavigationTarget("import-action", { confirmed: true }, draft("import.commit", { tableKey: "refunds" })).section, "sources");
  assert.equal(confirmedActionNavigationTarget("relationship-action", { confirmed: true }, draft("relationship.save", { leftTable: "orders" })).section, "sources");
  assert.equal(confirmedActionNavigationTarget("formula-action", { confirmed: true }, draft("formula.save", { tableKey: "orders" })).section, "sources");
  assert.deepEqual(
    confirmedActionNavigationTarget("view-action", { confirmed: true, savedView: { viewKey: "view-1", tableKey: "orders" } }, draft("view.save")),
    { section: "views", actionKey: "view-action", dashboardKey: undefined, viewKey: "view-1", tableKey: "orders" },
  );
});

test("confirmation receipts can route without a draft and unknown actions stay in Agent", () => {
  assert.equal(confirmedActionNavigationTarget("receipt-dashboard", { createdDashboardKey: "board-2" }).section, "dashboards");
  assert.equal(confirmedActionNavigationTarget("receipt-source", { targetSection: "sources" }).section, "sources");
  assert.equal(confirmedActionNavigationTarget("unknown", { confirmed: true }, draft("analysis.plan")).section, "agent");
});

test("deleted dashboards do not leave navigation focused on a removed key", () => {
  assert.deepEqual(
    confirmedActionNavigationTarget("delete-dashboard", { confirmed: true, operation: "delete", dashboardKey: "removed" }, draft("dashboard.delete", { dashboardKey: "removed" })),
    { section: "dashboards", actionKey: "delete-dashboard", dashboardKey: undefined, viewKey: undefined, tableKey: undefined },
  );
});
