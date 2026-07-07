import type { BusinessPathStepKey } from "../businessPathModel";
import type { ProductActivationModel, ProductActivationStep } from "../productActivationModel";
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

function stepClass(step: ProductActivationStep, currentStep?: BusinessPathStepKey) {
  const classes = ["productActivationStep", step.status];
  if (currentStep && step.route === currentStep) classes.push("current");
  return classes.join(" ");
}

export function ProductActivationPanel({
  activation,
  compact = false,
  currentStep,
  testId = "product-activation-panel",
  title,
  onOpenStep,
}: ProductActivationPanelProps) {
  const firstRunMode = !activation.hasData;
  const panelClassName = ["productActivationPanel"];
  if (compact) panelClassName.push("compact");
  if (firstRunMode) panelClassName.push("firstRun");
  const visibleSteps = firstRunMode
    ? activation.steps.filter((step) => step.key === activation.activeStepKey)
    : activation.steps;
  const primaryStepIsCurrent = currentStep === activation.primaryStep.route;

  return (
    <section className={panelClassName.join(" ")} data-testid={testId}>
      <div className="productActivationHeader">
        <div>
          <span className="storyMode"><Bilingual zh="首次成功路径" en="First success path" /></span>
          <h3>{title ?? biText("只做当前最必要的一步", "Only show the next needed step")}</h3>
          <p>{activation.stateDetail}</p>
        </div>
        <div className="productActivationState" data-testid="product-activation-state">
          <span>{activation.stateLabel}</span>
          <strong>{activation.progressLabel}</strong>
        </div>
      </div>

      <div className="productActivationSteps" data-testid="product-activation-steps">
        {visibleSteps.map((step) => {
          const isCurrentStep = currentStep === step.route;
          return (
            <button
              className={stepClass(step, currentStep)}
              data-testid={`product-activation-step-${step.key}`}
              disabled={step.status === "locked"}
              key={step.key}
              onClick={() => {
                if (!isCurrentStep) onOpenStep(step.route);
              }}
              type="button"
            >
              <span className="productActivationIcon"><Icon name={step.icon} /></span>
              <span>
                <strong>{step.title}</strong>
                <small>{step.detail}</small>
              </span>
              <em>{isCurrentStep ? biText("当前步骤", "Current") : step.status === "complete" ? biText("完成", "Done") : step.status === "active" ? step.actionLabel : biText("等待", "Locked")}</em>
            </button>
          );
        })}
      </div>

      {!firstRunMode ? (
        <div className="productActivationFooter">
          <div className="productActivationFactGrid" data-testid="product-activation-facts">
            {activation.facts.map((fact) => (
              <span className={`productActivationFact ${fact.tone}`} key={fact.label}>
                <strong>{fact.value}</strong>
                <small>{fact.label}</small>
              </span>
            ))}
          </div>
          {primaryStepIsCurrent ? (
            <span className="primaryButton productActivationPrimary current" data-testid="product-activation-primary">
              <Icon name={activation.primaryStep.icon} />
              {biText("当前步骤", "Current step")}
            </span>
          ) : (
            <button className="primaryButton productActivationPrimary" data-testid="product-activation-primary" onClick={() => onOpenStep(activation.primaryStep.route)} type="button">
              <Icon name={activation.primaryStep.icon} />
              {activation.primaryStep.actionLabel}
            </button>
          )}
        </div>
      ) : null}

      {!compact && !firstRunMode ? (
        <details className="advancedDetails compactAdvanced productActivationTrust" data-testid="product-activation-trust">
          <summary>{biText("查看字段、关系和写入边界", "View fields, links, and write gate")}</summary>
          <div className="productActivationFactGrid secondary">
            {activation.trustFacts.map((fact) => (
              <span className={`productActivationFact ${fact.tone}`} key={fact.label}>
                <strong>{fact.value}</strong>
                <small>{fact.label}</small>
              </span>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}
