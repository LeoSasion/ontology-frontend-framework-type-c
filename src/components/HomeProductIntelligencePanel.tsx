import type { ComponentProps } from "react";
import type { WorkbenchPayload } from "../types";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import { numberValue, recordArray, stringValue } from "../homeOverviewModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import { MetricSemanticRepairActions } from "./MetricSemanticRepairActions";
import type { AppSection } from "./Sidebar";

type BusyKey = "profile" | "dashboardDraft" | "dashboardCreate" | "query" | "ask";

type QualityDoctorView = {
  score: number;
  tone: string;
  summary: string;
  issues: Array<{ key: string; tone: string; value?: string | number; title: string; detail: string }>;
};

type SandboxComparisonView = {
  title: string;
  summary: string;
  facts: Array<{ key: string; tone: string; value?: string | number; title: string }>;
  versionHints: Array<{ key: string; title: string; detail: string }>;
};

type HomeProductIntelligencePanelProps = {
  askMetricRepairReason: () => Promise<void>;
  busy: BusyKey | null;
  liveFailedMetricSamples: Record<string, unknown>[];
  liveMetricBlocked: number;
  liveMetricExecutable: number;
  liveMetricPlanned: number;
  liveMetricRate: number;
  liveMissingSemantics: Record<string, unknown>[];
  liveQualityDoctor: Record<string, unknown> | null;
  liveQualityIssues: Record<string, unknown>[];
  liveRepairDraft: Record<string, unknown> | null;
  liveScore: number;
  liveSummary: string;
  liveTone: string;
  metricRepairPlan: ComponentProps<typeof MetricSemanticRepairActions>["plan"];
  onOpenSection: (section: AppSection) => void;
  onSetSemantic: (options: { table: string; field: string; role: string; tags?: string[]; usage?: string[]; confidence?: number; note?: string; confirm?: boolean; stayOnPage?: boolean }) => Promise<Record<string, unknown>>;
  onSourceIntelligenceRun: (options?: SourceIntelligenceRunOptions) => Promise<Record<string, unknown> | void>;
  qualityDoctor: QualityDoctorView;
  sandboxComparison: SandboxComparisonView;
  workbench: WorkbenchPayload;
};

export function HomeProductIntelligencePanel({
  askMetricRepairReason,
  busy,
  liveFailedMetricSamples,
  liveMetricBlocked,
  liveMetricExecutable,
  liveMetricPlanned,
  liveMetricRate,
  liveMissingSemantics,
  liveQualityDoctor,
  liveQualityIssues,
  liveRepairDraft,
  liveScore,
  liveSummary,
  liveTone,
  metricRepairPlan,
  onOpenSection,
  onSetSemantic,
  onSourceIntelligenceRun,
  qualityDoctor,
  sandboxComparison,
}: HomeProductIntelligencePanelProps) {
  return (
    <div className="homeIntelligenceGrid" data-testid="home-product-intelligence">
      <section className={`qualityDoctorPanel ${liveTone}`} data-testid="home-data-quality-doctor">
        <div className="qualityDoctorHeader">
          <div>
            <span className="storyMode"><Bilingual zh="数据质量医生" en="Data quality doctor" /></span>
            <h3>{liveSummary}</h3>
            <small>{liveQualityDoctor ? biText("实时诊断已连接", "Live diagnosis connected") : biText("使用本地估算，等待服务诊断", "Using local estimate while service diagnosis loads")}</small>
          </div>
          <strong>{liveScore}</strong>
        </div>
        <div className="qualityDoctorIssues">
          {liveQualityIssues.length ? liveQualityIssues.slice(0, 5).map((issue) => (
            <div className={stringValue(issue.tone) || "info"} key={stringValue(issue.key) || stringValue(issue.title)}>
              <span>{stringValue(issue.value)}</span>
              <strong>{stringValue(issue.title)}</strong>
              <small>{stringValue(issue.detail)}</small>
            </div>
          )) : qualityDoctor.issues.slice(0, 5).map((issue) => (
            <div className={issue.tone} key={issue.key}>
              <span>{issue.value ?? ""}</span>
              <strong>{issue.title}</strong>
              <small>{issue.detail}</small>
            </div>
          ))}
        </div>
        {liveMetricPlanned > 0 ? (
          <div className="qualityDoctorMetricSql" data-testid="home-quality-metric-sql">
            <div>
              <span className={liveMetricRate >= 0.8 ? "ok" : "warn"}>{liveMetricExecutable}/{liveMetricPlanned}</span>
              <strong>{biText("指标 SQL 可执行", "Executable metric SQL")}</strong>
              <small>{liveMetricBlocked ? biText(`${liveMetricBlocked} 个问题需要补字段语义`, `${liveMetricBlocked} questions need semantic fixes`) : biText("当前指标问题可执行", "Current metric questions are executable")}</small>
            </div>
            <div className="metricSemanticChips" data-testid="home-quality-missing-semantics">
              {liveMissingSemantics.slice(0, 5).map((item) => (
                <span key={stringValue(item.semantic)}>
                  <strong>{stringValue(item.semantic)}</strong>
                  <small>{numberValue(item.count)}</small>
                </span>
              ))}
            </div>
            {liveRepairDraft ? (
              <details className="metricRepairDraft" data-testid="home-quality-repair-draft">
                <summary>{stringValue(liveRepairDraft.title) || biText("查看修复草案", "View repair draft")}</summary>
                <p>{stringValue(liveRepairDraft.summary)}</p>
                <ol>
                  {recordArray(liveRepairDraft.steps).length
                    ? recordArray(liveRepairDraft.steps).map((step, index) => <li key={`${stringValue(step)}-${index}`}>{stringValue(step)}</li>)
                    : (Array.isArray(liveRepairDraft.steps) ? liveRepairDraft.steps : []).map((step, index) => <li key={`${String(step)}-${index}`}>{String(step)}</li>)}
                </ol>
              </details>
            ) : null}
            {metricRepairPlan.bindingDrafts.length ? (
              <div className="metricRepairWizard" data-testid="home-metric-repair-wizard">
                <div>
                  <strong>{biText("指标 SQL 修复向导", "Metric SQL repair guide")}</strong>
                  <small>{metricRepairPlan.summary}</small>
                </div>
                <MetricSemanticRepairActions
                  actionsTestId="home-semantic-binding-drafts"
                  loopTestId="home-semantic-confirm-loop"
                  onOpenEvidence={() => onOpenSection("evidence")}
                  onSetSemantic={onSetSemantic}
                  onSourceIntelligenceRun={onSourceIntelligenceRun}
                  plan={metricRepairPlan}
                />
                <div className="metricRepairActions single">
                  <button className="miniButton" disabled={busy === "ask"} onClick={askMetricRepairReason} type="button">
                    <Icon name="agent" />
                    {biText("问原因", "Ask why")}
                  </button>
                </div>
              </div>
            ) : null}
            {liveFailedMetricSamples.length ? (
              <div className="metricFailureSamples" data-testid="home-quality-failed-metrics">
                {liveFailedMetricSamples.slice(0, 3).map((sample) => (
                  <span key={stringValue(sample.analysisId)}>
                    <strong>{stringValue(sample.label)}</strong>
                    <small>{stringValue(sample.reason) || stringValue(sample.agentInstruction)}</small>
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="qualityDoctorActions">
          <button className="miniButton" onClick={() => onOpenSection("sources")} type="button">{biText("修复数据", "Fix data")}</button>
          <button className="miniButton" onClick={() => onOpenSection("evidence")} type="button">{biText("看证据", "View evidence")}</button>
        </div>
      </section>

      <section className="sandboxComparePanel" data-testid="home-sandbox-compare">
        <div>
          <span className="storyMode"><Bilingual zh="沙箱对比" en="Sandbox compare" /></span>
          <h3>{sandboxComparison.title}</h3>
          <p>{sandboxComparison.summary}</p>
        </div>
        <div className="sandboxCompareFacts">
          {sandboxComparison.facts.map((fact) => (
            <span className={fact.tone} key={fact.key}>
              <strong>{fact.value}</strong>
              <small>{fact.title}</small>
            </span>
          ))}
        </div>
        <details className="advancedDetails compactAdvanced">
          <summary>{biText("查看版本和撤销路线", "View version and undo path")}</summary>
          <div className="sandboxVersionHints">
            {sandboxComparison.versionHints.map((hint) => (
              <span key={hint.key}><strong>{hint.title}</strong><small>{hint.detail}</small></span>
            ))}
          </div>
        </details>
      </section>
    </div>
  );
}
