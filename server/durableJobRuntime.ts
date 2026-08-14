import { spawn, type ChildProcess } from "node:child_process";
import { randomUUID } from "node:crypto";
import { resolve } from "node:path";

type Cli = (args: string[]) => Promise<Record<string, unknown>>;

type JobIdentity = {
  jobKey: string;
  workspaceId: string;
};

const IMPORT_RETRY_DELAY_MS = 100;
const MAX_IMPORT_RETRY_DELAY_MS = 2_000;
const IMPORT_RETRY_ALERT_THRESHOLD = 10;

function jobIdentity(result: Record<string, unknown>): JobIdentity {
  const job = result.job;
  if (!job || typeof job !== "object" || Array.isArray(job)) {
    throw new Error("Durable job creation did not return a job record.");
  }
  const jobKey = String((job as Record<string, unknown>).jobKey ?? "").trim();
  const workspaceId = String((job as Record<string, unknown>).workspaceId ?? "").trim();
  if (!jobKey || !workspaceId) {
    throw new Error("Durable job creation returned an incomplete identity.");
  }
  return { jobKey, workspaceId };
}

export class DurableJobRuntime {
  private readonly workers = new Map<string, ChildProcess>();
  private activeImport: JobIdentity | null = null;
  private readonly pendingImports: JobIdentity[] = [];
  private readonly importRetryCounts = new Map<string, number>();
  private readonly reconciliations = new Set<Promise<void>>();
  private shuttingDown = false;

  constructor(
    private readonly root: string,
    private readonly cli: Cli,
  ) {}

  async startSourceIntelligence(body: Record<string, unknown>) {
    const args = ["source-intelligence-job-create"];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    if (body.label) args.push("--label", String(body.label));
    if (body.outputDir) args.push("--output-dir", String(body.outputDir));
    if (Array.isArray(body.inputs)) args.push(...body.inputs.map(String));
    const result = await this.cli(args);
    if (result.ok === false) return result;

    const identity = jobIdentity(result);
    this.launch(identity, [
      "source-intelligence-job-run",
      "--job",
      identity.jobKey,
      "--workspace",
      identity.workspaceId,
    ]);
    return {
      ...result,
      execution: {
        mode: "durable-background",
        ownedProcess: true,
      },
    };
  }

  async startImport(body: Record<string, unknown>) {
    const args = [
      "import-job-create",
      "--import-kind",
      String(body.importKind ?? "single"),
      "--path",
      String(body.path ?? body.filePath ?? body.folderPath ?? ""),
      "--request-key",
      String(body.requestKey ?? ""),
      "--expected-plan",
      String(body.expectedPlan ?? ""),
    ];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    if (body.label) args.push("--label", String(body.label));
    if (body.table) args.push("--table", String(body.table));
    if (body.name) args.push("--name", String(body.name));
    if (body.mode) args.push("--mode", String(body.mode));
    if (body.stageKey) args.push("--stage-key", String(body.stageKey));
    if (body.stageBindings && typeof body.stageBindings === "object") {
      args.push("--stage-bindings", JSON.stringify(body.stageBindings));
    }
    if (body.confirmSchemaChange === true) args.push("--confirm-schema-change");
    if (Array.isArray(body.uniqueFields) && body.uniqueFields.length) {
      args.push("--unique-fields", body.uniqueFields.map(String).join(","));
    }
    if (body.conflictRule) args.push("--conflict-rule", String(body.conflictRule));
    if (body.limit) args.push("--limit", String(body.limit));
    if (body.recursive === false) args.push("--no-recursive");
    const result = await this.cli(args);
    if (result.ok === false) return result;
    const identity = jobIdentity(result);
    const job = result.job as Record<string, unknown>;
    if (String(job.status ?? "") === "queued" && !this.workers.has(identity.jobKey)) {
      this.enqueueImport(identity);
    }
    return {
      ...result,
      execution: {
        mode: "durable-background",
        ownedProcess: this.workers.has(identity.jobKey),
        queuedBehindWorkspaceWriter: !this.workers.has(identity.jobKey),
      },
    };
  }

  async startSqlServerActivation(body: Record<string, unknown>) {
    const args = [
      "sqlserver-adapter-activate",
      "--connector",
      String(body.connectorKey ?? body.connector ?? ""),
      "--request-key",
      String(body.requestKey ?? ""),
      "--expected-plan",
      String(body.expectedPlanFingerprint ?? ""),
      "--expected-manifest",
      String(body.expectedManifestFingerprint ?? ""),
      "--yes",
    ];
    if (body.workspaceId) args.push("--workspace", String(body.workspaceId));
    const result = await this.cli(args);
    if (result.ok === false) return result;
    const identity = jobIdentity(result);
    const job = result.job as Record<string, unknown>;
    if (String(job.status ?? "") === "queued" && !this.workers.has(identity.jobKey)) {
      this.enqueueImport(identity);
    }
    return {
      ...result,
      execution: {
        mode: "durable-background",
        ownedProcess: this.workers.has(identity.jobKey),
        queuedBehindWorkspaceWriter: !this.workers.has(identity.jobKey),
      },
    };
  }

  async resumeImport(jobKey: string, workspaceId?: string) {
    const args = ["import-job-resume", "--job", jobKey];
    if (workspaceId) args.push("--workspace", workspaceId);
    const result = await this.cli(args);
    if (result.ok === false) return result;
    const identity = jobIdentity(result);
    if (!this.workers.has(identity.jobKey)) {
      if (this.activeImport?.jobKey === identity.jobKey) this.activeImport = null;
      this.enqueueImport(identity);
    }
    return {
      ...result,
      execution: {
        mode: "durable-background",
        ownedProcess: this.workers.has(identity.jobKey),
        queuedBehindWorkspaceWriter: !this.workers.has(identity.jobKey),
      },
    };
  }

  cancel(jobKey: string) {
    const child = this.workers.get(jobKey);
    if (!child) {
      let dequeued = false;
      const index = this.pendingImports.findIndex((item) => item.jobKey === jobKey);
      if (index >= 0) {
        this.pendingImports.splice(index, 1);
        dequeued = true;
      }
      if (this.activeImport?.jobKey === jobKey) {
        this.activeImport = null;
        this.importRetryCounts.delete(jobKey);
        void this.launchNextImport();
        dequeued = true;
      }
      return { ownedProcess: false, signalRequested: false, dequeued };
    }
    return {
      ownedProcess: true,
      signalRequested: child.kill(),
    };
  }

  async shutdown() {
    this.shuttingDown = true;
    this.pendingImports.length = 0;
    this.importRetryCounts.clear();
    const exits = [...this.workers.values()].map((child) => new Promise<void>((resolveExit) => {
      if (child.exitCode !== null || child.signalCode !== null) {
        resolveExit();
        return;
      }
      child.once("close", () => resolveExit());
      child.kill();
    }));
    await Promise.allSettled(exits);
    await Promise.allSettled([...this.reconciliations]);
  }

  private enqueueImport(identity: JobIdentity) {
    if (this.shuttingDown) return;
    if (!this.activeImport) {
      this.launchImport(identity);
      return;
    }
    if (this.activeImport.jobKey !== identity.jobKey && !this.pendingImports.some((item) => item.jobKey === identity.jobKey)) {
      this.pendingImports.push(identity);
    }
  }

  private launchImport(identity: JobIdentity) {
    if (this.shuttingDown) return;
    this.activeImport = identity;
    const leaseToken = randomUUID();
    this.launch(
      identity,
      ["import-job-run", "--job", identity.jobKey, "--workspace", identity.workspaceId, "--lease-token", leaseToken],
      "import-job-process-exit",
      (reconciled) => {
        if (!this.shuttingDown) {
          void this.afterImportSettled(identity, reconciled);
        }
      },
      ["--lease-token", leaseToken],
    );
  }

  private async retryReservedImport(identity: JobIdentity, task: () => void | Promise<void>) {
    this.activeImport = identity;
    const attempts = (this.importRetryCounts.get(identity.jobKey) ?? 0) + 1;
    this.importRetryCounts.set(identity.jobKey, attempts);
    const delay = Math.min(MAX_IMPORT_RETRY_DELAY_MS, IMPORT_RETRY_DELAY_MS * (2 ** Math.min(attempts - 1, 5)));
    if (attempts === IMPORT_RETRY_ALERT_THRESHOLD || attempts % 30 === 0) {
      console.error(JSON.stringify({
        event: "import_queue_retry_delayed",
        workspaceId: identity.workspaceId,
        jobKey: identity.jobKey,
        attempts,
        retryDelayMs: delay,
        queuePolicy: "fail-closed",
      }));
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, delay));
    if (!this.shuttingDown && this.activeImport?.jobKey === identity.jobKey && !this.workers.has(identity.jobKey)) {
      await task();
    }
  }

  private async afterImportSettled(identity: JobIdentity, reconciled: boolean) {
    if (reconciled) {
      await this.finalizeSqlServerActivation(identity);
      if (this.activeImport?.jobKey === identity.jobKey) this.activeImport = null;
      this.importRetryCounts.delete(identity.jobKey);
      await this.launchNextImport();
      return;
    }
    try {
      const payload = await this.cli(["jobs", "--job", identity.jobKey]);
      const job = payload.job as Record<string, unknown> | undefined;
      const status = String(job?.status ?? "");
      if (!job || String(job.workspaceId ?? "") !== identity.workspaceId) return;
      if (["succeeded", "failed", "canceled"].includes(status)) {
        if (status === "succeeded") await this.finalizeSqlServerActivation(identity);
        if (this.activeImport?.jobKey === identity.jobKey) this.activeImport = null;
        this.importRetryCounts.delete(identity.jobKey);
        await this.launchNextImport();
        return;
      }
      if (["created", "queued"].includes(status)) {
        // Keep the identity reserved during backoff. New imports therefore
        // remain queued and cannot race this retry into a second child.
        await this.retryReservedImport(identity, () => this.launchImport(identity));
        return;
      }
      // A current owner or needs_attention state keeps the queue fenced. A
      // current worker's own terminal reconciliation or explicit resume is
      // the only action allowed to release this reservation.
    } catch (error) {
      console.error(JSON.stringify({
        event: "import_queue_reconcile_inspection_failed",
        workspaceId: identity.workspaceId,
        jobKey: identity.jobKey,
        error: error instanceof Error ? error.message : String(error),
      }));
      await this.retryReservedImport(identity, () => this.afterImportSettled(identity, false));
    }
  }

  private async finalizeSqlServerActivation(identity: JobIdentity) {
    try {
      const result = await this.cli([
        "sqlserver-adapter-activation-finalize",
        "--job",
        identity.jobKey,
        "--workspace",
        identity.workspaceId,
        "--yes",
      ]);
      if (result.ok === false) {
        console.error(JSON.stringify({
          event: "sqlserver_activation_finalize_failed",
          workspaceId: identity.workspaceId,
          jobKey: identity.jobKey,
          failed: result.failed,
        }));
      }
    } catch (error) {
      console.error(JSON.stringify({
        event: "sqlserver_activation_finalize_failed",
        workspaceId: identity.workspaceId,
        jobKey: identity.jobKey,
        error: error instanceof Error ? error.message : String(error),
      }));
    }
  }

  private async launchNextImport() {
    if (this.activeImport) return;
    while (!this.shuttingDown) {
      const next = this.pendingImports.shift();
      if (!next) return;
      // Reserve the queue head before the asynchronous status lookup. Without
      // this fence, a same-tick create could launch a second child while the
      // selected item is temporarily absent from both active and pending state.
      this.activeImport = next;
      try {
        const payload = await this.cli(["jobs", "--job", next.jobKey]);
        const job = payload.job as Record<string, unknown> | undefined;
        if (this.activeImport?.jobKey === next.jobKey && job && String(job.workspaceId ?? "") === next.workspaceId && String(job.status ?? "") === "queued") {
          this.launchImport(next);
          return;
        }
        if (this.activeImport?.jobKey === next.jobKey) this.activeImport = null;
        if (job && ["succeeded", "failed", "canceled"].includes(String(job.status ?? ""))) {
          this.importRetryCounts.delete(next.jobKey);
        }
      } catch (error) {
        console.error(JSON.stringify({
          event: "import_queue_claim_failed",
          workspaceId: next.workspaceId,
          jobKey: next.jobKey,
          error: error instanceof Error ? error.message : String(error),
        }));
        await this.retryReservedImport(next, () => this.afterImportSettled(next, false));
        return;
      }
    }
  }

  private launch(
    identity: JobIdentity,
    args: string[],
    reconcileCommand = "job-process-exit",
    onSettled?: (reconciled: boolean) => void,
    reconcileExtraArgs: string[] = [],
  ) {
    if (this.shuttingDown) return;
    if (this.workers.has(identity.jobKey)) {
      throw new Error(`Job already has an owned worker: ${identity.jobKey}`);
    }
    const child = spawn("python", [resolve(this.root, "tools/aibi_cli.py"), "--json", ...args], {
      cwd: this.root,
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
      },
      stdio: ["ignore", "ignore", "pipe"],
      windowsHide: true,
    });
    this.workers.set(identity.jobKey, child);

    let workerError = "";
    child.stderr?.on("data", (chunk) => {
      workerError = `${workerError}${Buffer.from(chunk).toString("utf8")}`.slice(-16_384);
    });
    child.on("error", (error) => {
      workerError = error.message;
    });
    child.on("close", (code, signal) => {
      this.workers.delete(identity.jobKey);
      const reconcileArgs = [
        reconcileCommand,
        "--job",
        identity.jobKey,
        "--workspace",
        identity.workspaceId,
        ...reconcileExtraArgs,
      ];
      if (typeof code === "number") reconcileArgs.push("--exit-code", String(code));
      if (signal) reconcileArgs.push("--signal", String(signal));
      let reconciled = false;
      const reconciliation = this.cli(reconcileArgs)
        .then((result) => {
          reconciled = reconcileCommand === "import-job-process-exit"
            ? result.safeToDrain === true
            : result.ok !== false;
        })
        .catch((error) => {
          console.error(JSON.stringify({
            event: "job_worker_reconcile_failed",
            jobKey: identity.jobKey,
            exitCode: code,
            signal,
            workerError,
            error: error instanceof Error ? error.message : String(error),
          }));
        })
        .finally(() => {
          this.reconciliations.delete(reconciliation);
          onSettled?.(reconciled);
        });
      this.reconciliations.add(reconciliation);
    });
  }
}
