import { previewRelationship, saveRelationship } from "./apiRelationship";
import { refreshStatusAndWorkbench } from "./appRefreshModel";
import type { RelationshipSaveOptions } from "./dashboardCanvasContracts";
import { latestRelationshipResult } from "./relationshipRequestGuard";

export async function previewWorkspaceRelationship(workspaceId: string, options: RelationshipSaveOptions) {
  const result = await latestRelationshipResult(previewRelationship({ ...options, workspaceId }));
  return result?.workspaceId === workspaceId ? result : undefined;
}

export async function saveWorkspaceRelationship(
  workspaceId: string,
  options: RelationshipSaveOptions,
  refresh: boolean,
) {
  const outcome = await latestRelationshipResult((async () => {
    const result = await saveRelationship({ ...options, workspaceId });
    return { result, surface: refresh ? await refreshStatusAndWorkbench() : null };
  })());
  if (!outcome || outcome.result.workspaceId !== workspaceId) return undefined;
  if (outcome.surface && outcome.surface.status.workspace.id !== workspaceId) return undefined;
  return outcome;
}
