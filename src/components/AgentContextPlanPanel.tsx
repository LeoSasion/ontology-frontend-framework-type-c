import type { AgentAskResult, SelectionConfidence } from "../types";
import { confidenceClass, confidenceText } from "../agentPanelModel";
import { Bilingual, biText, localizedText, translateName } from "./Bilingual";

type AgentContextPlanPanelProps = {
  activeBoundaryBlocked: boolean;
  activeDashboardConfidence: SelectionConfidence | "draft";
  activeDashboardLabel: string;
  activeHasWriteDraft: boolean;
  canConfirmCurrent: boolean;
  result: AgentAskResult;
  targetBoundaryState: "blocked" | "draft" | "readonly";
};

export function AgentContextPlanPanel({
  activeBoundaryBlocked,
  activeDashboardConfidence,
  activeDashboardLabel,
  activeHasWriteDraft,
  canConfirmCurrent,
  result,
  targetBoundaryState,
}: AgentContextPlanPanelProps) {
  return (
    <>
      <article className={`agentTargetBoundary ${targetBoundaryState}`} data-testid="agent-target-boundary">
        <div>
          <h3><Bilingual zh="目标匹配与写入边界" en="Target match and write boundary" /></h3>
          <p>
            {activeBoundaryBlocked
              ? biText("没有明确命中目标看板，因此不会写入或生成默认看板修改。请说出已有看板名称，或先创建新看板。", "No target dashboard was matched, so no default dashboard write or pending change is created. Name an existing dashboard, or create a new one first.")
              : canConfirmCurrent
                ? biText("当前任务包已有待确认修改；确认前不会写入，拒绝后会从队列移除。", "The current task packet has a change awaiting approval; nothing writes before confirmation, and rejecting removes it from the queue.")
                : biText("当前是只读回答或规划，不需要确认写入。", "This is a read-only answer or plan; no write approval is needed.")}
          </p>
        </div>
        <div className="agentBoundaryChips">
          <span className={confidenceClass(activeDashboardConfidence)} data-testid="agent-dashboard-confidence">
            {biText("看板", "Dashboard")}: {activeDashboardConfidence === "draft" ? biText("待确认修改", "Change queued") : confidenceText(activeDashboardConfidence)}
          </span>
          <span>
            {activeDashboardLabel ? <Bilingual {...translateName(activeDashboardLabel)} /> : biText("未选择看板", "No dashboard selected")}
          </span>
          <span>{activeHasWriteDraft ? biText("有待确认修改", "Change requires approval") : biText("无待写入修改", "No write change")}</span>
        </div>
      </article>

      <article>
        <h3><Bilingual zh="匹配上下文" en="Matched context" /></h3>
        <dl className="definitionGrid">
          <div>
            <dt>{biText("表", "Table")}</dt>
            <dd>{result.matched.table ? <Bilingual {...translateName(result.matched.table.display_name)} /> : biText("缺失", "missing")}</dd>
          </div>
          <div>
            <dt>{biText("表置信", "Table confidence")}</dt>
            <dd>{result.matched.tableSelectionConfidence}</dd>
          </div>
          <div>
            <dt>{biText("看板", "Dashboard")}</dt>
            <dd>{result.matched.dashboard ? <Bilingual {...translateName(result.matched.dashboard.name)} /> : biText("缺失", "missing")}</dd>
          </div>
          <div>
            <dt>{biText("看板置信", "Dashboard confidence")}</dt>
            <dd>{confidenceText(result.matched.dashboardSelectionConfidence)}</dd>
          </div>
        </dl>
      </article>

      <article>
        <h3><Bilingual zh="计划" en="Plan" /></h3>
        <ol className="planList">
          {result.plan.map((step) => (
            <li key={step}>{localizedText(step)}</li>
          ))}
        </ol>
      </article>
    </>
  );
}
