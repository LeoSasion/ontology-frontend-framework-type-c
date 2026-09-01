import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  activateSqlServerSnapshot,
  createSqlServerSnapshot,
  discoverSqlServerCatalog,
  fetchSqlServerActivationStatus,
  planSqlServerSnapshot,
  probeSqlServerAdapter,
  testSqlServerConnection,
} from "../apiSqlServerSnapshot";
import { fetchImportJob } from "../apiImportJobs";
import { invalidateTableQueryCache } from "../dashboardWidgetQueryRuntime";
import type { AnalysisJob } from "../typesJobs";
import type {
  SqlServerActivationPayload,
  SqlServerAdapterContract,
  SqlServerCatalog,
  SqlServerSnapshotPlan,
  SqlServerSnapshotReceipt,
  SqlServerSnapshotSelectionInput,
} from "../typesSqlServerSnapshot";
import { Bilingual, biText } from "./Bilingual";
import { loadSqlServerAdapterCapabilityPanel } from "./sqlServerAdapterLoader";

const SqlServerAdapterCapabilityPanel = lazy(() => (
  loadSqlServerAdapterCapabilityPanel().then((module) => ({
    default: module.SqlServerAdapterCapabilityPanel,
  }))
));

type SqlServerOperation = "probe" | "test" | "discover" | "plan" | "snapshot" | "activate";

type ActiveRequest = {
  id: number;
  connectorKey: string;
  operation: SqlServerOperation;
  controller: AbortController;
};

type ConnectorScopedValue<T> = {
  connectorKey: string;
  value: T;
};

type SqlServerLifecycle = {
  catalog?: SqlServerCatalog;
  plan?: SqlServerSnapshotPlan;
  snapshot?: SqlServerSnapshotReceipt;
  activationRequestKey?: string;
  job?: AnalysisJob;
  activation?: SqlServerActivationPayload;
};

type SourceWorkbenchSqlServerCapabilityProps = {
  connectorKey: string;
  connectorName: string;
};

function publicErrorMessage(error: unknown) {
  const message = error instanceof Error && error.message.trim()
    ? error.message.trim()
    : biText("本地服务未返回可用的错误说明。", "The local service did not return a usable error message.");
  return message
    .replace(/(?:pwd|pass(?:word)?|secret|token|user\s*id|uid)\s*[:=]\s*[^;\s,]+/gi, "[redacted]")
    .replace(/\/\/[^@\s/]+@/g, "//[redacted]@")
    .replace(/\s+/g, " ")
    .slice(0, 320);
}

function activatedTableKeys(job?: AnalysisJob) {
  const keys = new Set<string>();
  const inputKeys = job?.input.tableKeys;
  if (Array.isArray(inputKeys)) inputKeys.map(String).filter(Boolean).forEach((key) => keys.add(key));
  const result = job?.result && typeof job.result === "object" && !Array.isArray(job.result)
    ? job.result as Record<string, unknown>
    : null;
  const tables = Array.isArray(result?.tables) ? result.tables : [];
  for (const table of tables) {
    if (!table || typeof table !== "object" || Array.isArray(table)) continue;
    const tableKey = String((table as Record<string, unknown>).tableKey ?? "").trim();
    if (tableKey) keys.add(tableKey);
  }
  return [...keys];
}

function shortHash(value: string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function targetTableKey(resourceKey: string, used: Set<string>) {
  const normalized = resourceKey
    .normalize("NFKD")
    .replace(/[^A-Za-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 104);
  const seed = normalized && /[A-Za-z]/.test(normalized) ? `sql_${normalized}` : `sql_source_${shortHash(resourceKey)}`;
  let candidate = seed.slice(0, 120);
  let suffix = 2;
  while (used.has(candidate)) {
    candidate = `${seed.slice(0, 116)}_${suffix}`;
    suffix += 1;
  }
  used.add(candidate);
  return candidate;
}

function selectionsForCatalog(catalog: SqlServerCatalog) {
  const used = new Set<string>();
  return catalog.resources.slice(0, 8).flatMap<SqlServerSnapshotSelectionInput>((resource) => {
    const columnNames = resource.columns.slice(0, 64).map((column) => column.name);
    const key = resource.keyCandidates.find((candidate) => (
      candidate.length > 0 && candidate.every((column) => columnNames.includes(column))
    ));
    if (!key || resource.rowEstimate > 100_000) return [];
    return [{
      resourceKey: resource.resourceKey,
      columns: columnNames,
      orderBy: key,
      targetTableKey: targetTableKey(resource.resourceKey, used),
      estimatedRows: resource.rowEstimate,
    }];
  });
}

function operationRequestKey(prefix: string, connectorKey: string) {
  return `${prefix}:${connectorKey}:${crypto.randomUUID()}`;
}

export function SourceWorkbenchSqlServerCapability({
  connectorKey,
  connectorName,
}: SourceWorkbenchSqlServerCapabilityProps) {
  const connectorKeyRef = useRef(connectorKey);
  const requestSequenceRef = useRef(0);
  const requestRef = useRef<ActiveRequest | null>(null);
  const [contractState, setContractState] = useState<ConnectorScopedValue<SqlServerAdapterContract> | null>(null);
  const [lifecycleState, setLifecycleState] = useState<ConnectorScopedValue<SqlServerLifecycle> | null>(null);
  const [busyState, setBusyState] = useState<ConnectorScopedValue<SqlServerOperation> | null>(null);
  const [noticeState, setNoticeState] = useState<ConnectorScopedValue<string> | null>(null);
  const [errorState, setErrorState] = useState<ConnectorScopedValue<string> | null>(null);
  connectorKeyRef.current = connectorKey;

  const lifecycle = lifecycleState?.connectorKey === connectorKey ? lifecycleState.value : {};
  const jobKey = lifecycle.job?.jobKey ?? "";
  const jobStatus = lifecycle.job?.status ?? "";
  const activationRequestKey = lifecycle.activationRequestKey ?? "";
  const planFingerprint = lifecycle.plan?.planFingerprint ?? "";
  const manifestFingerprint = lifecycle.snapshot?.manifestFingerprint ?? "";
  const activationWorkspaceId = lifecycle.snapshot?.workspaceId ?? "";

  function setLifecycle(update: (current: SqlServerLifecycle) => SqlServerLifecycle) {
    setLifecycleState((current) => ({
      connectorKey,
      value: update(current?.connectorKey === connectorKey ? current.value : {}),
    }));
  }

  function beginRequest(operation: SqlServerOperation): ActiveRequest {
    requestRef.current?.controller.abort();
    const request = {
      id: requestSequenceRef.current + 1,
      connectorKey,
      operation,
      controller: new AbortController(),
    };
    requestSequenceRef.current = request.id;
    requestRef.current = request;
    setBusyState({ connectorKey, value: operation });
    setErrorState(null);
    return request;
  }

  function isCurrentRequest(request: ActiveRequest) {
    return !request.controller.signal.aborted
      && requestRef.current?.id === request.id
      && connectorKeyRef.current === request.connectorKey;
  }

  function finishRequest(request: ActiveRequest) {
    if (requestRef.current?.id !== request.id) return;
    requestRef.current = null;
    setBusyState(null);
  }

  useEffect(() => {
    requestRef.current?.controller.abort();
    const request: ActiveRequest = {
      id: requestSequenceRef.current + 1,
      connectorKey,
      operation: "probe",
      controller: new AbortController(),
    };
    requestSequenceRef.current = request.id;
    requestRef.current = request;
    setBusyState({ connectorKey, value: "probe" });
    setLifecycleState({ connectorKey, value: {} });
    setNoticeState(null);
    setErrorState(null);

    void probeSqlServerAdapter(connectorKey, request.controller.signal)
      .then((contract) => {
        if (!isCurrentRequest(request)) return;
        setContractState({ connectorKey, value: contract });
      })
      .catch((error: unknown) => {
        if (!isCurrentRequest(request)) return;
        setErrorState({ connectorKey, value: publicErrorMessage(error) });
      })
      .finally(() => finishRequest(request));

    return () => {
      request.controller.abort();
      if (requestRef.current?.id === request.id) {
        requestRef.current = null;
        requestSequenceRef.current += 1;
      }
    };
  }, [connectorKey]);

  useEffect(() => {
    if (!jobKey || ["succeeded", "failed", "canceled"].includes(jobStatus)) return undefined;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | null = null;
    const poll = async () => {
      try {
        const payload = await fetchImportJob(jobKey, controller.signal);
        const job = payload.job;
        if (controller.signal.aborted || connectorKeyRef.current !== connectorKey || !job) return;
        setLifecycle((current) => ({ ...current, job }));
        if (!["succeeded", "failed", "canceled"].includes(job.status)) {
          timer = setTimeout(() => void poll(), 750);
        }
      } catch (error) {
        if (controller.signal.aborted || connectorKeyRef.current !== connectorKey) return;
        setErrorState({ connectorKey, value: publicErrorMessage(error) });
        timer = setTimeout(() => void poll(), 1_500);
      }
    };
    timer = setTimeout(() => void poll(), 350);
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [connectorKey, jobKey, jobStatus]);

  useEffect(() => {
    if (jobStatus !== "succeeded" || !activationRequestKey || !planFingerprint || !manifestFingerprint || !activationWorkspaceId) return undefined;
    const controller = new AbortController();
    void fetchSqlServerActivationStatus({
      connectorKey,
      workspaceId: activationWorkspaceId,
      requestKey: activationRequestKey,
      expectedPlanFingerprint: planFingerprint,
      expectedManifestFingerprint: manifestFingerprint,
    }, controller.signal).then((activation) => {
      if (controller.signal.aborted || connectorKeyRef.current !== connectorKey) return;
      setLifecycle((current) => ({ ...current, activation, job: activation.job ?? current.job }));
      if (activation.capability === "active") {
        const tableKeys = activatedTableKeys(activation.job ?? lifecycle.job);
        if (tableKeys.length) {
          tableKeys.forEach((table) => invalidateTableQueryCache({ workspaceId: activationWorkspaceId, table }));
        } else {
          invalidateTableQueryCache({ workspaceId: activationWorkspaceId });
        }
        setContractState((current) => current?.connectorKey === connectorKey
          ? { connectorKey, value: { ...current.value, capability: "active" } }
          : current);
        setNoticeState({
          connectorKey,
          value: biText("Durable Import 与 Activation Journal 已完成，来源现在可用于分析。", "Durable Import and the Activation Journal are complete; the source is now active."),
        });
      }
    }).catch((error) => {
      if (controller.signal.aborted || connectorKeyRef.current !== connectorKey) return;
      setErrorState({ connectorKey, value: publicErrorMessage(error) });
    });
    return () => controller.abort();
  }, [activationRequestKey, activationWorkspaceId, connectorKey, jobStatus, manifestFingerprint, planFingerprint]);

  async function runProbe() {
    const request = beginRequest("probe");
    setContractState(null);
    setNoticeState(null);
    try {
      const contract = await probeSqlServerAdapter(connectorKey, request.controller.signal);
      if (!isCurrentRequest(request)) return;
      setContractState({ connectorKey, value: contract });
    } catch (error) {
      if (!isCurrentRequest(request)) return;
      setErrorState({ connectorKey, value: publicErrorMessage(error) });
    } finally {
      finishRequest(request);
    }
  }

  async function runTest() {
    const request = beginRequest("test");
    setNoticeState(null);
    try {
      const receipt = await testSqlServerConnection({ connectorKey }, request.controller.signal);
      if (!isCurrentRequest(request)) return;
      setContractState((current) => current?.connectorKey === connectorKey
        ? { connectorKey, value: { ...current.value, capability: receipt.capability } }
        : current);
      setNoticeState({ connectorKey, value: biText("只读连接测试已通过。", "The read-only connection test passed.") });
    } catch (error) {
      if (!isCurrentRequest(request)) return;
      setErrorState({ connectorKey, value: publicErrorMessage(error) });
    } finally {
      finishRequest(request);
    }
  }

  async function runDiscover() {
    const request = beginRequest("discover");
    setNoticeState(null);
    try {
      const catalog = await discoverSqlServerCatalog({ connectorKey }, request.controller.signal);
      if (!isCurrentRequest(request)) return;
      if (catalog.rawRowsReturned !== false) throw new Error("SQLSERVER_CATALOG_CONTRACT_INVALID");
      setLifecycle(() => ({ catalog }));
      setNoticeState({
        connectorKey,
        value: biText(`已读取 ${catalog.resources.length} 个目录资源；未返回业务数据行。`, `Read ${catalog.resources.length} catalog resources; no business rows were returned.`),
      });
    } catch (error) {
      if (!isCurrentRequest(request)) return;
      setErrorState({ connectorKey, value: publicErrorMessage(error) });
    } finally {
      finishRequest(request);
    }
  }

  async function runPlan() {
    if (!lifecycle.catalog) return;
    const selections = selectionsForCatalog(lifecycle.catalog);
    if (!selections.length) {
      setErrorState({
        connectorKey,
        value: biText("目录中没有同时满足唯一键与 10 万行默认预算的资源。", "No catalog resource has both a stable unique key and the default 100k-row budget."),
      });
      return;
    }
    const request = beginRequest("plan");
    setNoticeState(null);
    try {
      const plan = await planSqlServerSnapshot({
        connectorKey,
        requestKey: operationRequestKey("sqlserver-plan", connectorKey),
        catalogFingerprint: lifecycle.catalog.catalogFingerprint,
        selections,
      }, request.controller.signal);
      if (!isCurrentRequest(request)) return;
      setLifecycle((current) => ({ catalog: current.catalog, plan }));
      setContractState((current) => current?.connectorKey === connectorKey
        ? { connectorKey, value: { ...current.value, capability: "ready_for_snapshot" } }
        : current);
      setNoticeState({ connectorKey, value: biText(`已锁定 ${plan.selections.length} 张表的快照计划。`, `Snapshot plan locked for ${plan.selections.length} tables.`) });
    } catch (error) {
      if (!isCurrentRequest(request)) return;
      setErrorState({ connectorKey, value: publicErrorMessage(error) });
    } finally {
      finishRequest(request);
    }
  }

  async function runSnapshot() {
    if (!lifecycle.plan) return;
    const request = beginRequest("snapshot");
    setNoticeState(null);
    try {
      const snapshot = await createSqlServerSnapshot({
        connectorKey,
        requestKey: lifecycle.plan.requestKey,
        expectedPlanFingerprint: lifecycle.plan.planFingerprint,
        confirm: true,
      }, request.controller.signal);
      if (!isCurrentRequest(request)) return;
      setLifecycle((current) => ({ ...current, snapshot }));
      setNoticeState({ connectorKey, value: biText("快照已写入隔离暂存区，尚未激活。", "Snapshot sealed in isolated staging; it is not active yet.") });
    } catch (error) {
      if (!isCurrentRequest(request)) return;
      setErrorState({ connectorKey, value: publicErrorMessage(error) });
    } finally {
      finishRequest(request);
    }
  }

  async function runActivate() {
    if (!lifecycle.plan || !lifecycle.snapshot?.manifestFingerprint) return;
    const request = beginRequest("activate");
    const retryingTerminalJob = lifecycle.job && ["failed", "canceled"].includes(lifecycle.job.status);
    const requestKey = !retryingTerminalJob && lifecycle.activationRequestKey
      ? lifecycle.activationRequestKey
      : operationRequestKey("sqlserver-activation", connectorKey);
    setLifecycle((current) => ({ ...current, activationRequestKey: requestKey }));
    setNoticeState(null);
    try {
      const activation = await activateSqlServerSnapshot({
        connectorKey,
        workspaceId: lifecycle.snapshot.workspaceId,
        requestKey,
        expectedPlanFingerprint: lifecycle.plan.planFingerprint,
        expectedManifestFingerprint: lifecycle.snapshot.manifestFingerprint,
        confirm: true,
      }, request.controller.signal);
      if (!isCurrentRequest(request)) return;
      setLifecycle((current) => ({ ...current, activationRequestKey: requestKey, activation, job: activation.job }));
      setNoticeState({ connectorKey, value: biText("已提交 Durable Import；Journal 完成前不会显示为 active。", "Durable Import queued; active remains blocked until the Journal finalizes.") });
    } catch (error) {
      if (!isCurrentRequest(request)) return;
      setErrorState({ connectorKey, value: publicErrorMessage(error) });
    } finally {
      finishRequest(request);
    }
  }

  const contract = contractState?.connectorKey === connectorKey ? contractState.value : null;
  const operation = busyState?.connectorKey === connectorKey ? busyState.value : null;
  const notice = noticeState?.connectorKey === connectorKey ? noticeState.value : "";
  const error = errorState?.connectorKey === connectorKey ? errorState.value : "";
  const panelBusy = operation === "test" || operation === "discover" || operation === "plan" || operation === "snapshot" || operation === "activate"
    ? operation
    : null;

  return (
    <div className="sqlServerCapabilityHost" data-testid="source-sqlserver-capability" aria-label={biText("SQL Server 只读能力", "SQL Server read-only capability")}>
      <p className="quietText" data-testid="source-sqlserver-connector-name">
        <Bilingual zh="当前连接" en="Current connection" /> · {connectorName}
      </p>

      {contract ? (
        <Suspense fallback={<div className="moduleSkeleton" data-testid="sqlserver-capability-loading" aria-busy="true" />}>
          <SqlServerAdapterCapabilityPanel
            contract={contract}
            busy={panelBusy}
            catalog={lifecycle.catalog}
            plan={lifecycle.plan}
            snapshot={lifecycle.snapshot}
            job={lifecycle.job}
            activation={lifecycle.activation}
            onTest={() => void runTest()}
            onDiscover={() => void runDiscover()}
            onPlan={() => void runPlan()}
            onSnapshot={() => void runSnapshot()}
            onActivate={() => void runActivate()}
          />
        </Suspense>
      ) : operation === "probe" ? (
        <div className="moduleSkeleton" data-testid="sqlserver-capability-loading" aria-busy="true" />
      ) : null}

      {notice ? (
        <p className="sqlServerCapability__notice" data-testid="sqlserver-capability-notice" aria-live="polite">{notice}</p>
      ) : null}
      {error ? (
        <div className="sqlServerCapability__notice" role="alert" data-testid="sqlserver-capability-error">
          <p>{error}</p>
          <button className="secondaryButton" disabled={operation !== null} onClick={() => void runProbe()} type="button">
            {biText("重新探测", "Probe again")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
