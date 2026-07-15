import { biText } from "./Bilingual";

type AgentSemanticRootClarificationProps = {
  candidates: string[];
  onSelect?: (tableKey: string) => void;
  tableNameByKey?: Map<string, string>;
};

function candidateLabel(tableKey: string, tableNameByKey?: Map<string, string>) {
  const label = tableNameByKey?.get(tableKey) ?? tableKey;
  return label === tableKey ? tableKey : `${label} · ${tableKey}`;
}

export function AgentSemanticRootClarification({ candidates, onSelect, tableNameByKey }: AgentSemanticRootClarificationProps) {
  return (
    <div className="agentSemanticPlanGroup" data-testid="agent-semantic-root-clarification">
      <span>{biText("选择这次分析的起点表", "Choose the root table for this analysis")}</span>
      <small>{biText("多个起点都能覆盖所需字段。选择后会保留原问题，并用明确的 tableKey 重新规划。", "Multiple roots cover the requested fields. Your choice keeps the original question and replans with an explicit tableKey.")}</small>
      <div className="agentSemanticChips warning">
        {candidates.map((tableKey) => (
          <button
            className="miniButton"
            data-testid="agent-semantic-root-candidate"
            disabled={!onSelect}
            key={tableKey}
            onClick={() => onSelect?.(tableKey)}
            title={tableKey}
            type="button"
          >
            {candidateLabel(tableKey, tableNameByKey)}
          </button>
        ))}
      </div>
    </div>
  );
}
