import { Bilingual } from "./Bilingual";

type EvidenceBusinessMetric = {
  label: string;
  value: string;
};

type EvidenceBusinessSummaryPanelProps = {
  businessMetrics: EvidenceBusinessMetric[];
  businessTitle: string;
  coverageText: string;
  decisionText: string;
  nextEvidenceActions: string[];
};

export function EvidenceBusinessSummaryPanel({
  businessMetrics,
  businessTitle,
  coverageText,
  decisionText,
  nextEvidenceActions,
}: EvidenceBusinessSummaryPanelProps) {
  return (
    <article className="wideArticle evidenceBusinessSummary" data-testid="evidence-business-summary">
      <div className="evidenceBusinessLead">
        <div>
          <span className="storyMode"><Bilingual zh="业务先读" en="Business first" /></span>
          <h3>{businessTitle}</h3>
          <p>{decisionText}</p>
        </div>
        <span>{coverageText}</span>
      </div>
      <div className="evidenceBusinessMetrics" data-testid="evidence-business-summary-metrics">
        {businessMetrics.map((metric) => (
          <div key={metric.label}>
            <strong>{metric.value}</strong>
            <span>{metric.label}</span>
          </div>
        ))}
      </div>
      <div className="evidenceBusinessNext" data-testid="evidence-business-next-actions">
        {nextEvidenceActions.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
    </article>
  );
}
