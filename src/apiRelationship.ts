import { fetchJson } from "./apiClient";
import type { RelationshipSaveOptions } from "./dashboardCanvasContracts";
import { emptyRelationshipPreview } from "./emptyWorkspaceData";
import type { RelationshipPreviewPayload } from "./types";

type WorkspaceRelationshipOptions = RelationshipSaveOptions & { workspaceId: string };

export function previewRelationship(options: WorkspaceRelationshipOptions) {
  return fetchJson<RelationshipPreviewPayload>("/api/relationships/preview", emptyRelationshipPreview, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function saveRelationship(options: WorkspaceRelationshipOptions) {
  return fetchJson<RelationshipPreviewPayload>("/api/relationships/save", emptyRelationshipPreview, {
    method: "POST",
    body: JSON.stringify(options),
  });
}
