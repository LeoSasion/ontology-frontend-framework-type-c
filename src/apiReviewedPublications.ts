import { fetchJsonStrict } from "./apiClient";
import type { ReviewedPublicationPayload } from "./typesReviewedPublication";

function workspaceQuery(workspaceId: string) {
  return new URLSearchParams({ workspaceId });
}

export function getReviewedPublications(workspaceId: string, signal?: AbortSignal) {
  const query = workspaceQuery(workspaceId);
  query.set("limit", "50");
  return fetchJsonStrict<ReviewedPublicationPayload>(`/api/reviewed-publications?${query}`, { signal });
}

export function getReviewedPublication(workspaceId: string, publicationKey: string, signal?: AbortSignal) {
  return fetchJsonStrict<ReviewedPublicationPayload>(
    `/api/reviewed-publications/${encodeURIComponent(publicationKey)}?${workspaceQuery(workspaceId)}`,
    { signal },
  );
}

export function exportReviewedPublication(workspaceId: string, publicationKey: string, signal?: AbortSignal) {
  return fetchJsonStrict<ReviewedPublicationPayload>(
    `/api/reviewed-publications/${encodeURIComponent(publicationKey)}/export?${workspaceQuery(workspaceId)}`,
    { signal },
  );
}

export function deprecateReviewedPublication(input: {
  workspaceId: string;
  publicationKey: string;
  reason: string;
  confirm?: boolean;
  expectedHeadHash?: string;
}, signal?: AbortSignal) {
  return fetchJsonStrict<ReviewedPublicationPayload>(
    `/api/reviewed-publications/${encodeURIComponent(input.publicationKey)}/deprecate`,
    {
      method: "POST",
      body: JSON.stringify({
        workspaceId: input.workspaceId,
        reason: input.reason,
        confirm: input.confirm === true,
        expectedHeadHash: input.expectedHeadHash,
      }),
      signal,
    },
  );
}
