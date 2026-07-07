import { getActionDrafts, getDashboards, getWorkbenchData, getWorkspaceStatus } from "./api";
import { normalizeDashboards, normalizeStatus, normalizeWorkbench } from "./appWorkspaceModel";
import type { ActionDraft, DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";

function actionDraftsFromPayload(payload: { actionDrafts?: unknown }): ActionDraft[] {
  return Array.isArray(payload.actionDrafts) ? payload.actionDrafts as ActionDraft[] : [];
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
  const [status, workbench] = await Promise.all([getWorkspaceStatus(), getWorkbenchData()]);
  return {
    status: normalizeStatus(status),
    workbench: normalizeWorkbench(workbench),
  };
}

export async function refreshStatusWorkbenchDashboards(): Promise<{
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  dashboards: DashboardPayload;
}> {
  const [status, workbench, dashboards] = await Promise.all([getWorkspaceStatus(), getWorkbenchData(), getDashboards()]);
  return {
    status: normalizeStatus(status),
    workbench: normalizeWorkbench(workbench),
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
  const [status, dashboards, workbench, drafts] = await Promise.all([
    getWorkspaceStatus(),
    getDashboards(),
    getWorkbenchData(),
    getActionDrafts(),
  ]);
  return {
    status: normalizeStatus(status),
    dashboards: normalizeDashboards(dashboards),
    workbench: normalizeWorkbench(workbench),
    actionDrafts: actionDraftsFromPayload(drafts),
  };
}

export async function refreshStatusWorkbenchDrafts(): Promise<{
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  actionDrafts: ActionDraft[];
}> {
  const [status, workbench, drafts] = await Promise.all([
    getWorkspaceStatus(),
    getWorkbenchData(),
    getActionDrafts(),
  ]);
  return {
    status: normalizeStatus(status),
    workbench: normalizeWorkbench(workbench),
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
