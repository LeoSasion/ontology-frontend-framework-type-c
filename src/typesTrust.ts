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
