import { useState } from "react";
import type { MetricRepairPlan, SemanticBindingDraft } from "../metricRepairModel";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import { biText } from "./Bilingual";
import { Icon } from "./Icons";

type SemanticSetOptions = {
  table: string;
  field: string;
  role: string;
  tags?: string[];
  usage?: string[];
  confidence?: number;
  note?: string;
  confirm?: boolean;
  stayOnPage?: boolean;
};

type MetricSemanticRepairActionsProps = {
  plan: MetricRepairPlan;
  maxDrafts?: number;
  actionsTestId: string;
  loopTestId: string;
  onSetSemantic: (options: SemanticSetOptions) => Promise<Record<string, unknown>>;
  onSourceIntelligenceRun: (options?: SourceIntelligenceRunOptions) => Promise<Record<string, unknown> | void>;
  onOpenEvidence?: () => void;
};

type MetricSqlSnapshot = {
  planned: number;
  executable: number;
  blocked: number;
};

function bindingReady(draft: SemanticBindingDraft) {
  return Boolean(draft.tableKey && draft.fieldName && draft.fieldName !== "待选择字段");
}

function roleAndUsageForSemantic(semantic: string): Pick<SemanticSetOptions, "role" | "usage" | "tags"> {
  const lower = semantic.toLowerCase();
  if (lower.includes("date") || lower.endsWith("_at") || lower.includes("time")) {
    return { role: "event_time", usage: ["time_filter", "groupable"], tags: [semantic] };
  }
  if (lower.endsWith("_id") || lower.includes("customer") || lower.includes("sku") || lower.includes("shop")) {
    return { role: "identity_key", usage: ["joinable", "groupable"], tags: [semantic] };
  }
  return { role: "measure", usage: ["aggregatable"], tags: [semantic] };
}

function actionLabel(result: Record<string, unknown> | null) {
  if (!result) return "";
  if (result.confirmed === true) return biText("已确认字段语义，可以重跑画像。", "Field semantic confirmed. You can rerun profiling.");
  if (result.requiresConfirmation === true || result.dryRun === true) return biText("预演完成，确认前不会写入。", "Preview complete. Nothing writes before confirmation.");
  if (result.ok === false) return String(result.error ?? biText("动作失败。", "Action failed."));
  return biText("动作已返回。", "Action returned.");
}

function snapshotFromPlan(plan: MetricRepairPlan): MetricSqlSnapshot {
  return {
    planned: plan.planned,
    executable: plan.executable,
    blocked: plan.blocked,
  };
}

function snapshotFromResult(result: Record<string, unknown> | void | null): MetricSqlSnapshot | null {
  if (!result || typeof result !== "object") return null;
  const manifest = result.manifest && typeof result.manifest === "object" && !Array.isArray(result.manifest)
    ? result.manifest as Record<string, unknown>
    : null;
  const planned = typeof manifest?.metricSqlPlanCount === "number" ? manifest.metricSqlPlanCount : 0;
  const executable = typeof manifest?.metricSqlExecutableCount === "number" ? manifest.metricSqlExecutableCount : 0;
  if (!planned) return null;
  return {
    planned,
    executable,
    blocked: Math.max(0, planned - executable),
  };
}

export function MetricSemanticRepairActions({
  plan,
  maxDrafts = 4,
  actionsTestId,
  loopTestId,
  onSetSemantic,
  onSourceIntelligenceRun,
  onOpenEvidence,
}: MetricSemanticRepairActionsProps) {
  const [busyKey, setBusyKey] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [beforeSnapshot, setBeforeSnapshot] = useState<MetricSqlSnapshot | null>(null);
  const [afterSnapshot, setAfterSnapshot] = useState<MetricSqlSnapshot | null>(null);
  const [previewedSemantics, setPreviewedSemantics] = useState<Set<string>>(() => new Set());
  const drafts = plan.bindingDrafts.slice(0, maxDrafts);

  async function runSemanticAction(draft: SemanticBindingDraft, confirm: boolean) {
    if (!bindingReady(draft)) return;
    const semanticOptions = roleAndUsageForSemantic(draft.semantic);
    setBusyKey(`${confirm ? "confirm" : "preview"}:${draft.semantic}`);
    try {
      setResult(await onSetSemantic({
        table: draft.tableKey,
        field: draft.fieldName,
        confidence: Math.max(0.72, draft.confidence || 0.72),
        note: `metric-sql repair: ${draft.semantic}`,
        confirm,
        stayOnPage: true,
        ...semanticOptions,
      }));
      if (confirm) {
        setBeforeSnapshot(snapshotFromPlan(plan));
        setAfterSnapshot(null);
      } else {
        setPreviewedSemantics((current) => new Set(current).add(draft.semantic));
      }
    } finally {
      setBusyKey("");
    }
  }

  async function rerunSourceIntelligence() {
    setBusyKey("rerun-source-intelligence");
    const baseline = beforeSnapshot ?? snapshotFromPlan(plan);
    setBeforeSnapshot(baseline);
    setAfterSnapshot(null);
    try {
      if (!plan.rerunInputs.length) {
        const blocked = {
          ok: false,
          action: "source-intelligence",
          error: biText("没有找到原始输入。请先在数据源工作台导入本地文件或文件夹。", "No original inputs were found. Import local files or folders in the source workbench first."),
        };
        setResult(blocked);
        return;
      }
      const nextResult = await onSourceIntelligenceRun({ inputs: plan.rerunInputs, label: "metric semantic repair rerun", stayOnPage: true });
      setResult(nextResult && typeof nextResult === "object" ? nextResult : { ok: true, action: "source-intelligence" });
      setAfterSnapshot(snapshotFromResult(nextResult));
    } finally {
      setBusyKey("");
    }
  }

  const comparison = beforeSnapshot && afterSnapshot ? {
    before: `${beforeSnapshot.executable}/${beforeSnapshot.planned}`,
    after: `${afterSnapshot.executable}/${afterSnapshot.planned}`,
    delta: afterSnapshot.executable - beforeSnapshot.executable,
    blockedDelta: beforeSnapshot.blocked - afterSnapshot.blocked,
  } : null;

  return (
    <div className="semanticRepairLoop" data-testid={loopTestId}>
      <div className="semanticBindingDrafts" data-testid={actionsTestId}>
        {drafts.map((draft) => {
          const ready = bindingReady(draft);
          const previewRequired = draft.requiresPreview && !previewedSemantics.has(draft.semantic);
          return (
            <div className={`semanticBindingCard ${draft.tone}`} key={draft.semantic}>
              <strong>{draft.semantic}</strong>
              <small>{draft.fieldName} · {draft.tableName}</small>
              <em>{Math.round(draft.confidence * 100)}% · {draft.impactCount} {biText("个问题", "questions")}</em>
              {draft.requiresPreview ? (
                <span className={`semanticBindingRisk ${draft.riskLevel}`}>{draft.riskReason}</span>
              ) : null}
              <div className="semanticBindingActions">
                <button className="miniButton" disabled={!ready || Boolean(busyKey)} onClick={() => void runSemanticAction(draft, false)} type="button">
                  {busyKey === `preview:${draft.semantic}` ? biText("预演中", "Previewing") : biText("预演", "Preview")}
                </button>
                <button className="miniButton primary" disabled={!ready || previewRequired || Boolean(busyKey)} onClick={() => void runSemanticAction(draft, true)} type="button">
                  {busyKey === `confirm:${draft.semantic}` ? biText("确认中", "Confirming") : previewRequired ? biText("先预演", "Preview first") : biText("确认", "Confirm")}
                </button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="semanticRepairBenefit" data-testid={`${loopTestId}-benefit`}>
        <strong>{biText("修复收益", "Repair impact")}</strong>
        <span>{plan.benefitSummary}</span>
        <small>{plan.rerunInputs.length ? biText(`将重跑 ${plan.currentRunLabel}`, `Will rerun ${plan.currentRunLabel}`) : biText("没有找到原始输入。请先导入数据，再重跑画像。", "No original inputs found. Import data first, then rerun profiling.")}</small>
      </div>
      <ol className="metricRepairSteps">
        {plan.nextSteps.map((step) => <li key={step}>{step}</li>)}
      </ol>
      <div className="semanticRepairFooter">
        <button className="miniButton" disabled={Boolean(busyKey)} onClick={rerunSourceIntelligence} type="button">
          <Icon name="source" />
          {busyKey === "rerun-source-intelligence" ? biText("重跑中", "Rerunning") : biText("重跑画像", "Rerun profile")}
        </button>
        {onOpenEvidence ? (
          <button className="miniButton" onClick={onOpenEvidence} type="button">
            <Icon name="evidence" />
            {biText("看缺口", "View gaps")}
          </button>
        ) : null}
      </div>
      {comparison ? (
        <div className={comparison.delta >= 0 ? "semanticRepairComparison improved" : "semanticRepairComparison declined"} data-testid={`${loopTestId}-comparison`}>
          <strong>{comparison.before} → {comparison.after}</strong>
          <span>
            {comparison.delta >= 0
              ? biText(`新增 ${comparison.delta} 个可执行指标，减少 ${comparison.blockedDelta} 个阻塞。`, `${comparison.delta} more executable metrics, ${comparison.blockedDelta} fewer blockers.`)
              : biText(`可执行指标减少 ${Math.abs(comparison.delta)} 个，请检查本次字段确认。`, `${Math.abs(comparison.delta)} fewer executable metrics. Review this field confirmation.`)}
          </span>
        </div>
      ) : null}
      {result ? <div className="semanticRepairResult" data-testid={`${loopTestId}-result`}>{actionLabel(result)}</div> : null}
    </div>
  );
}
