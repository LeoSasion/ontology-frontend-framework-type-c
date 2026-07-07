import { fetchJson } from "./apiClient";
import { emptyDashboardPayload, emptyWorkspaceStatus, emptyWorkbenchPayload } from "./emptyWorkspaceData";
import type { DashboardPayload, WorkbenchPayload, WorkspaceStatus } from "./types";

type WorkspaceEnvelope = {
  ok: boolean;
  workspaces?: WorkspaceStatus["workspaces"];
  status?: WorkspaceStatus;
};

export function getWorkspaceStatus() {
  return fetchJson<WorkspaceStatus | WorkspaceEnvelope>("/api/workspaces", emptyWorkspaceStatus).then((payload) => {
    if ("status" in payload && typeof payload.status === "object") {
      return {
        ...(payload.status as WorkspaceStatus),
        workspaces: Array.isArray(payload.workspaces) ? payload.workspaces : (payload.status as WorkspaceStatus).workspaces,
      };
    }
    return payload as WorkspaceStatus;
  });
}

export function createWorkspace(name: string, confirm = false) {
  return fetchJson<Record<string, unknown>>("/api/workspaces", { ok: false }, {
    method: "POST",
    body: JSON.stringify({ op: "create", name, confirm }),
  });
}

export function selectWorkspace(workspaceId: string, confirm = true) {
  return fetchJson<Record<string, unknown>>("/api/workspaces", { ok: false }, {
    method: "POST",
    body: JSON.stringify({ op: "select", workspaceId, confirm }),
  });
}

export function deleteWorkspace(workspaceId: string, confirm = false) {
  return fetchJson<Record<string, unknown>>("/api/workspaces", { ok: false }, {
    method: "POST",
    body: JSON.stringify({ op: "delete", workspaceId, confirm }),
  });
}

export function renameWorkspace(workspaceId: string, name: string, confirm = false) {
  return fetchJson<Record<string, unknown>>("/api/workspaces", { ok: false }, {
    method: "POST",
    body: JSON.stringify({ op: "rename", workspaceId, name, confirm }),
  });
}

export function getDashboards() {
  return fetchJson<DashboardPayload>("/api/dashboards", emptyDashboardPayload);
}

export function getWorkbenchData() {
  return fetchJson<WorkbenchPayload>("/api/workbench?limit=12", emptyWorkbenchPayload);
}
