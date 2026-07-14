import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import type { BusinessPathStepKey } from "../businessPathModel";

type HomeActionDockProps = {
  agentRequiresConfirmation: boolean;
  hasData: boolean;
  tableCount: number;
  onOpenStep: (step: BusinessPathStepKey) => void;
};

export function HomeActionDock({
  agentRequiresConfirmation,
  hasData,
  tableCount,
  onOpenStep,
}: HomeActionDockProps) {
  return (
    <div className={hasData ? "homeActionDock" : "homeActionDock firstRun"} data-testid="home-action-dock">
      <button className="homeActionCard primary" data-testid="home-action-import" onClick={() => onOpenStep("data")} type="button">
        <span className="homeActionIcon"><Icon name="source" /></span>
        <strong><Bilingual zh="导入或扫描数据" en="Import or scan data" /></strong>
        <small>{hasData ? biText(`${tableCount} 张表可用`, `${tableCount} tables ready`) : biText("选择文件或文件夹，先检查再确认", "Choose files or folders, preview first")}</small>
      </button>
      <button className="homeActionCard" data-testid="home-action-chart" disabled={!hasData} onClick={() => onOpenStep("chart")} type="button">
        <span className="homeActionIcon"><Icon name="dashboard" /></span>
        <strong><Bilingual zh="生成一个图表" en="Create one chart" /></strong>
        <small>{hasData ? biText("到仪表盘页说需求", "Open dashboards and describe it") : biText("导入数据后可用", "Available after import")}</small>
      </button>
      <button className="homeActionCard" data-testid="home-action-ask" disabled={!hasData} onClick={() => onOpenStep("evidence")} type="button">
        <span className="homeActionIcon"><Icon name="evidence" /></span>
        <strong><Bilingual zh="核对证据" en="Review evidence" /></strong>
        <small>{hasData ? biText("来源、口径和缺口集中看", "Sources, definitions, and gaps") : biText("暂无证据可核对", "No evidence to review yet")}</small>
      </button>
      <button className="homeActionCard" data-testid="home-action-confirm" disabled={!hasData && !agentRequiresConfirmation} onClick={() => onOpenStep("confirm")} type="button">
        <span className="homeActionIcon"><Icon name="check" /></span>
        <strong><Bilingual zh="确认修改" en="Approve changes" /></strong>
        <small>{agentRequiresConfirmation ? biText("有草案待处理", "Drafts need review") : biText("写入前都会停住", "Writes stop for approval")}</small>
      </button>
    </div>
  );
}
