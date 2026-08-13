export type ImportJobPollingScheduler = (
  task: () => void,
  delayMs: number,
) => () => void;

type ImportJobPollingOptions<Job> = {
  fetch: () => Promise<Job>;
  isTerminal: (job: Job) => boolean;
  onUpdate: (job: Job) => void;
  onRetry: (error: unknown, attempt: number, delayMs: number) => void;
  schedule: ImportJobPollingScheduler;
  initialDelayMs?: number;
  intervalMs?: number;
};

export function importJobPollingRetryDelay(attempt: number) {
  return Math.min(5_000, 600 * (2 ** Math.min(Math.max(0, attempt), 3)));
}

export function startImportJobPolling<Job>({
  fetch,
  isTerminal,
  onUpdate,
  onRetry,
  schedule,
  initialDelayMs = 1_200,
  intervalMs = 1_200,
}: ImportJobPollingOptions<Job>) {
  let canceled = false;
  let cancelScheduledPoll = () => {};
  let attempt = 0;

  const queue = (delayMs: number) => {
    cancelScheduledPoll = schedule(() => void poll(), delayMs);
  };

  const poll = async () => {
    try {
      const latest = await fetch();
      if (canceled) return;
      attempt = 0;
      onUpdate(latest);
      // Successful reads may return the same status and timestamp for several
      // intervals. Keep polling until the durable job reaches a stop state.
      if (!isTerminal(latest)) queue(intervalMs);
    } catch (error) {
      if (canceled) return;
      const delayMs = importJobPollingRetryDelay(attempt);
      attempt += 1;
      onRetry(error, attempt, delayMs);
      queue(delayMs);
    }
  };

  queue(initialDelayMs);
  return () => {
    canceled = true;
    cancelScheduledPoll();
  };
}
