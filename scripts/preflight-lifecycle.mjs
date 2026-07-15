const PRE_SERVICE_NPM_STAGES = [
  ["production build and bundle budgets", "build"],
  ["core, CLI, and AI verification", "verify"],
  ["workspace landing flow", "verify:workspace-flow"],
  ["local backup and restore", "verify:backup"],
  ["local schema migration and rollback", "verify:migration"],
  ["multi-domain Beta repeatability", "verify:multi-domain-beta"],
  ["local query release baseline", "verify:release-baseline"],
  ["production readiness", "verify:production"],
];

function asError(value) {
  return value instanceof Error ? value : new Error(String(value));
}

export function runPreflightLifecycle({
  args = [],
  runNpmScript,
  runPowerShell,
  inspectLocalServices,
  log = console.log,
} = {}) {
  if (typeof runNpmScript !== "function" || typeof runPowerShell !== "function" || typeof inspectLocalServices !== "function") {
    throw new TypeError("Preflight lifecycle requires npm, PowerShell, and local-health runners.");
  }

  const options = new Set(args);
  const skipUi = options.has("--skip-ui");
  const stopAfter = options.has("--stop-after");
  let preExistingServices = false;
  let ownsServiceLifecycle = false;
  let servicesStarted = false;
  let servicesStopped = false;
  let primaryError = null;

  try {
    for (const [label, scriptName] of PRE_SERVICE_NPM_STAGES) {
      runNpmScript(label, scriptName);
    }

    const inspected = inspectLocalServices();
    const serviceState = typeof inspected === "boolean"
      ? { healthy: inspected, ownershipKnown: true, listeners: [] }
      : {
          healthy: inspected?.healthy === true,
          ownershipKnown: inspected?.ownershipKnown === true,
          listeners: Array.isArray(inspected?.listeners) ? inspected.listeners : [],
        };
    preExistingServices = serviceState.healthy;
    if (preExistingServices) {
      log("\n[preflight] Reusing healthy AIBI-C local services; this run does not own their lifecycle.");
    } else {
      if (!serviceState.ownershipKnown) {
        throw new Error("Local service ownership could not be inspected; refusing to start or stop services.");
      }
      if (serviceState.listeners.length > 0) {
        const ports = [...new Set(serviceState.listeners.map((listener) => listener?.port).filter(Boolean))].join(", ");
        throw new Error(`Local ports are partially or incompatibly occupied${ports ? ` (${ports})` : ""}; refusing to modify pre-existing services.`);
      }
      ownsServiceLifecycle = true;
      runPowerShell("start local services", "scripts/start-local.ps1");
      servicesStarted = true;
    }

    runPowerShell("health check", "scripts/local-health.ps1");
    runNpmScript("server security runtime", "verify:security-runtime");

    if (skipUi) {
      log("\n[preflight] UI verification skipped by --skip-ui.");
    } else {
      runNpmScript("complete UI verification", "verify:ui");
      runPowerShell("final health check", "scripts/local-health.ps1");
    }
  } catch (error) {
    primaryError = asError(error);
  } finally {
    const mustCleanFailedRun = primaryError !== null && ownsServiceLifecycle;
    const mustStopSuccessfulRun = primaryError === null && stopAfter && ownsServiceLifecycle;
    if (mustCleanFailedRun || mustStopSuccessfulRun) {
      try {
        runPowerShell(
          mustCleanFailedRun ? "clean up local services after failure" : "stop local services",
          "scripts/stop-local.ps1",
        );
        servicesStopped = true;
      } catch (cleanupFailure) {
        const cleanupError = asError(cleanupFailure);
        primaryError = primaryError
          ? new AggregateError([primaryError, cleanupError], "Preflight failed and could not clean up the services started by this run.")
          : cleanupError;
      }
    } else if (stopAfter && preExistingServices) {
      log("\n[preflight] --stop-after did not stop services that existed before this run.");
    }
  }

  if (primaryError) {
    throw primaryError;
  }

  return {
    ok: true,
    skipUi,
    stopAfter,
    services: {
      preExisting: preExistingServices,
      startedByPreflight: servicesStarted,
      stoppedByPreflight: servicesStopped,
    },
  };
}
