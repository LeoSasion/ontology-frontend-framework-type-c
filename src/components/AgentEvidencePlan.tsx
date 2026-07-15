import type { AgentEvidencePlan as AgentEvidencePlanContract } from "../typesAgent";
import { biText } from "./Bilingual";


function statusText(status: string) {
  if (status === "completed") return biText("完成", "Completed");
  if (status === "blocked") return biText("已阻断", "Blocked");
  if (status === "waiting-confirmation") return biText("等待确认", "Awaiting approval");
  if (status === "failed") return biText("失败", "Failed");
  return biText("已规划", "Planned");
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
        {plan.steps.map((step) => (
          <li className={step.status} key={step.stepKey}>
            <span>{step.kind}</span>
            <strong>{statusText(step.status)}</strong>
            {step.blockers.length ? <small>{step.blockers.join(" · ")}</small> : null}
          </li>
        ))}
      </ol>
      <small>{biText("计划指纹", "Plan fingerprint")} · {plan.fingerprint.slice(0, 12)}</small>
    </details>
  );
}
