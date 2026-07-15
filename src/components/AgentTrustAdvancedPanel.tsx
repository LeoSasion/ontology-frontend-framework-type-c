import { useEffect, useState } from "react";
import { getAnalysisRuns } from "../apiTrust";
import type { AgentAskResult } from "../types";
import { biText } from "./Bilingual";
import "../styles/trustContext.css";

type AgentTrustAdvancedPanelProps = {
  result: AgentAskResult;
  canBranch: boolean;
  onAskBranch: (prompt: string, parentRunKey: string, branchLabel?: string) => Promise<void>;
};

export function AgentTrustAdvancedPanel({ result, canBranch, onAskBranch }: AgentTrustAdvancedPanelProps) {
  const [branchPrompt, setBranchPrompt] = useState("");
  const [branchLabel, setBranchLabel] = useState("");
  const [branchCount, setBranchCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const run = result.analysisRun;
  const receipt = result.queryPlanReceipt;

  useEffect(() => {
    if (!run?.run_key) return;
    void getAnalysisRuns(run.run_key).then((payload) => setBranchCount(payload.branches?.length ?? 0)).catch(() => setBranchCount(0));
  }, [run?.run_key]);

  async function submitBranch() {
    if (!run?.run_key || !branchPrompt.trim() || !canBranch) return;
    setBusy(true);
    try {
      await onAskBranch(branchPrompt.trim(), run.run_key, branchLabel.trim());
      setBranchPrompt("");
      setBranchLabel("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="agentTrustAdvanced" data-testid="agent-trust-advanced">
      <div className="agentTrustSummary">
        <span><strong>{receipt?.status ?? biText("等待", "waiting")}</strong><small>{biText("查询计划", "query plan")}</small></span>
        <span><strong>{result.context?.matchedTermCount ?? 0}</strong><small>{biText("命中术语", "matched terms")}</small></span>
        <span><strong>{result.context?.confirmedQueries?.length ?? 0}</strong><small>{biText("确认问法", "confirmed queries")}</small></span>
        <span><strong>{branchCount}</strong><small>{biText("比较分支", "branches")}</small></span>
      </div>
      {receipt ? (
        <dl className="agentTrustPlan">
          <div><dt>{biText("指标", "Measure")}</dt><dd>{receipt.selection.measure || "-"}</dd></div>
          <div><dt>{biText("分组", "Group")}</dt><dd>{receipt.selection.group || "-"}</dd></div>
          <div><dt>{biText("聚合", "Aggregation")}</dt><dd>{receipt.selection.aggregation || "-"}</dd></div>
          <div><dt>{biText("未决项", "Unresolved")}</dt><dd>{receipt.unresolved.length}</dd></div>
        </dl>
      ) : null}
      <details className="advancedDetails compactAdvanced">
        <summary>{biText("查看查询计划技术细节", "View query-plan technical details")}</summary>
        <code className="trustSql">{receipt?.runtime.compiledSql || biText("尚无编译 SQL", "No compiled SQL yet")}</code>
      </details>
      <div className="agentBranchForm">
        <strong>{biText("从当前结果继续比较", "Compare from this result")}</strong>
        {canBranch ? (
          <>
            <input aria-label={biText("比较分支名称，可选", "Comparison branch label, optional")} placeholder={biText("分支名称，可选", "Branch label, optional")} value={branchLabel} onChange={(event) => setBranchLabel(event.target.value)} />
            <textarea aria-label={biText("下一项比较内容", "Next comparison request")} placeholder={biText("描述下一项比较", "Describe the next comparison")} value={branchPrompt} onChange={(event) => setBranchPrompt(event.target.value)} />
            <button className="secondaryButton" disabled={busy || !branchPrompt.trim()} onClick={() => void submitBranch()} type="button">{busy ? biText("生成中", "Creating") : biText("创建比较分支", "Create comparison branch")}</button>
          </>
        ) : <span>{biText("确认当前图表后才开放分支，避免从未核对结果继续推导。", "Branches unlock after the chart is confirmed, preventing analysis from unreviewed results.")}</span>}
      </div>
    </div>
  );
}

export default AgentTrustAdvancedPanel;
