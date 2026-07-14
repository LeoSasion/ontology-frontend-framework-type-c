import { fetchJsonStrict } from "./apiClient";
import type { WorkspaceDomainPackRuntime } from "./types";

export type DomainPackState = "enabled" | "disabled";

export function getDomainPacks(workspaceId?: string) {
  const query = workspaceId ? `?workspace=${encodeURIComponent(workspaceId)}` : "";
  return fetchJsonStrict<WorkspaceDomainPackRuntime & { ok: boolean }>(`/api/domain-packs${query}`);
}

export function setDomainPack(options: {
  packId: string;
  state: DomainPackState;
  workspaceId?: string;
  confirm?: boolean;
}) {
  return fetchJsonStrict<Record<string, unknown>>("/api/domain-packs", {
    method: "POST",
    body: JSON.stringify(options),
  });
}
