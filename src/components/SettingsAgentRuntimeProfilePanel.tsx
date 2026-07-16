import { useEffect, useState } from "react";
import { getAgentProviderEvaluations, getAgentRuntimeProfiles, selectAgentRuntimeProfile, type AgentRuntimeProfileStatus } from "../apiAgentRuntimeProfiles";
import { getRuntimeCatalog } from "../apiWorkspaceContext";
import type { RuntimeCatalogSummary } from "../typesWorkspaceContext";
import { Bilingual, biText } from "./Bilingual";

type Props = { workspaceId: string };

export default function SettingsAgentRuntimeProfilePanel({ workspaceId }: Props) {
  const [profiles, setProfiles] = useState<AgentRuntimeProfileStatus[]>([]);
  const [summary, setSummary] = useState<{ total: number; passed: number; fallbacks: number; validationFailures: number; providerWriteCount: number } | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [runtimeCatalog, setRuntimeCatalog] = useState<RuntimeCatalogSummary | null>(null);

  async function refresh() {
    const [catalogResult, evaluationsResult, runtimeResult] = await Promise.allSettled([
      getAgentRuntimeProfiles(workspaceId),
      getAgentProviderEvaluations(workspaceId),
      getRuntimeCatalog(),
    ]);
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
    setMessage(issues.join("；"));
  }

  useEffect(() => {
    void refresh().catch((error) => setMessage(error instanceof Error ? error.message : String(error)));
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
