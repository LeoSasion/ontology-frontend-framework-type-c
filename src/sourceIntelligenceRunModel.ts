import type { AnalysisJob } from "./typesJobs";

export type SourceIntelligenceRunRequest = {
  workspaceId: string;
  inputs: string[];
  label?: string;
  outputDir?: string;
  async?: boolean;
};

export type SourceIntelligenceRunResult = {
  ok: true;
  workspaceId: string;
  runKey: string;
  label: string;
  inputRoots: string[];
  tableKey?: string;
  manifest?: Record<string, unknown>;
  dashboardCandidate?: Record<string, unknown>;
  evidenceBundle?: Record<string, unknown>;
  evidenceFiles?: string[];
  outputDir?: string;
};

export type SourceIntelligenceJobAcceptedResult = {
  ok: true;
  accepted: true;
  job: AnalysisJob;
  execution?: {
    mode?: string;
    ownedProcess?: boolean;
  };
};

export type SourceIntelligenceRunResponse = SourceIntelligenceRunResult | SourceIntelligenceJobAcceptedResult;

export type SourceIntelligenceRunOptions = Omit<SourceIntelligenceRunRequest, "workspaceId"> & {
  stayOnPage?: boolean;
};
