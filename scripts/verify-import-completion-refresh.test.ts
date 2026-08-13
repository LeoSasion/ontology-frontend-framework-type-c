import assert from "node:assert/strict";
import test from "node:test";
import { startImportCompletionRefresh } from "../src/importCompletionRefresh";

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
