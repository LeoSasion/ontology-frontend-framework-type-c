import { getAppSection } from "../appSections";
import { buildProductReadiness } from "../productReadinessModel";
import type { WorkspaceStatus } from "../types";
import type { WorkspaceFlowModel } from "../workspaceFlowModel";
import { Bilingual, biText, LanguageToggle } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type TopBarProps = {
  activeSection: AppSection;
  status: WorkspaceStatus;
  flow: WorkspaceFlowModel;
  apiMode: "loading" | "live" | "fallback";
  pendingDraftCount: number;
  onOpenAgent: () => void;
};

export function TopBar({ activeSection, status, flow, apiMode, pendingDraftCount, onOpenAgent }: TopBarProps) {
  const sectionMeta = getAppSection(activeSection);
  const readiness = buildProductReadiness(status, {
    hasData: flow.hasData,
    hasEvidence: flow.hasEvidence,
    hasPendingDraft: flow.hasPendingDraft,
  });
  const showServiceDiagnostics = apiMode !== "live";
  const diagnosticTitle = apiMode === "loading"
    ? biText("正在连接本地服务", "Connecting to local services")
    : biText("本地数据服务尚未就绪", "Local data service is not ready");
  const diagnosticDetail = apiMode === "loading"
    ? biText("界面已打开，正在读取当前工作区。", "The interface is open and loading the current workspace.")
    : biText("请启动本地服务，或进入数据页检查数据接入状态。", "Start the local service or open Data to check the connection.");
  const diagnosticNotes = Array.isArray(status.health?.notes) ? status.health.notes.slice(0, 2) : [];

  return (
    <div className="topBarStack">
      <header className="topBar">
        <div className="topBarTitle">
          <span><Bilingual zh={sectionMeta.zh} en={sectionMeta.en} /></span>
          <h1><Bilingual {...sectionMeta.headline} /></h1>
        </div>
        <div className="topBarMeta">
          {pendingDraftCount > 0 ? (
            <button className="pendingDraftButton" data-testid="topbar-pending-drafts" onClick={onOpenAgent} type="button">
              <Icon name="check" />
              <span>{biText(`${pendingDraftCount} 个修改待确认`, `${pendingDraftCount} changes to review`)}</span>
            </button>
          ) : null}
          <div className="serviceState" title={apiMode === "live" ? readiness.label : diagnosticTitle}>
            <span className={`dot ${apiMode === "loading" ? "warn" : readiness.tone}`} />
            <span>{apiMode === "live" ? readiness.label : diagnosticTitle}</span>
          </div>
          <LanguageToggle />
        </div>
      </header>
      {showServiceDiagnostics ? (
        <section className={`serviceDiagnostics ${apiMode}`} data-testid="service-diagnostics" aria-label={biText("本地服务诊断", "Local service diagnostics")}>
          <div className="serviceDiagnosticsLead">
            <span className="serviceDiagnosticsIcon"><Icon name={apiMode === "loading" ? "query" : "lock"} /></span>
            <div>
              <strong data-testid="service-diagnostics-title">{diagnosticTitle}</strong>
              <p>{diagnosticDetail}</p>
            </div>
          </div>
          <details className="serviceDiagnosticsTechnical" data-testid="service-diagnostics-technical">
            <summary>{biText("启动命令和端口", "Startup commands and ports")}</summary>
            <div className="serviceDiagnosticsCommands" data-testid="service-diagnostics-commands">
              <code>npm run local:start</code>
              <span>{biText("界面 8686 · API 8787", "UI 8686 · API 8787")}</span>
            </div>
          </details>
          {diagnosticNotes.length ? (
            <div className="serviceDiagnosticsNotes" data-testid="service-diagnostics-notes">
              {diagnosticNotes.map((note) => <span key={note}>{note}</span>)}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
