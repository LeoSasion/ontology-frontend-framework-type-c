import { getActionDrafts, getDashboards, getWorkbenchData, getWorkspaceStatus } from "./api";
import { normalizeDashboards, normalizeStatus, normalizeWorkbench } from "./appWorkspaceModel";
import type { ActionDraft, DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";

function actionDraftsFromPayload(payload: { actionDrafts?: unknown }): ActionDraft[] {
  return Array.isArray(payload.actionDrafts) ? payload.actionDrafts as ActionDraft[] : [];
}

function workspaceSurfaceIsConsistent(status: WorkspaceStatus, workbench: WorkbenchPayload) {
  return status.counts.tables === workbench.tables.length &&
    workbench.tables.every((table) => !table.workspace_id || table.workspace_id === status.workspace.id);
}

function waitForSurfaceRetry(delay: number) {
  return new Promise((resolve) => window.setTimeout(resolve, delay));
}

async function readConsistentWorkspaceSurface() {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const status = normalizeStatus(await getWorkspaceStatus());
    const workbench = normalizeWorkbench(await getWorkbenchData());
    if (workspaceSurfaceIsConsistent(status, workbench)) return { status, workbench };
    if (attempt < 2) await waitForSurfaceRetry(120 * (attempt + 1));
  }
  throw new Error("Workspace data is still synchronizing. Retry the refresh without changing the current workspace.");
}

export async function refreshWorkbench(): Promise<WorkbenchPayload> {
  return normalizeWorkbench(await getWorkbenchData());
}

export async function refreshDashboards(): Promise<DashboardPayload> {
  return normalizeDashboards(await getDashboards());
}

export async function refreshStatusAndWorkbench(): Promise<{
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
}> {
  return readConsistentWorkspaceSurface();
}

export async function refreshStatusWorkbenchDashboards(): Promise<{
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  dashboards: DashboardPayload;
}> {
  const [{ status, workbench }, dashboards] = await Promise.all([readConsistentWorkspaceSurface(), getDashboards()]);
  return {
    status,
    workbench,
    dashboards: normalizeDashboards(dashboards),
  };
}

export async function refreshDashboardsAndWorkbench(): Promise<{
  dashboards: DashboardPayload;
  workbench: WorkbenchPayload;
}> {
  const [dashboards, workbench] = await Promise.all([getDashboards(), getWorkbenchData()]);
  return {
    dashboards: normalizeDashboards(dashboards),
    workbench: normalizeWorkbench(workbench),
  };
}

export async function refreshStatusAndDashboards(): Promise<{
  status: WorkspaceStatus;
  dashboards: DashboardPayload;
}> {
  const [status, dashboards] = await Promise.all([getWorkspaceStatus(), getDashboards()]);
  return {
    status: normalizeStatus(status),
    dashboards: normalizeDashboards(dashboards),
  };
}

export async function refreshStatusDashboardsWorkbenchDrafts(): Promise<{
  status: WorkspaceStatus;
  dashboards: DashboardPayload;
  workbench: WorkbenchPayload;
  actionDrafts: ActionDraft[];
}> {
  const [{ status, workbench }, dashboards, drafts] = await Promise.all([
    readConsistentWorkspaceSurface(),
    getDashboards(),
    getActionDrafts(),
  ]);
  return {
    status,
    dashboards: normalizeDashboards(dashboards),
    workbench,
    actionDrafts: actionDraftsFromPayload(drafts),
  };
}

export async function refreshStatusWorkbenchDrafts(): Promise<{
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  actionDrafts: ActionDraft[];
}> {
  const [{ status, workbench }, drafts] = await Promise.all([
    readConsistentWorkspaceSurface(),
    getActionDrafts(),
  ]);
  return {
    status,
    workbench,
    actionDrafts: actionDraftsFromPayload(drafts),
  };
}

export async function refreshStatusAndDrafts(): Promise<{
  status: WorkspaceStatus;
  actionDrafts: ActionDraft[];
}> {
  const [status, drafts] = await Promise.all([getWorkspaceStatus(), getActionDrafts()]);
  return {
    status: normalizeStatus(status),
    actionDrafts: actionDraftsFromPayload(drafts),
  };
}

export async function refreshActionDrafts(): Promise<ActionDraft[]> {
  return actionDraftsFromPayload(await getActionDrafts());
}
