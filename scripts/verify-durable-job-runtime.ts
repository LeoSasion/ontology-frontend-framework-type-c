import { DurableJobRuntime } from "../server/durableJobRuntime";

type JobStatus = "queued" | "running" | "canceled";

const checks: Array<{ label: string; ok: boolean; detail?: unknown }> = [];
function check(label: string, ok: boolean, detail?: unknown) {
  checks.push({ label, ok, detail });
}

function runtimeWithStatuses(statuses: JobStatus[]) {
  const calls: string[][] = [];
  let index = 0;
  const runtime = new DurableJobRuntime(process.cwd(), async (args) => {
    calls.push(args);
    if (args[0] !== "jobs") throw new Error(`Unexpected command: ${args.join(" ")}`);
    const status = statuses[Math.min(index, statuses.length - 1)];
    index += 1;
    return { ok: true, job: { jobKey: args[2], workspaceId: "workspace-a", status } };
  });
  const launched: string[] = [];
  (runtime as any).launchImport = (identity: { jobKey: string; workspaceId: string }) => {
    (runtime as any).activeImport = identity;
    launched.push(identity.jobKey);
  };
  return { runtime, calls, launched };
}

const canceled = runtimeWithStatuses(["canceled", "queued"]);
(canceled.runtime as any).activeImport = { jobKey: "canceled-before-claim", workspaceId: "workspace-a" };
(canceled.runtime as any).pendingImports.push({ jobKey: "next-job", workspaceId: "workspace-a" });
await (canceled.runtime as any).afterImportSettled({ jobKey: "canceled-before-claim", workspaceId: "workspace-a" }, false);
check(
  "cancel-before-claim-does-not-stall-the-global-import-queue",
  canceled.launched.join(",") === "next-job",
  { launched: canceled.launched, calls: canceled.calls },
);

const deferred = runtimeWithStatuses(["queued", "queued"]);
(deferred.runtime as any).activeImport = { jobKey: "deferred-job", workspaceId: "workspace-a" };
(deferred.runtime as any).pendingImports.push({ jobKey: "later-job", workspaceId: "workspace-a" });
await (deferred.runtime as any).afterImportSettled({ jobKey: "deferred-job", workspaceId: "workspace-a" }, false);
check(
  "lease-deferred-job-is-retried-before-later-work",
  deferred.launched.join(",") === "deferred-job",
  { launched: deferred.launched, calls: deferred.calls },
);

const stale = runtimeWithStatuses(["running"]);
(stale.runtime as any).activeImport = { jobKey: "stale-worker-token", workspaceId: "workspace-a" };
(stale.runtime as any).pendingImports.push({ jobKey: "must-not-launch", workspaceId: "workspace-a" });
await (stale.runtime as any).afterImportSettled({ jobKey: "stale-worker-token", workspaceId: "workspace-a" }, false);
check(
  "unmatched-stale-worker-cannot-drain-past-a-current-running-owner",
  stale.launched.length === 0 && (stale.runtime as any).pendingImports.length === 1,
  { launched: stale.launched, calls: stale.calls },
);

const sameTick = runtimeWithStatuses(["queued"]);
const sameTickIdentity = { jobKey: "retry-first", workspaceId: "workspace-a" };
(sameTick.runtime as any).activeImport = sameTickIdentity;
const sameTickRetry = (sameTick.runtime as any).afterImportSettled(sameTickIdentity, false);
(sameTick.runtime as any).enqueueImport({ jobKey: "created-during-backoff", workspaceId: "workspace-b" });
await sameTickRetry;
check(
  "backoff-reservation-prevents-same-tick-second-child",
  sameTick.launched.join(",") === "retry-first" &&
    (sameTick.runtime as any).pendingImports.map((item: { jobKey: string }) => item.jobKey).join(",") === "created-during-backoff",
  { launched: sameTick.launched, pending: (sameTick.runtime as any).pendingImports },
);

const canceledBackoff = runtimeWithStatuses(["queued", "queued"]);
const canceledBackoffIdentity = { jobKey: "cancel-during-backoff", workspaceId: "workspace-a" };
(canceledBackoff.runtime as any).activeImport = canceledBackoffIdentity;
(canceledBackoff.runtime as any).pendingImports.push({ jobKey: "next-after-cancel", workspaceId: "workspace-a" });
const canceledBackoffRetry = (canceledBackoff.runtime as any).afterImportSettled(canceledBackoffIdentity, false);
await new Promise((resolveDelay) => setTimeout(resolveDelay, 10));
const cancelResult = canceledBackoff.runtime.cancel(canceledBackoffIdentity.jobKey);
await canceledBackoffRetry;
check(
  "cancel-during-backoff-dequeues-reservation-without-relaunch",
  cancelResult.dequeued === true && canceledBackoff.launched.join(",") === "next-after-cancel",
  { launched: canceledBackoff.launched, cancelResult },
);

const shutdownBackoff = runtimeWithStatuses(["queued"]);
const shutdownIdentity = { jobKey: "shutdown-during-backoff", workspaceId: "workspace-a" };
(shutdownBackoff.runtime as any).activeImport = shutdownIdentity;
const shutdownRetry = (shutdownBackoff.runtime as any).afterImportSettled(shutdownIdentity, false);
await new Promise((resolveDelay) => setTimeout(resolveDelay, 10));
await shutdownBackoff.runtime.shutdown();
await shutdownRetry;
check(
  "shutdown-during-backoff-never-spawns-a-new-worker",
  shutdownBackoff.launched.length === 0 && (shutdownBackoff.runtime as any).shuttingDown === true,
  { launched: shutdownBackoff.launched },
);

let transientLookups = 0;
const transientCalls: string[][] = [];
const transientRuntime = new DurableJobRuntime(process.cwd(), async (args) => {
  transientCalls.push(args);
  transientLookups += 1;
  if (transientLookups === 1) throw new Error("transient runtime restart");
  return { ok: true, job: { jobKey: args[2], workspaceId: "workspace-a", status: "queued" } };
});
const transientLaunched: string[] = [];
(transientRuntime as any).launchImport = (identity: { jobKey: string; workspaceId: string }) => {
  (transientRuntime as any).activeImport = identity;
  transientLaunched.push(identity.jobKey);
};
const transientIdentity = { jobKey: "lookup-retry-head", workspaceId: "workspace-a" };
(transientRuntime as any).activeImport = transientIdentity;
const transientRetry = (transientRuntime as any).afterImportSettled(transientIdentity, false);
(transientRuntime as any).enqueueImport({ jobKey: "must-remain-second", workspaceId: "workspace-b" });
await transientRetry;
check(
  "transient-status-lookup-failure-retries-the-reserved-head",
  transientLookups === 2
    && transientLaunched.join(",") === "lookup-retry-head"
    && (transientRuntime as any).pendingImports.map((item: { jobKey: string }) => item.jobKey).join(",") === "must-remain-second",
  { transientLookups, transientLaunched, pending: (transientRuntime as any).pendingImports, transientCalls },
);

const failed = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failed.length === 0,
  schema: "aibi-durable-job-runtime-verify/v1",
  generatedBy: "scripts/verify-durable-job-runtime.ts",
  checks,
  failedChecks: failed,
}, null, 2));
if (failed.length) process.exitCode = 1;
