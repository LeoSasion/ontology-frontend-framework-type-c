import { useEffect, useMemo, useRef, useState } from "react";
import { proveFederationPlan } from "../apiFederation";
import type { DataConnectorConfig, RelationshipRecord } from "../types";
import type { FederationProof } from "../typesFederation";
import { Bilingual, biText } from "./Bilingual";

type FederationProofPanelProps = {
  workspaceId: string;
  connectors: DataConnectorConfig[];
  relationships: RelationshipRecord[];
};

function splitFields(value: string) {
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
}

export default function FederationProofPanel({ workspaceId, connectors, relationships }: FederationProofPanelProps) {
  const eligible = useMemo(
    () => connectors.filter((connector) => connector.status === "active" && connector.lastSyncStatus === "success" && connector.config.targetTableKey),
    [connectors],
  );
  const [leftConnector, setLeftConnector] = useState(eligible[0]?.connectorKey ?? "");
  const [rightConnector, setRightConnector] = useState(eligible[1]?.connectorKey ?? "");
  const [leftFields, setLeftFields] = useState("");
  const [rightFields, setRightFields] = useState("");
  const [relationshipKey, setRelationshipKey] = useState("");
  const [grain, setGrain] = useState(String(eligible[0]?.config.targetTableKey ?? ""));
  const [entityKey, setEntityKey] = useState("");
  const [proof, setProof] = useState<FederationProof | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const requestRef = useRef<{ id: number; workspaceId: string; controller: AbortController } | null>(null);

  useEffect(() => {
    requestRef.current?.controller.abort();
    requestRef.current = null;
    setProof(null);
    setError("");
    setBusy(false);
    setLeftConnector(eligible[0]?.connectorKey ?? "");
    setRightConnector(eligible[1]?.connectorKey ?? "");
    setRelationshipKey("");
    setGrain(String(eligible[0]?.config.targetTableKey ?? ""));
  }, [workspaceId, eligible]);

  const left = eligible.find((connector) => connector.connectorKey === leftConnector);
  const right = eligible.find((connector) => connector.connectorKey === rightConnector);
  const selectedTables = new Set([left?.config.targetTableKey, right?.config.targetTableKey].filter(Boolean));
  const relationshipOptions = relationships.filter(
    (relationship) => selectedTables.has(relationship.left_table_key) && selectedTables.has(relationship.right_table_key),
  );
  const grainOptions = [...selectedTables].filter((value): value is string => typeof value === "string" && Boolean(value));

  function selectSource(side: "left" | "right", connectorKey: string) {
    const connector = eligible.find((item) => item.connectorKey === connectorKey);
    if (side === "left") setLeftConnector(connectorKey);
    else setRightConnector(connectorKey);
    setRelationshipKey("");
    setProof(null);
    setError("");
    if (side === "left" && connector?.config.targetTableKey) setGrain(connector.config.targetTableKey);
  }
  const canRun = Boolean(
    leftConnector && rightConnector && leftConnector !== rightConnector && splitFields(leftFields).length
    && splitFields(rightFields).length && relationshipKey && grain.trim() && entityKey.trim(),
  );

  async function runProof() {
    if (!canRun) return;
    requestRef.current?.controller.abort();
    const controller = new AbortController();
    const id = Date.now();
    const expectedWorkspace = workspaceId;
    requestRef.current = { id, workspaceId: expectedWorkspace, controller };
    setBusy(true);
    setError("");
    setProof(null);
    try {
      const result = await proveFederationPlan({
        connectors: [leftConnector, rightConnector],
        projections: {
          [leftConnector]: splitFields(leftFields),
          [rightConnector]: splitFields(rightFields),
        },
        relationships: [relationshipKey],
        grain: grain.trim(),
        entityKey: entityKey.trim(),
        filters: [],
      }, controller.signal);
      if (requestRef.current?.id !== id || requestRef.current.workspaceId !== expectedWorkspace || result.workspaceId !== expectedWorkspace) return;
      setProof(result);
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (requestRef.current?.id !== id || requestRef.current.workspaceId !== expectedWorkspace) return;
      setError(reason instanceof Error ? reason.message : biText("联邦证明失败", "Federation proof failed"));
    } finally {
      if (requestRef.current?.id === id) {
        requestRef.current = null;
        setBusy(false);
      }
    }
  }

  if (eligible.length < 2) {
    return (
      <article className="workbenchPanel advancedPanel" data-testid="federation-proof-panel">
        <div className="tileHeader"><h3><Bilingual zh="只读联邦证明" en="Read-only federation proof" /></h3></div>
        <p>{biText("至少需要两个已启用且同步成功的 Adapter 连接。证明只检查计划，不执行跨源查询。", "At least two active, successfully synced Adapter connections are required. The proof checks the plan only; it never runs a cross-source query.")}</p>
      </article>
    );
  }

  return (
    <article className="workbenchPanel advancedPanel widePanel" data-testid="federation-proof-panel">
      <div className="tileHeader">
        <h3><Bilingual zh="只读联邦证明" en="Read-only federation proof" /></h3>
        <span>{biText("不执行 · 不落库 · 不复制业务行", "No execution · no writes · no row copy")}</span>
      </div>
      <div className="connectorBusinessLead">
        <strong>{biText("先证明多个来源能否组成安全计划", "Prove that multiple sources can form a safe plan")}</strong>
        <span>{biText("只有来源指纹、语义、关系版本、实体键、粒度和预算全部成立，才会显示“可证明”。", "The plan is provable only when source fingerprints, semantics, relationship versions, entity key, grain, and budgets all pass.")}</span>
      </div>
      <div className="formGrid">
        <label><span>{biText("来源 A", "Source A")}</span><select value={leftConnector} onChange={(event) => selectSource("left", event.target.value)}>{eligible.map((connector) => <option key={connector.connectorKey} value={connector.connectorKey}>{connector.name}</option>)}</select></label>
        <label><span>{biText("来源 B", "Source B")}</span><select value={rightConnector} onChange={(event) => selectSource("right", event.target.value)}>{eligible.map((connector) => <option key={connector.connectorKey} value={connector.connectorKey}>{connector.name}</option>)}</select></label>
        <label><span>{biText("A 投影字段（逗号分隔）", "A projected fields (comma-separated)")}</span><input value={leftFields} onChange={(event) => setLeftFields(event.target.value)} placeholder="id, date, amount" /></label>
        <label><span>{biText("B 投影字段（逗号分隔）", "B projected fields (comma-separated)")}</span><input value={rightFields} onChange={(event) => setRightFields(event.target.value)} placeholder="id, category" /></label>
        <label><span>{biText("已验证关系", "Validated relationship")}</span><select value={relationshipKey} onChange={(event) => setRelationshipKey(event.target.value)}><option value="">{biText("请选择", "Select")}</option>{relationshipOptions.map((relationship) => <option key={relationship.relation_key} value={relationship.relation_key}>{relationship.name}</option>)}</select></label>
        <label><span>{biText("实体键（表.字段）", "Entity key (table.field)")}</span><input value={entityKey} onChange={(event) => setEntityKey(event.target.value)} placeholder={`${left?.config.targetTableKey ?? "table"}.id`} /></label>
        <label className="wideField"><span>{biText("分析粒度表", "Analytical grain table")}</span><select value={grainOptions.includes(grain) ? grain : ""} onChange={(event) => setGrain(event.target.value)}><option value="">{biText("请选择", "Select")}</option>{grainOptions.map((table) => <option key={table} value={table}>{table}</option>)}</select></label>
      </div>
      <div className="panelActions"><button className="primaryButton" type="button" disabled={!canRun || busy} onClick={runProof}>{busy ? biText("正在验证…", "Proving…") : biText("验证联邦计划", "Prove federation plan")}</button></div>
      {error ? <p className="statusError" role="alert">{error}</p> : null}
      {proof ? (
        <div className={proof.provable ? "successNotice" : "warningNotice"} data-testid="federation-proof-result">
          <strong>{proof.provable ? biText("计划可证明，但尚未执行", "Plan is provable, but not executed") : biText("计划被阻断", "Plan is blocked")}</strong>
          <span>{proof.provable ? biText("所有只读门禁均通过。该结果不授予执行、物化或写入权限。", "All read-only gates passed. This result grants no execution, materialization, or write permission.") : biText(`仍有 ${proof.blockers.length} 个条件未满足。`, `${proof.blockers.length} conditions remain unresolved.`)}</span>
          <details className="advancedDetails compactAdvanced">
            <summary>{biText("查看门禁与指纹", "View gates and fingerprint")}</summary>
            <ul>{Object.entries(proof.gates).map(([key, gate]) => <li key={key}><strong>{key}</strong> · {gate.status}{gate.blockers.length ? ` · ${gate.blockers.join(", ")}` : ""}</li>)}</ul>
            <small>{proof.proofFingerprint}</small>
          </details>
        </div>
      ) : null}
    </article>
  );
}
