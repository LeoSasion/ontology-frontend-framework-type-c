import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

const closureItems = [
  {
    key: "service-health",
    tone: "ok",
    icon: "check",
    titleZh: "刷新不白屏",
    titleEn: "Refresh-safe shell",
    detailZh: "8686 使用 strictPort；前端先显示连接中，API 失败时才进入可解释 fallback。",
    detailEn: "Port 8686 uses strictPort. The UI shows connecting first and falls back only with an explainable state.",
    command: "npm run dev",
    proof: "frontend-loading-state-not-fallback-sample",
  },
  {
    key: "cli-bridge",
    tone: "ok",
    icon: "query",
    titleZh: "本地 BI 操作已并入当前工作区",
    titleEn: "Local BI operations are part of this workspace",
    detailZh: "导入、视图、看板、筛选、关系、公式、连接和安全恢复都走当前项目的沙箱与确认机制。",
    detailEn: "Import, views, dashboards, filters, relationships, formulas, connectors, and safe restore now use this workspace sandbox and confirmation flow.",
    command: "python tools/bi_cli.py --json cli-capabilities",
    proof: "b-bi-cli-bridge-core-areas",
  },
  {
    key: "empty-runtime",
    tone: "ok",
    icon: "source",
    titleZh: "空工作区只引导导入",
    titleEn: "Empty workspaces guide import",
    detailZh: "没有数据时不加载内置素材、不自动查询、不预热 Agent，只引导用户导入本地文件或文件夹。",
    detailEn: "With no data, the app loads no bundled material, runs no automatic query, warms up no Agent, and guides users to import local files or folders.",
    command: "npm run verify",
    proof: "empty-workspace-data-boundary",
  },
  {
    key: "widget-catalog",
    tone: "ok",
    icon: "dashboard",
    titleZh: "看板阅读和编辑动作集中可验收",
    titleEn: "Dashboard reading and editing actions are testable together",
    detailZh: "从看总量、看排行、看趋势到筛选、下钻、复制删除和调样式，都在一个验收面里检查。",
    detailEn: "Totals, rankings, trends, filtering, drilldown, copy/delete, and style tuning are checked in one acceptance surface.",
    command: "python tools/bi_cli.py --json dashboard-widget-catalog",
    proof: "frontend-b-widget-acceptance-gallery",
  },
  {
    key: "beginner-mode",
    tone: "ok",
    icon: "agent",
    titleZh: "新手路径已收敛",
    titleEn: "Beginner path is consolidated",
    detailZh: "首页和看板先给业务动作：导入、证据摘要、看板、提问；高级配置折叠。",
    detailEn: "Home and dashboards lead with business actions: import, evidence summary, dashboard, ask. Advanced controls stay folded.",
    command: "Start -> Sources -> Dashboards -> AI",
    proof: "frontend-home-workspace-start-guide",
  },
  {
    key: "status-doc",
    tone: "warn",
    icon: "evidence",
    titleZh: "实现状态有单页交接",
    titleEn: "Implementation status has one handoff page",
    detailZh: "能力吸收情况、剩余缺口和回归命令集中到 docs/implementation-status.md。",
    detailEn: "Capability adoption, remaining gaps, and regression commands live in docs/implementation-status.md.",
    command: "docs/implementation-status.md",
    proof: "implementation-status-handoff",
  },
] as const;

export function SettingsAcceptanceEvidencePanel() {
  return (
    <>
      <section className="settingsCard settingsEvidenceCard" aria-labelledby="settings-evidence-title">
        <div className="settingsCardHeader">
          <div>
            <span className="eyebrow"><Bilingual zh="迁移证据" en="Migration evidence" /></span>
            <h3 id="settings-evidence-title"><Bilingual zh="已吸收的工作台能力" en="Adopted workbench capabilities" /></h3>
          </div>
        </div>
        <dl className="settingsEvidenceList">
          <div>
            <dt><Bilingual zh="偏好和主题" en="Preferences and themes" /></dt>
            <dd><Bilingual zh="用户偏好、主题调色板已进入当前工作区" en="User preferences and theme palettes live in this workspace" /></dd>
          </div>
          <div>
            <dt><Bilingual zh="写入保护" en="Write protection" /></dt>
            <dd><Bilingual zh="所有高风险动作先预演，再由界面按钮确认" en="Risky actions preview first, then require explicit UI confirmation" /></dd>
          </div>
          <div>
            <dt><Bilingual zh="Agent 边界" en="Agent boundary" /></dt>
            <dd><Bilingual zh="手动资产默认不让 Agent 直接管理" en="Manual assets are not Agent-managed by default" /></dd>
          </div>
        </dl>
      </section>

      <section className="settingsCard closureWorkbenchCard" aria-labelledby="closure-workbench-title" data-testid="settings-closure-workbench">
        <div className="settingsCardHeader">
          <div>
            <span className="eyebrow"><Bilingual zh="快速收口" en="Closeout" /></span>
            <h3 id="closure-workbench-title"><Bilingual zh="集成验收台" en="Integration acceptance bench" /></h3>
          </div>
          <span className="settingsHint"><Bilingual zh="6 条主线" en="6 tracks" /></span>
        </div>
        <p className="closureLead" data-testid="settings-closure-lead">
          <Bilingual
            zh="把服务稳定性、本地 BI 能力、安全边界、空工作区、看板组件和新手路径放在同一张检查台里；默认看结论，命令和证据可展开。"
            en="Service stability, local BI capabilities, safety boundaries, empty workspaces, dashboard widgets, and beginner flow are checked in one bench. Conclusions stay visible; commands and verification details expand on demand."
          />
        </p>
        <div className="closureGrid" data-testid="settings-closure-grid">
          {closureItems.map((item) => (
            <article className={`closureItem ${item.tone}`} data-testid={`settings-closure-${item.key}`} key={item.key}>
              <span className="closureIcon"><Icon name={item.icon} /></span>
              <div>
                <strong><Bilingual zh={item.titleZh} en={item.titleEn} /></strong>
                <p><Bilingual zh={item.detailZh} en={item.detailEn} /></p>
                <details className="closureTechnical" data-testid={`settings-closure-technical-${item.key}`}>
                  <summary>{biText("查看验证命令", "View verification command")}</summary>
                  <code>{item.command}</code>
                  <small>{item.proof}</small>
                </details>
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
