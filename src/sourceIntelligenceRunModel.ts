export type SourceIntelligenceRunRequest = {
  inputs?: string[];
  label?: string;
  outputDir?: string;
};

export type SourceIntelligenceRunOptions = SourceIntelligenceRunRequest & {
  stayOnPage?: boolean;
};
