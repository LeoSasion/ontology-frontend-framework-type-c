export type SourceIntelligenceRunRequest = {
  workspaceId: string;
  inputs: string[];
  label?: string;
  outputDir?: string;
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

export type SourceIntelligenceRunOptions = Omit<SourceIntelligenceRunRequest, "workspaceId"> & {
  stayOnPage?: boolean;
};
