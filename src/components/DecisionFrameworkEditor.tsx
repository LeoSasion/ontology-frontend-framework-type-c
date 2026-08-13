import { useCallback, useEffect, useRef, useState } from "react";
import {
  createDecisionFramework,
  exportDecisionFramework,
  getDecisionFramework,
  getDecisionFrameworks,
  publishDecisionFramework,
  saveDecisionFramework,
} from "../apiDecisionFrameworks";
import type {
  DecisionClaim,
  DecisionClaimKind,
  DecisionFramework,
  DecisionFrameworkPublicationPlan,
  DecisionFrameworkSummary,
  DecisionFrameworkType,
} from "../typesDecisionFramework";
import { biText } from "./Bilingual";
import "./decisionFramework.css";

type DecisionFrameworkEditorProps = {
  unitKey: string;
};

type ClaimEditorProps = {
  categories: Array<{ key: string; label: string }>;
  claim: DecisionClaim;
  disabled: boolean;
  onChange: (claim: DecisionClaim) => void;
  onRemove: () => void;
};

const KIND_LABELS: Record<DecisionClaimKind, { zh: string; en: string }> = {
  evidence_fact: { zh: "证据事实", en: "Evidence fact" },
  user_judgment: { zh: "用户判断", en: "User judgment" },
  hypothesis: { zh: "待验证假设", en: "Hypothesis" },
};

function message(error: unknown) {
  return error instanceof Error && error.message
    ? error.message
    : biText("决策框架操作失败。", "Decision framework operation failed.");
}

function localKey() {
  return `claim_local_${typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID().replaceAll("-", "")
    : `${Date.now()}_${Math.random().toString(16).slice(2)}`}`;
}

function requestKey() {
  return `decision-framework:${typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
}

function cloneClaim(claim: DecisionClaim): DecisionClaim {
  return {
    ...claim,
    evidenceRefs: claim.evidenceRefs.map((ref) => ({ ...ref })),
  };
}

function downloadJson(filename: string, value: Record<string, unknown>) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function ClaimEditor({ categories, claim, disabled, onChange, onRemove }: ClaimEditorProps) {
  const fact = claim.claimKind === "evidence_fact";

  return (
    <article className={`decisionClaim ${claim.claimKind}`} data-claim-kind={claim.claimKind}>
      <div className="decisionClaimMeta">
        <label>
          <span>{biText("分类", "Category")}</span>
          <select
            disabled={disabled}
            onChange={(event) => onChange({ ...claim, category: event.target.value })}
            value={claim.category}
          >
            {categories.map((category) => <option key={category.key} value={category.key}>{category.label}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("性质", "Claim kind")}</span>
          <select
            disabled={disabled || fact}
            onChange={(event) => {
              const claimKind = event.target.value as DecisionClaimKind;
              onChange({
                ...claim,
                claimKind,
                evidenceRefs: [],
                verificationRequirement: claimKind === "hypothesis" ? claim.verificationRequirement : "",
              });
            }}
            value={claim.claimKind}
          >
            <option disabled={!fact} value="evidence_fact">{biText(KIND_LABELS.evidence_fact.zh, KIND_LABELS.evidence_fact.en)}</option>
            <option value="user_judgment">{biText(KIND_LABELS.user_judgment.zh, KIND_LABELS.user_judgment.en)}</option>
            <option value="hypothesis">{biText(KIND_LABELS.hypothesis.zh, KIND_LABELS.hypothesis.en)}</option>
          </select>
        </label>
        <span className={`decisionClaimBadge ${claim.claimKind}`}>{biText(KIND_LABELS[claim.claimKind].zh, KIND_LABELS[claim.claimKind].en)}</span>
      </div>
      <label className="decisionClaimText">
        <span>{biText("内容", "Claim")}</span>
        <textarea
          disabled={disabled || fact}
          maxLength={2000}
          onChange={(event) => onChange({ ...claim, text: event.target.value })}
          rows={fact ? 2 : 4}
          value={claim.text}
        />
      </label>
      {claim.claimKind === "hypothesis" ? (
        <label className="decisionClaimText">
          <span>{biText("需要怎样验证", "Validation needed")}</span>
          <textarea
            disabled={disabled}
            maxLength={1000}
            onChange={(event) => onChange({ ...claim, verificationRequirement: event.target.value })}
            rows={3}
            value={claim.verificationRequirement}
          />
        </label>
      ) : null}
      <div className="decisionClaimFooter">
        <small>
          {fact
            ? biText("文本锁定到当前执行回执；不能改写为未被证据证明的结论。", "Text is locked to the current executed receipt and cannot be rewritten into an unsupported conclusion.")
            : claim.claimKind === "user_judgment"
              ? biText("明确标记为人工判断。", "Explicitly labeled as a human judgment.")
              : biText("不会计入已证明结论。", "Does not count as a proven conclusion.")}
        </small>
        {!disabled ? <button className="miniButton secondary" onClick={onRemove} type="button">{biText("移除", "Remove")}</button> : null}
      </div>
    </article>
  );
}

export function DecisionFrameworkEditor({ unitKey }: DecisionFrameworkEditorProps) {
  const [summaries, setSummaries] = useState<DecisionFrameworkSummary[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [framework, setFramework] = useState<DecisionFramework | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftClaims, setDraftClaims] = useState<DecisionClaim[]>([]);
  const [newType, setNewType] = useState<DecisionFrameworkType>("swot");
  const [newTitle, setNewTitle] = useState(biText("当前分析决策框架", "Current analysis decision framework"));
  const [showCreate, setShowCreate] = useState(false);
  const [candidateCategories, setCandidateCategories] = useState<Record<string, string>>({});
  const [publicationPlan, setPublicationPlan] = useState<DecisionFrameworkPublicationPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const createRequestRef = useRef("");
  const detailRequestRef = useRef(0);

  const loadList = useCallback(async (preferredKey = "") => {
    const result = await getDecisionFrameworks(unitKey);
    if (!result.ok) throw new Error(result.error || biText("无法读取决策框架。", "Unable to load decision frameworks."));
    const next = result.decisionFrameworks ?? [];
    setSummaries(next);
    setSelectedKey((current) => preferredKey || (current && next.some((item) => item.frameworkKey === current) ? current : next[0]?.frameworkKey ?? ""));
  }, [unitKey]);

  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    setNotice("");
    setFramework(null);
    setSummaries([]);
    setSelectedKey("");
    setShowCreate(false);
    getDecisionFrameworks(unitKey, controller.signal)
      .then((result) => {
        if (!result.ok) throw new Error(result.error || biText("无法读取决策框架。", "Unable to load decision frameworks."));
        const next = result.decisionFrameworks ?? [];
        setSummaries(next);
        setSelectedKey(next[0]?.frameworkKey ?? "");
        setShowCreate(next.length === 0);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setNotice(message(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [unitKey]);

  useEffect(() => {
    if (!selectedKey) {
      setFramework(null);
      return;
    }
    const controller = new AbortController();
    const requestId = ++detailRequestRef.current;
    setBusy(true);
    setPublicationPlan(null);
    getDecisionFramework(selectedKey, controller.signal)
      .then((result) => {
        if (controller.signal.aborted || requestId !== detailRequestRef.current) return;
        if (!result.ok || !result.decisionFramework) throw new Error(result.error || biText("无法读取当前框架。", "Unable to load the selected framework."));
        const next = result.decisionFramework;
        setFramework(next);
        setDraftTitle(next.title);
        setDraftClaims(next.claims.map(cloneClaim));
        setCandidateCategories({});
      })
      .catch((error) => {
        if (!controller.signal.aborted && requestId === detailRequestRef.current) setNotice(message(error));
      })
      .finally(() => {
        if (!controller.signal.aborted && requestId === detailRequestRef.current) setBusy(false);
      });
    return () => controller.abort();
  }, [selectedKey]);

  async function createDraft() {
    const title = newTitle.trim();
    if (!title) {
      setNotice(biText("请先填写框架名称。", "Add a framework title first."));
      return;
    }
    if (!createRequestRef.current) createRequestRef.current = requestKey();
    setBusy(true);
    setNotice("");
    try {
      const result = await createDecisionFramework({ unitKey, type: newType, title, requestKey: createRequestRef.current });
      if (!result.decisionFramework) throw new Error(result.error || biText("无法创建框架草稿。", "Unable to create the framework draft."));
      const key = result.decisionFramework.frameworkKey;
      createRequestRef.current = "";
      setShowCreate(false);
      await loadList(key);
      setNotice(biText("已创建结构骨架；尚未生成任何业务判断。", "Structure created; no business judgment was generated."));
    } catch (error) {
      setNotice(message(error));
    } finally {
      setBusy(false);
    }
  }

  function acceptCandidate(candidate: DecisionClaim) {
    const category = candidateCategories[candidate.claimKey] ?? "";
    if (!category) {
      setNotice(biText("请先为证据候选选择分类。", "Choose a category for the evidence candidate first."));
      return;
    }
    if (draftClaims.some((claim) => claim.claimKey === candidate.claimKey)) {
      setNotice(biText("该证据事实已经加入。", "That evidence fact is already included."));
      return;
    }
    setDraftClaims((current) => [...current, { ...cloneClaim(candidate), category, status: "supported" }]);
    setNotice("");
  }

  function addManualClaim() {
    const category = framework?.structure.sections[0]?.key ?? "";
    setDraftClaims((current) => [...current, {
      claimKey: localKey(),
      category,
      text: "",
      claimKind: "user_judgment",
      evidenceRefs: [],
      author: "local-user",
      status: "user_asserted",
      verificationRequirement: "",
      contentFingerprint: "",
    }]);
  }

  function updateClaim(claimKey: string, next: DecisionClaim) {
    setDraftClaims((current) => current.map((claim) => claim.claimKey === claimKey ? next : claim));
  }

  async function saveDraft() {
    if (!framework) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await saveDecisionFramework({
        frameworkKey: framework.frameworkKey,
        title: draftTitle,
        claims: draftClaims,
        expectedContentFingerprint: framework.contentFingerprint,
      });
      if (!result.decisionFramework) throw new Error(result.error || biText("无法保存框架草稿。", "Unable to save the framework draft."));
      setFramework(result.decisionFramework);
      setDraftTitle(result.decisionFramework.title);
      setDraftClaims(result.decisionFramework.claims.map(cloneClaim));
      setPublicationPlan(null);
      await loadList(result.decisionFramework.frameworkKey);
      setNotice(result.changed === false
        ? biText("内容没有变化。", "No content changed.")
        : biText("草稿已保存。", "Draft saved."));
    } catch (error) {
      setNotice(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function previewPublication() {
    if (!framework) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await publishDecisionFramework({ frameworkKey: framework.frameworkKey });
      if (!result.decisionFrameworkPlan) throw new Error(result.error || biText("无法生成发布预演。", "Unable to preview publication."));
      setPublicationPlan(result.decisionFrameworkPlan);
    } catch (error) {
      setNotice(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function confirmPublication() {
    if (!framework || !publicationPlan) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await publishDecisionFramework({
        frameworkKey: framework.frameworkKey,
        confirm: true,
        expectedPlanFingerprint: publicationPlan.planFingerprint,
      });
      if (!result.confirmed || !result.decisionFramework) throw new Error(result.error || biText("框架发布失败。", "Framework publication failed."));
      setFramework(result.decisionFramework);
      setDraftClaims(result.decisionFramework.claims.map(cloneClaim));
      setPublicationPlan(null);
      await loadList(result.decisionFramework.frameworkKey);
      setNotice(biText("审核版本已发布并写入证据链。", "The reviewed version was published to the evidence ledger."));
    } catch (error) {
      setPublicationPlan(null);
      setNotice(message(error));
    } finally {
      setBusy(false);
    }
  }

  async function exportArtifact() {
    if (!framework) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await exportDecisionFramework(framework.frameworkKey);
      if (!result.decisionFrameworkExport) throw new Error(result.error || biText("无法导出框架。", "Unable to export the framework."));
      downloadJson(`${framework.frameworkKey}.json`, result.decisionFrameworkExport);
      setNotice(framework.freshness.current
        ? biText("已导出当前框架。", "Current framework exported.")
        : biText("已导出脱敏的过期框架；旧证据数字未包含。", "Stale framework exported with old evidence numbers removed."));
    } catch (error) {
      setNotice(message(error));
    } finally {
      setBusy(false);
    }
  }

  const categories = framework?.structure.sections.map((section) => ({
    key: section.key,
    label: biText(section.label.zh, section.label.en),
  })) ?? [];
  const editable = Boolean(framework?.canEdit && framework.freshness.current);

  return (
    <div className="decisionFrameworkEditor" data-testid="decision-framework-editor">
      <header className="decisionFrameworkHeader">
        <div>
          <span>{biText("证据绑定", "Evidence-bound")}</span>
          <h3>{biText("决策框架", "Decision framework")}</h3>
          <p>{biText("证据事实来自 current executed Receipt；人工判断和待验证假设始终分开。", "Evidence facts come from a current executed Receipt; human judgments and hypotheses stay separate.")}</p>
        </div>
        {summaries.length ? (
          <div className="decisionFrameworkSelector">
            <label>
              <span>{biText("当前框架", "Current framework")}</span>
              <select disabled={busy} onChange={(event) => setSelectedKey(event.target.value)} value={selectedKey}>
                {summaries.map((item) => <option key={item.frameworkKey} value={item.frameworkKey}>{item.title} · {item.status}</option>)}
              </select>
            </label>
            <button
              className="miniButton secondary"
              disabled={busy}
              onClick={() => {
                createRequestRef.current = "";
                setShowCreate((current) => !current);
              }}
              type="button"
            >
              {showCreate ? biText("取消新建", "Cancel new") : biText("新建框架", "New framework")}
            </button>
          </div>
        ) : null}
      </header>

      {showCreate && !busy ? (
        <fieldset className="decisionFrameworkCreate">
          <legend>{biText("新建结构骨架", "Create a structure")}</legend>
          <label>
            <span>{biText("类型", "Type")}</span>
            <select onChange={(event) => { setNewType(event.target.value as DecisionFrameworkType); createRequestRef.current = ""; }} value={newType}>
              <option value="swot">SWOT</option>
              <option value="process">{biText("流程", "Process")}</option>
            </select>
          </label>
          <label>
            <span>{biText("名称", "Title")}</span>
            <input maxLength={200} onChange={(event) => { setNewTitle(event.target.value); createRequestRef.current = ""; }} value={newTitle} />
          </label>
          <button className="miniButton" onClick={() => void createDraft()} type="button">{biText("创建空骨架", "Create empty structure")}</button>
          <small>{biText("不会自动填入机会、威胁、因果或行动建议。", "No opportunities, threats, causes, or actions are invented automatically.")}</small>
        </fieldset>
      ) : null}

      {framework ? (
        <>
          <section
            aria-live="polite"
            className={`decisionFrameworkTrust ${framework.freshness.status}`}
            data-evidence-facts-unloaded={framework.freshness.evidenceFactsUnloaded}
          >
            <div>
              <strong>{framework.freshness.current ? biText("证据当前可用", "Evidence is current") : biText("证据已漂移", "Evidence has drifted")}</strong>
              <span>{framework.type.toUpperCase()} · r{framework.revision} · {framework.contentFingerprint.slice(0, 12)}</span>
            </div>
            <dl>
              <div><dt>{biText("证据事实", "Evidence facts")}</dt><dd>{framework.claimCounts.evidenceFact}</dd></div>
              <div><dt>{biText("人工判断", "Judgments")}</dt><dd>{framework.claimCounts.userJudgment}</dd></div>
              <div><dt>{biText("待验证", "Hypotheses")}</dt><dd>{framework.claimCounts.hypothesis}</dd></div>
            </dl>
            {!framework.freshness.current ? (
              <p role="alert">{biText("旧证据事实及数字已经卸载，不能继续发布或作为当前经营结论。", "Old evidence facts and numbers were unloaded and cannot support publication or a current decision.")}</p>
            ) : null}
          </section>

          <label className="decisionFrameworkTitle">
            <span>{biText("框架名称", "Framework title")}</span>
            <input disabled={!editable || busy} maxLength={200} onChange={(event) => setDraftTitle(event.target.value)} value={draftTitle} />
          </label>

          {editable && framework.evidenceCandidates.length ? (
            <section className="decisionCandidatePanel" aria-labelledby="decision-candidate-title">
              <div>
                <span>{biText("候选事实", "Evidence candidates")}</span>
                <strong id="decision-candidate-title">{biText("由你选择放在哪个分类", "You choose the category")}</strong>
                <small>{biText("候选只复述有界计算结果，不推断机会、威胁、原因或行动。", "Candidates only restate bounded calculations; they infer no opportunity, threat, cause, or action.")}</small>
              </div>
              <div className="decisionCandidateList">
                {framework.evidenceCandidates.map((candidate) => (
                  <article key={candidate.claimKey}>
                    <p>{candidate.text}</p>
                    <label>
                      <span>{biText("放入", "Place in")}</span>
                      <select
                        aria-label={biText(`为候选“${candidate.text}”选择分类`, `Choose a category for candidate “${candidate.text}”`)}
                        onChange={(event) => setCandidateCategories((current) => ({ ...current, [candidate.claimKey]: event.target.value }))}
                        value={candidateCategories[candidate.claimKey] ?? ""}
                      >
                        <option value="">{biText("请选择", "Choose")}</option>
                        {categories.map((category) => <option key={category.key} value={category.key}>{category.label}</option>)}
                      </select>
                    </label>
                    <button className="miniButton secondary" disabled={!candidateCategories[candidate.claimKey]} onClick={() => acceptCandidate(candidate)} type="button">{biText("加入事实", "Add fact")}</button>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <section className="decisionClaims" aria-labelledby="decision-claims-title">
            <div className="decisionClaimsLead">
              <div>
                <span>{biText("内容", "Contents")}</span>
                <strong id="decision-claims-title">{biText("事实、判断与假设", "Facts, judgments, and hypotheses")}</strong>
              </div>
              {editable ? <button className="miniButton secondary" onClick={addManualClaim} type="button">{biText("添加人工内容", "Add human input")}</button> : null}
            </div>
            <div className="decisionClaimList">
              {draftClaims.length ? draftClaims.map((claim) => (
                <ClaimEditor
                  categories={categories}
                  claim={claim}
                  disabled={!editable || busy}
                  key={claim.claimKey}
                  onChange={(next) => updateClaim(claim.claimKey, next)}
                  onRemove={() => setDraftClaims((current) => current.filter((item) => item.claimKey !== claim.claimKey))}
                />
              )) : <p>{biText("目前只有结构骨架。先选择一个证据候选，或添加明确标记的人工判断/假设。", "This is only a structure. Add an evidence candidate or explicitly labeled judgment/hypothesis.")}</p>}
            </div>
          </section>

          <footer className="decisionFrameworkActions">
            {editable ? <button className="miniButton" disabled={busy} onClick={() => void saveDraft()} type="button">{biText("保存草稿", "Save draft")}</button> : null}
            {framework.canPublish && framework.storedStatus === "draft" ? <button className="miniButton secondary" disabled={busy} onClick={() => void previewPublication()} type="button">{biText("预演审核发布", "Preview reviewed publication")}</button> : null}
            <button className="miniButton secondary" disabled={busy} onClick={() => void exportArtifact()} type="button">{biText("导出 JSON", "Export JSON")}</button>
          </footer>

          {publicationPlan ? (
            <section className="decisionPublicationConfirm" data-testid="decision-framework-publication-confirmation" role="status">
              <div>
                <strong>{biText("只需这一次显式确认", "One explicit confirmation")}</strong>
                <span>{biText("发布后草稿不可原位改写，并由审核制品证据链记录。", "After publication the draft is immutable and recorded by the reviewed-artifact ledger.")}</span>
                <code>{publicationPlan.planFingerprint.slice(0, 16)}</code>
              </div>
              <button className="miniButton" disabled={busy} onClick={() => void confirmPublication()} type="button">{biText("确认发布", "Confirm publication")}</button>
              <button className="miniButton secondary" disabled={busy} onClick={() => setPublicationPlan(null)} type="button">{biText("取消", "Cancel")}</button>
            </section>
          ) : null}
        </>
      ) : null}

      {busy ? <p className="decisionFrameworkNotice" role="status">{biText("正在处理…", "Working…")}</p> : null}
      {notice ? <p className="decisionFrameworkNotice" role="status">{notice}</p> : null}
    </div>
  );
}
