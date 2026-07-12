import { useMemo, useState } from "react";
import { confirmQueryMemory, exportEvidence } from "../apiTrust";
import type { AgentAskResult } from "../types";
import { biText } from "./Bilingual";
import "../styles/trustContext.css";

function record(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

export function EvidenceTrustActions({ agent, lastActionResult }: { agent: AgentAskResult; lastActionResult?: Record<string, unknown> | null }) {
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const candidate = useMemo(() => record(lastActionResult?.confirmedQueryCandidate), [lastActionResult]);
  const candidateIsConfirmed = String(candidate?.status ?? "") === "confirmed";
  const receiptKey = agent.queryPlanReceipt?.receiptKey ?? agent.answerCard?.queryPlanReceipt?.receiptKey ?? "";

  if (!receiptKey && !candidate) return null;

  async function runExport() {
    if (!receiptKey) return;
    setBusy("export");
    try {
      await exportEvidence(receiptKey);
      setMessage(biText("证据包已导出到本地导出目录。", "Evidence package exported to the local export directory."));
    } finally { setBusy(""); }
  }

  async function saveMemory() {
    const queryKey = String(candidate?.query_key ?? "");
    if (!queryKey) return;
    setBusy("memory");
    try {
      await confirmQueryMemory(queryKey, true);
      setMessage(biText("已保存为确认问法；结构变化时会自动失效。", "Saved as a confirmed query; it will become stale when the structure changes."));
    } finally { setBusy(""); }
  }

  return (
    <article className="evidenceTrustActions" data-testid="evidence-trust-actions">
      <div><strong>{biText("结果交付与复用", "Deliver and reuse")}</strong><span>{biText("只使用当前查询回执，不重新计算口径。", "Uses the current query receipt without recalculating logic.")}</span></div>
      <div className="evidenceTrustButtons">
        {receiptKey ? <button className="secondaryButton" disabled={Boolean(busy)} onClick={() => void runExport()} type="button">{busy === "export" ? biText("导出中", "Exporting") : biText("导出证据包", "Export evidence")}</button> : null}
        {candidate && !candidateIsConfirmed ? <button className="secondaryButton" disabled={Boolean(busy)} onClick={() => void saveMemory()} type="button">{busy === "memory" ? biText("保存中", "Saving") : biText("保存为确认问法", "Save confirmed query")}</button> : null}
      </div>
      {candidateIsConfirmed && !message ? <small>{biText("当前问法已确认，可直接复用。", "This query is confirmed and ready to reuse.")}</small> : null}
      {message ? <small role="status">{message}</small> : null}
    </article>
  );
}

export default EvidenceTrustActions;
