export type ReviewedPublicationStatus = "current" | "stale" | "deprecated" | "integrity_failed";

export interface EvidenceLedgerVerification {
  schema: "aibi-evidence-ledger-verification/v1" | string;
  workspaceId: string;
  publicationKey: string;
  ok: boolean;
  blockers: string[];
  currentEvidence: boolean;
  evidenceBlockers: string[];
  entryCount: number;
  genesisHash?: string;
  headHash: string;
}

export interface ReviewedPublicationDriftReason {
  code: string;
  expected?: unknown;
  current?: unknown;
}

export interface ReviewedPublication {
  schema: "aibi-reviewed-publication/v1" | string;
  publicationKey: string;
  workspaceId: string;
  memoryKey: string;
  queryReceiptKey: string;
  unitKey: string;
  title: string;
  status: ReviewedPublicationStatus;
  storedStatus: ReviewedPublicationStatus;
  content: Record<string, unknown>;
  contentFingerprint: string;
  inputContract: Record<string, unknown>;
  inputFingerprint: string;
  ledgerHeadHash: string;
  createdAt: string;
  updatedAt: string;
  reviewedAt?: string | null;
  deprecatedAt?: string | null;
  deprecationReason?: string | null;
  ledger: EvidenceLedgerVerification;
  drift: {
    status: "current" | "drifted";
    reasons: ReviewedPublicationDriftReason[];
    reasonCodes: string[];
  };
  canSupportCurrentDecision: boolean;
  readOnly: true;
}

export interface ReviewedPublicationExport {
  schema: "aibi-reviewed-publication-export/v1" | string;
  workspaceId: string;
  publication: ReviewedPublication;
  ledgerEntries: Array<Record<string, unknown>>;
  currentDecisionBasis: boolean;
  forensic: false;
}

export interface ReviewedPublicationPayload {
  ok: boolean;
  workspaceId: string;
  reviewedPublications?: ReviewedPublication[];
  reviewedPublication?: ReviewedPublication;
  reviewedPublicationExport?: ReviewedPublicationExport;
  publication?: ReviewedPublication;
  count?: number;
  dryRun?: boolean;
  requiresConfirmation?: boolean;
  confirmed?: boolean;
  deprecated?: boolean;
  publicationKey?: string;
  expectedHeadHash?: string;
  currentStatus?: ReviewedPublicationStatus;
  canDeprecate?: boolean;
  code?: string;
  error?: string;
}
