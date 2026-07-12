import "./productActivationPanel.css";
import type { BusinessPathStepKey } from "../businessPathModel";
import type { ProductActivationModel } from "../productActivationModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type ProductActivationPanelProps = {
  activation: ProductActivationModel;
  compact?: boolean;
  currentStep?: BusinessPathStepKey;
  testId?: string;
  title?: string;
  onOpenStep: (step: BusinessPathStepKey) => void;
};

export function ProductActivationPanel({
  activation,
  compact = false,
  currentStep,
  testId = "product-activation-panel",
  title,
  onOpenStep,
}: ProductActivationPanelProps) {
  const panelClassName = ["productActivationPanel"];
  if (compact) panelClassName.push("compact");
  if (!activation.hasData) panelClassName.push("firstRun");
  const step = activation.primaryStep;
  const primaryStepIsCurrent = currentStep === activation.primaryStep.route;

  return (
    <section className={panelClassName.join(" ")} data-testid={testId}>
      <div className="productActivationHeader">
        <div>
          <span className="storyMode"><Bilingual zh="下一步" en="Next step" /></span>
          <h3>{title ?? activation.stateLabel}</h3>
          <p>{activation.stateDetail}</p>
        </div>
        <div className="productActivationState" data-testid="product-activation-state">
          <strong>{activation.progressLabel}</strong>
        </div>
      </div>

      <div className="productActivationSteps" data-testid="product-activation-steps">
        <div
          className={`productActivationStep ${step.status}${primaryStepIsCurrent ? " current" : ""}`}
          data-testid={`product-activation-step-${step.key}`}
        >
          <span className="productActivationIcon"><Icon name={step.icon} /></span>
          <span>
            <strong>{step.title}</strong>
            <small>{step.detail}</small>
          </span>
          <em>{biText("当前目标", "Current goal")}</em>
        </div>
      </div>

      <button className="primaryButton productActivationPrimary" data-testid="product-activation-primary" onClick={() => onOpenStep(step.route)} type="button">
        <Icon name={step.icon} />
        {primaryStepIsCurrent ? biText("继续当前步骤", "Continue current step") : step.actionLabel}
      </button>
    </section>
  );
}
