import { fetchJsonStrict } from "./apiClient";
import type { BusinessFieldProfileCollection, RuntimeCatalogSummary, WorkspaceManifestSummary } from "./typesWorkspaceContext";

export function getBusinessFieldProfiles(table: string, signal?: AbortSignal) {
  return fetchJsonStrict<BusinessFieldProfileCollection>(
    `/api/business-field-profiles?table=${encodeURIComponent(table)}`,
    { signal },
  );
}

export function getRuntimeCatalog(signal?: AbortSignal) {
  return fetchJsonStrict<{ ok: boolean; runtimeCatalog: RuntimeCatalogSummary }>("/api/runtime/catalog", { signal });
}

export function getWorkspaceManifest(signal?: AbortSignal) {
  return fetchJsonStrict<{ ok: boolean; workspaceManifest: WorkspaceManifestSummary }>("/api/workspace/manifest", { signal });
}
