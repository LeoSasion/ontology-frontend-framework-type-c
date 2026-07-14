import type { WorkbenchPayload } from "../types";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type HomeDetailedPathBusy = "profile" | "dashboardDraft" | "dashboardCreate" | "query" | "ask" | null;

type HomeDetailedPathPanelProps = {
  agentRequiresConfirmation: boolean;
  busy: HomeDetailedPathBusy;
  dashboardPlan: Record<string, unknown> | null;
  dashboardPlanKey: string;
  dashboardPlanNeedsConfirmation: boolean;
  dashboardPlanTable: string;
  dashboardPlanTitle: string;
  dashboardPlanWidgetCount: number;
  mainTable?: WorkbenchPayload["tables"][number];
  onAsk: (prompt: string) => Promise<void>;
  onOpenSection: (section: AppSection) => void;
  onSourceIntelligenceRun: () => Promise<Record<string, unknown> | void>;
  runBusy: <T>(key: Exclude<HomeDetailedPathBusy, null>, task: () => Promise<T>, nextSection?: AppSection) => Promise<void>;
  runDashboardTemplate: (confirm: boolean) => Promise<void>;
};

export function HomeDetailedPathPanel({
  agentRequiresConfirmation,
  busy,
  dashboardPlan,
  dashboardPlanKey,
  dashboardPlanNeedsConfirmation,
  dashboardPlanTable,
  dashboardPlanTitle,
  dashboardPlanWidgetCount,
  mainTable,
  onAsk,
  onOpenSection,
  onSourceIntelligenceRun,
  runBusy,
  runDashboardTemplate,
}: HomeDetailedPathPanelProps) {
  return (
    <details className="advancedDetails homeDetailedPath" data-testid="home-detailed-path">
      <summary>{biText("查看更多数据源、通用看板和 Agent 路径", "Show more source, dashboard, and Agent paths")}</summary>
      <div className="nextStepGrid">
        <article className="nextStep primaryStep">
          <div className="stepIcon"><Icon name="source" /></div>
          <div>
            <h3><Bilingual zh="1. 接入或检查数据" en="1. Add or check data" /></h3>
            <p>
              {mainTable
                ? biText(`当前主表 ${mainTable.display_name}，${mainTable.row_count.toLocaleString()} 行。`, `Current main table is ${mainTable.display_name}, ${mainTable.row_count.toLocaleString()} rows.`)
                : biText("当前没有数据。先进入数据源工作台导入本地文件或文件夹。", "No data yet. Open the source workbench to import local files or folders first.")}
            </p>
          </div>
          <div className="stepActions">
            <button className="primaryButton" onClick={() => onOpenSection("sources")} type="button">
              <Icon name="source" />
              <Bilingual zh="数据源工作台" en="Source workbench" />
            </button>
            <button
              className="secondaryButton"
              disabled={busy === "profile"}
              onClick={() => runBusy("profile", onSourceIntelligenceRun)}
              type="button"
            >
              <Bilingual zh="生成证据摘要" en="Create evidence summary" />
            </button>
          </div>
        </article>

        <article className="nextStep">
          <div className="stepIcon"><Icon name="dashboard" /></div>
          <div>
            <h3><Bilingual zh="2. 生成分析看板" en="2. Create analysis dashboard" /></h3>
            <p>
              <Bilingual
                zh="使用系统的 metric、bar、line、pie、table、text、slicer 组件能力，并在看板里保留证据与动作边界。"
                en="Use the system metric, bar, line, pie, table, text, and slicer components while keeping evidence and action boundaries."
              />
            </p>
          </div>
          <div className="stepActions">
            <button
              className="secondaryButton"
              disabled={busy === "dashboardDraft"}
              onClick={() => runBusy("dashboardDraft", () => runDashboardTemplate(false))}
              type="button"
            >
              <Icon name="evidence" />
              <Bilingual zh="预览看板草案" en="Preview dashboard draft" />
            </button>
            <button
              className="primaryButton"
              disabled={busy === "dashboardCreate"}
              onClick={() => runBusy("dashboardCreate", () => runDashboardTemplate(true))}
              type="button"
            >
              <Icon name="check" />
              <Bilingual zh="确认创建" en="Create now" />
            </button>
          </div>
          {dashboardPlan ? (
            <div className="simpleActionResult homeDashboardPreview" data-testid="home-dashboard-preview-result">
              <span>
                {dashboardPlanNeedsConfirmation
                  ? biText("看板预演已生成，还没有写入。确认后才会创建可编辑看板。", "Dashboard preview is ready and has not been written. Confirm to create an editable board.")
                  : biText("看板已创建，可以进入仪表盘继续编辑。", "Dashboard created. Open dashboards to keep editing.")}
              </span>
              <strong>
                {dashboardPlanWidgetCount
                  ? biText(`${dashboardPlanTitle} · ${dashboardPlanWidgetCount} 个组件 · ${dashboardPlanTable}`, `${dashboardPlanTitle} · ${dashboardPlanWidgetCount} widgets · ${dashboardPlanTable}`)
                  : dashboardPlanKey || dashboardPlanTitle}
              </strong>
              <div className="buttonRow tight">
                {dashboardPlanNeedsConfirmation ? (
                  <button
                    className="primaryButton compactAction"
                    data-testid="home-dashboard-preview-confirm"
                    disabled={busy === "dashboardCreate"}
                    onClick={() => runBusy("dashboardCreate", () => runDashboardTemplate(true))}
                    type="button"
                  >
                    <Icon name="check" />
                    <Bilingual zh="确认创建" en="Confirm create" />
                  </button>
                ) : null}
                <button
                  className="miniButton"
                  data-testid="home-dashboard-preview-open"
                  onClick={() => onOpenSection("dashboards")}
                  type="button"
                >
                  {dashboardPlanNeedsConfirmation ? biText("先看仪表盘区", "Open dashboard area") : biText("打开看板", "Open dashboard")}
                </button>
              </div>
            </div>
          ) : null}
        </article>

        <article className="nextStep">
          <div className="stepIcon"><Icon name="agent" /></div>
          <div>
            <h3><Bilingual zh="3. 直接问 Agent" en="3. Ask the Agent" /></h3>
            <p>
              {agentRequiresConfirmation
                ? biText("已有需要确认的草案，确认前不会改数据。", "A draft is waiting for confirmation. No data changes before approval.")
                : biText("不需要先学字段、公式或关系。Agent 会说明已检查内容、可回答内容和缺口。", "No need to learn fields, formulas, or relationships first. The Agent states what it checked, what it can answer, and gaps.")}
            </p>
          </div>
          <div className="stepActions">
            <button className="secondaryButton" onClick={() => onOpenSection("agent")} type="button">
              <Icon name="agent" />
              <Bilingual zh="打开 Agent" en="Open Agent" />
            </button>
            <button
              className="miniButton"
              disabled={busy === "ask"}
              onClick={() => runBusy("ask", () => onAsk(biText("帮我生成分析看板并说明证据", "Create an analysis dashboard and explain the evidence")), "agent")}
              type="button"
            >
              {biText("让 Agent 起草", "Ask Agent")}
            </button>
          </div>
        </article>
      </div>
    </details>
  );
}
