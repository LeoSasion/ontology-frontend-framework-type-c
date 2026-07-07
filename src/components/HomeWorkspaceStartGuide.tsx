import type { GuideStep } from "../homeOverviewModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import type { AppSection } from "./Sidebar";

type HomeWorkspaceStartGuideProps = {
  guideSteps: GuideStep[];
  readiness: {
    label: string;
    next: AppSection;
  };
  onOpenSection: (section: AppSection) => void;
};

export function HomeWorkspaceStartGuide({ guideSteps, readiness, onOpenSection }: HomeWorkspaceStartGuideProps) {
  return (
    <details className="advancedDetails workspaceStartGuideDetails" data-testid="workspace-start-guide">
      <summary>{biText("查看工作区起步建议", "View workspace start guidance")}</summary>
      <div className="workspaceStartGuide">
        <div className="workspaceGuideHeader">
          <div>
            <span className="eyebrow">{biText("下一步", "Next step")}</span>
            <h3><Bilingual zh="按业务路径推进，不先学配置" en="Follow the business path before learning configuration" /></h3>
          </div>
          <button className="miniButton" onClick={() => onOpenSection(readiness.next)} type="button" data-testid="workspace-start-guide-primary">
            {readiness.label}
          </button>
        </div>
        <div className="workspaceGuideSteps">
          {guideSteps.map((step, index) => (
            <button
              className={`workspaceGuideStep ${step.state}`}
              data-testid={`workspace-guide-step-${step.key}`}
              key={step.key}
              onClick={() => onOpenSection(step.actionSection)}
              type="button"
            >
              <span className="workspaceGuideIndex">{index + 1}</span>
              <span className="workspaceGuideIcon"><Icon name={step.icon} /></span>
              <strong>{step.label}</strong>
              <small>{step.detail}</small>
              <em>{step.actionLabel}</em>
            </button>
          ))}
        </div>
        <p className="workspaceGuideBoundary" data-testid="workspace-start-guide-boundary">
          <Bilingual
            zh="所有导入、删除、覆盖、关系保存和看板写入都会先形成草案或预演，确认后才执行。"
            en="Imports, deletes, overwrites, relationship saves, and dashboard writes become drafts or previews before execution."
          />
        </p>
      </div>
    </details>
  );
}
