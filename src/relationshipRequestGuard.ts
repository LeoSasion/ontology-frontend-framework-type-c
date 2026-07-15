let relationshipRequestId = 0;

export function invalidateRelationshipRequests() {
  relationshipRequestId++;
}

export async function latestRelationshipResult<T>(request: Promise<T>) {
  const requestId = ++relationshipRequestId;
  const result = await request;
  return relationshipRequestId === requestId ? result : null;
}
