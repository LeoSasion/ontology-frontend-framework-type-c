export type ImportCompletionRetryScheduler = (
  task: () => void,
  delayMs: number,
) => () => void;

type ImportCompletionRefreshOptions = {
  complete: () => Promise<void>;
  onCompleted: () => void;
  onRetry: (error: unknown, attempt: number, delayMs: number) => void;
  schedule: ImportCompletionRetryScheduler;
};

export function importCompletionRetryDelay(attempt: number) {
  return Math.min(5_000, 750 * (2 ** Math.min(Math.max(0, attempt), 3)));
}

export function startImportCompletionRefresh({
  complete,
  onCompleted,
  onRetry,
  schedule,
}: ImportCompletionRefreshOptions) {
  let canceled = false;
  let cancelScheduledRetry = () => {};
  let attempt = 0;

  const run = async () => {
    try {
      await complete();
    } catch (error) {
      if (canceled) return;
      const delayMs = importCompletionRetryDelay(attempt);
      attempt += 1;
      onRetry(error, attempt, delayMs);
      cancelScheduledRetry = schedule(() => void run(), delayMs);
      return;
    }
    if (!canceled) onCompleted();
  };

  void run();
  return () => {
    canceled = true;
    cancelScheduledRetry();
  };
}
