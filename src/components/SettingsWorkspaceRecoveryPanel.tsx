import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  compareWorkspaceRecoveryPoint,
  getWorkspaceRecoveryPoints,
  inspectWorkspaceRecoveryPoint,
  mutateWorkspaceRecovery,
  type WorkspaceRecoveryMutation,
} from "../apiWorkspaceRecovery";
import type { WorkspaceRecoveryComparison, WorkspaceRecoveryOperation, WorkspaceRecoveryPlan, WorkspaceRecoveryPoint } from "../typesWorkspaceRecovery";
import { Bilingual, biText } from "./Bilingual";
import "./workspaceRecoveryPanel.css";

type SettingsWorkspaceRecoveryPanelProps = {
  workspaceId: string;
  onInvalidated?: (keys: string[]) => void;
};

type PendingRecovery = {
  input: WorkspaceRecoveryMutation;
  plan: WorkspaceRecoveryPlan;
};

function newRequestKey() {
  if (globalThis.crypto?.randomUUID) return `workspace-recovery:${globalThis.crypto.randomUUID()}`;
  return `workspace-recovery:${Date.now()}:${Math.random().toString(36).slice(2)}`;
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function operationLabel(operation: WorkspaceRecoveryOperation) {
  if (operation === "restore") return biText("恢复工作区", "restore workspace");
  if (operation === "delete") return biText("删除恢复点", "delete recovery point");
  return biText("创建恢复点", "create recovery point");
}

function localDate(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

export default function SettingsWorkspaceRecoveryPanel({ workspaceId, onInvalidated }: SettingsWorkspaceRecoveryPanelProps) {
  const [points, setPoints] = useState<WorkspaceRecoveryPoint[]>([]);
  const [health, setHealth] = useState<"empty" | "ready" | "attention">("empty");
  const [totalCount, setTotalCount] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [reason, setReason] = useState(biText("危险写入前的手动恢复点", "Manual recovery point before a risky write"));
  const [pending, setPending] = useState<PendingRecovery | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [comparison, setComparison] = useState<WorkspaceRecoveryComparison | null>(null);
  const requestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const workspaceRef = useRef(workspaceId);
  workspaceRef.current = workspaceId;

  const load = useCallback(async (options: { limit?: number; verify?: boolean; successMessage?: string } = {}) => {
    requestRef.current?.controller.abort();
    const controller = new AbortController();
    const requestId = (requestRef.current?.id ?? 0) + 1;
    requestRef.current = { id: requestId, controller };
    const expectedWorkspace = workspaceId;
    setBusy(options.verify ? "verify-all" : "load");
    try {
      const payload = await getWorkspaceRecoveryPoints({
        limit: options.limit ?? 5,
        verify: options.verify,
        signal: controller.signal,
      });
      if (requestRef.current?.id !== requestId || controller.signal.aborted || workspaceRef.current !== expectedWorkspace) return;
      if (payload.workspaceId !== expectedWorkspace) throw new Error(biText("恢复点列表与当前工作区不一致。", "Recovery points do not match the active workspace."));
      setPoints(payload.recoveryPoints ?? []);
      setHealth(payload.health ?? "empty");
      setTotalCount(payload.count ?? 0);
      setMessage(options.successMessage ?? "");
    } catch (error) {
      if (controller.signal.aborted || requestRef.current?.id !== requestId) return;
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (requestRef.current?.id === requestId) setBusy(null);
    }
  }, [workspaceId]);

  useEffect(() => {
    requestRef.current?.controller.abort();
    setPoints([]);
    setHealth("empty");
    setTotalCount(0);
    setExpanded(false);
    setPending(null);
    setComparison(null);
    setMessage("");
    void load({ limit: 5 });
    return () => requestRef.current?.controller.abort();
  }, [load, workspaceId]);

  const visiblePoints = useMemo(() => expanded ? points : points.slice(0, 1), [expanded, points]);
  const recentPoint = points[0];

  async function preview(operation: WorkspaceRecoveryOperation, recoveryPointKey?: string) {
    if (operation === "create" && !reason.trim()) {
      setMessage(biText("请填写创建恢复点的原因。", "Add a reason for the recovery point."));
      return;
    }
    const expectedWorkspace = workspaceId;
    const input: WorkspaceRecoveryMutation = {
      operation,
      requestKey: newRequestKey(),
      recoveryPointKey,
      reason: operation === "create" ? reason.trim() : undefined,
    };
    setBusy(`preview-${operation}`);
    setMessage("");
    try {
      const payload = await mutateWorkspaceRecovery(input);
      if (workspaceRef.current !== expectedWorkspace) return;
      if (payload.workspaceId !== expectedWorkspace || !payload.recoveryPlan) {
        throw new Error(biText("恢复预演没有返回当前工作区的计划。", "Recovery preview did not return a plan for the active workspace."));
      }
      setComparison((current) => operation === "restore" && current?.recoveryPointKey === payload.recoveryPlan!.recoveryPointKey ? current : null);
      setPending({ input, plan: payload.recoveryPlan });
    } catch (error) {
      if (workspaceRef.current !== expectedWorkspace) return;
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }

  async function confirmPending() {
    if (!pending) return;
    const expectedWorkspace = workspaceId;
    setBusy(`confirm-${pending.input.operation}`);
    setMessage("");
    try {
      const payload = await mutateWorkspaceRecovery({
        ...pending.input,
        confirm: true,
        expectedPlanFingerprint: pending.plan.planFingerprint,
      });
      if (workspaceRef.current !== expectedWorkspace) return;
      if (payload.workspaceId !== expectedWorkspace || !payload.confirmed) {
        throw new Error(payload.error || biText("恢复操作没有完成，请重新预演。", "Recovery operation did not complete; preview it again."));
      }
      const operation = pending.input.operation;
      setPending(null);
      if (operation === "restore") onInvalidated?.(payload.invalidationKeys ?? pending.plan.invalidationKeys);
      await load({
        limit: expanded ? 50 : 5,
        successMessage: payload.changed === false
          ? biText("相同请求已完成，没有重复写入。", "The same request already completed; nothing was duplicated.")
          : operation === "restore"
            ? biText("工作区已恢复，并保留了恢复前安全点。", "Workspace restored; the pre-restore safety point was retained.")
            : operation === "delete"
              ? biText("恢复点已安全删除。", "Recovery point safely deleted.")
              : biText("已创建并校验恢复点。", "Recovery point created and verified."),
      });
    } catch (error) {
      if (workspaceRef.current !== expectedWorkspace) return;
      setPending(null);
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }

  async function verifyPoint(point: WorkspaceRecoveryPoint) {
    const expectedWorkspace = workspaceId;
    setBusy(`verify-${point.recoveryPointKey}`);
    setMessage("");
    try {
      const payload = await inspectWorkspaceRecoveryPoint(point.recoveryPointKey);
      if (workspaceRef.current !== expectedWorkspace) return;
      if (payload.workspaceId !== expectedWorkspace || payload.recoveryPoint?.verified !== true) {
        throw new Error(biText("恢复点完整性校验未通过。", "Recovery point integrity verification failed."));
      }
      setPoints((current) => current.map((item) => item.recoveryPointKey === point.recoveryPointKey ? payload.recoveryPoint! : item));
      setMessage(biText("清单、文件大小和 SHA-256 均已通过。", "Manifest, file sizes, and SHA-256 checks passed."));
    } catch (error) {
      if (workspaceRef.current !== expectedWorkspace) return;
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }

  async function comparePoint(point: WorkspaceRecoveryPoint) {
    const expectedWorkspace = workspaceId;
    setBusy(`compare-${point.recoveryPointKey}`);
    setMessage("");
    try {
      const payload = await compareWorkspaceRecoveryPoint(point.recoveryPointKey);
      if (workspaceRef.current !== expectedWorkspace) return;
      if (payload.workspaceId !== expectedWorkspace || payload.verified !== true || payload.exposesBusinessRows !== false) {
        throw new Error(biText("恢复点差异对比未通过边界校验。", "Recovery comparison failed its trust-boundary checks."));
      }
      setComparison(payload);
      setMessage(payload.changedCount ? biText("已列出恢复后会变化的数据表。", "Tables affected by restore are now listed.") : biText("当前数据版本与该恢复点一致。", "Current data versions match this recovery point."));
    } catch (error) {
      if (workspaceRef.current !== expectedWorkspace) return;
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }

  async function loadAll() {
    setExpanded(true);
    await load({ limit: 50 });
  }

  return (
    <section className="workspaceRecoveryPanel" data-testid="settings-workspace-recovery-panel" aria-labelledby="workspace-recovery-title">
      <div className="workspaceRecoveryHeading">
        <div>
          <span><Bilingual zh="本地 · 工作区隔离 · SHA-256" en="Local · workspace-scoped · SHA-256" /></span>
          <strong id="workspace-recovery-title"><Bilingual zh="工作区恢复" en="Workspace recovery" /></strong>
          <small><Bilingual zh="危险写入前保留控制面和当前分析副本。默认只显示最近一项，恢复一定先预演并自动建立安全点。" en="Preserves the control plane and current analytics replica before risky writes. Only the latest point is shown by default; restore always starts with a preview and creates a safety point." /></small>
        </div>
        <div className={`workspaceRecoveryHealth ${health}`}>
          <strong>{health === "attention" ? biText("需要检查", "Attention") : health === "ready" ? biText("可恢复", "Recoverable") : biText("尚无恢复点", "No recovery point")}</strong>
          <span>{totalCount} {biText("项", "points")}</span>
        </div>
      </div>

      <div className="workspaceRecoveryCreate">
        <label>
          <span>{biText("创建原因", "Reason")}</span>
          <input disabled={busy !== null} maxLength={500} onChange={(event) => setReason(event.target.value)} value={reason} />
        </label>
        <button className="secondaryButton" disabled={busy !== null || !reason.trim()} onClick={() => void preview("create")} type="button">
          {busy === "preview-create" ? biText("预演中…", "Previewing…") : biText("预演创建", "Preview create")}
        </button>
      </div>

      {pending ? (
        <div className="workspaceRecoveryConfirmation" data-testid="workspace-recovery-confirmation" role="status">
          <div>
            <span>{biText("等待显式确认", "Explicit confirmation required")}</span>
            <strong>{operationLabel(pending.input.operation)} · {pending.plan.recoveryPointKey}</strong>
            <small>{pending.plan.planFingerprint.slice(0, 16)} · {pending.plan.requiresSafetyPoint ? biText("确认前会建立安全点", "A safety point will be created first") : biText("当前未写入", "No write yet")}</small>
          </div>
          <button className="primaryButton" disabled={busy !== null} onClick={() => void confirmPending()} type="button">
            {busy?.startsWith("confirm-") ? biText("确认中…", "Confirming…") : biText("确认执行", "Confirm")}
          </button>
          <button className="secondaryButton" disabled={busy !== null} onClick={() => setPending(null)} type="button">{biText("取消", "Cancel")}</button>
        </div>
      ) : null}

      {comparison ? (
        <div className="workspaceRecoveryComparison" data-testid="workspace-recovery-comparison">
          <div><strong>{biText("恢复影响", "Restore impact")} · {comparison.recoveryPointKey}</strong><span>{comparison.changedCount} {biText("项变化", "changes")}</span></div>
          {comparison.changes.some((item) => item.change !== "unchanged") ? <ul>{comparison.changes.filter((item) => item.change !== "unchanged").map((item) => <li key={item.tableKey}><strong>{item.tableKey}</strong><span>{item.change}</span><code>{item.currentDataVersion ?? "—"} → {item.targetDataVersion ?? "—"}</code></li>)}</ul> : <p>{biText("没有表级版本变化。", "No table-level version changes.")}</p>}
          <small>{biText("仅比较版本与指纹，不读取或展示业务行。", "Only versions and fingerprints are compared; no business rows are read or shown.")}</small>
          <button className="textButton" onClick={() => setComparison(null)} type="button">{biText("关闭", "Close")}</button>
        </div>
      ) : null}

      <div className="workspaceRecoveryList" data-testid="workspace-recovery-list">
        {visiblePoints.length ? visiblePoints.map((point) => (
          <article key={point.recoveryPointKey}>
            <div className="workspaceRecoveryPointTitle">
              <span>{point.verified ? biText("已校验", "Verified") : biText("清单可用", "Manifest ready")}</span>
              <strong>{point.reason}</strong>
              <small>{localDate(point.createdAt)} · {formatBytes(point.totalBytes)}</small>
            </div>
            <dl>
              <div><dt>{biText("来源版本", "Source")}</dt><dd>{point.currentSourceRunId?.slice(-12) || "—"}</dd></div>
              <div><dt>{biText("数据表", "Tables")}</dt><dd>{point.sourceVersions.length}</dd></div>
              <div><dt>{biText("指纹", "Fingerprint")}</dt><dd>{point.contentFingerprint.slice(0, 12)}</dd></div>
            </dl>
            <div className="workspaceRecoveryActions">
              <button className="secondaryButton" disabled={busy !== null} onClick={() => void verifyPoint(point)} type="button">{biText("校验", "Verify")}</button>
              <button className="secondaryButton" disabled={busy !== null} onClick={() => void comparePoint(point)} type="button">{biText("对比影响", "Compare impact")}</button>
              <button className="secondaryButton" disabled={busy !== null} onClick={() => void preview("restore", point.recoveryPointKey)} type="button">{biText("预演恢复", "Preview restore")}</button>
              <button className="secondaryButton danger" disabled={busy !== null} onClick={() => void preview("delete", point.recoveryPointKey)} type="button">{biText("预演删除", "Preview delete")}</button>
            </div>
            <details>
              <summary>{biText("技术校验详情", "Technical verification details")}</summary>
              <ul>
                {point.files.map((file) => <li key={file.kind}><span>{file.kind}</span><code>{file.sha256.slice(0, 16)}</code><span>{formatBytes(file.bytes)}</span></li>)}
              </ul>
            </details>
          </article>
        )) : <p className="workspaceRecoveryEmpty">{busy === "load" ? biText("正在读取恢复状态…", "Loading recovery status…") : biText("尚未创建工作区恢复点。", "No workspace recovery point has been created.")}</p>}
      </div>

      <div className="workspaceRecoveryFooter">
        {totalCount > 1 && !expanded ? <button className="textButton" disabled={busy !== null} onClick={() => void loadAll()} type="button">{biText(`展开全部 ${totalCount} 项`, `Show all ${totalCount} points`)}</button> : null}
        {expanded ? <button className="textButton" disabled={busy !== null} onClick={() => setExpanded(false)} type="button">{biText("只看最近一项", "Show latest only")}</button> : null}
        {recentPoint ? <button className="textButton" disabled={busy !== null} onClick={() => void load({ limit: expanded ? 50 : 5, verify: true })} type="button">{busy === "verify-all" ? biText("校验中…", "Verifying…") : biText("校验当前列表", "Verify visible list")}</button> : null}
      </div>

      {message ? <p className="workspaceRecoveryMessage" role="status">{message}</p> : null}
      <p className="workspaceRecoveryBoundary"><Bilingual zh="响应不展示本地绝对路径、源文件或业务行；恢复仅允许回到同一工作区。" en="Responses expose no absolute path, source file, or business row; restore is limited to the same workspace." /></p>
    </section>
  );
}
