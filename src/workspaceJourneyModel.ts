import type { AgentAskResult, SourceIntelligenceRunSummary, WorkbenchPayload, WorkspaceStatus } from "./types";
import type { AnalysisJob } from "./typesJobs";
import { latestUsableSourceIntelligenceRun } from "./workspaceFlowModel";

const ACTIVE_JOB_STATUSES = new Set(["created", "queued", "running", "cancel_requested"]);
const FAILED_JOB_STATUSES = new Set(["failed", "canceled"]);

export type WorkspaceJourneyPhase = "connect" | "understand" | "ask" | "review" | "confirm";
export type WorkspaceJourneyStepState = "complete" | "current" | "upcoming";
export type WorkspaceUnderstandingState = "empty" | "starting" | "running" | "ready" | "stale" | "failed";
export type WorkspaceResultState = "none" | "ready" | "blocked";

export type WorkspaceJourneyModel = {
  phase: WorkspaceJourneyPhase;
  currentStep: number;
  stepStates: WorkspaceJourneyStepState[];
  hasData: boolean;
  hasCurrentEvidence: boolean;
  hasAnswer: boolean;
  resultState: WorkspaceResultState;
  hasPendingDraft: boolean;
  hasDashboard: boolean;
  latestRun?: SourceIntelligenceRunSummary;
  latestUsableRun?: SourceIntelligenceRunSummary;
  activeJob?: AnalysisJob;
  latestJob?: AnalysisJob;
  understanding: {
    state: WorkspaceUnderstandingState;
    progress: number;
    stage: string;
    inputRoots: string[];
  };
};

function newestFirst(left: AnalysisJob, right: AnalysisJob) {
  return Date.parse(right.updatedAt || right.createdAt) - Date.parse(left.updatedAt || left.createdAt);
}

export function sourceIntelligenceInputs(workbench: WorkbenchPayload) {
  const successfulImports = workbench.importJobs
    .filter((job) => job.status === "success" && job.source_file.trim())
    .map((job) => job.source_file.trim());
  const latestRunInputs = (workbench.sourceIntelligenceRuns[0]?.inputRoots ?? []).filter((item) => item.trim());
  const tableSources = workbench.tables.map((table) => table.source_file.trim()).filter(Boolean);
  return Array.from(new Set([...successfulImports, ...latestRunInputs, ...tableSources]));
}

export function buildWorkspaceJourney(options: {
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  agent: AgentAskResult;
  sourceIntelligenceJobs?: AnalysisJob[];
  pendingDraftCount?: number;
}): WorkspaceJourneyModel {
  const { status, workbench, agent } = options;
  const workspaceId = status.workspace.id;
  const runs = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const latestRun = runs[0];
  const latestUsableRun = latestUsableSourceIntelligenceRun(runs);
  const jobs = (options.sourceIntelligenceJobs ?? [])
    .filter((job) => job.workspaceId === workspaceId && job.kind === "source-intelligence")
    .sort(newestFirst);
  const activeJob = jobs.find((job) => ACTIVE_JOB_STATUSES.has(job.status));
  const latestJob = jobs[0];
  const hasData = status.counts.tables > 0 || workbench.tables.length > 0;
  const hasCurrentEvidence = Boolean(latestUsableRun);
  const hasAnswer = agent.workspaceId === workspaceId && Boolean(
    agent.answerCard
    || agent.analysisRun
    || agent.agentTurn?.finishedAt
    || agent.llm.response?.summary,
  );
  const resultState: WorkspaceResultState = !hasAnswer
    ? "none"
    : (
      agent.answerCard?.resultState === "blocked"
      || agent.answerCard?.resultState === "stale"
      || agent.llm.response?.certainty === "needs_clarification"
    )
      ? "blocked"
      : "ready";
  const hasPendingDraft = agent.requiresConfirmation === true
    || (options.pendingDraftCount ?? status.counts.actionDrafts ?? 0) > 0;
  const hasDashboard = status.counts.dashboards > 0;

  let phase: WorkspaceJourneyPhase;
  if (!hasData) phase = "connect";
  else if (!hasCurrentEvidence) phase = "understand";
  else if (hasPendingDraft) phase = "confirm";
  else if (hasAnswer) phase = "review";
  else phase = "ask";

  const currentStep = phase === "connect" ? 0 : phase === "understand" ? 1 : phase === "ask" ? 2 : 3;
  const stepStates = [0, 1, 2, 3].map<WorkspaceJourneyStepState>((index) => (
    index < currentStep ? "complete" : index === currentStep ? "current" : "upcoming"
  ));

  let understandingState: WorkspaceUnderstandingState = "empty";
  if (hasCurrentEvidence) understandingState = "ready";
  else if (activeJob) understandingState = activeJob.status === "created" || activeJob.status === "queued" ? "starting" : "running";
  else if (latestRun?.freshness?.usableForPlanning === false) understandingState = "stale";
  else if (latestJob && FAILED_JOB_STATUSES.has(latestJob.status)) understandingState = "failed";
  else if (hasData) understandingState = "starting";

  return {
    phase,
    currentStep,
    stepStates,
    hasData,
    hasCurrentEvidence,
    hasAnswer,
    resultState,
    hasPendingDraft,
    hasDashboard,
    latestRun,
    latestUsableRun,
    activeJob,
    latestJob,
    understanding: {
      state: understandingState,
      progress: activeJob ? Math.max(0, Math.min(100, activeJob.progress)) : hasCurrentEvidence ? 100 : 0,
      stage: activeJob?.stage ?? "",
      inputRoots: sourceIntelligenceInputs(workbench),
    },
  };
}
