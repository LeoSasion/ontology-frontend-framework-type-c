import assert from "node:assert/strict";
import test from "node:test";
import { startImportCompletionRefresh } from "../src/importCompletionRefresh";
import { startImportJobPolling } from "../src/importJobPolling";

type ScheduledTask = {
  canceled: boolean;
  delayMs: number;
  task: () => void;
};

function settle() {
  return new Promise<void>((resolve) => setImmediate(resolve));
}

function fakeScheduler(queue: ScheduledTask[]) {
  return (task: () => void, delayMs: number) => {
    const scheduled = { canceled: false, delayMs, task };
    queue.push(scheduled);
    return () => {
      scheduled.canceled = true;
    };
  };
}

test("a transient completion refresh failure retries before marking the import complete", async () => {
  const scheduled: ScheduledTask[] = [];
  const retries: Array<{ attempt: number; delayMs: number }> = [];
  let completionAttempts = 0;
  let completed = 0;

  const cancel = startImportCompletionRefresh({
    complete: async () => {
      completionAttempts += 1;
      if (completionAttempts === 1) throw new Error("temporary refresh failure");
    },
    onCompleted: () => {
      completed += 1;
    },
    onRetry: (_error, attempt, delayMs) => retries.push({ attempt, delayMs }),
    schedule: fakeScheduler(scheduled),
  });

  await settle();
  assert.equal(completionAttempts, 1);
  assert.equal(completed, 0);
  assert.deepEqual(retries, [{ attempt: 1, delayMs: 750 }]);
  assert.equal(scheduled.length, 1);

  scheduled.shift()?.task();
  await settle();
  assert.equal(completionAttempts, 2);
  assert.equal(completed, 1);
  assert.equal(scheduled.length, 0);
  cancel();
});

test("canceling the completion refresh prevents a queued retry", async () => {
  const scheduled: ScheduledTask[] = [];
  let completionAttempts = 0;
  let completed = 0;

  const cancel = startImportCompletionRefresh({
    complete: async () => {
      completionAttempts += 1;
      throw new Error("service unavailable");
    },
    onCompleted: () => {
      completed += 1;
    },
    onRetry: () => {},
    schedule: fakeScheduler(scheduled),
  });

  await settle();
  assert.equal(scheduled.length, 1);
  cancel();
  assert.equal(scheduled[0].canceled, true);
  if (!scheduled[0].canceled) scheduled[0].task();
  await settle();
  assert.equal(completionAttempts, 1);
  assert.equal(completed, 0);
});

test("canceling an in-flight successful refresh suppresses stale completion", async () => {
  let resolveRefresh = () => {};
  let completed = 0;
  const pendingRefresh = new Promise<void>((resolve) => {
    resolveRefresh = resolve;
  });

  const cancel = startImportCompletionRefresh({
    complete: () => pendingRefresh,
    onCompleted: () => {
      completed += 1;
    },
    onRetry: () => {},
    schedule: () => () => {},
  });

  cancel();
  resolveRefresh();
  await settle();
  assert.equal(completed, 0);
});

test("durable import polling continues when consecutive successful reads are unchanged", async () => {
  const scheduled: ScheduledTask[] = [];
  const updates: string[] = [];
  const jobs = [
    { status: "running", updatedAt: "same" },
    { status: "running", updatedAt: "same" },
    { status: "succeeded", updatedAt: "done" },
  ];
  const runNext = async () => {
    const scheduledTask = scheduled.shift();
    assert.ok(scheduledTask);
    scheduledTask.task();
    await settle();
  };

  const cancel = startImportJobPolling({
    fetch: async () => jobs.shift() ?? { status: "succeeded", updatedAt: "done" },
    isTerminal: (job) => job.status === "succeeded",
    onUpdate: (job) => updates.push(`${job.status}:${job.updatedAt}`),
    onRetry: () => assert.fail("successful polling must not enter retry handling"),
    schedule: fakeScheduler(scheduled),
  });

  assert.equal(scheduled[0]?.delayMs, 1_200);
  await runNext();
  assert.equal(scheduled[0]?.delayMs, 1_200);
  await runNext();
  assert.equal(scheduled[0]?.delayMs, 1_200);
  await runNext();
  assert.deepEqual(updates, ["running:same", "running:same", "succeeded:done"]);
  assert.equal(scheduled.length, 0);
  cancel();
});
