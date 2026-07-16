import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getMetricMonitors, mutateMetricMonitor, type MetricMonitorMutation } from "../apiMetricMonitors";
import type { AnalysisSnapshot, MetricMonitor, MetricMonitorPlan } from "../types";
import { biText } from "./Bilingual";
import "./MetricMonitorPanel.css";

type MetricMonitorPanelProps = {
  snapshots: AnalysisSnapshot[];
};

type PendingMonitorMutation = {
  input: MetricMonitorMutation;
  plan: MetricMonitorPlan;
};

function monitorStatus(status: string) {
  if (status === "baseline") return biText("基线已建立", "Baseline established");
  if (status === "normal") return biText("正常", "Normal");
  if (status === "warning") return biText("接近阈值", "Warning");
  if (status === "breached") return biText("已越过阈值", "Breached");
  if (status === "blocked") return biText("比较已阻断", "Blocked");
  return biText("尚未运行", "Not run");
}

export function MetricMonitorPanel({ snapshots }: MetricMonitorPanelProps) {
  const [monitors, setMonitors] = useState<MetricMonitor[]>([]);
  const [label, setLabel] = useState(biText("关键指标本地监控", "Local KPI monitor"));
  const [threshold, setThreshold] = useState("");
  const [cadence, setCadence] = useState<"manual" | "daily" | "weekly" | "monthly">("manual");
  const [strategy, setStrategy] = useState<"absolute-change" | "percent-change">("absolute-change");
  const [direction, setDirection] = useState<"increase" | "decrease" | "absolute">("absolute");
  const [pending, setPending] = useState<PendingMonitorMutation | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const requestRef = useRef(0);
  const currentSnapshots = useMemo(() => snapshots.filter((snapshot) => snapshot.status === "current"), [snapshots]);
  const latestSnapshot = currentSnapshots[0];
  const visibleMonitors = useMemo(() => {
    const semantics = new Set(snapshots.map((snapshot) => snapshot.semanticFingerprint));
    return monitors.filter((monitor) => semantics.has(monitor.semanticFingerprint));
  }, [monitors, snapshots]);

  const loadMonitors = useCallback(async (successMessage = "") => {
    const requestId = ++requestRef.current;
    setBusy(true);
    const payload = await getMetricMonitors();
    if (requestRef.current !== requestId) return;
    if (payload.ok) {
      setMonitors((payload.metricMonitors ?? []).filter((monitor) => monitor.status === "active"));
      setMessage(successMessage);
    } else {
      setMessage(payload.error || biText("无法读取指标监控。", "Unable to load Metric Monitors."));
    }
    setBusy(false);
  }, []);

  useEffect(() => {
    requestRef.current += 1;
    setPending(null);
    setMessage("");
    void loadMonitors();
    return () => { requestRef.current += 1; };
  }, [loadMonitors]);

  function definition(operation: "create" | "replace", monitorKey?: string): MetricMonitorMutation | null {
    if (!latestSnapshot) {
      setMessage(biText("需要一个当前可用的单值快照。", "A current scalar Snapshot is required."));
      return null;
    }
    if (!label.trim()) {
      setMessage(biText("请填写监控名称。", "Add a monitor label."));
      return null;
    }
    const parsedThreshold = threshold.trim() ? Number(threshold) : undefined;
    if (parsedThreshold !== undefined && (!Number.isFinite(parsedThreshold) || parsedThreshold < 0)) {
      setMessage(biText("阈值必须是非负数字。", "Threshold must be a non-negative number."));
      return null;
    }
    return {
      operation,
      monitorKey,
      snapshotKey: latestSnapshot.snapshotKey,
      label: label.trim(),
      cadence,
      comparisonStrategy: strategy,
      direction,
      threshold: parsedThreshold,
      warningRatio: 0.8,
    };
  }

  async function preview(input: MetricMonitorMutation | null) {
    if (!input) return;
    const requestId = ++requestRef.current;
    setBusy(true);
    setMessage("");
    const payload = await mutateMetricMonitor(input);
    if (requestRef.current !== requestId) return;
    if (payload.metricMonitorPlan) {
      setPending({ input, plan: payload.metricMonitorPlan });
    } else {
      setMessage(payload.error || biText("无法生成监控变更预演。", "Unable to preview the Monitor change."));
    }
    setBusy(false);
  }

  async function confirm() {
    if (!pending) return;
    const requestId = ++requestRef.current;
    setBusy(true);
    setMessage("");
    const payload = await mutateMetricMonitor({
      ...pending.input,
      confirm: true,
      expectedPlanFingerprint: pending.plan.planFingerprint,
    });
    if (requestRef.current !== requestId) return;
    if (!payload.ok || !payload.confirmed) {
      setPending(null);
      setBusy(false);
      setMessage(payload.error || biText("确认失败，请重新预演。", "Confirmation failed; preview again."));
      return;
    }
    setPending(null);
    await loadMonitors(payload.changed === false
      ? biText("相同定义已存在，没有重复写入。", "The same definition already exists; nothing was duplicated.")
      : biText("监控定义已确认。", "Monitor definition confirmed."));
  }

  async function run(monitor: MetricMonitor) {
    const requestId = ++requestRef.current;
    setBusy(true);
    setMessage("");
    const payload = await mutateMetricMonitor({
      operation: "run",
      monitorKey: monitor.monitorKey,
      snapshotKey: latestSnapshot?.snapshotKey,
    });
    if (requestRef.current !== requestId) return;
    if (!payload.ok || !payload.metricMonitorEvaluation) {
      setBusy(false);
      setMessage(payload.error || biText("本地评估失败。", "Local evaluation failed."));
      return;
    }
    const evaluation = payload.metricMonitorEvaluation;
    const change = evaluation.absoluteChange === null || evaluation.absoluteChange === undefined
      ? ""
      : ` · Δ ${evaluation.absoluteChange.toLocaleString()}`;
    await loadMonitors(`${monitorStatus(evaluation.status)}${change}`);
  }

  return (
    <section className="metricMonitorPanel" data-testid="metric-monitor-panel">
      <div className="metricMonitorLead">
        <div>
          <span>{biText("手动、本地、可重放", "Manual, local, replayable")}</span>
          <strong>{biText("指标监控", "Metric Monitor")}</strong>
          <small>{biText("只比较兼容快照；节奏仅作定义记录，不启用后台调度，也不发送通知。", "Compares compatible Snapshots only; cadence is descriptive and never enables background scheduling or notifications.")}</small>
        </div>
        <label><span>{biText("名称", "Label")}</span><input disabled={busy} onChange={(event) => setLabel(event.target.value)} value={label} /></label>
        <label><span>{biText("阈值（可空）", "Threshold (optional)")}</span><input disabled={busy} min="0" onChange={(event) => setThreshold(event.target.value)} placeholder={biText("不填则只报告变化", "Track change only")} type="number" value={threshold} /></label>
        <label><span>{biText("比较", "Comparison")}</span><select disabled={busy} onChange={(event) => setStrategy(event.target.value as typeof strategy)} value={strategy}><option value="absolute-change">{biText("绝对变化", "Absolute change")}</option><option value="percent-change">{biText("百分比变化", "Percent change")}</option></select></label>
        <label><span>{biText("方向", "Direction")}</span><select disabled={busy} onChange={(event) => setDirection(event.target.value as typeof direction)} value={direction}><option value="absolute">{biText("任一方向", "Either direction")}</option><option value="increase">{biText("上升", "Increase")}</option><option value="decrease">{biText("下降", "Decrease")}</option></select></label>
        <label><span>{biText("复核节奏", "Review cadence")}</span><select disabled={busy} onChange={(event) => setCadence(event.target.value as typeof cadence)} value={cadence}><option value="manual">{biText("手动", "Manual")}</option><option value="daily">{biText("每日", "Daily")}</option><option value="weekly">{biText("每周", "Weekly")}</option><option value="monthly">{biText("每月", "Monthly")}</option></select></label>
        <button className="miniButton" disabled={busy || !latestSnapshot} onClick={() => void preview(definition("create"))} type="button">{biText("预演创建", "Preview create")}</button>
      </div>

      {pending ? <div className="metricMonitorConfirmation" data-testid="metric-monitor-confirmation" role="status"><div><strong>{biText("等待显式确认", "Explicit confirmation required")}</strong><small>{pending.plan.planFingerprint.slice(0, 16)} · {biText("无通知、无业务写入", "No notification or business write")}</small></div><button className="miniButton" disabled={busy} onClick={() => void confirm()} type="button">{biText("确认定义", "Confirm definition")}</button><button className="miniButton secondary" disabled={busy} onClick={() => setPending(null)} type="button">{biText("取消", "Cancel")}</button></div> : null}

      <div className="metricMonitorList" data-testid="metric-monitor-list">
        {visibleMonitors.length ? visibleMonitors.map((monitor) => <article className={monitor.latestStatus} key={monitor.monitorKey}><div><span>{monitorStatus(monitor.latestStatus)}</span><strong>{monitor.label}</strong><small>{monitor.metric} · {monitor.comparisonStrategy} · {monitor.threshold === null || monitor.threshold === undefined ? biText("无告警阈值", "No alert threshold") : `${biText("阈值", "threshold")} ${monitor.threshold}`}</small></div><dl><div><dt>{biText("节奏", "Cadence")}</dt><dd>{monitor.cadence}</dd></div><div><dt>{biText("基线", "Baseline")}</dt><dd>{monitor.baselineSnapshotKey.slice(-12)}</dd></div><div><dt>{biText("能力", "Capability")}</dt><dd>{monitor.capabilityVersion}</dd></div></dl><div className="metricMonitorActions"><button className="miniButton" disabled={busy || (!latestSnapshot && monitor.latestStatus !== "not-run")} onClick={() => void run(monitor)} type="button">{monitor.latestStatus === "not-run" ? biText("建立基线", "Establish baseline") : biText("运行当前快照", "Run current Snapshot")}</button><button className="miniButton secondary" disabled={busy || !latestSnapshot} onClick={() => void preview(definition("replace", monitor.monitorKey))} type="button">{biText("预演替换", "Preview replace")}</button><button className="miniButton danger" disabled={busy} onClick={() => void preview({ operation: "delete", monitorKey: monitor.monitorKey })} type="button">{biText("预演删除", "Preview delete")}</button></div></article>) : <p>{busy ? biText("正在读取监控…", "Loading Monitors…") : biText("当前快照口径尚无指标监控。", "No Metric Monitor for this Snapshot definition yet.")}</p>}
      </div>
      {message ? <p className="metricMonitorMessage" role="status">{message}</p> : null}
      <p className="metricMonitorBoundary">{biText("阈值只能来自用户明确输入；未设置阈值时只报告变化。异常状态不会被自动解释成业务原因。", "Thresholds come only from explicit user input; without one, changes are reported without alerts. Anomaly states are never auto-explained as business causes.")}</p>
    </section>
  );
}
