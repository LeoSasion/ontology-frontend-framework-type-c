import type { EvidenceNarrative } from "../productIntelligenceModel";
import { Bilingual } from "./Bilingual";

type EvidenceNumberExplainerPanelProps = {
  evidenceNarrative: EvidenceNarrative;
};

export function EvidenceNumberExplainerPanel({ evidenceNarrative }: EvidenceNumberExplainerPanelProps) {
  return (
    <article className="wideArticle evidenceNarrativeCard" data-testid="evidence-number-explainer">
      <div className="tileHeader">
        <div>
          <span className="storyMode"><Bilingual zh="数字说明书" en="Number explainer" /></span>
          <h3>{evidenceNarrative.title}</h3>
          <span>{evidenceNarrative.summary}</span>
        </div>
      </div>
      <div className="evidenceNarrativeSteps" data-testid="evidence-calculation-steps">
        {evidenceNarrative.calculationSteps.map((step) => (
          <div className={step.tone} key={step.key}>
            <strong>{step.title}</strong>
            <span>{step.detail}</span>
          </div>
        ))}
      </div>
      <div className="evidenceTrustChecks" data-testid="evidence-trust-checks">
        {evidenceNarrative.trustChecks.map((check) => (
          <span className={check.tone} key={check.key}>
            <strong>{check.title}</strong>
            <small>{check.detail}</small>
          </span>
        ))}
      </div>
    </article>
  );
}
