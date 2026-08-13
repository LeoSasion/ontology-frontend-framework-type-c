import type { AnalysisJob } from "../typesJobs";
import type {
  SqlServerActivationPayload,
  SqlServerAdapterCapability,
  SqlServerAdapterContract,
  SqlServerCatalog,
  SqlServerSnapshotPlan,
  SqlServerSnapshotReceipt,
} from "../typesSqlServerSnapshot";
import { Bilingual, biText } from "./Bilingual";
import { ImportJobStatusCard } from "./ImportJobStatusCard";
import "./sqlServerAdapterCapabilityPanel.css";

type SqlServerAdapterCapabilityPanelProps = {
  contract: SqlServerAdapterContract;
  busy?: "test" | "discover" | "plan" | "snapshot" | "activate" | null;
  catalog?: SqlServerCatalog;
  plan?: SqlServerSnapshotPlan;
  snapshot?: SqlServerSnapshotReceipt;
  job?: AnalysisJob;
  activation?: SqlServerActivationPayload;
  onTest?: () => void;
  onDiscover?: () => void;
  onPlan?: () => void;
  onSnapshot?: () => void;
  onActivate?: () => void;
};

const capabilityCopy: Record<SqlServerAdapterCapability, { zh: string; en: string }> = {
  unavailable: { zh: "环境未就绪", en: "Environment unavailable" },
  ready_for_test: { zh: "可以测试只读连接", en: "Ready for read-only test" },
  ready_for_snapshot: { zh: "快照计划已就绪", en: "Snapshot plan ready" },
  active: { zh: "来源已激活", en: "Source active" },
};

function stepState(done: boolean, current: boolean) {
  return done ? "done" : current ? "current" : "pending";
}

export function SqlServerAdapterCapabilityPanel({
  contract,
  busy = null,
  catalog,
  plan,
  snapshot,
  job,
  activation,
  onTest,
  onDiscover,
  onPlan,
  onSnapshot,
  onActivate,
}: SqlServerAdapterCapabilityPanelProps) {
  const copy = capabilityCopy[contract.capability];
  const unavailable = contract.capability === "unavailable";
  const canTest = contract.capability === "ready_for_test" && Boolean(onTest);
  const canDiscover = !unavailable && Boolean(onDiscover);
  const canPlan = !unavailable && Boolean(catalog) && !plan && Boolean(onPlan);
  const canSnapshot = contract.capability === "ready_for_snapshot" && Boolean(plan) && !snapshot && Boolean(onSnapshot);
  const canActivate = contract.capability === "ready_for_snapshot" && Boolean(snapshot?.manifestFingerprint)
    && (!job || ["failed", "canceled"].includes(job.status)) && Boolean(onActivate);
  const journalCommitted = activation?.activation.status === "committed" && activation.activation.phase === "finalized";
  const pipeline = [
    { label: biText("目录", "Catalog"), state: stepState(Boolean(catalog), !catalog) },
    { label: biText("计划", "Plan"), state: stepState(Boolean(plan), Boolean(catalog) && !plan) },
    { label: biText("暂存", "Stage"), state: stepState(Boolean(snapshot), Boolean(plan) && !snapshot) },
    { label: "Durable Import", state: stepState(job?.status === "succeeded", Boolean(job) && job?.status !== "succeeded") },
    { label: "Journal", state: stepState(journalCommitted, job?.status === "succeeded" && !journalCommitted) },
  ];

  return (
    <section className="sqlServerCapability" data-capability={contract.capability} data-testid="sqlserver-adapter-capability">
      <div className="sqlServerCapability__header">
        <div>
          <span className="eyebrow"><Bilingual zh="可选只读来源" en="Optional read-only source" /></span>
          <h3>SQL Server</h3>
        </div>
        <span className="statusPill" data-testid="sqlserver-capability-status"><Bilingual zh={copy.zh} en={copy.en} /></span>
      </div>

      <p className="quietText">
        {biText(
          "只读取允许目录并生成有界快照；不会接受任意 SQL，也不会在不可用时切换到其他来源。",
          "Reads only the allowed catalog into a bounded snapshot. Arbitrary SQL and source fallback are disabled.",
        )}
      </p>

      {contract.reason ? (
        <p className="sqlServerCapability__notice" role="status" data-testid="sqlserver-capability-reason">{contract.reason}</p>
      ) : null}

      {contract.config ? (
        <dl className="sqlServerCapability__facts">
          <div><dt>{biText("目标别名", "Target alias")}</dt><dd>{contract.config.hostAlias}</dd></div>
          <div><dt>{biText("数据库", "Database")}</dt><dd>{contract.config.database}</dd></div>
          <div><dt>{biText("加密", "Encryption")}</dt><dd>{contract.config.encryption}</dd></div>
          <div><dt>{biText("只读凭据", "Read-only credential")}</dt><dd>{contract.config.credentialConfigured ? biText("已配置", "Configured") : biText("未配置", "Missing")}</dd></div>
        </dl>
      ) : null}

      <ol className="sqlServerCapability__pipeline" aria-label={biText("激活进度", "Activation progress")}>
        {pipeline.map((step) => (
          <li data-state={step.state} key={step.label}><span aria-hidden="true" />{step.label}</li>
        ))}
      </ol>

      <div className="buttonRow sqlServerCapability__actions">
        <button className="secondaryButton" data-testid="sqlserver-test-button" disabled={!canTest || busy !== null} onClick={onTest} type="button">
          {busy === "test" ? biText("正在验证…", "Testing…") : biText("测试连接", "Test connection")}
        </button>
        <button className="secondaryButton" data-testid="sqlserver-discover-button" disabled={!canDiscover || busy !== null} onClick={onDiscover} type="button">
          {busy === "discover" ? biText("正在读取目录…", "Reading catalog…") : biText("读取目录", "Read catalog")}
        </button>
        <button className="secondaryButton" data-testid="sqlserver-plan-button" disabled={!canPlan || busy !== null} onClick={onPlan} type="button">
          {busy === "plan" ? biText("正在锁定计划…", "Locking plan…") : biText("准备快照计划", "Prepare snapshot plan")}
        </button>
        <button className="primaryButton" data-testid="sqlserver-snapshot-button" disabled={!canSnapshot || busy !== null} onClick={onSnapshot} type="button">
          {busy === "snapshot" ? biText("正在创建快照…", "Creating snapshot…") : biText("确认创建快照", "Confirm snapshot")}
        </button>
        <button className="primaryButton" data-testid="sqlserver-activate-button" disabled={!canActivate || busy !== null} onClick={onActivate} type="button">
          {busy === "activate" ? biText("正在提交任务…", "Queuing job…") : biText("确认激活来源", "Confirm activation")}
        </button>
      </div>

      {plan ? (
        <p className="quietText" data-testid="sqlserver-plan-status">
          {biText("计划表数", "Planned tables")}: {plan.selections.length} · {biText("上限", "Row cap")}: {plan.budget.maxRowsPerTable.toLocaleString()}
        </p>
      ) : null}
      {snapshot ? (
        <p className="quietText" data-testid="sqlserver-snapshot-status">
          {biText("暂存完成", "Staged")}: {snapshot.totalRows?.toLocaleString() ?? 0} {biText("行", "rows")} · {biText("等待 Durable Import", "Awaiting Durable Import")}
        </p>
      ) : null}
      {job ? <ImportJobStatusCard job={job} /> : null}
      {activation ? (
        <p className="sqlServerCapability__journal" data-state={journalCommitted ? "done" : "pending"} data-testid="sqlserver-activation-status" role="status">
          <strong>Activation Journal</strong>
          <span>{journalCommitted ? biText("finalized · committed", "finalized · committed") : String(activation.activation.status)}</span>
        </p>
      ) : null}
    </section>
  );
}
