import { useEffect, useMemo, useRef, useState } from "react";
import { createResearchRun, finalizeResearchRun, getResearchRuns, observeResearchRun, reviseResearchRun } from "../apiResearch";
import type { ExplorationThread, LimitedResearchRun, ResearchMutationPayload } from "../types";
import { biText } from "./Bilingual";
import "./ResearchRunPanel.css";

type ResearchRunPanelProps = {
  thread: ExplorationThread;
};

type PendingResearch = {
  label: string;
  payload: ResearchMutationPayload;
  confirm: () => Promise<ResearchMutationPayload>;
};

function splitItems(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function outcomeLabel(outcome?: string) {
  if (outcome === "supported") return biText("支持", "Supported");
  if (outcome === "challenged") return biText("受挑战", "Challenged");
  if (outcome === "mixed") return biText("证据混合", "Mixed");
  if (outcome === "inconclusive") return biText("证据不足", "Inconclusive");
  return biText("研究中", "Active");
}

export function ResearchRunPanel({ thread }: ResearchRunPanelProps) {
  const [runs, setRuns] = useState<LimitedResearchRun[]>([]);
  const [goal, setGoal] = useState("");
  const [hypotheses, setHypotheses] = useState("");
  const [counterexamples, setCounterexamples] = useState("");
  const [sensitivities, setSensitivities] = useState("");
  const [revisionReason, setRevisionReason] = useState("");
  const [revisionGoal, setRevisionGoal] = useState("");
  const [revisionHypotheses, setRevisionHypotheses] = useState("");
  const [revisionCounterexamples, setRevisionCounterexamples] = useState("");
  const [revisionSensitivities, setRevisionSensitivities] = useState("");
  const [selectedRunKey, setSelectedRunKey] = useState("");
  const [observationAnchor, setObservationAnchor] = useState("");
  const [observationStep, setObservationStep] = useState("");
  const [observationVerdict, setObservationVerdict] = useState<"supports" | "challenges" | "inconclusive">("supports");
  const [observationNote, setObservationNote] = useState("");
  const [pending, setPending] = useState<PendingResearch | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const requestRef = useRef(0);

  const threadRuns = useMemo(() => runs.filter((run) => run.threadKey === thread.threadKey), [runs, thread.threadKey]);
  const selected = threadRuns.find((run) => run.researchKey === selectedRunKey) ?? threadRuns[0] ?? null;
  const currentRevision = selected?.currentRevision ?? null;
  const observableSteps = currentRevision?.steps.filter((step) => ["evidence", "counterexample", "sensitivity"].includes(step.kind)) ?? [];
  const selectedStep = observableSteps.find((step) => step.stepKey === observationStep) ?? observableSteps[0] ?? null;
  const currentAnchors = thread.anchors.filter((anchor) => anchor.freshness.usableForContinuation);

  async function refresh() {
    const requestId = ++requestRef.current;
    try {
      const payload = await getResearchRuns();
      if (requestRef.current !== requestId || payload.workspaceId !== thread.workspaceId) return;
      setRuns(payload.researchRuns ?? []);
    } catch (error) {
      if (requestRef.current === requestId) setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    setPending(null);
    setMessage("");
    void refresh();
    return () => { requestRef.current += 1; };
  }, [thread.threadKey, thread.workspaceId]);

  useEffect(() => {
    if (!selectedRunKey && threadRuns[0]) setSelectedRunKey(threadRuns[0].researchKey);
  }, [selectedRunKey, threadRuns]);

  useEffect(() => {
    if (!observationAnchor && currentAnchors[0]) setObservationAnchor(currentAnchors[0].anchorKey);
    if (!observationStep && observableSteps[0]) setObservationStep(observableSteps[0].stepKey);
  }, [currentAnchors, observableSteps, observationAnchor, observationStep]);

  useEffect(() => {
    if (!currentRevision) return;
    setRevisionGoal(currentRevision.goal);
    setRevisionHypotheses(currentRevision.hypotheses.join("\n"));
    setRevisionCounterexamples(currentRevision.counterexampleChecks.join("\n"));
    setRevisionSensitivities(currentRevision.sensitivityChecks.join("\n"));
    setRevisionReason("");
  }, [currentRevision?.fingerprint]);

  async function preview(task: () => Promise<PendingResearch>) {
    setBusy(true);
    setMessage("");
    try {
      setPending(await task());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function confirmPending() {
    if (!pending) return;
    setBusy(true);
    setMessage("");
    try {
      const result = await pending.confirm();
      setPending(null);
      setMessage(result.changed === false ? biText("目标状态已存在。", "The requested state already exists.") : biText("研究账本已更新。", "Research ledger updated."));
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  function previewCreate() {
    const request = {
      threadKey: thread.threadKey,
      anchorKey: thread.currentAnchorKey,
      goal: goal.trim(),
      hypotheses: splitItems(hypotheses),
      counterexampleChecks: splitItems(counterexamples),
      sensitivityChecks: splitItems(sensitivities),
    };
    void preview(async () => {
      const payload = await createResearchRun(request);
      return { label: biText("建立有限研究", "Create finite research"), payload, confirm: () => createResearchRun({ ...request, confirm: true, expectedPlanFingerprint: payload.researchPlan.planFingerprint }) };
    });
  }

  function previewRevise() {
    if (!selected || !currentRevision) return;
    const request = {
      researchKey: selected.researchKey,
      reason: revisionReason.trim(),
      goal: revisionGoal.trim(),
      hypotheses: splitItems(revisionHypotheses),
      counterexampleChecks: splitItems(revisionCounterexamples),
      sensitivityChecks: splitItems(revisionSensitivities),
      expectedRevisionFingerprint: currentRevision.fingerprint,
    };
    void preview(async () => {
      const payload = await reviseResearchRun(request);
      return { label: biText("追加计划修订", "Append plan revision"), payload, confirm: () => reviseResearchRun({ ...request, confirm: true, expectedPlanFingerprint: payload.researchPlan.planFingerprint }) };
    });
  }

  function previewObserve() {
    if (!selected || !currentRevision || !selectedStep) return;
    const request = {
      researchKey: selected.researchKey,
      anchorKey: observationAnchor,
      kind: selectedStep.kind as "evidence" | "counterexample" | "sensitivity",
      stepKey: selectedStep.stepKey,
      verdict: observationVerdict,
      note: observationNote.trim(),
      expectedRevisionFingerprint: currentRevision.fingerprint,
    };
    void preview(async () => {
      const payload = await observeResearchRun(request);
      return { label: biText("采纳研究证据", "Adopt research evidence"), payload, confirm: () => observeResearchRun({ ...request, confirm: true, expectedPlanFingerprint: payload.researchPlan.planFingerprint }) };
    });
  }

  function previewFinalize() {
    if (!selected || !currentRevision) return;
    const request = { researchKey: selected.researchKey, expectedRevisionFingerprint: currentRevision.fingerprint };
    void preview(async () => {
      const payload = await finalizeResearchRun(request);
      return { label: biText("完成有限研究", "Finalize finite research"), payload, confirm: () => finalizeResearchRun({ ...request, confirm: true, expectedPlanFingerprint: payload.researchPlan.planFingerprint }) };
    });
  }

  return (
    <details className="advancedDetails compactAdvanced researchRunPanel" data-testid="research-run-panel">
      <summary>{biText("有限研究：反例、敏感性与计划修订", "Finite research: counterexamples, sensitivity, and revisions")}</summary>
      <div className="researchRunBody">
        <div className="researchRunLead">
          <div>
            <strong>{selected?.goal ?? biText("从当前锚点建立有预算的研究账本", "Create a budgeted research ledger from the current Anchor")}</strong>
            <span>{selected ? `${selected.revisionCount}/${selected.budget.maxRevisions} revisions · ${selected.observationCount}/${selected.budget.maxObservations} observations` : biText("不联网、不执行任意 SQL、不复制业务结果行。", "No web access, arbitrary SQL, or copied business rows.")}</span>
          </div>
          <span className={`researchRunStatus ${selected?.freshness.status ?? "idle"}`}>{selected ? outcomeLabel(selected.conclusion?.outcome) : biText("未建立", "Not created")}</span>
        </div>

        {threadRuns.length > 1 ? (
          <label><span>{biText("研究运行", "Research Run")}</span><select value={selected?.researchKey ?? ""} onChange={(event) => setSelectedRunKey(event.target.value)}>{threadRuns.map((run) => <option key={run.researchKey} value={run.researchKey}>{run.goal}</option>)}</select></label>
        ) : null}

        {!selected ? (
          <div className="researchRunForm" data-testid="research-create-form">
            <label><span>{biText("研究目标", "Research goal")}</span><input value={goal} onChange={(event) => setGoal(event.target.value)} /></label>
            <label><span>{biText("候选假设（每行一项）", "Hypotheses (one per line)")}</span><textarea value={hypotheses} onChange={(event) => setHypotheses(event.target.value)} /></label>
            <label><span>{biText("反例检查（每行一项）", "Counterexample checks (one per line)")}</span><textarea value={counterexamples} onChange={(event) => setCounterexamples(event.target.value)} /></label>
            <label><span>{biText("敏感性检查（每行一项）", "Sensitivity checks (one per line)")}</span><textarea value={sensitivities} onChange={(event) => setSensitivities(event.target.value)} /></label>
            <button className="secondaryButton" data-testid="research-preview-create" disabled={busy || !goal.trim()} onClick={previewCreate} type="button">{biText("预演建立研究", "Preview research")}</button>
          </div>
        ) : (
          <>
            <div className="researchCoverage" data-testid="research-coverage">
              <span>{biText("普通证据", "Evidence")} <strong>{selected.coverage.evidence}</strong></span>
              <span>{biText("反例", "Counterexample")} <strong>{selected.coverage.counterexample}</strong></span>
              <span>{biText("敏感性", "Sensitivity")} <strong>{selected.coverage.sensitivity}</strong></span>
              <span>{biText("新鲜度", "Freshness")} <strong>{selected.freshness.status}</strong></span>
            </div>

            {selected.storedStatus === "active" && selected.freshness.usableForPlanning ? (
              <div className="researchRunForm">
                <label><span>{biText("证据锚点", "Evidence Anchor")}</span><select value={observationAnchor} onChange={(event) => setObservationAnchor(event.target.value)}>{currentAnchors.map((anchor) => <option key={anchor.anchorKey} value={anchor.anchorKey}>{anchor.label}</option>)}</select></label>
                <label><span>{biText("研究步骤", "Research step")}</span><select value={selectedStep?.stepKey ?? ""} onChange={(event) => setObservationStep(event.target.value)}>{observableSteps.map((step) => <option key={step.stepKey} value={step.stepKey}>{step.kind} · {step.question}</option>)}</select></label>
                <label><span>{biText("判断", "Verdict")}</span><select value={observationVerdict} onChange={(event) => setObservationVerdict(event.target.value as typeof observationVerdict)}><option value="supports">supports</option><option value="challenges">challenges</option><option value="inconclusive">inconclusive</option></select></label>
                <label><span>{biText("可审计说明", "Auditable note")}</span><input value={observationNote} onChange={(event) => setObservationNote(event.target.value)} /></label>
                <button className="secondaryButton" disabled={busy || !selectedStep || !observationAnchor || !observationNote.trim()} onClick={previewObserve} type="button">{biText("预演采纳证据", "Preview observation")}</button>
                <details className="advancedDetails compactAdvanced researchRevisionEditor">
                  <summary>{biText("修订研究计划", "Revise research plan")}</summary>
                  <label><span>{biText("研究目标", "Research goal")}</span><input value={revisionGoal} onChange={(event) => setRevisionGoal(event.target.value)} /></label>
                  <label><span>{biText("候选假设（每行一项）", "Hypotheses (one per line)")}</span><textarea value={revisionHypotheses} onChange={(event) => setRevisionHypotheses(event.target.value)} /></label>
                  <label><span>{biText("反例检查（每行一项）", "Counterexample checks (one per line)")}</span><textarea value={revisionCounterexamples} onChange={(event) => setRevisionCounterexamples(event.target.value)} /></label>
                  <label><span>{biText("敏感性检查（每行一项）", "Sensitivity checks (one per line)")}</span><textarea value={revisionSensitivities} onChange={(event) => setRevisionSensitivities(event.target.value)} /></label>
                  <label><span>{biText("修订原因", "Revision reason")}</span><input value={revisionReason} onChange={(event) => setRevisionReason(event.target.value)} /></label>
                  <button className="miniButton" disabled={busy || !revisionGoal.trim() || !revisionReason.trim() || selected.revisionCount >= selected.budget.maxRevisions} onClick={previewRevise} type="button">{biText("预演追加修订", "Preview revision")}</button>
                </details>
                <button className="secondaryButton" disabled={busy} onClick={previewFinalize} type="button">{biText("预演完成研究", "Preview finalize")}</button>
              </div>
            ) : null}

            <div className="researchRevisionList" data-testid="research-revisions">
              {selected.revisions.map((revision) => <div key={revision.revisionKey}><strong>v{revision.revisionNumber}</strong><span>{revision.reason}</span><code>{revision.fingerprint.slice(0, 12)}</code></div>)}
            </div>
            <details className="advancedDetails compactAdvanced"><summary>{biText(`统一 Trace · ${selected.trace.eventCount}`, `Unified trace · ${selected.trace.eventCount}`)}</summary><ol className="researchTrace">{selected.trace.events.map((event) => <li key={event.sequence}><strong>{event.eventType}</strong><span>{event.summary}</span></li>)}</ol></details>
            {selected.freshness.blockers.length ? <p className="explorationBlocker">{selected.freshness.blockers.join(" · ")}</p> : null}
          </>
        )}

        {pending ? (
          <div className="explorationConfirm" data-testid="research-confirmation">
            <div><strong>{pending.label}</strong><span>{biText("确认只写研究元数据与证据引用；计划版本不会被覆盖。", "Confirmation writes only research metadata and evidence references; revisions are never overwritten.")}</span><code>{pending.payload.researchPlan.planFingerprint.slice(0, 16)}</code></div>
            <div className="explorationConfirmActions"><button className="primaryButton" data-testid="research-confirm" disabled={busy} onClick={() => void confirmPending()} type="button">{biText("确认", "Confirm")}</button><button className="secondaryButton" disabled={busy} onClick={() => setPending(null)} type="button">{biText("取消", "Cancel")}</button></div>
          </div>
        ) : null}
        {message ? <p className="explorationMessage" role="status">{message}</p> : null}
      </div>
    </details>
  );
}
