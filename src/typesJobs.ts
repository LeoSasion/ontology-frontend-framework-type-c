export type AnalysisJobStatus =
  | "created"
  | "queued"
  | "running"
  | "cancel_requested"
  | "canceled"
  | "succeeded"
  | "failed"
  | string;

export interface AnalysisJobEvent {
  schema: "aibi-analysis-job-event/v1" | string;
  sequence: number;
  workspaceId: string;
  jobKey: string;
  type: string;
  status: AnalysisJobStatus;
  progress: number;
  stage: string;
  message: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

export interface AnalysisJob {
  schema: "aibi-analysis-job/v1" | string;
  jobKey: string;
  workspaceId: string;
  parentJobKey: string | null;
  kind: string;
  capabilityId: string;
  label: string;
  status: AnalysisJobStatus;
  progress: number;
  stage: string;
  cancelRequested: boolean;
  inputFingerprint: string;
  input: Record<string, unknown>;
  result: unknown;
  error: Record<string, unknown> | null;
  artifactRefs: Array<Record<string, unknown>>;
  evidenceRefs: Array<Record<string, unknown>>;
  queryReceiptKey: string | null;
  analysisRunKey: string | null;
  sourceRunId: string | null;
  createdAt: string;
  queuedAt: string | null;
  startedAt: string | null;
  updatedAt: string;
  finishedAt: string | null;
  events?: AnalysisJobEvent[];
}

export interface AnalysisJobsPayload {
  ok: boolean;
  jobs?: AnalysisJob[];
  job?: AnalysisJob;
  events?: AnalysisJobEvent[];
  count?: number;
  activeCount?: number;
  lastEventSequence?: number;
}
