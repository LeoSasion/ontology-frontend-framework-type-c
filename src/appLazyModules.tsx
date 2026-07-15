import { getAppSection } from "./appSections";
import type { AppSection } from "./components/Sidebar";
import { lazyWithRetry } from "./lazyWithRetry";

const loadAppMainView = () => import("./components/AppMainView").then((module) => ({ default: module.AppMainView }));
const loadTopBar = () => import("./components/TopBar").then((module) => ({ default: module.TopBar }));
const loadAgentPanel = () => import("./components/AgentPanel").then((module) => ({ default: module.AgentPanel }));
const loadDashboardCanvas = () => import("./components/DashboardCanvas").then((module) => ({ default: module.DashboardCanvas }));
const loadEvidenceView = () => import("./components/EvidenceView").then((module) => ({ default: module.EvidenceView }));
const loadHomeOverview = () => import("./components/HomeOverview").then((module) => ({ default: module.HomeOverview }));
const loadSettingsPanel = () => import("./components/SettingsPanel").then((module) => ({ default: module.SettingsPanel }));
const loadSourceWorkbench = () => import("./components/SourceWorkbench").then((module) => ({ default: module.SourceWorkbench }));
const loadViewWorkspace = () => import("./components/ViewWorkspace").then((module) => ({ default: module.ViewWorkspace }));

export const AppMainView = lazyWithRetry(loadAppMainView);
export const TopBar = lazyWithRetry(loadTopBar);
export const AgentPanel = lazyWithRetry(loadAgentPanel);
export const DashboardCanvas = lazyWithRetry(loadDashboardCanvas);
export const EvidenceView = lazyWithRetry(loadEvidenceView);
export const HomeOverview = lazyWithRetry(loadHomeOverview);
export const SettingsPanel = lazyWithRetry(loadSettingsPanel);
export const SourceWorkbench = lazyWithRetry(loadSourceWorkbench);
export const ViewWorkspace = lazyWithRetry(loadViewWorkspace);

export const sectionPreloaders: Record<AppSection, Array<() => Promise<unknown>>> = {
  home: [loadHomeOverview],
  dashboards: [loadDashboardCanvas],
  agent: [loadAgentPanel],
  evidence: [loadEvidenceView],
  sources: [loadSourceWorkbench],
  views: [loadViewWorkspace],
  settings: [loadSettingsPanel],
};

export const allSectionPreloaders = Array.from(new Set(Object.values(sectionPreloaders).flat()));
export const topBarPreloader = loadTopBar;

export function preloadModules(loaders: Array<() => Promise<unknown>>) {
  void Promise.allSettled(loaders.map((loader) => loader()));
}

export function scheduleIdlePreload(callback: () => void) {
  const browserWindow = window as Window & {
    requestIdleCallback?: (handler: () => void, options?: { timeout: number }) => number;
    cancelIdleCallback?: (handle: number) => void;
  };
  if (browserWindow.requestIdleCallback) {
    const handle = browserWindow.requestIdleCallback(callback, { timeout: 2500 });
    return () => browserWindow.cancelIdleCallback?.(handle);
  }
  const handle = window.setTimeout(callback, 900);
  return () => window.clearTimeout(handle);
}

function sectionText(section: AppSection, language: "zh" | "en", field: "loading" | "loadingDetail") {
  const text = getAppSection(section)[field];
  return language === "zh" ? text.zh : text.en;
}

const loadingFlow: AppSection[] = ["home", "sources", "views", "dashboards", "agent", "evidence"];

function sectionLabel(section: AppSection, language: "zh" | "en") {
  const meta = getAppSection(section);
  return language === "zh" ? meta.shortZh : meta.shortEn;
}

function loadingSupportText(section: AppSection, language: "zh" | "en") {
  if (section === "dashboards") {
    return language === "zh"
      ? "看板打开后会保留当前筛选、证据入口和全局 Agent 上下文。"
      : "The dashboard keeps current filters, evidence entry points, and global Agent context.";
  }
  if (section === "sources") {
    return language === "zh"
      ? "数据源打开后优先展示导入、画像和下一步建议，高级配置保持折叠。"
      : "Sources open to import, profiling, and next steps first; advanced controls stay folded.";
  }
  if (section === "agent") {
    return language === "zh"
      ? "Agent 面板会读取当前工作区和待确认草案，加载期间不会执行写入。"
      : "The Agent reads the workspace and pending drafts; no write runs while loading.";
  }
  return language === "zh"
    ? "外壳和当前工作区已保持，模块载入完成后可继续刚才的流程。"
    : "The shell and workspace stay in place; continue the same flow after the module loads.";
}

function LoadingFlowRail({ section, language }: { section: AppSection; language: "zh" | "en" }) {
  const currentIndex = loadingFlow.includes(section) ? loadingFlow.indexOf(section) : loadingFlow.length - 1;
  return (
    <ol className="moduleLoadingFlow" aria-label={language === "zh" ? "工作流加载进度" : "Workflow loading progress"}>
      {loadingFlow.map((step, index) => (
        <li
          key={step}
          className={index < currentIndex ? "complete" : index === currentIndex ? "current" : "pending"}
          data-testid={index === currentIndex ? "lazy-section-current-step" : undefined}
        >
          <span>{index + 1}</span>
          <strong>{sectionLabel(step, language)}</strong>
        </li>
      ))}
    </ol>
  );
}

export function ModuleLoadingPanel({ section, language }: { section: AppSection; language: "zh" | "en" }) {
  const loadingBody = section === "dashboards" ? (
    <div className="dashboardLoadingFrame" aria-hidden="true">
      <div className="dashboardLoadingToolbar">
        <span />
        <span />
        <span />
      </div>
      <div className="dashboardLoadingGrid">
        <div className="dashboardLoadingLead">
          <span />
          <strong />
          <small />
        </div>
        <div className="dashboardLoadingMetric" />
        <div className="dashboardLoadingMetric" />
        <div className="dashboardLoadingMetric" />
        <div className="dashboardLoadingMetric" />
        <div className="dashboardLoadingWide" />
        <div className="dashboardLoadingChart" />
        <div className="dashboardLoadingChart" />
      </div>
    </div>
  ) : (
    <div className="moduleSkeleton" aria-hidden="true">
      <span />
      <span />
      <span />
      <span />
    </div>
  );

  if (section === "dashboards") {
    return (
      <section className="mainPanel moduleLoadingPanel dashboardModuleLoadingPanel" data-testid="lazy-section-loading" aria-busy="true">
        <div className="dashboardLoadingHeader">
          <div>
            <span className="storyMode">{language === "zh" ? "看板工作台" : "Dashboard workbench"}</span>
            <h2>{sectionText(section, language, "loading")}</h2>
            <p>{sectionText(section, language, "loadingDetail")}</p>
          </div>
          <div className="dashboardLoadingStatus" aria-hidden="true">
            <span />
            <strong>{language === "zh" ? "读取中" : "Loading"}</strong>
          </div>
        </div>
        <LoadingFlowRail section={section} language={language} />
        {loadingBody}
        <div className="moduleLoadingSupport" data-testid="lazy-section-loading-support">
          <strong>{language === "zh" ? "加载期间保持上下文" : "Context stays intact"}</strong>
          <span>{loadingSupportText(section, language)}</span>
        </div>
      </section>
    );
  }
  return (
    <section className="mainPanel moduleLoadingPanel" data-testid="lazy-section-loading" aria-busy="true">
      <div className="moduleLoadingLead">
        <p className="eyebrow">{language === "zh" ? "模块加载" : "Loading module"}</p>
        <h2>{sectionText(section, language, "loading")}</h2>
        <p>{sectionText(section, language, "loadingDetail")}</p>
      </div>
      <LoadingFlowRail section={section} language={language} />
      {loadingBody}
      <div className="moduleLoadingSupport" data-testid="lazy-section-loading-support">
        <strong>{language === "zh" ? "加载期间保持上下文" : "Context stays intact"}</strong>
        <span>{loadingSupportText(section, language)}</span>
      </div>
    </section>
  );
}

export function InspectorLoadingPanel({ language }: { language: "zh" | "en" }) {
  return (
    <aside className="inspector inspectorLoadingPanel" data-testid="lazy-inspector-loading" aria-busy="true">
      <div className="inspectorLoadingHeader">
        <p className="eyebrow">{language === "zh" ? "上下文抽屉" : "Context drawer"}</p>
        <h2>{language === "zh" ? "正在准备当前对象" : "Preparing current object"}</h2>
      </div>
      <div className="inspectorLoadingStack" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <p className="inspectorLoadingHint">
        {language === "zh"
          ? "这里会显示当前页面对象、证据入口和待确认草案。"
          : "This area will show the current object, evidence entry points, and pending drafts."}
      </p>
    </aside>
  );
}
