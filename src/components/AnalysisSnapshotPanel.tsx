import { useCallback, useEffect, useRef, useState } from "react";
import { getAnalysisSnapshots, mutateAnalysisSnapshot, type AnalysisSnapshotMutation, type AnalysisSnapshotOperation } from "../apiAnalysisSnapshots";
import type { AnalysisSnapshot, AnalysisSnapshotPlan } from "../types";
import { biText } from "./Bilingual";
import "./AnalysisSnapshotPanel.css";

type AnalysisSnapshotPanelProps = {
  unitKey: string;
};

type PendingMutation = {
  input: AnalysisSnapshotMutation;
  plan: AnalysisSnapshotPlan;
};

function operationText(operation: AnalysisSnapshotOperation) {
  if (operation === "refresh") return biText("刷新", "refresh");
  if (operation === "replace") return biText("替换", "replace");
  if (operation === "delete") return biText("删除", "delete");
  return biText("创建", "create");
}

function statusText(status: string) {
  if (status === "current") return biText("当前可用", "Current");
  if (status === "deleted") return biText("内容已删除", "Content deleted");
  if (status === "missing") return biText("来源缺失", "Source missing");
  return biText("历史已过期", "Stale history");
}

export function AnalysisSnapshotPanel({ unitKey }: AnalysisSnapshotPanelProps) {
  const [snapshots, setSnapshots] = useState<AnalysisSnapshot[]>([]);
  const [reason, setReason] = useState(biText("保留本次可信分析结果", "Preserve this trusted analysis result"));
  const [rowLimit, setRowLimit] = useState(500);
  const [pending, setPending] = useState<PendingMutation | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const requestRef = useRef(0);

  const loadSnapshots = useCallback(async (successMessage = "") => {
    const requestId = ++requestRef.current;
    setBusy(true);
    const payload = await getAnalysisSnapshots(unitKey);
    if (requestRef.current !== requestId) return;
    if (payload.ok) {
      setSnapshots(payload.analysisSnapshots ?? []);
      setMessage(successMessage);
    } else {
      setMessage(payload.error || biText("无法读取分析快照。", "Unable to load Analysis Snapshots."));
    }
    setBusy(false);
  }, [unitKey]);

  useEffect(() => {
    requestRef.current += 1;
    setSnapshots([]);
    setPending(null);
    setMessage("");
    void loadSnapshots();
    return () => { requestRef.current += 1; };
  }, [loadSnapshots]);

  async function preview(operation: AnalysisSnapshotOperation, snapshotKey?: string) {
    const input: AnalysisSnapshotMutation = {
      operation,
      unitKey: operation === "delete" ? undefined : unitKey,
      snapshotKey,
      reason: operation === "delete" ? undefined : reason.trim(),
      rowLimit,
    };
    if (operation !== "delete" && !input.reason) {
      setMessage(biText("请先填写保存原因。", "Add a reason before previewing."));
      return;
    }
    const requestId = ++requestRef.current;
    setBusy(true);
    setMessage("");
    const payload = await mutateAnalysisSnapshot(input);
    if (requestRef.current !== requestId) return;
    if (payload.analysisSnapshotPlan) {
      setPending({ input, plan: payload.analysisSnapshotPlan });
    } else {
      setMessage(payload.error || biText("无法生成快照变更预演。", "Unable to preview the Snapshot change."));
    }
    setBusy(false);
  }

  async function confirm() {
    if (!pending) return;
    const requestId = ++requestRef.current;
    setBusy(true);
    setMessage("");
    const payload = await mutateAnalysisSnapshot({
      ...pending.input,
      confirm: true,
      expectedPlanFingerprint: pending.plan.planFingerprint,
    });
    if (requestRef.current !== requestId) return;
    if (!payload.ok || !payload.confirmed) {
      setMessage(payload.error || biText("快照确认失败，请重新预演。", "Snapshot confirmation failed; preview again."));
      setPending(null);
      setBusy(false);
      return;
    }
    const successMessage = payload.changed === false
      ? biText("精确输入已存在，没有重复写入。", "The exact input already exists; nothing was duplicated.")
      : biText("快照变更已确认并写入。", "Snapshot change confirmed and persisted.");
    setPending(null);
    await loadSnapshots(successMessage);
  }

  return (
    <section className="analysisSnapshotPanel" data-testid="analysis-snapshot-panel">
      <div className="analysisSnapshotLead">
        <div>
          <span>{biText("本地可信持久化", "Local trusted persistence")}</span>
          <strong>{biText("物化分析快照", "Materialized Analysis Snapshots")}</strong>
          <small>{biText("只冻结当前 Analysis Unit 的有界结果与完整来源指纹；不会重查来源或回退到旧快照。", "Freezes only bounded current Unit results and complete provenance; never requeries sources or falls back to stale Snapshots.")}</small>
        </div>
        <label>
          <span>{biText("保存原因", "Reason")}</span>
          <input disabled={busy} onChange={(event) => setReason(event.target.value)} value={reason} />
        </label>
        <label>
          <span>{biText("最多行数", "Row cap")}</span>
          <input disabled={busy} max="500" min="1" onChange={(event) => setRowLimit(Math.max(1, Math.min(500, Number(event.target.value) || 1)))} type="number" value={rowLimit} />
        </label>
        <button className="miniButton" disabled={busy} onClick={() => void preview("create")} type="button">
          {biText("预演创建", "Preview create")}
        </button>
      </div>

      {pending ? (
        <div className="analysisSnapshotConfirmation" data-testid="analysis-snapshot-confirmation" role="status">
          <div>
            <span>{biText("等待一次显式确认", "Explicit confirmation required")}</span>
            <strong>{operationText(pending.input.operation)} · {pending.plan.snapshotKey ?? pending.input.snapshotKey}</strong>
            <small>{pending.plan.planFingerprint.slice(0, 16)} · {biText("响应不包含业务结果行", "No business result rows in this response")}</small>
          </div>
          <button className="miniButton" disabled={busy} onClick={() => void confirm()} type="button">
            {busy ? biText("确认中…", "Confirming…") : biText("确认写入", "Confirm write")}
          </button>
          <button className="miniButton secondary" disabled={busy} onClick={() => setPending(null)} type="button">
            {biText("取消", "Cancel")}
          </button>
        </div>
      ) : null}

      <div className="analysisSnapshotList" data-testid="analysis-snapshot-list">
        {snapshots.length ? snapshots.map((snapshot) => (
          <article className={snapshot.status} key={snapshot.snapshotKey}>
            <div>
              <span>{statusText(snapshot.status)}</span>
              <strong>{snapshot.summary.title || snapshot.snapshotKey}</strong>
              <small>{snapshot.snapshotKey} · {snapshot.contentHash.slice(0, 12)}</small>
            </div>
            <dl>
              <div><dt>{biText("行数", "Rows")}</dt><dd>{snapshot.rowCount}/{snapshot.rowLimit}</dd></div>
              <div><dt>{biText("类型", "Kind")}</dt><dd>{snapshot.summary.kind || "-"}</dd></div>
              <div><dt>{biText("来源", "Binding")}</dt><dd>{snapshot.bindingFingerprint.slice(0, 12)}</dd></div>
            </dl>
            {snapshot.freshness.blockers.length ? <small className="analysisSnapshotBlockers">{snapshot.freshness.blockers.join(" · ")}</small> : null}
            {snapshot.status !== "deleted" ? (
              <div className="analysisSnapshotActions">
                <button className="miniButton" disabled={busy} onClick={() => void preview("refresh", snapshot.snapshotKey)} type="button">{biText("预演刷新", "Preview refresh")}</button>
                <button className="miniButton secondary" disabled={busy} onClick={() => void preview("replace", snapshot.snapshotKey)} type="button">{biText("预演替换", "Preview replace")}</button>
                <button className="miniButton danger" disabled={busy} onClick={() => void preview("delete", snapshot.snapshotKey)} type="button">{biText("预演删除", "Preview delete")}</button>
              </div>
            ) : null}
          </article>
        )) : <p className="analysisSnapshotEmpty">{busy ? biText("正在读取快照…", "Loading Snapshots…") : biText("尚未保存物化快照。", "No materialized Snapshot yet.")}</p>}
      </div>
      {message ? <p className="analysisSnapshotMessage" role="status">{message}</p> : null}
      <p className="analysisSnapshotBoundary">{biText("Provider 未参与；列表只显示摘要、状态和指纹，不返回冻结的业务结果行。", "No Provider participated; this list exposes only summaries, status, and fingerprints—not frozen business rows.")}</p>
    </section>
  );
}
