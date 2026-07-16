import "./workspaceContextPanels.css";
import { useEffect, useState } from "react";
import { getWorkspaceManifest } from "../apiWorkspaceContext";
import type { WorkspaceManifestSummary } from "../typesWorkspaceContext";
import { Bilingual, biText } from "./Bilingual";

export default function EvidenceWorkspaceManifestPanel() {
  const [manifest, setManifest] = useState<WorkspaceManifestSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getWorkspaceManifest(controller.signal)
      .then((result) => setManifest(result.workspaceManifest))
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => controller.abort();
  }, []);

  return (
    <article className="wideArticle workspaceManifestPanel" data-testid="evidence-workspace-manifest">
      <div className="tileHeader">
        <div>
          <h3><Bilingual zh="工作区事实清单" en="Workspace fact manifest" /></h3>
          <span><Bilingual zh="把数据、口径、关系、Skills 和运行边界绑定到同一个可追溯指纹。" en="Binds data, semantics, relationships, Skills, and runtime boundaries to one traceable fingerprint." /></span>
        </div>
        {manifest ? <span className={`workspaceContextPill ${manifest.status}`}>{manifest.status}</span> : null}
      </div>
      {error ? <p className="workspaceContextError" role="alert">{error}</p> : null}
      {!manifest && !error ? <div className="workspaceContextLoading" aria-busy="true"><span /><span /><span /></div> : null}
      {manifest ? (
        <>
          <dl className="definitionGrid workspaceManifestFacts">
            <div><dt>{biText("数据表", "Tables")}</dt><dd>{manifest.sourceSnapshot.tableCount}</dd></div>
            <div><dt>{biText("字段", "Fields")}</dt><dd>{manifest.sourceSnapshot.fieldCount}</dd></div>
            <div><dt>{biText("已确认业务含义", "Confirmed meanings")}</dt><dd>{manifest.semanticSnapshot.confirmedBusinessMeanings}</dd></div>
            <div><dt>{biText("已验证关系", "Validated links")}</dt><dd>{manifest.semanticSnapshot.validatedRelationshipCount}/{manifest.semanticSnapshot.relationshipCount}</dd></div>
            <div><dt>{biText("启用 Skills", "Enabled Skills")}</dt><dd>{manifest.runtimeSnapshot.enabledAnalyticalSkillCount}</dd></div>
            <div><dt>{biText("可用于规划", "Usable for planning")}</dt><dd>{manifest.usableForPlanning ? biText("是", "Yes") : biText("否", "No")}</dd></div>
          </dl>
          {manifest.blockers.length || manifest.warnings.length ? <p className="workspaceManifestWarnings">{[...manifest.blockers, ...manifest.warnings].join(" · ")}</p> : null}
          <details className="advancedDetails compactAdvanced" data-testid="evidence-workspace-manifest-technical">
            <summary>{biText("查看清单技术指纹", "View manifest fingerprints")}</summary>
            <dl className="workspaceManifestFingerprints">
              <div><dt>manifest</dt><dd>{manifest.fingerprint}</dd></div>
              {Object.entries(manifest.componentFingerprints).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}
            </dl>
          </details>
        </>
      ) : null}
    </article>
  );
}
