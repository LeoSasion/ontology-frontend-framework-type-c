import type { AgentAskResult, ImportPreview } from "../types";
import { Bilingual, biText, translateName, translatePipelineStage } from "./Bilingual";

type InspectorEvidenceDetailsProps = {
  agent: AgentAskResult;
  lastActionResult: Record<string, unknown> | null;
  preview: ImportPreview;
};

export function InspectorEvidenceDetails({ agent, lastActionResult, preview }: InspectorEvidenceDetailsProps) {
  return (
    <>
      <details className="contextReservePanel">
        <summary>{biText("扩展能力", "Extended tools")}</summary>
        <h2><Bilingual zh="需要深度编辑时再展开" en="Expand only for deep editing" /></h2>
        <ul>
          <li>{biText("组件属性、字段语义、公式 DSL", "Widget properties, field semantics, formula DSL")}</li>
          <li>{biText("关系预览、证据链、Agent 影响范围", "Relationship preview, evidence chain, Agent impact scope")}</li>
        </ul>
      </details>

      <details className="advancedDetails inspectorDetails">
        <summary>{biText("技术细节", "Technical details")}</summary>
        <section>
          <span className="eyebrow">{biText("分析链路", "Analysis chain")}</span>
          <ol className="stageList">
            {preview.sourcePipelineContract.stages.map((stage, index) => (
              <li key={stage.id}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{stage.id}</strong>
                <small><Bilingual inline {...translatePipelineStage(stage.label)} /></small>
              </li>
            ))}
          </ol>
        </section>
        <section>
          <span className="eyebrow">{biText("业务语义", "Business semantics")}</span>
          <h2><Bilingual {...translateName(agent.coreSemanticRuntime.label)} /></h2>
          <div className="chipGrid">
            {agent.coreSemanticRuntime.semanticHints.map((hint) => <span key={hint.semantic}>{hint.semantic} · {hint.role}</span>)}
          </div>
        </section>
        <section>
          <span className="eyebrow">{biText("证据文件", "Evidence files")}</span>
          <ul className="evidenceList">
            {agent.ontology.evidenceFiles.map((file) => <li key={file}>{file}</li>)}
          </ul>
        </section>
        {lastActionResult ? (
          <section>
            <span className="eyebrow">{biText("动作 JSON", "Action JSON")}</span>
            <pre>{JSON.stringify(lastActionResult, null, 2)}</pre>
          </section>
        ) : null}
      </details>
    </>
  );
}
