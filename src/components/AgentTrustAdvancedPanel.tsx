import { useEffect, useState } from "react";
import { getAnalysisRuns } from "../apiTrust";
import type { AgentAskResult } from "../types";
import { biText } from "./Bilingual";
import { ExplorationThreadPanel } from "./ExplorationThreadPanel";
import "../styles/trustContext.css";

type AgentTrustAdvancedPanelProps = {
  result: AgentAskResult;
  canBranch: boolean;
  onAskBranch: (prompt: string, parentRunKey: string, branchLabel?: string) => Promise<void>;
};

export function AgentTrustAdvancedPanel({ result, canBranch, onAskBranch }: AgentTrustAdvancedPanelProps) {
  const [branchCount, setBranchCount] = useState(0);
  const run = result.analysisRun;
  const receipt = result.queryPlanReceipt;
  const storedPathProof = receipt?.selection.relationshipPathProof;
  const hopProofs = Array.isArray(storedPathProof)
    ? storedPathProof
    : storedPathProof?.hopProofs ?? [];
  const verifiedHops = hopProofs.filter((proof) => proof.proofStatus === "verified").length;
  const sourceTableCount = receipt?.source.tableKeys?.length ?? (receipt?.source.tableKey ? 1 : 0);
  const resultState = receipt?.resultState ?? receipt?.status ?? "blocked";
  const coverageComplete = receipt?.selection.executionCoverage?.complete === true;

  useEffect(() => {
    if (!run?.run_key) return;
    void getAnalysisRuns(run.run_key).then((payload) => setBranchCount(payload.branches?.length ?? 0)).catch(() => setBranchCount(0));
  }, [run?.run_key]);

  return (
    <div className="agentTrustAdvanced" data-testid="agent-trust-advanced">
      <div className="agentTrustSummary">
        <span><strong>{resultState}</strong><small>{biText("结果状态", "result state")}</small></span>
        <span><strong>{result.context?.matchedTermCount ?? 0}</strong><small>{biText("命中术语", "matched terms")}</small></span>
        <span><strong>{result.context?.confirmedQueries?.length ?? 0}</strong><small>{biText("确认问法", "confirmed queries")}</small></span>
        <span><strong>{branchCount}</strong><small>{biText("比较分支", "branches")}</small></span>
        {hopProofs.length || sourceTableCount > 1 ? <span><strong>{verifiedHops}/{hopProofs.length}</strong><small>{biText("关系跳已验证", "verified hops")}</small></span> : null}
      </div>
      {receipt ? (
        <dl className="agentTrustPlan">
          <div><dt>{biText("指标", "Measure")}</dt><dd>{receipt.selection.measure || "-"}</dd></div>
          <div><dt>{biText("分组", "Group")}</dt><dd>{receipt.selection.group || "-"}</dd></div>
          <div><dt>{biText("聚合", "Aggregation")}</dt><dd>{receipt.selection.aggregation || "-"}</dd></div>
          <div><dt>{biText("参与表", "Source tables")}</dt><dd>{sourceTableCount}</dd></div>
          <div><dt>{biText("最终粒度", "Final grain")}</dt><dd>{receipt.selection.executionPlan?.finalGrain?.join(" + ") || "-"}</dd></div>
          <div><dt>{biText("路径证明", "Path proof")}</dt><dd>{receipt.source.relationshipPathFingerprint?.slice(0, 12) || "-"}</dd></div>
          <div><dt>{biText("未决项", "Unresolved")}</dt><dd>{receipt.unresolved.length}</dd></div>
          <div><dt>current sourceRun</dt><dd>{receipt.source.currentSourceRunId?.slice(0, 12) || "-"}</dd></div>
          <div><dt>{biText("执行覆盖", "Execution coverage")}</dt><dd>{coverageComplete ? biText("完整", "complete") : biText("未完成", "incomplete")}</dd></div>
          <div><dt>{biText("可发布经营数字", "Business conclusion")}</dt><dd>{receipt.validation.canSupportBusinessConclusion === true ? biText("允许", "allowed") : biText("禁止", "blocked")}</dd></div>
        </dl>
      ) : null}
      <details className="advancedDetails compactAdvanced">
        <summary>{biText("查看查询计划技术细节", "View query-plan technical details")}</summary>
        <code className="trustSql">{receipt?.runtime.compiledSql || biText("尚无编译 SQL", "No compiled SQL yet")}</code>
      </details>
      <ExplorationThreadPanel canBranch={canBranch} onAskBranch={onAskBranch} result={result} />
    </div>
  );
}

export default AgentTrustAdvancedPanel;
