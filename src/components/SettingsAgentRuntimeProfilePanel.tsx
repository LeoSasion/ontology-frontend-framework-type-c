import { useEffect, useState } from "react";
import { getAgentProviderEvaluations, getAgentRuntimeProfiles, selectAgentRuntimeProfile, type AgentRuntimeProfileStatus } from "../apiAgentRuntimeProfiles";
import { Bilingual, biText } from "./Bilingual";

type Props = { workspaceId: string };

export default function SettingsAgentRuntimeProfilePanel({ workspaceId }: Props) {
  const [profiles, setProfiles] = useState<AgentRuntimeProfileStatus[]>([]);
  const [summary, setSummary] = useState<{ total: number; passed: number; fallbacks: number; validationFailures: number; providerWriteCount: number } | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function refresh() {
    const [catalog, evaluations] = await Promise.all([
      getAgentRuntimeProfiles(workspaceId),
      getAgentProviderEvaluations(workspaceId),
    ]);
    setProfiles(catalog.runtimeProfiles ?? []);
    setSummary(evaluations.summary);
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
      {message ? <p className="settingsInlineMessage" role="status">{message}</p> : null}
    </div>
  );
}
