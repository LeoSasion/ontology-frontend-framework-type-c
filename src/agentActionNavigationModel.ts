import type { AppSection } from "./appSections";
import type { AppNavigationTarget } from "./appNavigationModel";
import { objectRecord, stringValue } from "./safeValue";
import type { ActionDraft } from "./types";

const SOURCE_ACTION_PREFIXES = [
  "connector.",
  "field.",
  "formula.",
  "import.",
  "index.",
  "metric.",
  "relationship.",
  "semantic.",
  "source.",
  "table.",
];

function firstString(...values: unknown[]) {
  for (const value of values) {
    const resolved = stringValue(value).trim();
    if (resolved) return resolved;
  }
  return undefined;
}

function sectionFromTarget(value: unknown): AppSection | undefined {
  const normalized = stringValue(value).trim().toLowerCase();
  if (!normalized) return undefined;
  if (normalized === "dashboard" || normalized === "dashboards" || normalized === "widget") return "dashboards";
  if (normalized === "view" || normalized === "views" || normalized === "detail" || normalized === "details") return "views";
  if (["source", "sources", "data", "table", "relationship", "formula", "import", "metric", "semantic", "index", "connector"].includes(normalized)) return "sources";
  if (normalized === "agent") return "agent";
  return undefined;
}

function sectionFromReceipt(result: Record<string, unknown>): AppSection | undefined {
  const target = objectRecord(result.target);
  const explicitTarget = sectionFromTarget(result.targetSection)
    ?? sectionFromTarget(target?.section)
    ?? sectionFromTarget(target?.type)
    ?? sectionFromTarget(result.target);
  if (explicitTarget) return explicitTarget;

  if (
    ["createdDashboardKey", "savedDashboardKey", "dashboardKey", "addedWidget", "filter", "filters"]
      .some((key) => Object.hasOwn(result, key))
  ) return "dashboards";
  if (["createdViewKey", "savedViewKey", "viewKey", "savedView"].some((key) => Object.hasOwn(result, key))) return "views";
  if (
    ["optimizedDataset", "importResult", "relationshipPreview", "savedFormula", "savedMetric", "savedRelationship", "semantic"]
      .some((key) => Object.hasOwn(result, key))
  ) return "sources";
  return undefined;
}

function sectionFromDraftKind(kind: string | undefined): AppSection | undefined {
  const normalized = kind?.trim().toLowerCase();
  if (!normalized) return undefined;
  if (normalized.startsWith("dashboard.")) return "dashboards";
  if (normalized.startsWith("view.")) return "views";
  if (SOURCE_ACTION_PREFIXES.some((prefix) => normalized.startsWith(prefix))) return "sources";
  return undefined;
}

export function confirmedActionNavigationTarget(
  actionKey: string,
  result: Record<string, unknown>,
  draft?: ActionDraft,
): AppNavigationTarget {
  const section = sectionFromReceipt(result) ?? sectionFromDraftKind(draft?.kind) ?? "agent";
  const payload = draft?.payload ?? {};
  const savedView = objectRecord(result.savedView);
  const addedWidget = objectRecord(result.addedWidget);
  const importResult = objectRecord(result.importResult);
  const sourceResult = objectRecord(result.savedRelationship)
    ?? objectRecord(result.savedFormula)
    ?? objectRecord(result.savedMetric)
    ?? objectRecord(result.semantic)
    ?? objectRecord(result.optimizedDataset);
  const isDeletedDashboard = result.operation === "delete" || draft?.kind === "dashboard.delete";
  const dashboardKey = isDeletedDashboard ? undefined : firstString(
    result.createdDashboardKey,
    result.savedDashboardKey,
    result.dashboardKey,
    addedWidget?.dashboardKey,
    addedWidget?.dashboard_key,
    payload.dashboardKey,
  );
  const viewKey = firstString(
    result.createdViewKey,
    result.savedViewKey,
    result.viewKey,
    savedView?.viewKey,
    savedView?.view_key,
    payload.viewKey,
    payload.view_key,
  );
  const tableKey = firstString(
    result.tableKey,
    result.table_key,
    importResult?.tableKey,
    importResult?.table_key,
    savedView?.tableKey,
    savedView?.table_key,
    sourceResult?.tableKey,
    sourceResult?.table_key,
    payload.tableKey,
    payload.table_key,
    payload.leftTable,
  );
  return { section, actionKey, dashboardKey, viewKey, tableKey };
}
