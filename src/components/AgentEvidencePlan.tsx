import type { AgentAskResult, AgentEvidencePlan as AgentEvidencePlanContract, AgentSkillReference } from "../typesAgent";
import { biText } from "./Bilingual";


function statusText(status: string) {
  if (status === "completed") return biText("完成", "Completed");
  if (status === "blocked") return biText("已阻断", "Blocked");
  if (status === "waiting-confirmation") return biText("等待确认", "Awaiting approval");
  if (status === "failed") return biText("失败", "Failed");
  return biText("已规划", "Planned");
}

function skillStatusText(status?: string) {
  const normalized = String(status ?? "").toLowerCase();
  if (["ready", "matched", "selected", "enabled", "completed"].includes(normalized)) return biText("就绪", "Ready");
  if (["blocked", "failed", "incompatible"].includes(normalized)) return biText("已阻断", "Blocked");
  if (["disabled", "not-selected"].includes(normalized)) return biText("未启用", "Disabled");
  return biText("待核对", "Pending");
}

function skillTone(status?: string) {
  const normalized = String(status ?? "").toLowerCase();
  if (["ready", "matched", "selected", "enabled", "completed"].includes(normalized)) return "ready";
  if (["blocked", "failed", "incompatible"].includes(normalized)) return "blocked";
  return "pending";
}

function isBusinessUnderstandingSkill(skill: AgentSkillReference) {
  const kind = String(skill.skillKind ?? "").toLowerCase();
  return kind.includes("business") || kind.includes("understanding") || kind === "semantic-interpretation";
}

function evidencePlanSkills(plan: AgentEvidencePlanContract, businessUnderstanding?: AgentAskResult["businessUnderstanding"]) {
  const byKey = new Map<string, AgentSkillReference>();
  for (const skill of plan.skillRefs ?? []) byKey.set(`${skill.skillId}@${skill.version}`, skill);
  for (const skill of businessUnderstanding?.supportingSkills ?? []) {
    const key = `${skill.skillId}@${skill.version}`;
    byKey.set(key, { ...byKey.get(key), ...skill, skillKind: skill.skillKind ?? "understanding" });
  }
  return [...byKey.values()];
}

function skillFactValues(values?: string[]) {
  return [...new Set((values ?? []).map((value) => String(value).trim()).filter(Boolean))];
}

function SkillCard({ skill }: { skill: AgentSkillReference }) {
  const activeSignals = skillFactValues(skill.activeSignals);
  const missingSlots = skillFactValues(skill.missingSlots);
  const allowedCapabilities = skillFactValues(skill.allowedCapabilities);
  return (
    <li>
      <div className="agentEvidencePlanSkillHeader">
        <strong>{skill.skillId} · v{skill.version}</strong>
        <span className={skillTone(skill.status)}>{skillStatusText(skill.status)}</span>
      </div>
      <dl className="agentEvidencePlanSkillFacts">
        <div data-testid="agent-skill-triggers">
          <dt>{biText("触发依据", "Trigger basis")}</dt>
          <dd>{activeSignals.length ? activeSignals.join(" · ") : biText("任务类型与字段角色", "Task type and field roles")}</dd>
        </div>
        <div data-testid="agent-skill-missing-slots">
          <dt>{biText("缺失槽位", "Missing slots")}</dt>
          <dd>{missingSlots.length ? missingSlots.join(" · ") : biText("无", "None")}</dd>
        </div>
        <div data-testid="agent-skill-capabilities">
          <dt>{biText("能力交集", "Capability intersection")}</dt>
          <dd>{allowedCapabilities.length ? allowedCapabilities.join(" · ") : biText("仅复核，无执行能力", "Review only; no execution capability")}</dd>
        </div>
      </dl>
    </li>
  );
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


export function AgentEvidencePlan({ plan, businessUnderstanding }: { plan: AgentEvidencePlanContract; businessUnderstanding?: AgentAskResult["businessUnderstanding"] }) {
  const completed = plan.steps.filter((step) => step.status === "completed").length;
  const blocked = plan.steps.filter((step) => step.status === "blocked" || step.status === "failed").length;
  const skills = evidencePlanSkills(plan, businessUnderstanding);
  const analyticalSkills = skills.filter((skill) => !isBusinessUnderstandingSkill(skill));
  const understandingSkills = skills.filter(isBusinessUnderstandingSkill);
  const skillBlocked = skills.some((skill) => skillTone(skill.status) === "blocked");
  const isBlocked = blocked > 0 || skillBlocked || ["blocked", "failed"].includes(plan.status.toLowerCase());
  return (
    <details className={`agentEvidencePlan ${isBlocked ? "blocked" : "ready"}`} data-testid="agent-evidence-plan" open={isBlocked}>
      <summary>
        <span>{biText("证据计划", "Evidence plan")}</span>
        <strong>{completed}/{plan.steps.length} · {statusText(plan.status)}</strong>
      </summary>
      {skills.length ? (
        <div className="agentEvidencePlanSkillGroups">
          {analyticalSkills.length ? (
            <section className="agentEvidencePlanSkills" data-testid="agent-evidence-analytical-skills">
              <span>{biText("分析 Skill", "Analytical Skill")}</span>
              <ul aria-label={biText("分析 Skills", "Analytical Skills")}>
                {analyticalSkills.map((skill) => (
                  <SkillCard key={`${skill.skillId}@${skill.version}`} skill={skill} />
                ))}
              </ul>
            </section>
          ) : null}
          {understandingSkills.length ? (
            <section className="agentEvidencePlanSkills" data-testid="agent-evidence-business-skills">
              <span>{biText("业务理解 Skills", "Business understanding Skills")}</span>
              <ul aria-label={biText("业务理解 Skills", "Business understanding Skills")}>
                {understandingSkills.map((skill) => (
                  <SkillCard key={`${skill.skillId}@${skill.version}`} skill={skill} />
                ))}
              </ul>
            </section>
          ) : null}
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
