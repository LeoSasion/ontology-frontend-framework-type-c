import { useCallback, useEffect, useMemo, useState } from "react";
import { cancelAnalysisJob, fetchAnalysisJobs } from "../apiJobs";
import type { AnalysisJob } from "../typesJobs";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import "./SourceJobRuntimePanel.css";

const ACTIVE_STATUSES = new Set(["created", "queued", "running", "cancel_requested"]);

function statusText(status: string) {
  const labels: Record<string, string> = {
    created: biText("已创建", "Created"),
    queued: biText("排队中", "Queued"),
    running: biText("执行中", "Running"),
    cancel_requested: biText("正在取消", "Canceling"),
    canceled: biText("已取消", "Canceled"),
    succeeded: biText("已完成", "Succeeded"),
    failed: biText("失败", "Failed"),
  };
  return labels[status] ?? status;
}

export function SourceJobRuntimePanel() {
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [error, setError] = useState("");
  const [canceling, setCanceling] = useState("");
  const sourceJobs = useMemo(
    () => jobs.filter((job) => ["source-intelligence", "import"].includes(job.kind)).slice(0, 8),
    [jobs],
  );
  const hasActive = sourceJobs.some((job) => ACTIVE_STATUSES.has(job.status));

  const refresh = useCallback(async () => {
    try {
      const payload = await fetchAnalysisJobs({ limit: 20 });
      setJobs(payload.jobs ?? []);
      setError("");
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : String(refreshError));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), hasActive ? 1500 : 8000);
    return () => window.clearInterval(timer);
  }, [hasActive, refresh]);

  async function cancel(job: AnalysisJob) {
    const preview = await cancelAnalysisJob(job.jobKey, { reason: "source-workbench-user-request" });
    if (preview.requiresConfirmation !== true) {
      await refresh();
      return;
    }
    if (!window.confirm(biText(`确认取消任务 ${job.label}？`, `Cancel job ${job.label}?`))) return;
    setCanceling(job.jobKey);
    try {
      await cancelAnalysisJob(job.jobKey, { reason: "source-workbench-user-request", confirm: true });
      await refresh();
    } finally {
      setCanceling("");
    }
  }

  if (!sourceJobs.length && !error) return null;
  return (
    <article className="workbenchPanel sourceJobRuntime" data-testid="source-job-runtime">
      <div className="tileHeader">
        <h3><Bilingual zh="导入与后台分析任务" en="Import and analysis jobs" /></h3>
        <span>{hasActive ? biText("运行中", "Active") : biText("最近记录", "Recent")}</span>
      </div>
      {error ? <p className="sourceJobError">{error}</p> : null}
      <div className="sourceJobList">
        {sourceJobs.map((job) => (
          <div className={`sourceJobRow ${job.status}`} key={job.jobKey}>
            <Icon name={job.status === "succeeded" ? "check" : "evidence"} />
            <div>
              <strong>{job.label}</strong>
              <span>{statusText(job.status)} · {job.stage} · {job.progress}%</span>
              <progress max={100} value={job.progress} />
              {job.error?.message ? <small>{String(job.error.message)}</small> : null}
            </div>
            {ACTIVE_STATUSES.has(job.status) && job.status !== "cancel_requested" ? (
              <button className="miniButton" disabled={canceling === job.jobKey} onClick={() => void cancel(job)} type="button">
                {biText("取消", "Cancel")}
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </article>
  );
}
