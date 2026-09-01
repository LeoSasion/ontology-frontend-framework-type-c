import type { AnalysisJob } from "../typesJobs";
import { biText } from "./Bilingual";

type ImportJobStatusCardProps = {
  job: AnalysisJob;
  busy?: boolean;
  onCancel?: (job: AnalysisJob) => Promise<void> | void;
  onResume?: (job: AnalysisJob) => Promise<void> | void;
};

const terminalStatuses = new Set(["succeeded", "failed", "canceled"]);

function stageLabel(stage: string) {
  return ({
    validate_plan: biText("校验导入计划", "Validate plan"),
    stage_source: biText("暂存来源数据", "Stage source"),
    publish_replica: biText("发布数据集目录", "Publish dataset catalog"),
    switch_source_run: biText("切换当前来源", "Switch current source"),
    postprocess: biText("完成后处理", "Post-process"),
    reconcile: biText("核对中断状态", "Reconcile interrupted state"),
  } as Record<string, string>)[stage] ?? stage;
}

function statusLabel(status: string) {
  return ({
    queued: biText("等待执行", "Queued"),
    running: biText("正在执行", "Running"),
    cancel_requested: biText("正在取消", "Cancel requested"),
    canceled: biText("已取消", "Canceled"),
    succeeded: biText("已完成", "Succeeded"),
    failed: biText("失败", "Failed"),
    needs_attention: biText("需要处理", "Needs attention"),
  } as Record<string, string>)[status] ?? status;
}

export function ImportJobStatusCard({ job, busy = false, onCancel, onResume }: ImportJobStatusCardProps) {
  const technical = {
    schema: job.schema,
    jobKey: job.jobKey,
    inputFingerprint: job.inputFingerprint,
    sourceRunId: job.sourceRunId,
    error: job.error,
  };
  return (
    <section className="operationReceipt" data-testid="import-job-status" role="status">
      <div className="tileHeader">
        <div>
          <span className={`statusBadge ${job.status === "succeeded" ? "ok" : job.status === "failed" || job.status === "needs_attention" ? "warn" : ""}`}>
            {statusLabel(job.status)}
          </span>
          <h4>{job.label}</h4>
          <p>{stageLabel(job.stage)} · {job.progress}%</p>
        </div>
        <div className="buttonRow tight">
          {job.status === "needs_attention" && onResume ? (
            <button className="primaryButton compactAction" disabled={busy} onClick={() => void onResume(job)} type="button">
              {biText("核对后恢复", "Resume after check")}
            </button>
          ) : null}
          {!terminalStatuses.has(job.status) && job.status !== "needs_attention" && onCancel ? (
            <button className="miniButton" disabled={busy || job.status === "cancel_requested"} onClick={() => void onCancel(job)} type="button">
              {job.status === "cancel_requested" ? biText("正在取消", "Canceling") : biText("取消任务", "Cancel job")}
            </button>
          ) : null}
        </div>
      </div>
      <progress aria-label={stageLabel(job.stage)} max={100} value={job.progress} />
      {job.error?.recoveryAction ? <p>{biText("下一步", "Next step")}: {String(job.error.recoveryAction)}</p> : null}
      <details>
        <summary>{biText("技术回执", "Technical receipt")}</summary>
        <pre>{JSON.stringify(technical, null, 2)}</pre>
      </details>
    </section>
  );
}
