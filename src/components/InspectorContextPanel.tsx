import type { AgentAskResult, EvidenceFocus, ImportPreview, WorkspaceStatus } from "../types";
import { buildObjectInspectorModel } from "../productIntelligenceModel";
import { drawerActionsForSection, sectionContext } from "../inspectorPanelModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type InspectorContextPanelProps = {
  activeDashboardName: string;
  activeSection: AppSection;
  activeTableName: string;
  activeViewName: string;
  agent: AgentAskResult;
  evidenceFocus?: EvidenceFocus | null;
  onOpenAgent: () => void;
  onOpenEvidence: () => void;
  preview: ImportPreview;
  status: WorkspaceStatus;
};

export function InspectorContextPanel({
  activeDashboardName,
  activeSection,
  activeTableName,
  activeViewName,
  agent,
  evidenceFocus,
  onOpenAgent,
  onOpenEvidence,
  preview,
  status,
}: InspectorContextPanelProps) {
  const fallbackContext = sectionContext(activeSection, activeDashboardName, activeViewName, activeTableName, agent);
  const objectModel = buildObjectInspectorModel({ activeSection, focus: evidenceFocus, status, preview, agent, activeDashboardName, activeViewName, activeTableName });
  const drawerActions = drawerActionsForSection(activeSection);
  const contextTitle = evidenceFocus?.title ?? objectModel.title;
  const focusChips = evidenceFocus
    ? [
      evidenceFocus.source,
      evidenceFocus.dashboardKey ? `${biText("看板", "dashboard")}: ${evidenceFocus.dashboardKey}` : "",
      evidenceFocus.viewKey ? `${biText("视图", "view")}: ${evidenceFocus.viewKey}` : "",
      evidenceFocus.tableKey ? `${biText("表", "table")}: ${evidenceFocus.tableKey}` : "",
      evidenceFocus.widgetType ? `${biText("组件", "widget")}: ${evidenceFocus.widgetType}` : "",
      biText(`${evidenceFocus.refs.length} 条证据线索`, `${evidenceFocus.refs.length} evidence items`),
    ].filter((chip): chip is string => Boolean(chip))
    : fallbackContext.chips;

  return (
    <>
      <section className="inspectorFocusContext" data-testid="inspector-selected-context">
        <div className="inspectorSectionHeader">
          <div>
            <span className="eyebrow">{evidenceFocus ? biText("当前对象", "Current object") : biText("未选中对象", "No object selected")}</span>
            <h2>{contextTitle}</h2>
          </div>
          <button className="miniButton" data-testid="inspector-open-evidence" onClick={onOpenEvidence} type="button">
            <Icon name="evidence" />
            {biText("证据", "Evidence")}
          </button>
        </div>
        <p className="quietText">
          {evidenceFocus?.subtitle ?? biText("选择图表、字段、公式、关系或 Agent 草案后，这里显示对应的编辑与证据入口。", "Select a chart, field, formula, relationship, or Agent draft to show matching edit and evidence controls here.")}
        </p>
        <div className="inspectorFocusChips" data-testid="inspector-selected-context-chips">
          {focusChips.map((chip) => <span key={chip}>{chip}</span>)}
        </div>
      </section>

      <section className="objectInspectorLens" data-testid="object-inspector-lens">
        <div className="objectInspectorLensHeader">
          <span className="storyMode">{objectModel.objectType}</span>
          <strong>{objectModel.subtitle}</strong>
        </div>
        <div className="objectInspectorFacts" data-testid="object-inspector-facts">
          {objectModel.facts.map((fact) => (
            <div className={fact.tone} key={fact.key}>
              <strong>{fact.value}</strong>
              <span>{fact.title}</span>
              <small>{fact.detail}</small>
            </div>
          ))}
        </div>
        <div className="objectInspectorSlots" data-testid="object-inspector-editor-slots">
          {objectModel.editorSlots.map((slot) => (
            <span className={slot.tone} key={slot.key}>
              <strong>{slot.title}</strong>
              <small>{slot.detail}</small>
            </span>
          ))}
        </div>
      </section>

      <section className="contextActionPanel">
        <div className="contextActionHeader">
          <span className="eyebrow">{biText("可做什么", "Available actions")}</span>
          <strong>{objectModel.primaryAction}</strong>
        </div>
        <div className="contextActionGrid">
          <button className="secondaryButton" onClick={onOpenEvidence} type="button">
            <Icon name="evidence" />
            <Bilingual {...drawerActions.evidence} />
          </button>
          <button className="secondaryButton" onClick={onOpenAgent} type="button">
            <Icon name="agent" />
            <Bilingual {...drawerActions.agent} />
          </button>
        </div>
        <p className="quietText"><Bilingual {...drawerActions.hint} /></p>
      </section>
    </>
  );
}
