import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";

type RuntimeResult = Record<string, unknown>;
type RuntimeCapability = {
  permissions?: { database?: string };
  timeoutClass?: string;
};

type PendingRequest = {
  resolve: (value: RuntimeResult) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
};

const MAX_RESPONSE_BYTES = 8 * 1_048_576;
const MAX_QUEUE_DEPTH = 200;
const DEFAULT_DEADLINE_MS = 120_000;

export type RuntimeHostPoolOptions = {
  workerScript?: string;
  maxQueueDepth?: number;
  deadlineMs?: number;
  startupDeadlineMs?: number;
};

function configuredDeadlineMs() {
  const value = Number(process.env.AIBI_CLI_TIMEOUT_MS ?? DEFAULT_DEADLINE_MS);
  return Number.isFinite(value) && value >= 1_000 && value <= 900_000 ? Math.trunc(value) : DEFAULT_DEADLINE_MS;
}

export class RuntimeHostUnavailableError extends Error {}
export class RuntimeHostCapacityError extends Error {}
export class RuntimeHostDeadlineError extends Error {}

class RuntimeHostWorker {
  private child: ChildProcessWithoutNullStreams | null = null;
  private buffer = "";
  private closed = false;
  private pending = new Map<string, PendingRequest>();
  private starts = 0;

  constructor(
    private readonly root: string,
    readonly label: string,
    private readonly workerScript: string,
  ) {}

  get ready() {
    return Boolean(this.child && this.child.exitCode === null && this.child.signalCode === null);
  }

  get startCount() {
    return this.starts;
  }

  private ensureStarted() {
    if (this.closed) throw new RuntimeHostUnavailableError(`${this.label} is shut down`);
    if (this.ready) return;
    const child = spawn(process.env.PYTHON || "python", [this.workerScript], {
      cwd: this.root,
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.child = child;
    this.buffer = "";
    this.starts += 1;
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => this.consume(child, chunk));
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk: string) => {
      const detail = chunk.trim();
      if (detail) console.error(JSON.stringify({ event: "runtime_host_stderr", worker: this.label, detail: detail.slice(0, 4_096) }));
    });
    child.on("error", (error) => {
      if (this.child !== child) return;
      this.child = null;
      this.failAll(new RuntimeHostUnavailableError(`${this.label} failed: ${error.message}`));
    });
    child.on("close", (code) => {
      if (this.child !== child) return;
      this.child = null;
      this.failAll(new RuntimeHostUnavailableError(`${this.label} exited with ${code ?? "unknown"}`));
    });
  }

  private terminate(child: ChildProcessWithoutNullStreams, error: Error) {
    if (this.child !== child) return;
    this.child = null;
    child.kill();
    this.failAll(error);
  }

  private consume(child: ChildProcessWithoutNullStreams, chunk: string) {
    if (this.child !== child) return;
    this.buffer += chunk;
    if (Buffer.byteLength(this.buffer, "utf8") > MAX_RESPONSE_BYTES) {
      this.terminate(child, new RuntimeHostUnavailableError(`${this.label} response exceeded ${MAX_RESPONSE_BYTES} bytes`));
      return;
    }
    for (;;) {
      const newline = this.buffer.indexOf("\n");
      if (newline < 0) break;
      const line = this.buffer.slice(0, newline);
      this.buffer = this.buffer.slice(newline + 1);
      if (!line.trim()) continue;
      let envelope: { id?: string; transportOk?: boolean; result?: RuntimeResult; error?: string };
      try {
        envelope = JSON.parse(line) as typeof envelope;
      } catch {
        this.terminate(child, new RuntimeHostUnavailableError(`${this.label} emitted an invalid response envelope`));
        return;
      }
      const request = this.pending.get(String(envelope.id ?? ""));
      if (!request) continue;
      this.pending.delete(String(envelope.id));
      clearTimeout(request.timer);
      if (envelope.transportOk !== true || !envelope.result) {
        request.reject(new RuntimeHostUnavailableError(envelope.error || `${this.label} transport failed`));
      } else {
        request.resolve(envelope.result);
      }
    }
  }

  private failAll(error: Error) {
    for (const request of this.pending.values()) {
      clearTimeout(request.timer);
      request.reject(error);
    }
    this.pending.clear();
  }

  request(op: "run" | "catalog" | "ping", args: string[] = [], deadlineMs = 120_000, traceId = "") {
    try {
      this.ensureStarted();
    } catch (error) {
      return Promise.reject(error);
    }
    const child = this.child;
    if (!child) return Promise.reject(new RuntimeHostUnavailableError(`${this.label} did not start`));
    const id = randomUUID();
    return new Promise<RuntimeResult>((resolveRequest, rejectRequest) => {
      const timer = setTimeout(() => {
        const request = this.pending.get(id);
        if (!request) return;
        this.pending.delete(id);
        request.reject(new RuntimeHostDeadlineError(`${this.label} command exceeded ${deadlineMs}ms deadline`));
        this.terminate(child, new RuntimeHostUnavailableError(`${this.label} was restarted after a command deadline`));
      }, deadlineMs);
      this.pending.set(id, { resolve: resolveRequest, reject: rejectRequest, timer });
      const payload = `${JSON.stringify({ id, op, args, traceId })}\n`;
      child.stdin.write(payload, "utf8", (error) => {
        if (!error) return;
        const request = this.pending.get(id);
        if (!request) return;
        this.pending.delete(id);
        clearTimeout(request.timer);
        request.reject(new RuntimeHostUnavailableError(`${this.label} write failed: ${error.message}`));
      });
    });
  }

  async shutdown() {
    this.closed = true;
    const child = this.child;
    this.child = null;
    this.failAll(new RuntimeHostUnavailableError(`${this.label} is shutting down`));
    if (!child || child.exitCode !== null || child.signalCode !== null) return;
    child.stdin.end();
    await new Promise<void>((resolveClose) => {
      const timer = setTimeout(() => {
        child.kill();
        resolveClose();
      }, 2_000);
      child.once("close", () => {
        clearTimeout(timer);
        resolveClose();
      });
    });
  }
}

export class RuntimeHostPool {
  private readonly writer: RuntimeHostWorker;
  private readonly readers: RuntimeHostWorker[];
  private catalog: Record<string, RuntimeCapability> | null = null;
  private startPromise: Promise<void> | null = null;
  private writerTail: Promise<unknown> = Promise.resolve();
  private readerTails: Promise<unknown>[];
  private readerCursor = 0;
  private queued = 0;
  private closed = false;
  private shutdownPromise: Promise<void> | null = null;
  private readonly maxQueueDepth: number;
  private readonly deadlineMs: number;
  private readonly startupDeadlineMs: number;

  constructor(private readonly root: string, readerCount = 2, options: RuntimeHostPoolOptions = {}) {
    const workerScript = options.workerScript ?? "tools/aibi_runtime_host.py";
    this.maxQueueDepth = Math.max(1, Math.min(1_000, Math.trunc(options.maxQueueDepth ?? MAX_QUEUE_DEPTH)));
    this.deadlineMs = Math.max(25, Math.min(900_000, Math.trunc(options.deadlineMs ?? configuredDeadlineMs())));
    this.startupDeadlineMs = Math.max(25, Math.min(120_000, Math.trunc(options.startupDeadlineMs ?? 15_000)));
    this.writer = new RuntimeHostWorker(root, "runtime-writer", workerScript);
    this.readers = Array.from(
      { length: Math.max(2, Math.min(4, readerCount)) },
      (_, index) => new RuntimeHostWorker(root, `runtime-reader-${index + 1}`, workerScript),
    );
    this.readerTails = this.readers.map(() => Promise.resolve());
  }

  start() {
    if (this.closed) return Promise.reject(new RuntimeHostUnavailableError("Runtime Host pool is shut down"));
    if (this.startPromise) return this.startPromise;
    this.startPromise = (async () => {
      await Promise.all([
        this.writer.request("ping", [], this.startupDeadlineMs),
        ...this.readers.map((worker) => worker.request("ping", [], this.startupDeadlineMs)),
      ]);
      this.catalog = await this.writer.request("catalog", [], this.startupDeadlineMs) as Record<string, RuntimeCapability>;
    })().catch((error) => {
      this.startPromise = null;
      throw error;
    });
    return this.startPromise;
  }

  private enqueue<T>(tail: Promise<unknown>, setTail: (next: Promise<unknown>) => void, task: () => Promise<T>) {
    if (this.closed) return Promise.reject(new RuntimeHostUnavailableError("Runtime Host pool is shut down"));
    if (this.queued >= this.maxQueueDepth) return Promise.reject(new RuntimeHostCapacityError(`Runtime Host queue reached ${this.maxQueueDepth} requests`));
    this.queued += 1;
    const next = tail.then(task, task);
    setTail(next.catch(() => undefined));
    return next.finally(() => { this.queued -= 1; });
  }

  async run(args: string[], traceId = "") {
    await this.start();
    if (this.closed) throw new RuntimeHostUnavailableError("Runtime Host pool is shut down");
    const command = String(args[0] ?? "");
    const capability = this.catalog?.[command];
    const isWrite = !capability || capability.permissions?.database !== "read-only";
    const deadlineMs = capability?.timeoutClass === "long" ? 900_000 : this.deadlineMs;
    if (isWrite) {
      return this.enqueue(this.writerTail, (next) => { this.writerTail = next; }, () => this.writer.request("run", args, deadlineMs, traceId));
    }
    const index = this.readerCursor++ % this.readers.length;
    return this.enqueue(this.readerTails[index], (next) => { this.readerTails[index] = next; }, () => this.readers[index].request("run", args, deadlineMs, traceId));
  }

  health() {
    return {
      ok: Boolean(this.catalog) && this.writer.ready && this.readers.every((worker) => worker.ready),
      schema: "aibi-runtime-host-health/v1",
      queueDepth: this.queued,
      writer: { ready: this.writer.ready, starts: this.writer.startCount },
      readers: this.readers.map((worker) => ({ ready: worker.ready, starts: worker.startCount })),
      commandCount: Object.keys(this.catalog ?? {}).length,
    };
  }

  shutdown() {
    if (this.shutdownPromise) return this.shutdownPromise;
    this.closed = true;
    this.shutdownPromise = (async () => {
      await Promise.all([this.writer.shutdown(), ...this.readers.map((worker) => worker.shutdown())]);
      this.catalog = null;
      this.startPromise = null;
    })();
    return this.shutdownPromise;
  }
}
