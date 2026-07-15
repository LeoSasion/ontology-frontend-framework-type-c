import type { AgentEvidencePlan as AgentEvidencePlanContract } from "../typesAgent";
import { biText } from "./Bilingual";


function statusText(status: string) {
  if (status === "completed") return biText("完成", "Completed");
  if (status === "blocked") return biText("已阻断", "Blocked");
  if (status === "waiting-confirmation") return biText("等待确认", "Awaiting approval");
  if (status === "failed") return biText("失败", "Failed");
  return biText("已规划", "Planned");
}


const blockerSummaryKeys = ["kind", "mention", "reason", "code", "message", "status"] as const;

function canonicalBlockerText(value: unknown, seen: Set<object>, depth = 0): string {
  if (value == null) return value === null ? "null" : "";
  if (["string", "number", "boolean", "bigint"].includes(typeof value)) return String(value).trim();
  if (typeof value === "symbol" || typeof value === "function") return String(value);
  if (depth >= 4) return "[nested]";
  if (typeof value !== "object") return "unreadable-blocker";
  if (seen.has(value)) return "[circular]";
  seen.add(value);
  try {
    if (Array.isArray(value)) {
      return `[${value.map((item) => canonicalBlockerText(item, seen, depth + 1)).join(", ")}]`;
    }
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record).sort().map((key) => `${key}: ${canonicalBlockerText(record[key], seen, depth + 1)}`).join(", ")}}`;
  } catch {
    return "unreadable-blocker";
  } finally {
    seen.delete(value);
  }
}

export function evidencePlanBlockerText(value: unknown): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    const summary = blockerSummaryKeys
      .map((key) => record[key])
      .filter((item): item is string | number | boolean => typeof item === "string" || typeof item === "number" || typeof item === "boolean")
      .map((item) => String(item).trim())
      .filter(Boolean);
    if (summary.length) return [...new Set(summary)].join(" · ");
  }
  return canonicalBlockerText(value, new Set()).trim();
}

export function evidencePlanBlockers(value: unknown): string[] {
  const values = Array.isArray(value) ? value : value == null ? [] : [value];
  return [...new Set(values.map(evidencePlanBlockerText).filter(Boolean))];
}


export function AgentEvidencePlan({ plan }: { plan: AgentEvidencePlanContract }) {
  const completed = plan.steps.filter((step) => step.status === "completed").length;
  const blocked = plan.steps.filter((step) => step.status === "blocked" || step.status === "failed").length;
  return (
    <details className={`agentEvidencePlan ${blocked ? "blocked" : "ready"}`} data-testid="agent-evidence-plan" open={blocked > 0}>
      <summary>
        <span>{biText("证据计划", "Evidence plan")}</span>
        <strong>{completed}/{plan.steps.length} · {statusText(plan.status)}</strong>
      </summary>
      {plan.skillRefs?.length ? (
        <div className="agentEvidencePlanSkills">
          <small>{biText("分析 Skill", "Analytical Skill")}</small>
          {plan.skillRefs.map((skill) => <span key={`${skill.skillId}@${skill.version}`}>{skill.skillId} · v{skill.version}</span>)}
        </div>
      ) : null}
      <ol>
        {plan.steps.map((step) => {
          const blockerLabels = evidencePlanBlockers(step.blockers);
          const relationshipRefs = step.evidenceRefs.filter((reference) => reference.type === "relationshipPathProof");
          return (
            <li className={step.status} key={step.stepKey}>
              <span>{step.kind}</span>
              <strong>{statusText(step.status)}</strong>
              {blockerLabels.length ? <small>{blockerLabels.join(" · ")}</small> : null}
              {relationshipRefs.length ? (
                <span className="agentEvidenceRelationshipRefs">
                  {relationshipRefs.map((reference, index) => (
                    <span key={`${String(reference.relationKey ?? "hop")}:${index}`}>
                      {biText("关系证明", "Path proof")} {index + 1} · {String(reference.fromTable ?? "?")} → {String(reference.toTable ?? "?")}
                    </span>
                  ))}
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
      <small>{biText("计划指纹", "Plan fingerprint")} · {plan.fingerprint.slice(0, 12)}</small>
    </details>
  );
}
