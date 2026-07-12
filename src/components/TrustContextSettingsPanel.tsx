import { useEffect, useState } from "react";
import { getConfirmedQueries, getContextPack, saveContextRule, saveContextTerm } from "../apiTrust";
import type { ConfirmedQuery, ContextPackPayload } from "../types";
import { Bilingual, biText } from "./Bilingual";
import "../styles/trustContext.css";

export function TrustContextSettingsPanel() {
  const [pack, setPack] = useState<ContextPackPayload["contextPack"] | null>(null);
  const [queries, setQueries] = useState<ConfirmedQuery[]>([]);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [termName, setTermName] = useState("");
  const [termDefinition, setTermDefinition] = useState("");
  const [termAliases, setTermAliases] = useState("");
  const [termScope, setTermScope] = useState("workspace");
  const [termScopeRef, setTermScopeRef] = useState("");
  const [ruleTitle, setRuleTitle] = useState("");
  const [ruleStatement, setRuleStatement] = useState("");
  const visibleQueries = queries.filter((item) => item.status === "confirmed" || item.status === "stale");

  async function refresh() {
    const [result, queryResult] = await Promise.all([getContextPack(), getConfirmedQueries()]);
    setPack(result.contextPack);
    setQueries(queryResult.confirmedQueries);
  }

  useEffect(() => { void refresh(); }, []);

  async function saveTerm() {
    if (!termName.trim() || !termDefinition.trim()) return;
    setBusy("term");
    setMessage("");
    try {
      await saveContextTerm({
        name: termName.trim(),
        definition: termDefinition.trim(),
        aliases: termAliases.split(/[,，]/).map((item) => item.trim()).filter(Boolean),
        scopeType: termScope,
        scopeRef: termScope === "workspace" ? "" : termScopeRef.trim(),
        status: "confirmed",
        source: "manual",
        evidenceRefs: ["manual-confirmation"],
        confirm: true,
      });
      setTermName("");
      setTermDefinition("");
      setTermAliases("");
      setTermScopeRef("");
      setMessage(biText("术语已确认并写入当前工作区。", "Term confirmed in this workspace."));
      await refresh();
    } finally {
      setBusy("");
    }
  }

  async function saveRule() {
    if (!ruleTitle.trim() || !ruleStatement.trim()) return;
    setBusy("rule");
    setMessage("");
    try {
      await saveContextRule({
        title: ruleTitle.trim(),
        statement: ruleStatement.trim(),
        ruleType: "other",
        status: "confirmed",
        source: "manual",
        evidenceRefs: ["manual-confirmation"],
        confirm: true,
      });
      setRuleTitle("");
      setRuleStatement("");
      setMessage(biText("规则已确认并写入当前工作区。", "Rule confirmed in this workspace."));
      await refresh();
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="trustContextPanel" data-testid="trust-context-settings">
      <div className="trustContextLead">
        <div>
          <span className="storyMode"><Bilingual zh="可信语境" en="Trusted context" /></span>
          <h3><Bilingual zh="业务术语与规则" en="Business terms and rules" /></h3>
        </div>
        <div className="trustContextCounts">
          <span><strong>{pack?.counts.confirmedTerms ?? 0}</strong><small>{biText("术语", "terms")}</small></span>
          <span><strong>{pack?.counts.confirmedRules ?? 0}</strong><small>{biText("规则", "rules")}</small></span>
          <span><strong>{queries.filter((item) => item.status === "confirmed").length}</strong><small>{biText("确认问法", "queries")}</small></span>
        </div>
      </div>

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
      ) : <p className="quietText">{biText("当前没有已确认业务语境。仅在实际使用中需要时添加。", "No confirmed business context yet. Add it only when real usage requires it.")}</p>}

      <details className="advancedDetails compactAdvanced">
        <summary>{biText("添加业务术语", "Add a business term")}</summary>
        <div className="trustContextForm">
          <label><span>{biText("术语", "Term")}</span><input value={termName} onChange={(event) => setTermName(event.target.value)} /></label>
          <label className="wide"><span>{biText("定义", "Definition")}</span><textarea value={termDefinition} onChange={(event) => setTermDefinition(event.target.value)} /></label>
          <label><span>{biText("别名", "Aliases")}</span><input placeholder={biText("逗号分隔", "Comma separated")} value={termAliases} onChange={(event) => setTermAliases(event.target.value)} /></label>
          <label><span>{biText("作用域", "Scope")}</span><select value={termScope} onChange={(event) => setTermScope(event.target.value)}><option value="workspace">workspace</option><option value="table">table</option><option value="field">field</option><option value="metric">metric</option></select></label>
          {termScope !== "workspace" ? <label><span>{biText("目标", "Target")}</span><input placeholder="table.field" value={termScopeRef} onChange={(event) => setTermScopeRef(event.target.value)} /></label> : null}
          <button className="primaryButton" disabled={busy === "term" || !termName.trim() || !termDefinition.trim()} onClick={() => void saveTerm()} type="button">{busy === "term" ? biText("写入中", "Saving") : biText("确认并保存", "Confirm and save")}</button>
        </div>
      </details>

      <details className="advancedDetails compactAdvanced">
        <summary>{biText("添加工作区规则", "Add a workspace rule")}</summary>
        <div className="trustContextForm">
          <label><span>{biText("标题", "Title")}</span><input value={ruleTitle} onChange={(event) => setRuleTitle(event.target.value)} /></label>
          <label className="wide"><span>{biText("规则", "Rule")}</span><textarea value={ruleStatement} onChange={(event) => setRuleStatement(event.target.value)} /></label>
          <button className="primaryButton" disabled={busy === "rule" || !ruleTitle.trim() || !ruleStatement.trim()} onClick={() => void saveRule()} type="button">{busy === "rule" ? biText("写入中", "Saving") : biText("确认并保存", "Confirm and save")}</button>
        </div>
      </details>
      {message ? <p className="trustContextMessage" role="status">{message}</p> : null}
    </section>
  );
}

export default TrustContextSettingsPanel;
