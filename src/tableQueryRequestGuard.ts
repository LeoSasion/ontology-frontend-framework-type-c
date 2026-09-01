export function shouldCommitTableQueryResult(options: {
  requestId: number;
  currentRequestId: number;
  expectedWorkspaceId: string;
  activeWorkspaceId: string;
  aborted: boolean;
}) {
  return !options.aborted
    && options.requestId === options.currentRequestId
    && options.expectedWorkspaceId === options.activeWorkspaceId;
}
