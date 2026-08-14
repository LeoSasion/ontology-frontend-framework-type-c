import { useEffect, useMemo, useRef, useState } from "react";
import { getMetricContracts, previewMetricContract, publishMetricContract, replayMetricContract, type MetricContractMutation } from "../apiModel";
import type { MetricContract, MetricContractPlan, MetricContractReplay, MetricDefinition } from "../types";
import { Bilingual, biText } from "./Bilingual";
import "./metricContractPanel.css";

type MetricContractPanelProps = { metric: MetricDefinition };
type Draft = MetricContractMutation & { expectedPlanFingerprint?: string };

function stableRequestKey(metricKey: string, values: unknown[]) {
  const text = JSON.stringify([metricKey, ...values]);
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `metric-contract-ui-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : String(error || biText("操作失败", "Operation failed"));
}

export function MetricContractPanel({ metric }: MetricContractPanelProps) {
  const [contracts, setContracts] = useState<MetricContract[]>([]);
  const [population, setPopulation] = useState(biText("保存筛选后的全部业务记录", "All business records after saved filters"));
  const [grain, setGrain] = useState(metric.dimension || biText("工作区总计", "Workspace total"));
  const [unit, setUnit] = useState(metric.value_format || "auto");
  const [nullPolicy, setNullPolicy] = useState<"exclude" | "zero" | "error">("exclude");
  const [dedupKey, setDedupKey] = useState("");
  const [direction, setDirection] = useState<"neutral" | "increase" | "decrease">("neutral");
  const [owner, setOwner] = useState(biText("工作区负责人", "Workspace owner"));
  const [pending, setPending] = useState<{ draft: Draft; plan: MetricContractPlan } | null>(null);
  const [replay, setReplay] = useState<MetricContractReplay | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const requestRef = useRef(0);
  const latest = contracts[0];
  const scenario = useMemo(() => ({
    name: biText("当前全量基准", "Current full-data baseline"),
    groups: metric.dimension ? [metric.dimension] : [],
    filters: [],
    limit: 50,
  }), [metric.dimension]);

  useEffect(() => {
    const requestId = ++requestRef.current;
    setPending(null);
    setReplay(null);
    setNotice("");
    void getMetricContracts(metric.metric_key).then((payload) => {
      if (requestRef.current === requestId) setContracts(payload.metricContracts ?? []);
    }).catch((error) => {
      if (requestRef.current === requestId) setNotice(message(error));
    });
    return () => { requestRef.current += 1; };
  }, [metric.metric_key]);

  function mutation(): Draft {
    const values = [population, grain, unit, nullPolicy, dedupKey, direction, owner, scenario];
    return {
      metric: metric.metric_key,
      requestKey: stableRequestKey(metric.metric_key, values),
      label: metric.label,
      population: population.trim(),
      grain: grain.trim(),
      unit: unit.trim(),
      nullPolicy,
      dedupKey: dedupKey.trim(),
      direction,
      owner: owner.trim(),
      scenarios: [scenario],
    };
  }

  async function previewPublish() {
    setBusy("preview");
    setNotice("");
    try {
      const draft = mutation();
      const payload = await previewMetricContract(draft);
      setPending({ draft, plan: payload.metricContractPlan });
      setNotice(biText("口径与基准场景已预演；确认前不会发布新版本。", "Definition and baseline are previewed; no version publishes before confirmation."));
    } catch (error) {
      setNotice(message(error));
    } finally {
      setBusy("");
    }
  }

  async function confirmPublish() {
    if (!pending) return;
    setBusy("publish");
    setNotice("");
    try {
      await publishMetricContract({ ...pending.draft, expectedPlanFingerprint: pending.plan.planFingerprint });
      const payload = await getMetricContracts(metric.metric_key);
      setContracts(payload.metricContracts ?? []);
      setPending(null);
      setNotice(biText("指标合同已发布；后续口径或数据漂移会被单独标记。", "Metric Contract published. Definition and data drift will be identified separately."));
    } catch (error) {
      setNotice(message(error));
    } finally {
      setBusy("");
    }
  }

  async function runReplay(contract: MetricContract) {
    setBusy(`replay-${contract.contractKey}`);
    setNotice("");
    try {
      const payload = await replayMetricContract(contract.contractKey);
      setReplay(payload);
      setNotice(payload.status === "passed"
        ? biText("全部场景与发布基准一致。", "All scenarios match the published baseline.")
        : biText("检测到差异；下方已区分口径变化与数据变化。", "Differences detected; definition and data changes are separated below."));
    } catch (error) {
      setNotice(message(error));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="metricContractPanel" data-testid="metric-contract-panel">
      <div className="metricContractHeader">
        <div><span><Bilingual zh="Metric Contract v2" en="Metric Contract v2" /></span><strong>{metric.label}</strong><small><Bilingual zh="把口径、总体、粒度与可重放基准冻结成版本" en="Version the definition, population, grain, and replay baseline" /></small></div>
        <span className={`metricContractStatus ${latest?.status ?? "empty"}`}>{latest ? `v${latest.version} · ${latest.status}` : biText("尚未发布", "Not published")}</span>
      </div>
      <div className="metricContractFields">
        <label><span>{biText("业务总体", "Population")}</span><input onChange={(event) => setPopulation(event.target.value)} value={population} /></label>
        <label><span>{biText("粒度", "Grain")}</span><input onChange={(event) => setGrain(event.target.value)} value={grain} /></label>
        <label><span>{biText("单位", "Unit")}</span><input onChange={(event) => setUnit(event.target.value)} value={unit} /></label>
        <label><span>{biText("去重键（可空）", "Dedup key (optional)")}</span><input onChange={(event) => setDedupKey(event.target.value)} value={dedupKey} /></label>
        <label><span>{biText("空值策略", "Null policy")}</span><select onChange={(event) => setNullPolicy(event.target.value as typeof nullPolicy)} value={nullPolicy}><option value="exclude">exclude</option><option value="zero">zero</option><option value="error">error</option></select></label>
        <label><span>{biText("期望方向", "Desired direction")}</span><select onChange={(event) => setDirection(event.target.value as typeof direction)} value={direction}><option value="neutral">neutral</option><option value="increase">increase</option><option value="decrease">decrease</option></select></label>
        <label><span>{biText("口径负责人", "Definition owner")}</span><input onChange={(event) => setOwner(event.target.value)} value={owner} /></label>
      </div>
      <div className="metricContractActions">
        {!pending ? <button className="miniButton" disabled={Boolean(busy)} onClick={() => void previewPublish()} type="button">{busy === "preview" ? biText("预演中…", "Previewing…") : biText("预演新版本", "Preview new version")}</button> : <>
          <div className="metricContractConfirmation" data-testid="metric-contract-confirmation"><strong>v{pending.plan.version} · {pending.plan.changes.length} {biText("处变化", "changes")}</strong><small>{pending.plan.scenarios.length} {biText("个场景已建立基准", "scenario baselines")}</small></div>
          <button className="miniButton primary" disabled={busy === "publish"} onClick={() => void confirmPublish()} type="button">{biText("确认发布", "Confirm publish")}</button>
          <button className="miniButton secondary" disabled={Boolean(busy)} onClick={() => setPending(null)} type="button">{biText("取消", "Cancel")}</button>
        </>}
        {latest ? <button className="miniButton secondary" disabled={Boolean(busy)} onClick={() => void runReplay(latest)} type="button">{busy.startsWith("replay-") ? biText("回放中…", "Replaying…") : biText("回放当前场景", "Replay scenarios")}</button> : null}
      </div>
      {replay ? <div className={`metricContractReplay ${replay.status}`} data-testid="metric-contract-replay"><strong>{replay.status} · {replay.attribution}</strong><span>{replay.summary.passed}/{replay.summary.total} {biText("一致", "passed")} · {replay.summary.changed} {biText("变化", "changed")} · {replay.summary.blocked} {biText("阻断", "blocked")}</span>{replay.comparisons.map((item) => <small key={item.name}>{item.name}: {item.status}{item.scalarDelta === null ? "" : ` · Δ ${item.scalarDelta}`}</small>)}</div> : null}
      {notice ? <p className="metricContractNotice" role="status">{notice}</p> : null}
      <p className="metricContractBoundary"><Bilingual zh="基准只保存结果指纹、规模与单值摘要；筛选值不回显。数据版本与口径同时变化时，不会把差异伪装成单一原因。" en="Baselines store only result fingerprints, shape, and scalar summaries; filter values are never echoed. When data and definition both change, the difference is not misattributed to one cause." /></p>
    </section>
  );
}
