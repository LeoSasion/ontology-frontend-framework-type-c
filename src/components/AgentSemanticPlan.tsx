import { useEffect, useMemo, useState } from "react";
import "./AgentSemanticPlan.css";
import type {
  RelationshipHopProof,
  SemanticFieldCandidate,
  SemanticQueryExecutionPlan,
  SemanticQueryPlan,
} from "../typesAgent";
import { biText } from "./Bilingual";
import { AgentSemanticRootClarification } from "./AgentSemanticRootClarification";

type AgentSemanticPlanProps = {
  plan: SemanticQueryPlan;
  executionPlan?: SemanticQueryExecutionPlan | null;
  tableNameByKey?: Map<string, string>;
  onSelectCandidates?: (candidates: SemanticFieldCandidate[]) => void;
  onSelectRoot?: (tableKey: string) => void;
  onSelectPath?: (relationKeys: string[]) => void;
};

function statusText(status: string) {
  if (status === "verified") return biText("关系路径已逐跳验证", "Relationship path verified hop by hop");
  if (status === "ready") return biText("字段与关系路径已定位", "Fields and relationship path located");
  if (status === "needs-clarification") return biText("需要选择字段、根表或关系路径", "Choose a field, root table, or relationship path");
  if (status === "needs-relationship") return biText("缺少已保存的关系路径", "A saved relationship path is missing");
  if (status === "needs-validation") return biText("关系路径需要验证", "Relationship path needs validation");
  if (status === "blocked") return biText("执行已安全阻断", "Execution safely blocked");
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

function tableLabel(tableKey: string, tableNameByKey?: Map<string, string>) {
  return tableNameByKey?.get(tableKey) ?? tableKey;
}

function directionText(direction: string) {
  return direction === "reverse" ? biText("反向遍历", "Reverse traversal") : biText("正向遍历", "Forward traversal");
}

function proofStatusText(status: string) {
  if (status === "verified") return biText("通过", "Verified");
  if (status === "blocked") return biText("阻断", "Blocked");
  return biText("待执行", "Planned");
}

function countText(value?: number) {
  return typeof value === "number" && Number.isFinite(value) ? new Intl.NumberFormat().format(value) : "—";
}

function expansionText(value?: number) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)}×` : "—";
}

function hopMappingText(hop: RelationshipHopProof) {
  const mappings = hop.traversalMappings?.length
    ? hop.traversalMappings.map((mapping) => `${mapping.fromField} = ${mapping.toField}`)
    : hop.fieldMappings.map((mapping) => `${mapping.leftField} = ${mapping.rightField}`);
  return mappings.join(" + ");
}

export function AgentSemanticPlan({ executionPlan, onSelectCandidates, onSelectPath, onSelectRoot, plan, tableNameByKey }: AgentSemanticPlanProps) {
  const proof = executionPlan?.relationshipPathProof;
  const blocked = plan.status !== "ready" || executionPlan?.status === "blocked" || proof?.status === "blocked";
  const selected = plan.fieldResolution.selected;
  const unresolved = plan.fieldResolution.unresolved;
  const clarificationKey = useMemo(
    () => unresolved.map((binding) => `${binding.mention}:${binding.candidates.map((candidate) => candidate.id).join(",")}`).join("|"),
    [unresolved],
  );
  const [candidateSelections, setCandidateSelections] = useState<Record<string, string>>({});
  useEffect(() => setCandidateSelections({}), [clarificationKey]);
  const selectedCandidates = unresolved
    .map((binding) => binding.candidates.find((candidate) => candidate.id === candidateSelections[binding.mention]))
    .filter((candidate): candidate is SemanticFieldCandidate => Boolean(candidate));
  const rootCandidates = plan.joinPlan.requiresRootClarification
    ? Array.from(new Set(plan.joinPlan.rootCandidates ?? []))
    : [];
  const pathSearchIncomplete = plan.joinPlan.pathSearchIncomplete === true;
  const pathClarifications = plan.joinPlan.targets.filter(
    (target) => target.requiresPathClarification && target.pathCandidates?.length,
  );

  const longestPath = useMemo(() => {
    const selectedPaths = plan.joinPlan.targets
      .map((target) => target.selectedPath)
      .filter((path): path is NonNullable<typeof path> => Boolean(path));
    return selectedPaths.reduce<typeof selectedPaths[number] | null>(
      (longest, path) => !longest || path.hops.length > longest.hops.length ? path : longest,
      null,
    );
  }, [plan.joinPlan.targets]);
  const pathTables = proof?.tables?.length ? proof.tables : executionPlan?.pathTables?.length ? executionPlan.pathTables : longestPath?.tables ?? [];
  const hopProofs = proof?.hopProofs ?? [];
  const maxExpansion = hopProofs.reduce((maximum, hop) => Math.max(maximum, Number(hop.rowExpansion ?? 0)), 0);
  const relationshipBlockers = Array.from(new Set([
    ...(pathSearchIncomplete ? ["relationship-path-search-incomplete"] : []),
    ...(proof?.blockers ?? []),
    ...(executionPlan?.blockers ?? []),
    ...(longestPath?.risks ?? []),
  ]));
  const primaryBlocker = relationshipBlockers[0];
  const summaryStatus = proof?.status === "verified" ? "verified" : blocked ? "blocked" : plan.status;

  return (
    <details className={`agentSemanticPlan ${blocked ? "blocked" : "ready"}`} data-testid="agent-semantic-plan" open={blocked}>
      <summary>
        <span className="agentSemanticPlanTitle">
          <span>{biText("关系路径", "Relationship path")}</span>
          <strong>{statusText(summaryStatus)}</strong>
        </span>
        {pathTables.length ? (
          <span className="agentSemanticPlanSummaryMeta">
            <strong>{pathTables.map((table) => tableLabel(table, tableNameByKey)).join(" → ")}</strong>
            <small>
              {biText(`${Math.max(0, pathTables.length - 1)} 跳`, `${Math.max(0, pathTables.length - 1)} hop(s)`)}
              {proof?.status === "verified" ? ` · ${biText(`最大 ${expansionText(maxExpansion)}`, `max ${expansionText(maxExpansion)}`)}` : ""}
            </small>
          </span>
        ) : null}
      </summary>
      <div className="agentSemanticPlanBody">
        {primaryBlocker ? (
          <div className="agentSemanticPrimaryBlocker" role="status">
            <strong>{biText("当前不能执行", "Execution is not available")}</strong>
            <span>{primaryBlocker}</span>
            {relationshipBlockers.length > 1 ? (
              <details className="agentRelationshipHopNotes">
                <summary>{biText(`查看全部 ${relationshipBlockers.length} 条阻断原因`, `View all ${relationshipBlockers.length} blockers`)}</summary>
                {relationshipBlockers.map((blocker) => <span key={blocker}>{blocker}</span>)}
              </details>
            ) : null}
          </div>
        ) : null}

        {selected.length ? (
          <div className="agentSemanticPlanGroup">
            <span>{biText("已定位字段", "Resolved fields")}</span>
            <div className="agentSemanticChips">
              {selected.map((candidate) => (
                <span key={candidate.id}>{candidateLabel(candidate, tableNameByKey)} · {roleText(candidate.role)}</span>
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

        {rootCandidates.length ? (
          <AgentSemanticRootClarification candidates={rootCandidates} onSelect={onSelectRoot} tableNameByKey={tableNameByKey} />
        ) : null}

        {pathSearchIncomplete ? (
          <div className="agentSemanticPlanGroup warning" data-testid="agent-semantic-path-search-incomplete" role="status">
            <span>{biText("候选关系路径过多，已停止自动选择", "Too many relationship paths; automatic selection stopped")}</span>
            <small>{biText(
              `搜索达到 ${plan.joinPlan.pathSearchLimit ?? 256} 条安全上限，候选集合未能证明完整。请在关系模型中核对业务键，并用明确的 relationKey 路径重新提问。`,
              `The search reached its safety limit of ${plan.joinPlan.pathSearchLimit ?? 256} paths without proving the candidate set complete. Review the business keys in the relationship model, then retry with an explicit relationKey path.`,
            )}</small>
          </div>
        ) : null}

        {pathClarifications.length ? (
          <div className="agentSemanticPlanGroup" data-testid="agent-semantic-path-clarification">
            <span>{biText("选择这次分析使用的关联语义", "Choose the relationship meaning for this analysis")}</span>
            <small>{biText("相同表可以通过不同业务键连接。选择后会保留原问题，并用明确的 relationKey 重新规划。", "The same tables can be joined through different business keys. Your choice keeps the original question and replans with explicit relation keys.")}</small>
            {pathClarifications.map((target) => (
              <div className="agentSemanticChips warning" key={target.targetTable}>
                <strong>{tableLabel(plan.joinPlan.rootTable, tableNameByKey)} → {tableLabel(target.targetTable, tableNameByKey)}</strong>
                {(target.pathCandidates ?? []).map((path) => {
                  const relationKeys = path.hops.map((hop) => hop.relationKey);
                  const mapping = path.hops.map((hop) => hop.fieldMappings.map((item) => `${item.leftField}=${item.rightField}`).join(" + ")).join(" · ");
                  return (
                    <button
                      className="miniButton"
                      data-testid="agent-semantic-path-candidate"
                      disabled={!onSelectPath}
                      key={relationKeys.join(">")}
                      onClick={() => onSelectPath?.(relationKeys)}
                      title={relationKeys.join(" > ")}
                      type="button"
                    >
                      {path.tables.map((table) => tableLabel(table, tableNameByKey)).join(" → ")} · {mapping}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        ) : null}

        {hopProofs.length ? (
          <div className="agentSemanticPlanGroup agentRelationshipProof" data-testid="agent-relationship-path-proof">
            <div className="agentRelationshipProofLead">
              <span>{biText("逐跳安全证明", "Hop-by-hop safety proof")}</span>
              <strong>{proofStatusText(proof?.status ?? "planned")}</strong>
            </div>
            <ol>
              {hopProofs.map((hop, index) => {
                const filterCount = hop.filterProof?.filters?.length ?? 0;
                const preaggregationApplied = hop.preaggregationProof?.status === "applied";
                const versionMatches = hop.dataVersions?.matches !== false;
                return (
                  <li className={hop.proofStatus} key={`${hop.relationKey}:${index}`}>
                    <div className="agentRelationshipHopHeading">
                      <span aria-hidden="true">{index + 1}</span>
                      <div>
                        <strong>
                          {tableLabel(hop.fromTable, tableNameByKey)} → {tableLabel(hop.toTable, tableNameByKey)}
                        </strong>
                        <small>{directionText(hop.direction)} · {hop.joinType.toUpperCase()} · {hopMappingText(hop)}</small>
                      </div>
                      <em>{proofStatusText(hop.proofStatus)}</em>
                    </div>
                    <dl className="agentRelationshipHopFacts">
                      <div><dt>{biText("行数", "Rows")}</dt><dd>{countText(hop.inputRows)} → {countText(hop.outputRows)}</dd></div>
                      <div><dt>{biText("行变化", "Expansion")}</dt><dd>{expansionText(hop.rowExpansion)}</dd></div>
                      <div><dt>{biText("函数依赖", "FD")}</dt><dd>{hop.functionDependencyProof?.status ?? "—"}</dd></div>
                      <div><dt>{biText("数据版本", "Versions")}</dt><dd>{versionMatches ? biText("一致", "Current") : biText("已漂移", "Drifted")}</dd></div>
                    </dl>
                    <div className="agentRelationshipHopPolicies">
                      <span>{filterCount ? biText(`${filterCount} 条筛选已应用`, `${filterCount} filter(s) applied`) : biText("无筛选", "No filters")}</span>
                      <span>{preaggregationApplied ? biText("预聚合已证明", "Preaggregation proven") : biText("无需预聚合", "No preaggregation required")}</span>
                      {hop.cardinalityProof?.unmatchedToRows ? <span>{biText(`目标侧 ${hop.cardinalityProof.unmatchedToRows} 行未匹配`, `${hop.cardinalityProof.unmatchedToRows} unmatched target row(s)`)}</span> : null}
                    </div>
                    {hop.blockers.length || hop.warnings.length ? (
                      <details className="agentRelationshipHopNotes">
                        <summary>{biText("查看阻断与警告", "View blockers and warnings")}</summary>
                        {[...hop.blockers, ...hop.warnings].map((item) => <span key={item}>{item}</span>)}
                      </details>
                    ) : null}
                  </li>
                );
              })}
            </ol>
          </div>
        ) : plan.joinPlan.targets.length ? (
          <div className="agentSemanticPlanGroup">
            <span>{biText("计划路径", "Planned path")}</span>
            <strong>{pathTables.length
              ? pathTables.map((table) => tableLabel(table, tableNameByKey)).join(" → ")
              : biText("没有已保存路径，推荐关系不会自动执行", "No saved path; recommendations never auto-execute")}</strong>
            {longestPath?.risks?.length ? <small>{longestPath.risks.join(" · ")}</small> : null}
          </div>
        ) : null}

        {executionPlan ? (
          <div className="agentSemanticExecutionSummary" data-testid="agent-semantic-execution-plan">
            <div>
              <span>{biText("最终粒度", "Final grain")}</span>
              <strong>{executionPlan.finalGrain?.length ? executionPlan.finalGrain.join(" + ") : biText("整体汇总", "Aggregate")}</strong>
            </div>
            <div>
              <span>{biText("计划哈希", "Plan hash")}</span>
              <code>{executionPlan.planHash.slice(0, 12)}</code>
            </div>
            <div>
              <span>{biText("路径证明", "Path proof")}</span>
              <code>{proof?.fingerprint?.slice(0, 12) ?? biText("待执行", "planned")}</code>
            </div>
          </div>
        ) : null}

        <p>{executionPlan?.status === "ready"
          ? biText("执行只使用已验证关系、参数化筛选和白名单聚合，不接受任意 SQL 或写入。", "Execution uses only validated relationships, parameterized filters, and whitelisted aggregations; it accepts no arbitrary SQL or writes.")
          : biText("该计划只提供证据；路径未通过时不会回退到单表猜测。", "This plan provides evidence only; a blocked path never falls back to a guessed single-table answer.")}</p>
      </div>
    </details>
  );
}
