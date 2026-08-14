import type { AnalysisRun, QueryPlanReceipt } from "./typesAgent";

export type ContextTerm = {
  term_key: string;
  canonical_name: string;
  aliases: string[];
  definition: string;
  scope_type: string;
  scope_ref: string;
  status: string;
  evidenceRefs: string[];
};

export type ContextRule = {
  rule_key: string;
  title: string;
  statement: string;
  rule_type: string;
  appliesTo: string[];
  status: string;
  evidenceRefs: string[];
};

export type ContextPackPayload = {
  ok: boolean;
  contextPack: {
    schema: string;
    workspaceId: string;
    version: string;
    schemaFingerprint: string;
    counts: { terms: number; confirmedTerms: number; rules: number; confirmedRules: number };
    terms: ContextTerm[];
    rules: ContextRule[];
  };
};

export type ConfirmedQuery = {
  query_key: string;
  question: string;
  status: string;
  query_receipt_key: string;
  source_table_key?: string;
  confirmed_at?: string | null;
  stale_reason?: string;
};

export type ConfirmedQueriesPayload = { ok: boolean; confirmedQueries: ConfirmedQuery[]; count: number; staleCount: number };
export type ConfirmedPlanMemory = {
  schema: string;
  memoryKey: string;
  queryKey: string;
  queryReceiptKey: string;
  question: string;
  status: "confirmed" | "stale" | "deprecated" | string;
  signature: { tables?: string[]; fields?: string[]; measure?: string; groups?: string[]; aggregation?: string };
  planFingerprint: string;
  bindingFingerprint: string;
  staleReason?: string;
  confirmedAt?: string | null;
};
export type ConfirmedPlansPayload = { ok: boolean; workspaceId: string; confirmedPlans: ConfirmedPlanMemory[]; count: number };
export type RecallCandidate = {
  memoryKey: string;
  queryKey: string;
  question: string;
  matchScore: number;
  matchChannels: Record<string, number>;
  canAuthorizeSelection: false;
  canBypassAmbiguity: false;
};
export type RecallReceipt = {
  schema: string;
  receiptKey: string;
  workspaceId: string;
  requestHash: string;
  status: string;
  policy: { strategy: string; adoption: "candidate-only" | string; canAuthorizeExecution: false };
  candidates: RecallCandidate[];
  returnedCandidates: RecallCandidate[];
  planningBindingFingerprint: string;
  createdAt: string;
};
export type RecallReceiptsPayload = { ok: boolean; workspaceId: string; recallReceipts: RecallReceipt[]; count: number };
export type AnalysisRunsPayload = { ok: boolean; analysisRuns?: AnalysisRun[]; analysisRun?: AnalysisRun; branches?: AnalysisRun[]; count?: number };
export type QueryReceiptsPayload = { ok: boolean; queryReceipts?: QueryPlanReceipt[]; queryReceipt?: QueryPlanReceipt; count?: number };

export type KnowledgeSource = {
  sourceKey: string;
  adapterId: string;
  sourceType: string;
  name: string;
  version: string;
  locatorRef: string;
  contentFingerprint: string;
  status: string;
  snapshot?: { counts?: { terms?: number; rules?: number; fieldSemantics?: number }; rawDocumentStored?: false; rawRowsStored?: false };
  createdAt?: string;
};

export type KnowledgeSourceAdapter = {
  adapterId: string;
  label: string;
  extensions: string[];
  sourceTypes: string[];
  limits: { maxBytes: number; maxEntries: number };
  permissions: { network: false; sql: false; code: false; rawRows: false };
};

export type SemanticPatchProposal = {
  schema: string;
  proposalKey: string;
  workspaceId: string;
  sourceKey: string;
  patchType: "term" | "rule" | "field-semantic";
  operation: "create" | "update";
  targetRef: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown>;
  confidence: number;
  status: "pending" | "accepted" | "rejected" | "stale";
  storedStatus: string;
  freshness: { status: string; usableForReview: boolean; mismatches: string[] };
  review: Record<string, unknown>;
  source: { adapterId: string; sourceType: string; name: string; version: string; locatorRef: string; contentFingerprint: string } | null;
  createdAt: string;
  reviewedAt?: string | null;
};

export type SemanticPatchCollectionPayload = {
  ok: boolean;
  workspaceId: string;
  proposals: SemanticPatchProposal[];
  proposal?: SemanticPatchProposal;
  count: number;
  counts: Record<string, number>;
};

export type SemanticReleasePlan = {
  schema: string;
  workspaceId: string;
  requestKeyFingerprint: string;
  label: string;
  proposalKeys: string[];
  changes: Array<{
    proposalKey: string;
    patchType: string;
    operation: string;
    targetRef: string;
    before: Record<string, unknown> | null;
    after: Record<string, unknown>;
    sourceKey: string;
  }>;
  blockers: string[];
  planFingerprint: string;
  readyToPublish: boolean;
};

export type SemanticRelease = {
  schema: string;
  releaseKey: string;
  workspaceId: string;
  requestKeyFingerprint?: string;
  label: string;
  status: "published" | "rolled_back" | "stale" | string;
  storedStatus: string;
  proposalKeys: string[];
  proposalCount: number;
  planFingerprint: string;
  current: boolean;
  freshness: { status: string; mismatches: string[]; currentFingerprint: string; publishedFingerprint: string };
  createdAt: string;
  publishedAt: string;
  rolledBackAt?: string | null;
};

export type SemanticReleasesPayload = {
  ok: boolean;
  workspaceId: string;
  releases: SemanticRelease[];
  release?: SemanticRelease;
  count: number;
};
