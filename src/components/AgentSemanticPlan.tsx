import { useEffect, useMemo, useState } from "react";
import type { SemanticFieldCandidate, SemanticQueryExecutionPlan, SemanticQueryPlan } from "../typesAgent";
import { biText } from "./Bilingual";

type AgentSemanticPlanProps = {
  plan: SemanticQueryPlan;
  executionPlan?: SemanticQueryExecutionPlan | null;
  tableNameByKey?: Map<string, string>;
  onSelectCandidates?: (candidates: SemanticFieldCandidate[]) => void;
};

function statusText(status: string) {
  if (status === "ready") return biText("字段与关系路径已定位", "Fields and relationship path located");
  if (status === "needs-clarification") return biText("需要选择字段所属表", "Choose the field's table");
  if (status === "needs-relationship") return biText("缺少已保存的关系路径", "A saved relationship path is missing");
  if (status === "needs-validation") return biText("关系路径需要验证", "Relationship path needs validation");
  return biText("语义计划待检查", "Semantic plan needs review");
}

function roleText(role: string) {
  if (role === "measure") return biText("指标", "Measure");
  if (role === "dimension") return biText("维度", "Dimension");
  if (role === "event_time") return biText("时间", "Time");
  if (role === "status") return biText("状态", "Status");
  if (role === "identity_key") return biText("关联键", "Join key");
  return biText("字段", "Field");
}

function candidateLabel(candidate: SemanticFieldCandidate, tableNameByKey?: Map<string, string>) {
  const table = tableNameByKey?.get(candidate.tableKey) ?? candidate.tableName ?? candidate.tableKey;
  return `${table}.${candidate.field}`;
}

export function AgentSemanticPlan({ executionPlan, onSelectCandidates, plan, tableNameByKey }: AgentSemanticPlanProps) {
  const blocked = plan.status !== "ready";
  const selected = plan.fieldResolution.selected;
  const unresolved = plan.fieldResolution.unresolved;
  const clarificationKey = useMemo(() => unresolved.map((binding) => `${binding.mention}:${binding.candidates.map((candidate) => candidate.id).join(",")}`).join("|"), [unresolved]);
  const [candidateSelections, setCandidateSelections] = useState<Record<string, string>>({});
  useEffect(() => setCandidateSelections({}), [clarificationKey]);
  const selectedCandidates = unresolved.map((binding) => binding.candidates.find((candidate) => candidate.id === candidateSelections[binding.mention])).filter((candidate): candidate is SemanticFieldCandidate => Boolean(candidate));
  return (
    <details className={`agentSemanticPlan ${blocked ? "blocked" : "ready"}`} data-testid="agent-semantic-plan" open={blocked}>
      <summary>
        <span>{biText("语义与跨表计划", "Semantic and join plan")}</span>
        <strong>{statusText(plan.status)}</strong>
      </summary>
      <div className="agentSemanticPlanBody">
        {selected.length ? (
          <div className="agentSemanticPlanGroup">
            <span>{biText("已定位字段", "Resolved fields")}</span>
            <div className="agentSemanticChips">
              {selected.map((candidate) => (
                <span key={candidate.id}>
                  {candidateLabel(candidate, tableNameByKey)} · {roleText(candidate.role)}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {unresolved.length ? (
          <div className="agentSemanticPlanGroup" data-testid="agent-semantic-clarification-bundle">
            <span>{biText("一次确认全部字段归属", "Confirm every field binding once")}</span>
            {unresolved.map((binding) => (
              <div className="agentSemanticChips warning" key={binding.mention}>
                <strong>{binding.mention}</strong>
                {binding.candidates.slice(0, 8).map((candidate) => {
                  const active = candidateSelections[binding.mention] === candidate.id;
                  return (
                    <button
                      aria-pressed={active}
                      className={active ? "miniButton active" : "miniButton"}
                      data-testid="agent-semantic-candidate"
                      key={candidate.id}
                      onClick={() => setCandidateSelections((current) => ({ ...current, [binding.mention]: candidate.id }))}
                      type="button"
                    >
                      {candidateLabel(candidate, tableNameByKey)} · {roleText(candidate.role)}
                    </button>
                  );
                })}
              </div>
            ))}
            <button
              className="primaryButton compactAction"
              data-testid="agent-semantic-confirm-candidates"
              disabled={!onSelectCandidates || selectedCandidates.length !== unresolved.length}
              onClick={() => onSelectCandidates?.(selectedCandidates)}
              type="button"
            >
              {biText("确认并继续分析", "Confirm and continue")}
            </button>
          </div>
        ) : null}
        {plan.joinPlan.targets.length ? (
          <div className="agentSemanticPlanGroup">
            <span>{biText("跨表路径", "Join paths")}</span>
            <div className="agentSemanticPaths">
              {plan.joinPlan.targets.map((target) => {
                const path = target.selectedPath;
                return (
                  <div key={target.targetTable}>
                    <strong>
                      {path
                        ? path.tables.map((table) => tableNameByKey?.get(table) ?? table).join(" → ")
                        : `${tableNameByKey?.get(plan.joinPlan.rootTable) ?? plan.joinPlan.rootTable} → ${tableNameByKey?.get(target.targetTable) ?? target.targetTable}`}
                    </strong>
                    <small>
                      {path
                        ? path.risks.length
                          ? path.risks.join(" · ")
                          : executionPlan?.status === "ready"
                            ? biText(`${path.hops.length} 跳；已使用当前验证快照`, `${path.hops.length} hop(s); current validation snapshot used`)
                            : biText(`${path.hops.length} 跳；执行前仍需当前数据预览`, `${path.hops.length} hop(s); current preview still required`)
                        : biText("没有已保存路径，推荐关系不会自动执行", "No saved path; recommendations never auto-execute")}
                    </small>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
        {executionPlan ? (
          <div className="agentSemanticPlanGroup" data-testid="agent-semantic-execution-plan">
            <span>{biText("受控执行计划", "Controlled execution plan")}</span>
            <strong>{executionPlan.status === "ready" ? biText("已按白名单执行", "Executed through whitelist") : biText("执行已阻断", "Execution blocked")}</strong>
            {executionPlan.finalGrain?.length ? <small>{biText("最终粒度", "Final grain")}: {executionPlan.finalGrain.join(" + ")}</small> : null}
            <small>{biText("计划哈希", "Plan hash")}: {executionPlan.planHash.slice(0, 12)}</small>
            {executionPlan.blockers.length ? <small>{executionPlan.blockers.join(" · ")}</small> : null}
          </div>
        ) : null}
        <p>{executionPlan?.status === "ready"
          ? biText("执行只使用已验证关系和白名单聚合，不接受任意 SQL 或写入。", "Execution uses only validated relationships and whitelisted aggregations; it accepts no arbitrary SQL or writes.")
          : biText("该计划只提供证据，不执行任意 SQL 或写入。", "This plan provides evidence only; it executes no arbitrary SQL or writes.")}</p>
      </div>
    </details>
  );
}
