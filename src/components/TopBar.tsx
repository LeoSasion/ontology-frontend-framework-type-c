import { getAppSection } from "../appSections";
import type { WorkspaceStatus } from "../types";
import { Bilingual, biText, LanguageToggle } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";
import { buildProductReadiness } from "../productReadinessModel";

type TopBarProps = {
  activeSection: AppSection;
  status: WorkspaceStatus;
  apiMode: "loading" | "live" | "fallback";
};

export function TopBar({ activeSection, status, apiMode }: TopBarProps) {
  const showServiceDiagnostics = apiMode !== "live";
  const sectionMeta = getAppSection(activeSection);
  const headline = sectionMeta.headline;
  const diagnosticTitle = apiMode === "loading"
    ? biText("正在连接本地服务", "Connecting to local services")
    : biText("等待导入数据", "Waiting for data import");
  const diagnosticDetail = apiMode === "loading"
    ? biText("前端已打开，正在等待本地数据服务返回工作区状态。", "The workspace is open and waiting for the local data service.")
    : biText("没有可用数据表。请先进入数据源工作台导入本地文件或文件夹。", "No data tables are available. Open the source workbench to import local files or folders.");
  const diagnosticNotes = Array.isArray(status.health?.notes) ? status.health.notes.slice(0, 2) : [];
  const readiness = buildProductReadiness(status);

  return (
    <div className={activeSection === "home" || activeSection === "agent" ? "topBarStack" : "topBarStack workbenchTopBar"}>
      <header className="topBar">
        <div>
          <p className="kicker">{biText("可信分析助手", "Trusted analysis assistant")}</p>
          <h1>
            <Bilingual {...headline} />
          </h1>
        </div>
        <div className="topBarMeta">
          <LanguageToggle />
          <div className="statusPill">
            <Icon name="lock" />
            <span>
              {apiMode === "live"
                ? biText("数据服务已连接", "Data service connected")
                : apiMode === "loading"
                  ? biText("正在连接", "Connecting")
                  : biText("待导入", "Import needed")}
            </span>
          </div>
          <div className="statusPill">
            <span className={`dot ${apiMode === "loading" ? "warn" : readiness.tone}`} />
            <span>{apiMode === "loading" ? biText("连接中", "Connecting") : readiness.label}</span>
          </div>
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
            <summary>{biText("查看启动命令和端口", "View startup commands and ports")}</summary>
            <div className="serviceDiagnosticsCommands" data-testid="service-diagnostics-commands">
              <code>npm run dev</code>
              <code>npm run api</code>
              <span>{biText("前端 8686 · API 8787", "Frontend 8686 · API 8787")}</span>
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
