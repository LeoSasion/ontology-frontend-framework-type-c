import { spawn, type ChildProcess } from "node:child_process";
import { resolve } from "node:path";

type Cli = (args: string[]) => Promise<Record<string, unknown>>;

type JobIdentity = {
  jobKey: string;
  workspaceId: string;
};

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
  private readonly reconciliations = new Set<Promise<void>>();

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

  cancel(jobKey: string) {
    const child = this.workers.get(jobKey);
    if (!child) {
      return { ownedProcess: false, signalRequested: false };
    }
    return {
      ownedProcess: true,
      signalRequested: child.kill(),
    };
  }

  async shutdown() {
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

  private launch(identity: JobIdentity, args: string[]) {
    if (this.workers.has(identity.jobKey)) {
      throw new Error(`Job already has an owned worker: ${identity.jobKey}`);
    }
    const child = spawn("python", [resolve(this.root, "tools/bi_cli.py"), "--json", ...args], {
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
        "job-process-exit",
        "--job",
        identity.jobKey,
        "--workspace",
        identity.workspaceId,
      ];
      if (typeof code === "number") reconcileArgs.push("--exit-code", String(code));
      if (signal) reconcileArgs.push("--signal", String(signal));
      const reconciliation = this.cli(reconcileArgs)
        .then(() => undefined)
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
        .finally(() => this.reconciliations.delete(reconciliation));
      this.reconciliations.add(reconciliation);
    });
  }
}
