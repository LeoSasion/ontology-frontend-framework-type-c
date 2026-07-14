import { createHash } from "node:crypto";

export type ContextPriority = "critical" | "evidence" | "supporting" | "diagnostic";

export type ContextSegment = {
  id: string;
  priority: ContextPriority;
  required?: boolean;
  content: Record<string, unknown>;
  evidenceRefs?: string[];
};

export type ContextBudgetReceipt = {
  schema: "aibi-context-budget/v1";
  status: "within-budget" | "compacted" | "blocked";
  maxChars: number;
  originalChars: number;
  retainedChars: number;
  originalFingerprint: string;
  retainedFingerprint: string;
  keptIds: string[];
  droppedIds: string[];
  requiredEvidenceRefs: string[];
  missingRequiredEvidenceRefs: string[];
  blockers: string[];
};

const priorityOrder: Record<ContextPriority, number> = {
  critical: 0,
  evidence: 1,
  supporting: 2,
  diagnostic: 3,
};

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

function fingerprint(value: unknown) {
  return createHash("sha256").update(canonical(value), "utf8").digest("hex");
}

export function compactContextSegments(segments: ContextSegment[], requestedMaxChars: number) {
  const maxChars = Math.max(256, Math.floor(requestedMaxChars));
  const normalized = segments.map((segment, index) => ({
    ...segment,
    required: segment.required === true || segment.priority === "critical" || segment.priority === "evidence",
    evidenceRefs: [...new Set(segment.evidenceRefs ?? [])].filter(Boolean).sort(),
    index,
    chars: canonical(segment.content).length,
  }));
  const ordered = [...normalized].sort((left, right) =>
    Number(right.required) - Number(left.required)
      || priorityOrder[left.priority] - priorityOrder[right.priority]
      || left.index - right.index,
  );
  const kept: typeof normalized = [];
  const dropped: typeof normalized = [];
  let retainedChars = 0;
  for (const segment of ordered) {
    if (segment.required || retainedChars + segment.chars <= maxChars) {
      kept.push(segment);
      retainedChars += segment.chars;
    } else {
      dropped.push(segment);
    }
  }
  const requiredEvidenceRefs = [...new Set(normalized.filter((segment) => segment.required).flatMap((segment) => segment.evidenceRefs))].sort();
  const retainedEvidenceRefs = new Set(kept.flatMap((segment) => segment.evidenceRefs));
  const missingRequiredEvidenceRefs = requiredEvidenceRefs.filter((reference) => !retainedEvidenceRefs.has(reference));
  const requiredOverflow = kept.filter((segment) => segment.required).reduce((total, segment) => total + segment.chars, 0) > maxChars;
  const blockers = [
    ...(requiredOverflow ? ["required-context-exceeds-budget"] : []),
    ...(missingRequiredEvidenceRefs.length ? ["required-evidence-reference-dropped"] : []),
  ];
  const clean = (segment: typeof normalized[number]) => ({
    id: segment.id,
    priority: segment.priority,
    content: segment.content,
    evidenceRefs: segment.evidenceRefs,
  });
  const keptSegments = kept.map(clean);
  const receipt: ContextBudgetReceipt = {
    schema: "aibi-context-budget/v1",
    status: blockers.length ? "blocked" : dropped.length ? "compacted" : "within-budget",
    maxChars,
    originalChars: normalized.reduce((total, segment) => total + segment.chars, 0),
    retainedChars,
    originalFingerprint: fingerprint(normalized.map(clean)),
    retainedFingerprint: fingerprint(keptSegments),
    keptIds: kept.map((segment) => segment.id),
    droppedIds: dropped.map((segment) => segment.id),
    requiredEvidenceRefs,
    missingRequiredEvidenceRefs,
    blockers,
  };
  return { receipt, segments: keptSegments };
}

export function configuredAgentContextMaxChars() {
  const value = Number(process.env.AIBI_AGENT_CONTEXT_MAX_CHARS ?? 12_000);
  return Number.isInteger(value) && value >= 256 && value <= 100_000 ? value : 12_000;
}
