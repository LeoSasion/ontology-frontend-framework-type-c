import { useEffect, useState } from "react";
import { getConfirmedPlans, getConfirmedQueries, getContextPack, getRecallReceipts, getSemanticPatches, proposeSemanticPatch, reviewSemanticPatch } from "../apiTrust";
import type { ConfirmedPlanMemory, ConfirmedQuery, ContextPackPayload, RecallReceipt, SemanticPatchProposal } from "../types";
import { Bilingual, biText } from "./Bilingual";
import "../styles/trustContext.css";

type ReviewDraft = { proposalKey: string; decision: "accept" | "reject" } | null;

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error || biText("操作失败", "Operation failed"));
}

function proposalTitle(proposal: SemanticPatchProposal) {
  const after = proposal.after;
  return String(after.canonicalName ?? after.title ?? after.fieldName ?? proposal.targetRef);
}

function proposalKind(proposal: SemanticPatchProposal) {
  if (proposal.patchType === "term") return biText("业务术语", "Business term");
  if (proposal.patchType === "rule") return biText("业务规则", "Business rule");
  return biText("字段语义", "Field semantic");
}

function compactJson(value: Record<string, unknown> | null) {
  if (!value) return biText("尚不存在，将新建", "Missing; this will be created");
  return JSON.stringify(value, null, 2);
}

export function TrustContextSettingsPanel() {
  const [pack, setPack] = useState<ContextPackPayload["contextPack"] | null>(null);
  const [queries, setQueries] = useState<ConfirmedQuery[]>([]);
  const [plans, setPlans] = useState<ConfirmedPlanMemory[]>([]);
  const [recallReceipts, setRecallReceipts] = useState<RecallReceipt[]>([]);
  const [proposals, setProposals] = useState<SemanticPatchProposal[]>([]);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [termName, setTermName] = useState("");
  const [termDefinition, setTermDefinition] = useState("");
  const [termAliases, setTermAliases] = useState("");
  const [termScope, setTermScope] = useState("workspace");
  const [termScopeRef, setTermScopeRef] = useState("");
  const [termPreviewed, setTermPreviewed] = useState(false);
  const [ruleTitle, setRuleTitle] = useState("");
  const [ruleStatement, setRuleStatement] = useState("");
  const [rulePreviewed, setRulePreviewed] = useState(false);
  const [reviewDraft, setReviewDraft] = useState<ReviewDraft>(null);
  const visibleQueries = queries.filter((item) => item.status === "confirmed" || item.status === "stale");
  const reviewProposals = proposals
    .slice()
    .sort((left, right) => Number(["pending", "stale"].includes(right.status)) - Number(["pending", "stale"].includes(left.status)))
    .slice(0, 12);
  const proposalCounts = proposals.reduce<Record<string, number>>((counts, proposal) => {
    counts[proposal.status] = (counts[proposal.status] ?? 0) + 1;
    return counts;
  }, {});

  async function refresh() {
    const [result, queryResult, planResult, recallResult, patchResult] = await Promise.all([getContextPack(), getConfirmedQueries(), getConfirmedPlans(), getRecallReceipts(), getSemanticPatches()]);
    setPack(result.contextPack);
    setQueries(queryResult.confirmedQueries);
    setPlans(planResult.confirmedPlans ?? []);
    setRecallReceipts(recallResult.recallReceipts ?? []);
    setProposals(patchResult.proposals ?? []);
  }

  useEffect(() => { void refresh().catch((error) => setMessage(errorMessage(error))); }, []);

  async function runTermProposal(confirm: boolean) {
    if (!termName.trim() || !termDefinition.trim()) return;
    setBusy(confirm ? "term-confirm" : "term-preview");
    setMessage("");
    try {
      await proposeSemanticPatch({
        kind: "term",
        sourceName: biText("用户术语纠正", "User term correction"),
        name: termName.trim(),
        definition: termDefinition.trim(),
        aliases: termAliases.split(/[,，]/).map((item) => item.trim()).filter(Boolean),
        scopeType: termScope,
        scopeRef: termScope === "workspace" ? "" : termScopeRef.trim(),
        confidence: 1,
        confirm,
      });
      if (!confirm) {
        setTermPreviewed(true);
        setMessage(biText("提案预演完成，尚未写入审核队列。请核对后确认提交。", "Proposal previewed without writes. Confirm to submit it for review."));
      } else {
        setTermName("");
        setTermDefinition("");
        setTermAliases("");
        setTermScopeRef("");
        setTermPreviewed(false);
        setMessage(biText("术语纠正已进入审核收件箱，尚未改变业务语义。", "The term correction is in the review inbox; business semantics are unchanged."));
        await refresh();
      }
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  async function runRuleProposal(confirm: boolean) {
    if (!ruleTitle.trim() || !ruleStatement.trim()) return;
    setBusy(confirm ? "rule-confirm" : "rule-preview");
    setMessage("");
    try {
      await proposeSemanticPatch({
        kind: "rule",
        sourceName: biText("用户规则纠正", "User rule correction"),
        title: ruleTitle.trim(),
        statement: ruleStatement.trim(),
        ruleType: "other",
        confidence: 1,
        confirm,
      });
      if (!confirm) {
        setRulePreviewed(true);
        setMessage(biText("规则提案预演完成，尚未写入审核队列。", "Rule proposal previewed without writes."));
      } else {
        setRuleTitle("");
        setRuleStatement("");
        setRulePreviewed(false);
        setMessage(biText("规则纠正已进入审核收件箱，等待单独接受或拒绝。", "The rule correction is awaiting a separate accept or reject decision."));
        await refresh();
      }
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  async function previewReview(proposal: SemanticPatchProposal, decision: "accept" | "reject") {
    setBusy(`review-${proposal.proposalKey}`);
    setMessage("");
    try {
      await reviewSemanticPatch(proposal.proposalKey, decision, false);
      setReviewDraft({ proposalKey: proposal.proposalKey, decision });
      setMessage(decision === "accept"
        ? biText("接受影响已预演；确认后才会写入受信业务语义。", "Acceptance previewed; trusted semantics change only after confirmation.")
        : biText("拒绝影响已预演；确认后提案会关闭且不会应用。", "Rejection previewed; confirmation closes the proposal without applying it."));
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  async function confirmReview(proposal: SemanticPatchProposal) {
    if (!reviewDraft || reviewDraft.proposalKey !== proposal.proposalKey) return;
    setBusy(`review-${proposal.proposalKey}`);
    setMessage("");
    try {
      await reviewSemanticPatch(proposal.proposalKey, reviewDraft.decision, true);
      setMessage(reviewDraft.decision === "accept"
        ? biText("提案已接受并应用；来源、差异与审核决定均已保留。", "Proposal accepted and applied with source, diff, and review evidence preserved.")
        : biText("提案已拒绝，没有修改业务语义。", "Proposal rejected without changing business semantics."));
      setReviewDraft(null);
      await refresh();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="trustContextPanel" data-testid="trust-context-settings">
      <div className="trustContextLead">
        <div>
          <span className="storyMode"><Bilingual zh="可信语境" en="Trusted context" /></span>
          <h3><Bilingual zh="业务术语、规则与人工审核" en="Business context and human review" /></h3>
          <p className="quietText"><Bilingual zh="用户纠正和外部知识先成为不可变提案；只有显式接受且仍然新鲜时，才进入受信语义。" en="Corrections and external knowledge become immutable proposals first. They enter trusted semantics only after explicit acceptance while still current." /></p>
        </div>
        <div className="trustContextCounts">
          <span><strong>{pack?.counts.confirmedTerms ?? 0}</strong><small>{biText("术语", "terms")}</small></span>
          <span><strong>{pack?.counts.confirmedRules ?? 0}</strong><small>{biText("规则", "rules")}</small></span>
          <span><strong>{proposalCounts.pending ?? 0}</strong><small>{biText("待审核", "pending")}</small></span>
          <span><strong>{proposalCounts.stale ?? 0}</strong><small>{biText("已过期", "stale")}</small></span>
        </div>
      </div>

      <section className="semanticReviewInbox" aria-labelledby="semantic-review-title" data-testid="semantic-review-inbox">
        <div className="semanticReviewHeader">
          <div>
            <span className="storyMode"><Bilingual zh="Review Inbox" en="Review Inbox" /></span>
            <h4 id="semantic-review-title"><Bilingual zh="语义补丁审核收件箱" en="Semantic patch review inbox" /></h4>
          </div>
          <span className="semanticGuardrail"><Bilingual zh="不会自动学习或自动写入" en="No automatic learning or writes" /></span>
        </div>
        {reviewProposals.length ? (
          <div className="semanticProposalList">
            {reviewProposals.map((proposal) => {
              const isReviewable = proposal.status === "pending";
              const isStale = proposal.status === "stale";
              const draft = reviewDraft?.proposalKey === proposal.proposalKey ? reviewDraft : null;
              return (
                <article className={`semanticProposalCard status-${proposal.status}`} key={proposal.proposalKey} data-testid={`semantic-patch-${proposal.proposalKey}`}>
                  <div className="semanticProposalTopline">
                    <div>
                      <span>{proposalKind(proposal)} · {proposal.operation === "create" ? biText("新建", "create") : biText("更新", "update")}</span>
                      <h5>{proposalTitle(proposal)}</h5>
                    </div>
                    <span className="semanticStatusChip">{proposal.status}</span>
                  </div>
                  <div className="semanticProposalMeta">
                    <span>{biText("目标", "Target")}: {proposal.targetRef}</span>
                    <span>{biText("置信度", "Confidence")}: {Math.round(proposal.confidence * 100)}%</span>
                    <span>{biText("来源", "Source")}: {proposal.source?.name ?? proposal.sourceKey}</span>
                  </div>
                  <div className="semanticDiff" aria-label={biText("语义变更差异", "Semantic change diff")}>
                    <div><strong>{biText("当前", "Before")}</strong><pre>{compactJson(proposal.before)}</pre></div>
                    <div><strong>{biText("提议", "After")}</strong><pre>{compactJson(proposal.after)}</pre></div>
                  </div>
                  {isStale ? <p className="semanticStaleReason">{biText("提案已因上下文漂移失效：", "Proposal is stale because context drifted: ")}{proposal.freshness.mismatches.join(", ")}</p> : null}
                  {isReviewable || isStale ? (
                    <div className="semanticReviewActions">
                      {!draft ? <>
                        <button className="primaryButton" disabled={!isReviewable || busy === `review-${proposal.proposalKey}`} onClick={() => void previewReview(proposal, "accept")} type="button"><Bilingual zh="预演接受" en="Preview accept" /></button>
                        <button className="secondaryButton" disabled={busy === `review-${proposal.proposalKey}`} onClick={() => void previewReview(proposal, "reject")} type="button"><Bilingual zh="预演拒绝" en="Preview reject" /></button>
                      </> : <>
                        <button className={draft.decision === "accept" ? "primaryButton" : "dangerButton"} disabled={busy === `review-${proposal.proposalKey}`} onClick={() => void confirmReview(proposal)} type="button">
                          {draft.decision === "accept" ? biText("确认接受并应用", "Confirm accept and apply") : biText("确认拒绝", "Confirm reject")}
                        </button>
                        <button className="secondaryButton" onClick={() => setReviewDraft(null)} type="button"><Bilingual zh="取消" en="Cancel" /></button>
                      </>}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : <div className="semanticInboxEmpty"><strong><Bilingual zh="审核收件箱为空" en="Review inbox is empty" /></strong><span><Bilingual zh="提交用户纠正或通过 CLI 接入数据字典后，提案会出现在这里。" en="User corrections and data dictionaries proposed through the CLI appear here." /></span></div>}
      </section>

      <section className="semanticReviewInbox recallEvidencePanel" data-testid="confirmed-plan-memory">
        <div className="semanticInboxHeader">
          <div><span className="eyebrow"><Bilingual zh="受控复用" en="Governed reuse" /></span><h3><Bilingual zh="确认计划记忆与召回回执" en="Confirmed plan memory and recall receipts" /></h3></div>
          <span className="statusPill">{plans.filter((item) => item.status === "confirmed").length} {biText("项当前可召回", "current memories")}</span>
        </div>
        <p className="quietText"><Bilingual zh="历史计划只参与候选排序；字段歧义、跨表关系和执行权限仍按当前证据重新验证。" en="Historical plans rank candidates only. Field ambiguity, relationships, and execution authority are revalidated against current evidence." /></p>
        {plans.length ? <div className="trustContextList recallMemoryList">
          {plans.slice(0, 6).map((plan) => <div key={plan.memoryKey}><strong>{plan.question}</strong><span>{[plan.signature.measure, ...(plan.signature.groups ?? [])].filter(Boolean).join(" · ") || biText("结构化计划快照", "Structured plan snapshot")}</span><small>{plan.status} · {plan.memoryKey}</small></div>)}
        </div> : <p className="quietText"><Bilingual zh="确认并提升一个成功分析后，计划记忆会出现在这里。" en="Confirm and promote a successful analysis to create a plan memory." /></p>}
        {recallReceipts[0] ? <div className="recallReceiptSummary" data-testid="recall-receipt-summary"><strong><Bilingual zh="最近召回" en="Latest recall" /></strong><span>{recallReceipts[0].status} · {recallReceipts[0].returnedCandidates.length} {biText("个候选", "candidates")}</span><small>{biText("仅候选，不自动采用", "Candidate only; never auto-adopted")}</small></div> : null}
      </section>

      {(pack?.terms.length || pack?.rules.length || visibleQueries.length) ? (
        <div className="trustContextList">
          {pack?.terms.slice(0, 6).map((term) => (
            <div key={term.term_key}><strong>{term.canonical_name}</strong><span>{term.definition}</span><small>{term.scope_type}{term.scope_ref ? ` · ${term.scope_ref}` : ""}</small></div>
          ))}
          {pack?.rules.slice(0, 4).map((rule) => (
            <div key={rule.rule_key}><strong>{rule.title}</strong><span>{rule.statement}</span><small>{biText("工作区规则", "workspace rule")}</small></div>
          ))}
          {visibleQueries.slice(0, 4).map((query) => (
            <div key={query.query_key}><strong>{biText("确认问法", "Confirmed query")}</strong><span>{query.question}</span><small>{query.status}{query.stale_reason ? ` · ${query.stale_reason}` : ""}</small></div>
          ))}
        </div>
      ) : <p className="quietText">{biText("当前没有已确认业务语境。请先提交纠正提案，再从审核收件箱接受。", "No trusted business context yet. Submit a correction proposal, then accept it from the review inbox.")}</p>}

      <details className="advancedDetails compactAdvanced">
        <summary>{biText("提交术语纠正提案", "Propose a term correction")}</summary>
        <div className="trustContextForm">
          <label><span>{biText("术语", "Term")}</span><input value={termName} onChange={(event) => { setTermName(event.target.value); setTermPreviewed(false); }} /></label>
          <label className="wide"><span>{biText("定义", "Definition")}</span><textarea value={termDefinition} onChange={(event) => { setTermDefinition(event.target.value); setTermPreviewed(false); }} /></label>
          <label><span>{biText("别名", "Aliases")}</span><input placeholder={biText("逗号分隔", "Comma separated")} value={termAliases} onChange={(event) => { setTermAliases(event.target.value); setTermPreviewed(false); }} /></label>
          <label><span>{biText("作用域", "Scope")}</span><select value={termScope} onChange={(event) => { setTermScope(event.target.value); setTermPreviewed(false); }}><option value="workspace">workspace</option><option value="table">table</option><option value="field">field</option><option value="metric">metric</option></select></label>
          {termScope !== "workspace" ? <label><span>{biText("目标", "Target")}</span><input placeholder="table.field" value={termScopeRef} onChange={(event) => { setTermScopeRef(event.target.value); setTermPreviewed(false); }} /></label> : null}
          <div className="semanticProposalSubmit">
            <button className={termPreviewed ? "secondaryButton" : "primaryButton"} disabled={busy.startsWith("term") || !termName.trim() || !termDefinition.trim()} onClick={() => void runTermProposal(false)} type="button">{biText("预览提案", "Preview proposal")}</button>
            {termPreviewed ? <button className="primaryButton" disabled={busy.startsWith("term")} onClick={() => void runTermProposal(true)} type="button">{biText("确认提交审核", "Confirm submit for review")}</button> : null}
          </div>
        </div>
      </details>

      <details className="advancedDetails compactAdvanced">
        <summary>{biText("提交规则纠正提案", "Propose a rule correction")}</summary>
        <div className="trustContextForm">
          <label><span>{biText("标题", "Title")}</span><input value={ruleTitle} onChange={(event) => { setRuleTitle(event.target.value); setRulePreviewed(false); }} /></label>
          <label className="wide"><span>{biText("规则", "Rule")}</span><textarea value={ruleStatement} onChange={(event) => { setRuleStatement(event.target.value); setRulePreviewed(false); }} /></label>
          <div className="semanticProposalSubmit">
            <button className={rulePreviewed ? "secondaryButton" : "primaryButton"} disabled={busy.startsWith("rule") || !ruleTitle.trim() || !ruleStatement.trim()} onClick={() => void runRuleProposal(false)} type="button">{biText("预览提案", "Preview proposal")}</button>
            {rulePreviewed ? <button className="primaryButton" disabled={busy.startsWith("rule")} onClick={() => void runRuleProposal(true)} type="button">{biText("确认提交审核", "Confirm submit for review")}</button> : null}
          </div>
        </div>
      </details>
      {message ? <p className="trustContextMessage" role="status">{message}</p> : null}
    </section>
  );
}

export default TrustContextSettingsPanel;
