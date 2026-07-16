export interface SourcePipelineStageContract {
  id: string;
  label: string;
  producedBy: string;
  timingKey: string;
  inputEvidence: string[];
  outputEvidence: string[];
  coreSemanticUsage: string[];
}

export interface SourcePipelineContract {
  version: number;
  status?: "ready" | string;
  generatedBy?: string;
  coreSemanticRuntime?: CoreSemanticRuntime;
  stages: SourcePipelineStageContract[];
  guardrails?: string[];
}

export interface CoreSemanticHint {
  semantic: string;
  label: string;
  role: string;
  objectTypeId: string;
  aliases: string[];
  requiredFor: string[];
  evidenceFiles: string[];
}

export interface CoreLinkHint {
  id: string;
  label: string;
  canonicalKey: string;
  fromObjectTypeId: string;
  toObjectTypeId: string;
  strength: string;
  caveats: string[];
  evidenceFiles: string[];
}

export interface CoreFunctionHint {
  id: string;
  label: string;
  sourceAnalysisId: string;
  status: string;
  inputObjectTypeIds: string[];
  requiredSemanticFieldIds: string[];
  resultEvidenceFiles: string[];
  decisionPolicy: string;
}

export interface CoreActionHint {
  id: string;
  label: string;
  actionTypeId: string;
  targetObjectTypeIds: string[];
  confirmationPolicy: string;
  sideEffectBoundary: string;
  evidenceFiles: string[];
}

export interface CoreSemanticRuntime {
  version: number;
  generatedBy?: string;
  coreSemanticId: string;
  ontologyDomain?: string;
  label: string;
  summary?: Record<string, unknown>;
  semanticHints: CoreSemanticHint[];
  linkKeyHints: CoreLinkHint[];
  functionHints: CoreFunctionHint[];
  actionGateHints: CoreActionHint[];
  evidenceContracts?: Array<Record<string, unknown>>;
  executionPolicy: string[];
}

export interface DomainPackReference {
  packId: string;
  version: string;
  fingerprint: string;
  capabilities: string[];
}

export interface DomainPackManifest extends DomainPackReference {
  schema: "aibi-domain-pack/v1" | string;
  displayName: { zh: string; en: string };
  description: { zh: string; en: string };
  compatible: boolean;
  enabled: boolean;
  configuredVersion?: string | null;
  enabledAt?: string | null;
  updatedAt?: string | null;
  source?: { type: "builtin" | "external" | string; publisher?: string; reference?: string };
  builtIn?: boolean;
  conflicts?: string[];
  uiContributions?: Array<{
    kind: "info-card" | "help-link" | string;
    title: { zh: string; en: string };
    body: { zh: string; en: string };
    href?: string;
  }>;
  contributions?: {
    semanticAliases?: Record<string, string[]>;
    semanticRoles?: Record<string, string[]>;
    sourceIntelligence?: Record<string, unknown>;
    [key: string]: unknown;
  };
}

export interface WorkspaceDomainPackRuntime {
  schema: "aibi-domain-pack-runtime/v1" | string;
  coreApiVersion: number;
  workspaceId: string;
  enabledDomainPacks: DomainPackReference[];
  availableDomainPacks: DomainPackManifest[];
}

export interface AnalyticalSkillReference {
  skillId: string;
  version: string;
  fingerprint: string;
  skillKind?: "analytical" | "analysis" | "understanding" | "business-understanding" | string;
  triggerSignals?: Array<string | Record<string, unknown>>;
  slotRules?: Record<string, Record<string, unknown>> | Array<Record<string, unknown>>;
  semanticGuards?: string[];
  compatibleContracts?: string[];
  taskTypes: string[];
  requiredRoles: string[];
  requiredDomainPacks: string[];
  allowedCapabilities: string[];
}

export interface WorkspaceAnalyticalSkillRuntime {
  schema: "aibi-analytical-skill-runtime/v1" | string;
  workspaceId: string;
  enabledAnalyticalSkills: AnalyticalSkillReference[];
  availableAnalyticalSkills: Array<AnalyticalSkillReference & { enabled: boolean; sourceType: string }>;
  fingerprint: string;
}
