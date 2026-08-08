import { runTableQuery } from "./apiViews";

type TableQueryOptions = Parameters<typeof runTableQuery>[0];
type SharedTableQuery = {
  controller: AbortController;
  promise: ReturnType<typeof runTableQuery>;
  subscribers: number;
};

const sharedTableQueries = new Map<string, SharedTableQuery>();

export function subscribeTableQuery(options: TableQueryOptions) {
  const key = JSON.stringify(options);
  let entry = sharedTableQueries.get(key);
  if (!entry) {
    const controller = new AbortController();
    const promise = runTableQuery(options, controller.signal).finally(() => sharedTableQueries.delete(key));
    entry = { controller, promise, subscribers: 0 };
    sharedTableQueries.set(key, entry);
  }
  entry.subscribers += 1;
  let released = false;
  return {
    promise: entry.promise,
    release() {
      if (released) return;
      released = true;
      entry!.subscribers -= 1;
      if (entry!.subscribers === 0 && sharedTableQueries.get(key) === entry) {
        sharedTableQueries.delete(key);
        entry!.controller.abort();
      }
    },
  };
}
