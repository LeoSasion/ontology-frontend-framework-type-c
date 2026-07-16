import { useEffect, useRef, useState } from "react";
import {
  getAgentProviderEvaluations,
  getAgentRuntimeProfiles,
  getBusinessExpressionCases,
  getPlanQualityScorecards,
  runPlanQualityEvaluation,
  selectAgentRuntimeProfile,
  type AgentRuntimeProfileStatus,
  type PlanQualityScorecard,
} from "../apiAgentRuntimeProfiles";
import { getRuntimeCatalog } from "../apiWorkspaceContext";
import type { RuntimeCatalogSummary } from "../typesWorkspaceContext";
import { Bilingual, biText } from "./Bilingual";
import "./planQualityPanel.css";

type Props = { workspaceId: string };

export default function SettingsAgentRuntimeProfilePanel({ workspaceId }: Props) {
  const [profiles, setProfiles] = useState<AgentRuntimeProfileStatus[]>([]);
  const [summary, setSummary] = useState<{ total: number; passed: number; fallbacks: number; validationFailures: number; providerWriteCount: number } | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [runtimeCatalog, setRuntimeCatalog] = useState<RuntimeCatalogSummary | null>(null);
  const [qualityScorecard, setQualityScorecard] = useState<PlanQualityScorecard | null>(null);
  const [qualityCaseCount, setQualityCaseCount] = useState(0);
  const [qualityCategories, setQualityCategories] = useState<string[]>([]);
  const [qualityBusy, setQualityBusy] = useState(false);
  const requestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const qualityRunRef = useRef(0);
  const workspaceRef = useRef(workspaceId);
  workspaceRef.current = workspaceId;

  async function refresh() {
    requestRef.current?.controller.abort();
    const controller = new AbortController();
    const requestId = (requestRef.current?.id ?? 0) + 1;
    requestRef.current = { id: requestId, controller };
    const expectedWorkspace = workspaceId;
    const [catalogResult, evaluationsResult, runtimeResult, casesResult, scorecardsResult] = await Promise.allSettled([
      getAgentRuntimeProfiles(workspaceId, controller.signal),
      getAgentProviderEvaluations(workspaceId, controller.signal),
      getRuntimeCatalog(controller.signal),
      getBusinessExpressionCases(controller.signal),
      getPlanQualityScorecards(controller.signal),
    ]);
    if (requestRef.current?.id !== requestId || controller.signal.aborted) return;
    const issues: string[] = [];
    if (catalogResult.status === "fulfilled") setProfiles(catalogResult.value.runtimeProfiles ?? []);
    else issues.push(biText("Runtime Profile 暂时不可用", "Runtime profiles are temporarily unavailable"));
    if (evaluationsResult.status === "fulfilled") setSummary(evaluationsResult.value.summary);
    else issues.push(biText("评估摘要暂时不可用", "Evaluation summary is temporarily unavailable"));
    if (runtimeResult.status === "fulfilled") setRuntimeCatalog(runtimeResult.value.runtimeCatalog);
    else {
      setRuntimeCatalog(null);
      issues.push(biText("运行目录暂时不可用", "Runtime catalog is temporarily unavailable"));
    }
    if (casesResult.status === "fulfilled") {
      setQualityCaseCount(casesResult.value.caseCount ?? 0);
      setQualityCategories(casesResult.value.categories ?? []);
    } else if (casesResult.reason?.name !== "AbortError") {
      issues.push(biText("业务表达基准暂时不可用", "Business expression cases are temporarily unavailable"));
    }
    if (scorecardsResult.status === "fulfilled" && scorecardsResult.value.workspaceId === expectedWorkspace) {
      setQualityScorecard(scorecardsResult.value.latestCurrent ?? scorecardsResult.value.scorecards?.[0] ?? null);
    } else if (scorecardsResult.status === "fulfilled") {
      issues.push(biText("质量回执与当前工作区不一致", "Quality receipt does not match the active workspace"));
    } else if (scorecardsResult.reason?.name !== "AbortError") {
      issues.push(biText("计划质量摘要暂时不可用", "Plan quality summary is temporarily unavailable"));
    }
    setMessage(issues.join("；"));
  }

  useEffect(() => {
    qualityRunRef.current += 1;
    setQualityBusy(false);
    setQualityScorecard(null);
    setQualityCaseCount(0);
    setQualityCategories([]);
    void refresh().catch((error) => setMessage(error instanceof Error ? error.message : String(error)));
    return () => requestRef.current?.controller.abort();
  }, [workspaceId]);

  async function choose(profileId: string) {
    if (pending !== profileId) {
      await selectAgentRuntimeProfile(workspaceId, profileId, false);
      setPending(profileId);
      setMessage(biText("请再次确认；切换只影响模型解释，不改变字段、SQL、回执或确认边界。", "Confirm once more. The switch affects model explanation only, never fields, SQL, receipts, or confirmation boundaries."));
      return;
    }
    setBusy(true);
    try {
      await selectAgentRuntimeProfile(workspaceId, profileId, true);
      setPending(null);
      setMessage(biText("Runtime Profile 已更新。", "Runtime Profile updated."));
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function runQualityBenchmark() {
    const expectedWorkspace = workspaceId;
    const runId = qualityRunRef.current + 1;
    qualityRunRef.current = runId;
    setQualityBusy(true);
    setMessage("");
    try {
      const result = await runPlanQualityEvaluation();
      if (qualityRunRef.current !== runId || workspaceRef.current !== expectedWorkspace) return;
      if (result.workspaceId !== expectedWorkspace) {
        throw new Error(biText("质量回执未绑定当前工作区。", "The quality receipt is not bound to the active workspace."));
      }
      setQualityScorecard({ ...result.scorecard, current: true, usableForRelease: result.scorecard.releaseReady });
      setMessage(result.scorecard.releaseReady
        ? biText("本地计划质量基准已通过。", "The local plan quality benchmark passed.")
        : biText("基准已完成；请展开失败 Case 查看缺口。", "Benchmark completed. Expand failed cases to inspect gaps."));
    } catch (error) {
      if (qualityRunRef.current !== runId || workspaceRef.current !== expectedWorkspace) return;
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (qualityRunRef.current === runId && workspaceRef.current === expectedWorkspace) setQualityBusy(false);
    }
  }

  const qualityState = !qualityScorecard
    ? biText("尚未运行", "Not run")
    : qualityScorecard.current === false
      ? biText("需重跑", "Stale")
      : qualityScorecard.releaseReady
        ? biText("达到门槛", "Ready")
        : biText("未达门槛", "Below threshold");
  const failedQualityCases = qualityScorecard?.caseResults.filter((item) => item.status !== "passed") ?? [];

  return (
    <div className="runtimeProfilePanel" data-testid="agent-runtime-profile-panel">
      <div className="settingsSectionHeading">
        <div>
          <strong><Bilingual zh="Agent Runtime Profile" en="Agent Runtime Profile" /></strong>
          <p><Bilingual zh="Provider 只解释本地确定性证据；没有 SQL、工具或写入权限。" en="Providers explain deterministic local evidence only, with no SQL, tools, or write access." /></p>
        </div>
        <span className="settingsStatusPill">{summary ? `${summary.passed}/${summary.total} ${biText("通过", "passed")}` : biText("加载中", "Loading")}</span>
      </div>
      {runtimeCatalog ? (
        <div className="runtimeCatalogSummary" data-testid="settings-runtime-catalog">
          <span><strong>{runtimeCatalog.tables.length}</strong><small>{biText("数据表", "tables")}</small></span>
          <span><strong>{runtimeCatalog.metrics.length}</strong><small>{biText("指标", "metrics")}</small></span>
          <span><strong>{runtimeCatalog.relationships.length}</strong><small>{biText("关系", "links")}</small></span>
          <span><strong>{runtimeCatalog.analyticalSkills.enabled.length}</strong><small>Skills</small></span>
          <span><strong>{runtimeCatalog.domainPacks.enabled.length}</strong><small>Domain Packs</small></span>
          <span><strong>{runtimeCatalog.capabilities.length}</strong><small>{biText("受控能力", "capabilities")}</small></span>
        </div>
      ) : null}
      <section className="planQualitySection" data-testid="settings-plan-quality">
        <div className="planQualityHeading">
          <div>
            <strong><Bilingual zh="业务理解质量" en="Business understanding quality" /></strong>
            <p><Bilingual zh="固定中立 Case 在内存夹具中重放；不读取业务行，也不调用 Provider。" en="Fixed neutral cases replay in memory without reading business rows or calling a Provider." /></p>
          </div>
          <div className="planQualityActions">
            <span className={`settingsStatusPill ${qualityScorecard?.releaseReady ? "success" : ""}`}>{qualityState}</span>
            <button className="secondaryButton" data-testid="run-plan-quality" disabled={qualityBusy || qualityCaseCount === 0} onClick={() => void runQualityBenchmark()} type="button">
              {qualityBusy ? biText("评测中…", "Evaluating…") : biText("运行本地基准", "Run local benchmark")}
            </button>
          </div>
        </div>
        {qualityScorecard ? (
          <>
            <dl className="planQualityMetrics" aria-label={biText("计划质量指标", "Plan quality metrics")}>
              <div><dt>{biText("核心槽位", "Core slots")}</dt><dd>{Math.round(qualityScorecard.metrics.coreSlotAccuracy * 100)}%</dd></div>
              <div><dt>{biText("字段精度", "Field precision")}</dt><dd>{Math.round(qualityScorecard.metrics.fieldBindingPrecision * 100)}%</dd></div>
              <div><dt>{biText("安全澄清", "Safe clarification")}</dt><dd>{Math.round(qualityScorecard.metrics.safeClarificationRate * 100)}%</dd></div>
              <div><dt>{biText("证据覆盖", "Evidence coverage")}</dt><dd>{Math.round(qualityScorecard.metrics.evidenceCoverage * 100)}%</dd></div>
              <div><dt>{biText("重放一致", "Replay consistency")}</dt><dd>{Math.round(qualityScorecard.metrics.replayConsistency * 100)}%</dd></div>
            </dl>
            <p className="planQualityBoundary">
              <Bilingual
                zh={`零容忍：静默消歧 ${qualityScorecard.metrics.silentDisambiguationCount} · 越权 ${qualityScorecard.metrics.permissionEscalationCount} · 跨工作区 ${qualityScorecard.metrics.crossWorkspaceLeakCount} · 跨 Pack ${qualityScorecard.metrics.domainPackLeakCount}`}
                en={`Zero tolerance: silent disambiguation ${qualityScorecard.metrics.silentDisambiguationCount} · permission escalation ${qualityScorecard.metrics.permissionEscalationCount} · cross-workspace ${qualityScorecard.metrics.crossWorkspaceLeakCount} · cross-Pack ${qualityScorecard.metrics.domainPackLeakCount}`}
              />
            </p>
            <details className="planQualityDetails" data-testid="plan-quality-details">
              <summary>{failedQualityCases.length
                ? biText(`${failedQualityCases.length} 个 Case 需要修复`, `${failedQualityCases.length} cases need attention`)
                : biText(`${qualityScorecard.caseResults.length} 个 Case 全部通过`, `All ${qualityScorecard.caseResults.length} cases passed`)}</summary>
              <div className="planQualityCaseList">
                {(failedQualityCases.length ? failedQualityCases : qualityScorecard.caseResults).map((item) => (
                  <div key={item.caseId}>
                    <strong>{item.caseId}</strong>
                    <span>{item.category} · {item.planStatus} · {item.businessStatus}</span>
                    <small>{item.error || (item.status === "passed" ? biText("通过", "Passed") : Object.entries(item.checks).filter(([, value]) => !value).map(([key]) => key).join(" · "))}</small>
                  </div>
                ))}
              </div>
            </details>
          </>
        ) : (
          <div className="planQualityEmpty">
            <strong><Bilingual zh={`${qualityCaseCount || "—"} 个固定 Case 等待运行`} en={`${qualityCaseCount || "—"} fixed cases are ready to run`} /></strong>
            <span>{qualityCategories.length ? qualityCategories.join(" · ") : biText("正在加载 Case Catalog", "Loading the case catalog")}</span>
          </div>
        )}
      </section>
      <div className="runtimeProfileGrid">
        {profiles.map((profile) => (
          <button
            className={`runtimeProfileCard ${profile.selected ? "selected" : ""}`}
            disabled={busy || (!profile.configured && profile.profileId !== "deterministic")}
            key={profile.profileId}
            onClick={() => void choose(profile.profileId)}
            type="button"
          >
            <strong>{profile.profileId}</strong>
            <span>{profile.provider} · {profile.model}</span>
            <small>{profile.structuredOutput} · {profile.retries} retry</small>
            <em>{profile.selected ? biText("当前", "Active") : !profile.configured ? biText("未配置", "Not configured") : pending === profile.profileId ? biText("再次点击确认", "Click again to confirm") : biText("可选择", "Available")}</em>
          </button>
        ))}
      </div>
      {summary ? <p className="runtimeProfileAudit"><Bilingual zh={`最近 ${summary.total} 次：降级 ${summary.fallbacks}，校验失败 ${summary.validationFailures}，Provider 写入 ${summary.providerWriteCount}`} en={`Last ${summary.total}: ${summary.fallbacks} fallbacks, ${summary.validationFailures} validation failures, ${summary.providerWriteCount} Provider writes`} /></p> : null}
      {runtimeCatalog ? (
        <details className="runtimeCatalogDetails">
          <summary>{biText("查看运行目录与安全边界", "View runtime catalog and boundaries")}</summary>
          <dl>
            <div><dt>{biText("当前解释 Profile", "Active profile")}</dt><dd>{runtimeCatalog.agentRuntime.selectedProfileId}</dd></div>
            <div><dt>{biText("查询引擎", "Query engine")}</dt><dd>{runtimeCatalog.queryRuntime.engine} · {runtimeCatalog.queryRuntime.available ? biText("可用", "available") : biText("降级", "fallback")}</dd></div>
            <div><dt>{biText("候选可授权连接", "Candidates authorize joins")}</dt><dd>{biText("否", "No")}</dd></div>
            <div><dt>fingerprint</dt><dd>{runtimeCatalog.fingerprint}</dd></div>
          </dl>
        </details>
      ) : null}
      {message ? <p className="settingsInlineMessage" role="status">{message}</p> : null}
    </div>
  );
}
