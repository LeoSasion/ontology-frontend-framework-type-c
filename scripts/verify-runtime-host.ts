import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import {
  RuntimeHostCapacityError,
  RuntimeHostDeadlineError,
  RuntimeHostPool,
  RuntimeHostUnavailableError,
} from "../server/runtimeHost";

const temp = mkdtempSync(join(tmpdir(), "aibi-runtime-host-"));
const previous = {
  db: process.env.AIBI_HYBRID_DB_PATH,
  duck: process.env.AIBI_HYBRID_DUCKDB_PATH,
  evidence: process.env.AIBI_EVIDENCE_BUNDLE_ROOT,
  recovery: process.env.AIBI_WORKSPACE_RECOVERY_ROOT,
  fixtureLog: process.env.AIBI_RUNTIME_FIXTURE_LOG,
  fixtureBlocked: process.env.AIBI_RUNTIME_FIXTURE_RECONCILE_BLOCKED,
};
process.env.AIBI_HYBRID_DB_PATH = join(temp, "runtime.sqlite");
process.env.AIBI_HYBRID_DUCKDB_PATH = join(temp, "runtime.duckdb");
process.env.AIBI_EVIDENCE_BUNDLE_ROOT = join(temp, "evidence");
process.env.AIBI_WORKSPACE_RECOVERY_ROOT = join(temp, "workspace-recovery");
const fixtureLog = join(temp, "runtime-host-fixture.ndjson");
process.env.AIBI_RUNTIME_FIXTURE_LOG = fixtureLog;

const host = new RuntimeHostPool(process.cwd());
const fixtureHosts: RuntimeHostPool[] = [];
const checks: Array<{ label: string; ok: boolean; detail?: unknown }> = [];

async function rejectsWith(task: () => Promise<unknown>, ErrorType: new (...args: never[]) => Error) {
  try {
    await task();
    return false;
  } catch (error) {
    return error instanceof ErrorType;
  }
}

async function waitForQueue(pool: RuntimeHostPool, expected: number) {
  const started = Date.now();
  while (Date.now() - started < 2_000) {
    if (pool.health().queueDepth === expected) return true;
    await new Promise((resolveWait) => setTimeout(resolveWait, 5));
  }
  return false;
}

function commandDiagnostic(result: Record<string, unknown>) {
  const envelope = result.envelope && typeof result.envelope === "object"
    ? result.envelope as Record<string, unknown>
    : {};
  const workflowStage = result.workflowStage && typeof result.workflowStage === "object"
    ? result.workflowStage as Record<string, unknown>
    : {};
  const rawError = String(result.error ?? workflowStage.error ?? "");
  return {
    ok: result.ok,
    command: result.command,
    errorCode: result.errorCode ?? null,
    error: rawError
      .replaceAll(temp, "<temp>")
      .replace(/[A-Za-z]:\\[^\s,"']+/g, "<path>")
      .slice(0, 500) || null,
    mutationMode: envelope.mutationMode ?? null,
    workflowStatus: workflowStage.status ?? null,
  };
}

try {
  await host.start();
  const [status, capabilities] = await Promise.all([
    host.run(["status"]),
    host.run(["cli-capabilities"]),
  ]);
  const health = host.health();
  const realCommandsOk = status.ok === true && capabilities.ok === true;
  checks.push({
    label: "runtime-host-serves-real-commands",
    ok: realCommandsOk,
    detail: realCommandsOk ? undefined : {
      status: commandDiagnostic(status),
      capabilities: commandDiagnostic(capabilities),
      health,
    },
  });
  checks.push({
    label: "runtime-host-loads-one-writer-and-two-readers-once",
    ok: health.ok === true
      && health.commandCount >= 170
      && health.writer.starts === 1
      && health.readers.length === 2
      && health.readers.every((reader) => reader.ready && reader.starts === 1),
    detail: health,
  });

  const fixture = resolve(import.meta.dirname, "fixtures", "runtime-host-fixture.py");
  const faultHost = new RuntimeHostPool(process.cwd(), 2, {
    workerScript: fixture,
    deadlineMs: 75,
    startupDeadlineMs: 2_000,
    maxQueueDepth: 1,
  });
  fixtureHosts.push(faultHost);
  await faultHost.start();

  const invalidRejected = await rejectsWith(() => faultHost.run(["invalid"]), RuntimeHostUnavailableError);
  const startsAfterInvalid = faultHost.health().writer.starts;
  const recoveredFromInvalid = await faultHost.run(["write"]);
  checks.push({
    label: "invalid-protocol-kills-and-restarts-worker",
    ok: invalidRejected && recoveredFromInvalid.ok === true && faultHost.health().writer.starts === startsAfterInvalid + 1,
    detail: faultHost.health(),
  });

  const deadlineRejected = await rejectsWith(() => faultHost.run(["sleep"]), RuntimeHostDeadlineError);
  const startsAfterDeadline = faultHost.health().writer.starts;
  const recoveredFromDeadline = await faultHost.run(["write"]);
  checks.push({
    label: "deadline-kills-and-restarts-worker",
    ok: deadlineRejected && recoveredFromDeadline.ok === true && faultHost.health().writer.starts === startsAfterDeadline + 1,
    detail: faultHost.health(),
  });

  const queuedRequest = faultHost.run(["sleep"]);
  const queueOccupied = await waitForQueue(faultHost, 1);
  const capacityRejected = await rejectsWith(() => faultHost.run(["read"]), RuntimeHostCapacityError);
  await queuedRequest.catch(() => undefined);
  checks.push({
    label: "queue-capacity-rejects-excess-work",
    ok: queueOccupied && capacityRejected && faultHost.health().queueDepth === 0,
    detail: faultHost.health(),
  });

  const crashRejected = await rejectsWith(() => faultHost.run(["crash"]), RuntimeHostUnavailableError);
  const startsAfterCrash = faultHost.health().writer.starts;
  const recoveredFromCrash = await faultHost.run(["write"]);
  checks.push({
    label: "process-crash-restarts-worker",
    ok: crashRejected && recoveredFromCrash.ok === true && faultHost.health().writer.starts === startsAfterCrash + 1,
    detail: faultHost.health(),
  });

  writeFileSync(fixtureLog, "", "utf8");
  const queueRaceHost = new RuntimeHostPool(process.cwd(), 2, {
    workerScript: fixture,
    deadlineMs: 2_000,
    startupDeadlineMs: 2_000,
    maxQueueDepth: 2,
  });
  fixtureHosts.push(queueRaceHost);
  await queueRaceHost.start();
  const prequeuedCrash = queueRaceHost.run(["crash"]);
  const prequeuedWrite = queueRaceHost.run(["write"]);
  const [prequeuedCrashResult, prequeuedWriteResult] = await Promise.allSettled([prequeuedCrash, prequeuedWrite]);
  const prequeuedEvents = readFileSync(fixtureLog, "utf8")
    .trim()
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line) as { pid: number; command: string });
  const crashIndex = prequeuedEvents.findIndex((event) => event.command === "crash");
  const reconcileIndex = prequeuedEvents.findIndex((event, index) => index > crashIndex && event.command === "workspace-recovery-reconcile");
  const writeIndex = prequeuedEvents.findIndex((event, index) => index > crashIndex && event.command === "write");
  checks.push({
    label: "prequeued-write-reconciles-new-writer-generation-first",
    ok: prequeuedCrashResult.status === "rejected"
      && prequeuedWriteResult.status === "fulfilled"
      && crashIndex >= 0
      && reconcileIndex > crashIndex
      && writeIndex > reconcileIndex
      && prequeuedEvents[crashIndex]?.pid !== prequeuedEvents[reconcileIndex]?.pid,
    detail: prequeuedEvents,
  });

  const blockedFixtureLog = join(temp, "runtime-host-blocked.ndjson");
  process.env.AIBI_RUNTIME_FIXTURE_LOG = blockedFixtureLog;
  process.env.AIBI_RUNTIME_FIXTURE_RECONCILE_BLOCKED = "1";
  const blockedHost = new RuntimeHostPool(process.cwd(), 2, {
    workerScript: fixture,
    deadlineMs: 2_000,
    startupDeadlineMs: 2_000,
    maxQueueDepth: 2,
  });
  fixtureHosts.push(blockedHost);
  await blockedHost.start();
  const blockedWrite = await rejectsWith(() => blockedHost.run(["write"]), RuntimeHostUnavailableError);
  const blockedEvents = readFileSync(blockedFixtureLog, "utf8")
    .trim()
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line) as { pid: number; command: string });
  checks.push({
    label: "blocked-reconciliation-prevents-prequeued-business-write",
    ok: blockedWrite
      && blockedEvents.some((event) => event.command === "workspace-recovery-reconcile")
      && blockedEvents.every((event) => event.command !== "write")
      && blockedHost.health().ok === false,
    detail: { events: blockedEvents, health: blockedHost.health() },
  });
  delete process.env.AIBI_RUNTIME_FIXTURE_RECONCILE_BLOCKED;
  process.env.AIBI_RUNTIME_FIXTURE_LOG = fixtureLog;

  const shutdownHost = new RuntimeHostPool(process.cwd(), 2, {
    workerScript: fixture,
    deadlineMs: 2_000,
    startupDeadlineMs: 2_000,
    maxQueueDepth: 2,
  });
  fixtureHosts.push(shutdownHost);
  await shutdownHost.start();
  const pendingDuringShutdown = shutdownHost.run(["sleep"]);
  await waitForQueue(shutdownHost, 1);
  const shutdown = shutdownHost.shutdown();
  const pendingRejected = await rejectsWith(() => pendingDuringShutdown, RuntimeHostUnavailableError);
  await shutdown;
  const postShutdownRejected = await rejectsWith(() => shutdownHost.run(["read"]), RuntimeHostUnavailableError);
  checks.push({
    label: "shutdown-rejects-pending-and-future-work",
    ok: pendingRejected && postShutdownRejected && shutdownHost.health().ok === false && shutdownHost.health().queueDepth === 0,
    detail: shutdownHost.health(),
  });
} finally {
  await Promise.allSettled([host.shutdown(), ...fixtureHosts.map((fixtureHost) => fixtureHost.shutdown())]);
  process.env.AIBI_HYBRID_DB_PATH = previous.db;
  process.env.AIBI_HYBRID_DUCKDB_PATH = previous.duck;
  process.env.AIBI_EVIDENCE_BUNDLE_ROOT = previous.evidence;
  if (previous.recovery === undefined) delete process.env.AIBI_WORKSPACE_RECOVERY_ROOT;
  else process.env.AIBI_WORKSPACE_RECOVERY_ROOT = previous.recovery;
  if (previous.fixtureLog === undefined) delete process.env.AIBI_RUNTIME_FIXTURE_LOG;
  else process.env.AIBI_RUNTIME_FIXTURE_LOG = previous.fixtureLog;
  if (previous.fixtureBlocked === undefined) delete process.env.AIBI_RUNTIME_FIXTURE_RECONCILE_BLOCKED;
  else process.env.AIBI_RUNTIME_FIXTURE_RECONCILE_BLOCKED = previous.fixtureBlocked;
  rmSync(temp, { recursive: true, force: true });
}

const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-runtime-host-verify/v1",
  generatedBy: "scripts/verify-runtime-host.ts",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
