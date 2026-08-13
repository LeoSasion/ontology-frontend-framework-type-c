export type DecisionFrameworkType = "swot" | "process";
export type DecisionClaimKind = "evidence_fact" | "user_judgment" | "hypothesis";
export type DecisionFrameworkStatus = "draft" | "published" | "stale" | "integrity_failed" | "deprecated" | string;

export interface DecisionEvidenceRef {
  type: "queryPlanReceipt" | string;
  receiptKey?: string;
  unitKey?: string;
  resultFingerprint?: string;
}

export interface DecisionClaim {
  claimKey: string;
  category: string;
  text: string;
  claimKind: DecisionClaimKind;
  evidenceRefs: DecisionEvidenceRef[];
  author: "local-user" | "system-evidence-candidate" | string;
  status: "candidate" | "supported" | "user_asserted" | "needs_validation" | "stale" | string;
  verificationRequirement: string;
  contentFingerprint: string;
  numberUnloaded?: boolean;
  staleLabel?: string;
}

export interface DecisionFrameworkSection {
  key: string;
  label: { zh: string; en: string };
  claimKeys: string[];
}

export interface DecisionFrameworkPublicationSummary {
  publicationKey: string;
  status: string;
  contentFingerprint?: string;
  inputFingerprint?: string;
  ledgerHeadHash?: string;
  canSupportCurrentDecision: boolean;
  drift?: { status: string; reasonCodes: string[]; reasons: Array<Record<string, unknown>> };
}

export interface DecisionFramework {
  schema: "aibi-decision-framework/v1" | string;
  frameworkKey: string;
  workspaceId: string;
  unitKey: string;
  queryReceiptKey: string;
  memoryKey: string;
  type: DecisionFrameworkType;
  title: string;
  status: DecisionFrameworkStatus;
  storedStatus: "draft" | "published" | string;
  structure: { schema: string; type: DecisionFrameworkType; sections: DecisionFrameworkSection[] };
  claims: DecisionClaim[];
  evidenceCandidates: DecisionClaim[];
  evidenceBinding: Record<string, unknown>;
  evidenceFingerprint: string;
  contentFingerprint: string;
  revision: number;
  publicationKey?: string | null;
  publication?: DecisionFrameworkPublicationSummary | null;
  freshness: {
    status: "current" | "stale" | string;
    current: boolean;
    blockers: string[];
    evidenceFactsUnloaded: boolean;
  };
  claimCounts: { evidenceFact: number; userJudgment: number; hypothesis: number };
  canEdit: boolean;
  canPublish: boolean;
  createdAt: string;
  updatedAt: string;
  publishedAt?: string | null;
}

export type DecisionFrameworkSummary = Pick<
  DecisionFramework,
  | "schema"
  | "frameworkKey"
  | "workspaceId"
  | "unitKey"
  | "queryReceiptKey"
  | "memoryKey"
  | "type"
  | "title"
  | "status"
  | "storedStatus"
  | "contentFingerprint"
  | "revision"
  | "publicationKey"
  | "publication"
  | "freshness"
  | "claimCounts"
  | "canEdit"
  | "canPublish"
  | "createdAt"
  | "updatedAt"
  | "publishedAt"
>;

export interface DecisionFrameworkPublicationPlan {
  schema: "aibi-decision-framework-publication-plan/v1" | string;
  workspaceId: string;
  frameworkKey: string;
  frameworkContentFingerprint: string;
  reviewedPublicationPlan: Record<string, unknown>;
  requiresConfirmation: true;
  planFingerprint: string;
}

export interface DecisionFrameworkPayload {
  ok: boolean;
  error?: string;
  code?: string;
  decisionFramework?: DecisionFramework;
  decisionFrameworks?: DecisionFrameworkSummary[];
  decisionFrameworkPlan?: DecisionFrameworkPublicationPlan;
  decisionFrameworkExport?: Record<string, unknown>;
  confirmed?: boolean;
  requiresConfirmation?: boolean;
  changed?: boolean;
}
