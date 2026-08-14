import { useEffect, useRef, useState } from "react";
import { getKnowledgeSourceAdapters, getKnowledgeSources, proposeKnowledgeSource } from "../apiTrust";
import type { KnowledgeSource, KnowledgeSourceAdapter } from "../types";
import { Bilingual, biText } from "./Bilingual";
import "./settingsKnowledgeSourcePanel.css";

type Draft = { input: string; adapter: string; sourceType: "data-dictionary" | "documentation"; sourceName: string };

export default function SettingsKnowledgeSourcePanel() {
  const [adapters, setAdapters] = useState<KnowledgeSourceAdapter[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [input, setInput] = useState("");
  const [adapter, setAdapter] = useState("auto");
  const [sourceType, setSourceType] = useState<Draft["sourceType"]>("documentation");
  const [sourceName, setSourceName] = useState("");
  const [pending, setPending] = useState<Draft | null>(null);
  const [previewCount, setPreviewCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const requestRef = useRef(0);

  async function refresh() {
    const requestId = ++requestRef.current;
    const [adapterPayload, sourcePayload] = await Promise.all([getKnowledgeSourceAdapters(), getKnowledgeSources()]);
    if (requestRef.current !== requestId) return;
    setAdapters(adapterPayload.adapters ?? []);
    setSources(sourcePayload.sources ?? []);
  }

  useEffect(() => {
    void refresh().catch((error) => setNotice(error instanceof Error ? error.message : String(error)));
    return () => { requestRef.current += 1; };
  }, []);

  async function run(confirm: boolean) {
    const draft = pending ?? { input: input.trim(), adapter, sourceType, sourceName: sourceName.trim() };
    if (!draft.input) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await proposeKnowledgeSource({ ...draft, confirm });
      if (!confirm) {
        const proposals = Array.isArray(result.proposals) ? result.proposals : [];
        setPreviewCount(proposals.length);
        setPending(draft);
        setNotice(biText("文件已只读解析；原文未入库，提案尚未写入。", "The file was parsed read-only; raw content was not stored and proposals were not written."));
      } else {
        setPending(null);
        setInput("");
        setSourceName("");
        setPreviewCount(0);
        setNotice(biText("知识快照与审核提案已保存；仍需在语义收件箱审核后才会生效。", "Knowledge snapshot and review proposals saved. They take effect only after semantic review."));
        await refresh();
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  return <section className="knowledgeSourcePanel" data-testid="settings-knowledge-sources">
    <div className="settingsSectionHeading"><div><strong><Bilingual zh="知识源" en="Knowledge sources" /></strong><p><Bilingual zh="只接收本地受限 JSON/Markdown；解析后先进入审核，不直接改变答案口径。" en="Accepts bounded local JSON/Markdown only. Parsed knowledge enters review before it can change answer semantics." /></p></div><span className="settingsStatusPill">{sources.length} {biText("个快照", "snapshots")}</span></div>
    <div className="knowledgeGuardrails"><span>{adapters.filter((item) => item.extensions.length).map((item) => item.extensions.join(" / ")).join(" · ") || ".json · .md"}</span><span>{biText("网络 / SQL / 代码：禁止", "Network / SQL / code: denied")}</span><span>{biText("原文与业务行：不保存", "Raw documents and rows: not stored")}</span></div>
    <details className="runtimeCatalogDetails"><summary>{biText("添加本地知识源", "Add a local knowledge source")}</summary><div className="knowledgeSourceForm">
      <label className="wide"><span>{biText("本地文件路径", "Local file path")}</span><input disabled={busy || Boolean(pending)} onChange={(event) => setInput(event.target.value)} placeholder="C:\\knowledge\\dictionary.json" value={input} /></label>
      <label><span>{biText("解析器", "Adapter")}</span><select disabled={busy || Boolean(pending)} onChange={(event) => setAdapter(event.target.value)} value={adapter}><option value="auto">auto</option>{adapters.filter((item) => item.extensions.length).map((item) => <option key={item.adapterId} value={item.adapterId}>{item.label}</option>)}</select></label>
      <label><span>{biText("类型", "Type")}</span><select disabled={busy || Boolean(pending)} onChange={(event) => setSourceType(event.target.value as Draft["sourceType"])} value={sourceType}><option value="documentation">documentation</option><option value="data-dictionary">data-dictionary</option></select></label>
      <label><span>{biText("名称（可空）", "Name (optional)")}</span><input disabled={busy || Boolean(pending)} onChange={(event) => setSourceName(event.target.value)} value={sourceName} /></label>
      {!pending ? <button className="secondaryButton" disabled={busy || !input.trim()} onClick={() => void run(false)} type="button">{biText("只读预演", "Read-only preview")}</button> : <div className="knowledgeConfirmation"><span>{previewCount} {biText("项提案", "proposals")}</span><button className="primaryButton" disabled={busy} onClick={() => void run(true)} type="button">{biText("确认进入审核", "Confirm for review")}</button><button className="secondaryButton" disabled={busy} onClick={() => setPending(null)} type="button">{biText("取消", "Cancel")}</button></div>}
    </div></details>
    {sources.length ? <div className="knowledgeSourceList">{sources.slice(0, 5).map((source) => <div key={source.sourceKey}><strong>{source.name}</strong><span>{source.sourceType} · {source.adapterId}</span><small>{source.snapshot?.counts?.terms ?? 0} terms · {source.snapshot?.counts?.rules ?? 0} rules · {source.snapshot?.counts?.fieldSemantics ?? 0} fields</small></div>)}</div> : null}
    {notice ? <p className="settingsInlineMessage" role="status">{notice}</p> : null}
  </section>;
}
