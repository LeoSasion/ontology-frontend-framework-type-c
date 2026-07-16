import "./workspaceContextPanels.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getBusinessFieldProfiles } from "../apiWorkspaceContext";
import type { BusinessFieldProfile, BusinessFieldProfileCollection, BusinessFieldProfileStatus } from "../typesWorkspaceContext";
import { Bilingual, biText } from "./Bilingual";

type Props = { workspaceId: string; tableKey: string };

const statusOrder: BusinessFieldProfileStatus[] = ["ready", "ambiguous", "blocked", "stale"];

function statusLabel(status: BusinessFieldProfileStatus) {
  const labels = {
    ready: biText("可用", "Ready"),
    ambiguous: biText("待确认", "Review"),
    blocked: biText("受阻", "Blocked"),
    stale: biText("已过期", "Stale"),
  };
  return labels[status];
}

function percent(value: number) {
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

function FieldProfileRow({ profile }: { profile: BusinessFieldProfile }) {
  const confirmed = profile.semantic.authority === "manual-confirmed";
  return (
    <details className="businessFieldProfileRow" data-status={profile.status}>
      <summary>
        <span>
          <strong>{profile.fieldRef.fieldName}</strong>
          <small>{profile.observedShape.logicalType} · {profile.semantic.savedRole}</small>
        </span>
        <span className={`workspaceContextPill ${profile.status}`}>{statusLabel(profile.status)}</span>
      </summary>
      <div className="businessFieldProfileBody">
        <dl>
          <div><dt>{biText("空值率", "Null rate")}</dt><dd>{percent(profile.observedShape.nullRate)}</dd></div>
          <div><dt>{biText("唯一值率", "Unique ratio")}</dt><dd>{percent(profile.observedShape.uniqueRatio)}</dd></div>
          <div><dt>{biText("业务含义", "Business meaning")}</dt><dd>{confirmed ? biText("已确认", "Confirmed") : biText("仅候选", "Candidate")}</dd></div>
          <div><dt>{biText("敏感性", "Sensitivity")}</dt><dd>{profile.sensitivity.level}</dd></div>
        </dl>
        {profile.semantic.statusCandidates.observedDistinctCount > 0 ? (
          <p><strong>{biText("分类基数", "Category cardinality")}</strong><span>{biText(`观察到 ${profile.semantic.statusCandidates.observedDistinctCount} 个不同值；原值不展示。`, `${profile.semantic.statusCandidates.observedDistinctCount} distinct values observed; raw values are withheld.`)}</span></p>
        ) : null}
        {profile.observedShape.timeCoverage ? (
          <p><strong>{biText("时间覆盖", "Time coverage")}</strong><span>{profile.observedShape.timeCoverage.minimum} → {profile.observedShape.timeCoverage.maximum}</span></p>
        ) : null}
        {profile.warnings.length || profile.blockers.length ? (
          <p><strong>{biText("复核提示", "Review notes")}</strong><span>{[...profile.blockers, ...profile.warnings].join(" · ")}</span></p>
        ) : null}
        <small className="workspaceContextTechnical">{profile.profileAlgorithmVersion} · {profile.fingerprint.slice(0, 12)}</small>
      </div>
    </details>
  );
}

export default function SourceWorkbenchBusinessFieldProfilePanel({ workspaceId, tableKey }: Props) {
  const [payload, setPayload] = useState<BusinessFieldProfileCollection | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const requestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const nextRequestId = useRef(0);

  const load = useCallback(() => {
    if (!tableKey) return Promise.resolve();
    requestRef.current?.controller.abort();
    const controller = new AbortController();
    const requestId = ++nextRequestId.current;
    requestRef.current = { id: requestId, controller };
    setLoading(true);
    setError("");
    return getBusinessFieldProfiles(tableKey, controller.signal)
      .then((result) => {
        if (requestRef.current?.id !== requestId || controller.signal.aborted) return;
        const responseMatchesRequest = result.workspaceId === workspaceId
          && result.requestScope.tableKey === tableKey
          && result.profiles.every((profile) => profile.fieldRef.workspaceId === workspaceId && profile.fieldRef.tableKey === tableKey);
        if (!responseMatchesRequest) throw new Error(biText("字段画像响应与当前工作区或表不匹配。", "Field profile response does not match the current workspace or table."));
        setPayload(result);
      })
      .catch((reason) => {
        if (controller.signal.aborted || requestRef.current?.id !== requestId || (reason instanceof DOMException && reason.name === "AbortError")) return;
        setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => {
        if (requestRef.current?.id === requestId && !controller.signal.aborted) setLoading(false);
      });
  }, [tableKey, workspaceId]);

  useEffect(() => {
    setPayload(null);
    void load();
    return () => requestRef.current?.controller.abort();
  }, [load]);

  const counts = useMemo(() => Object.fromEntries(statusOrder.map((status) => [status, payload?.profiles.filter((item) => item.status === status).length ?? 0])) as Record<BusinessFieldProfileStatus, number>, [payload]);
  const sensitiveCount = payload?.profiles.filter((item) => item.sensitivity.level !== "none").length ?? 0;

  return (
    <article className="workbenchPanel widePanel advancedPanel businessFieldProfilePanel" data-testid="source-business-field-profile" aria-busy={loading}>
      <div className="tileHeader">
        <div>
          <h3><Bilingual zh="字段画像与业务歧义" en="Field profiles and ambiguity" /></h3>
          <span><Bilingual zh="观察事实与业务候选分开；候选不会自动确认，也不能自动授权跨表连接。" en="Observed facts stay separate from business candidates; candidates never auto-confirm or authorize joins." /></span>
        </div>
        <button className="miniButton" disabled={loading || !tableKey} onClick={() => void load()} type="button">{biText("刷新画像", "Refresh")}</button>
      </div>
      <div className="workspaceContextStats">
        <span><strong>{counts.ready}</strong><small>{biText("可用", "ready")}</small></span>
        <span><strong>{counts.ambiguous}</strong><small>{biText("待确认", "review")}</small></span>
        <span><strong>{counts.blocked + counts.stale}</strong><small>{biText("受阻或过期", "blocked/stale")}</small></span>
        <span><strong>{sensitiveCount}</strong><small>{biText("敏感字段", "sensitive")}</small></span>
      </div>
      {error ? <div className="workspaceContextError" role="alert"><span>{error}</span><button className="miniButton" onClick={() => void load()} type="button">{biText("重试", "Retry")}</button></div> : null}
      {loading && !payload ? <div className="workspaceContextLoading" aria-label={biText("正在加载字段画像", "Loading field profiles")}><span /><span /><span /></div> : null}
      {payload ? (
        <div className="businessFieldProfileList">
          {payload.profiles.slice(0, 80).map((profile) => <FieldProfileRow key={`${profile.fieldRef.tableKey}.${profile.fieldRef.fieldName}`} profile={profile} />)}
          {payload.profiles.length > 80 ? <p className="quietText">{biText(`当前显示前 80 / ${payload.profiles.length} 个字段。`, `Showing the first 80 of ${payload.profiles.length} fields.`)}</p> : null}
        </div>
      ) : null}
    </article>
  );
}
