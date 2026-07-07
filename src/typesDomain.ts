export interface SourcePipelineStageContract {
  id: string;
  label: string;
  producedBy: string;
  timingKey: string;
  inputEvidence: string[];
  outputEvidence: string[];
  domainPackUsage: string[];
}

export interface SourcePipelineContract {
  version: 1;
  status?: "ready" | string;
  generatedBy?: string;
  domainPackRuntime?: DomainPackRuntime;
  stages: SourcePipelineStageContract[];
  guardrails?: string[];
}

export interface DomainSemanticHint {
  semantic: string;
  label: string;
  role: string;
  objectTypeId: string;
  aliases: string[];
  requiredFor: string[];
  evidenceFiles: string[];
}

export interface DomainLinkHint {
  id: string;
  label: string;
  canonicalKey: string;
  fromObjectTypeId: string;
  toObjectTypeId: string;
  strength: string;
  caveats: string[];
  evidenceFiles: string[];
}

export interface DomainFunctionHint {
  id: string;
  label: string;
  sourceAnalysisId: string;
  status: string;
  inputObjectTypeIds: string[];
  requiredSemanticFieldIds: string[];
  resultEvidenceFiles: string[];
  decisionPolicy: string;
}

export interface DomainActionHint {
  id: string;
  label: string;
  actionTypeId: string;
  targetObjectTypeIds: string[];
  confirmationPolicy: string;
  sideEffectBoundary: string;
  evidenceFiles: string[];
}

export interface DomainPackRuntime {
  version: 1;
  generatedBy?: string;
  domainPackId: string;
  ontologyDomain?: string;
  label: string;
  summary?: Record<string, unknown>;
  semanticHints: DomainSemanticHint[];
  linkKeyHints: DomainLinkHint[];
  functionHints: DomainFunctionHint[];
  actionGateHints: DomainActionHint[];
  evidenceContracts?: Array<Record<string, unknown>>;
  executionPolicy: string[];
}
