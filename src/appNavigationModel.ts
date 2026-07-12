import { isAppSection, type AppSection } from "./appSections";
import type { EvidenceFocus } from "./types";

export type AppNavigationContext = {
  tableKey?: string;
  dashboardKey?: string;
  viewKey?: string;
  sourceRunKey?: string;
  actionKey?: string;
  origin?: AppSection;
};

export type AppNavigationTarget = AppNavigationContext & {
  section: AppSection;
  evidenceFocus?: EvidenceFocus | null;
  allowLocked?: boolean;
};

const contextParams = {
  tableKey: "table",
  dashboardKey: "dashboard",
  viewKey: "view",
  sourceRunKey: "run",
  actionKey: "action",
  origin: "from",
} as const;

function optionalParam(params: URLSearchParams, key: string) {
  return params.get(key)?.trim() || undefined;
}

export function readNavigationTarget(search: string): AppNavigationTarget {
  const params = new URLSearchParams(search);
  const sectionParam = params.get("section");
  const originParam = params.get(contextParams.origin);
  return {
    section: isAppSection(sectionParam) ? sectionParam : "home",
    tableKey: optionalParam(params, contextParams.tableKey),
    dashboardKey: optionalParam(params, contextParams.dashboardKey),
    viewKey: optionalParam(params, contextParams.viewKey),
    sourceRunKey: optionalParam(params, contextParams.sourceRunKey),
    actionKey: optionalParam(params, contextParams.actionKey),
    origin: isAppSection(originParam) ? originParam : undefined,
  };
}

export function navigationContextFromEvidence(focus: EvidenceFocus, origin?: AppSection): AppNavigationContext {
  const sourceRunRef = focus.refs.find((ref) => ref.startsWith("source-intelligence:"));
  return {
    tableKey: focus.tableKey,
    dashboardKey: focus.dashboardKey,
    viewKey: focus.viewKey,
    sourceRunKey: sourceRunRef?.slice("source-intelligence:".length),
    origin,
  };
}

export function navigationContextFromTarget(target: AppNavigationTarget): AppNavigationContext {
  return {
    tableKey: target.tableKey,
    dashboardKey: target.dashboardKey,
    viewKey: target.viewKey,
    sourceRunKey: target.sourceRunKey,
    actionKey: target.actionKey,
    origin: target.origin,
  };
}

export function evidenceFocusFromNavigation(context: AppNavigationContext): EvidenceFocus | null {
  if (!context.tableKey && !context.dashboardKey && !context.viewKey && !context.sourceRunKey) return null;
  const refs = context.sourceRunKey ? [`source-intelligence:${context.sourceRunKey}`] : [];
  return {
    source: "navigation",
    title: "当前业务上下文",
    refs,
    tableKey: context.tableKey,
    dashboardKey: context.dashboardKey,
    viewKey: context.viewKey,
  };
}

export function writeNavigationUrl(currentHref: string, target: AppNavigationTarget) {
  const url = new URL(currentHref);
  url.searchParams.set("section", target.section);
  for (const [key, param] of Object.entries(contextParams) as Array<[keyof AppNavigationContext, string]>) {
    const value = target[key];
    if (typeof value === "string" && value.trim()) url.searchParams.set(param, value);
    else url.searchParams.delete(param);
  }
  return `${url.pathname}?${url.searchParams.toString()}${url.hash}`;
}

export function sameNavigationTarget(left: AppNavigationTarget, right: AppNavigationTarget) {
  return left.section === right.section
    && left.tableKey === right.tableKey
    && left.dashboardKey === right.dashboardKey
    && left.viewKey === right.viewKey
    && left.sourceRunKey === right.sourceRunKey
    && left.actionKey === right.actionKey
    && left.origin === right.origin;
}
