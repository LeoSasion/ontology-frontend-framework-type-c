import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type AnalysisUnitRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

const nonEmpty = (value: unknown) => String(value ?? "").trim();

export async function handleAnalysisUnitApi({ cli, request, response, url }: AnalysisUnitRoutesOptions) {
  if (url.pathname === "/api/metric-monitors" && request.method === "GET") {
    const args = ["metric-monitors"];
    const monitor = nonEmpty(url.searchParams.get("monitor"));
    const status = nonEmpty(url.searchParams.get("status"));
    const limit = nonEmpty(url.searchParams.get("limit")) || "30";
    if (monitor) args.push("--monitor", monitor);
    if (status) args.push("--status", status);
    args.push("--limit", limit);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }

  const monitorMutation = url.pathname.match(/^\/api\/metric-monitors\/(create|replace|delete|run)$/);
  if (monitorMutation && request.method === "POST") {
    const operation = monitorMutation[1];
    const body = await readBody(request);
    const monitor = nonEmpty(body.monitor ?? body.monitorKey);
    const snapshot = nonEmpty(body.snapshot ?? body.snapshotKey);
    if (["replace", "delete", "run"].includes(operation) && !monitor) {
      sendJson(response, 400, { ok: false, action: `metric-monitor-${operation}`, error: "monitor is required" });
      return true;
    }
    if (["create", "replace"].includes(operation) && (!snapshot || !nonEmpty(body.label))) {
      sendJson(response, 400, { ok: false, action: `metric-monitor-${operation}`, error: "snapshot and label are required" });
      return true;
    }
    const args = [`metric-monitor-${operation}`];
    if (monitor) args.push("--monitor", monitor);
    if (snapshot) args.push("--snapshot", snapshot);
    if (["create", "replace"].includes(operation)) {
      args.push("--label", nonEmpty(body.label));
      if (nonEmpty(body.metric)) args.push("--metric", nonEmpty(body.metric));
      args.push("--cadence", nonEmpty(body.cadence) || "manual");
      args.push("--strategy", nonEmpty(body.comparisonStrategy) || "absolute-change");
      args.push("--direction", nonEmpty(body.direction) || "absolute");
      args.push("--warning-ratio", nonEmpty(body.warningRatio) || "0.8");
      if (body.threshold !== undefined && body.threshold !== null && nonEmpty(body.threshold)) {
        args.push("--threshold", nonEmpty(body.threshold));
      }
    }
    if (["create", "replace", "delete"].includes(operation) && body.confirm === true) {
      args.push("--yes", "--expected-plan", nonEmpty(body.expectedPlanFingerprint));
    }
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/analysis-snapshots" && request.method === "GET") {
    const args = ["analysis-snapshots"];
    const snapshot = nonEmpty(url.searchParams.get("snapshot"));
    const unit = nonEmpty(url.searchParams.get("unit"));
    const status = nonEmpty(url.searchParams.get("status"));
    const limit = nonEmpty(url.searchParams.get("limit")) || "30";
    if (snapshot) args.push("--snapshot", snapshot);
    if (unit) args.push("--unit", unit);
    if (status) args.push("--status", status);
    args.push("--limit", limit);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }

  const snapshotMutation = url.pathname.match(/^\/api\/analysis-snapshots\/(create|refresh|replace|delete)$/);
  if (snapshotMutation && request.method === "POST") {
    const operation = snapshotMutation[1];
    const body = await readBody(request);
    const snapshot = nonEmpty(body.snapshot ?? body.snapshotKey);
    const unit = nonEmpty(body.unit ?? body.unitKey);
    const reason = nonEmpty(body.reason);
    if (operation !== "delete" && !unit) {
      sendJson(response, 400, { ok: false, action: `analysis-snapshot-${operation}`, error: "unit is required" });
      return true;
    }
    if (["refresh", "replace", "delete"].includes(operation) && !snapshot) {
      sendJson(response, 400, { ok: false, action: `analysis-snapshot-${operation}`, error: "snapshot is required" });
      return true;
    }
    if (operation !== "delete" && !reason) {
      sendJson(response, 400, { ok: false, action: `analysis-snapshot-${operation}`, error: "reason is required" });
      return true;
    }
    const args = [`analysis-snapshot-${operation}`];
    if (snapshot) args.push("--snapshot", snapshot);
    if (unit) args.push("--unit", unit);
    if (reason) args.push("--reason", reason);
    if (operation !== "delete") args.push("--row-limit", nonEmpty(body.rowLimit) || "500");
    if (body.confirm === true) args.push("--yes", "--expected-plan", nonEmpty(body.expectedPlanFingerprint));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/analysis-units" && request.method === "GET") {
    const args = ["analysis-units"];
    const unit = nonEmpty(url.searchParams.get("unit"));
    const receipt = nonEmpty(url.searchParams.get("receipt"));
    const limit = nonEmpty(url.searchParams.get("limit")) || "30";
    if (unit) args.push("--unit", unit);
    if (receipt) args.push("--receipt", receipt);
    args.push("--limit", limit);
    const result = await cli(args);
    const rejectedExistingUnit = result.ok === false && result.analysisUnit;
    const returnedList = Array.isArray(result.analysisUnits);
    sendJson(response, result.ok === false ? (rejectedExistingUnit ? 409 : returnedList ? 200 : 404) : 200, result);
    return true;
  }

  if (url.pathname === "/api/forecast-readiness" && request.method === "GET") {
    const unit = nonEmpty(url.searchParams.get("unit"));
    const horizon = nonEmpty(url.searchParams.get("horizon")) || "1";
    if (!unit) {
      sendJson(response, 400, { ok: false, action: "forecast-readiness", error: "unit is required" });
      return true;
    }
    const result = await cli(["forecast-readiness", "--unit", unit, "--horizon", horizon]);
    sendJson(response, result.forecastReadiness ? 200 : result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/analysis-units/build" && request.method === "POST") {
    const body = await readBody(request);
    const receipt = nonEmpty(body.receipt ?? body.queryReceiptKey);
    if (!receipt || !Array.isArray(body.rows)) {
      sendJson(response, 400, { ok: false, action: "analysis-unit-build", error: "receipt and rows are required" });
      return true;
    }
    const args = [
      "analysis-unit-build", "--receipt", receipt,
      "--kind", nonEmpty(body.kind) || "auto",
      "--rows-json", JSON.stringify(body.rows),
    ];
    if (body.title) args.push("--title", String(body.title));
    if (body.preferredChart) args.push("--preferred-chart", String(body.preferredChart));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/analysis-units/verify" && request.method === "POST") {
    const body = await readBody(request);
    const unit = nonEmpty(body.unit ?? body.unitKey);
    if (!unit) {
      sendJson(response, 400, { ok: false, action: "analysis-unit-verify", error: "unit is required" });
      return true;
    }
    const result = await cli(["analysis-unit-verify", "--unit", unit]);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  if (url.pathname === "/api/chart-adapt" && request.method === "POST") {
    const body = await readBody(request);
    const unit = nonEmpty(body.unit ?? body.unitKey);
    if (!unit) {
      sendJson(response, 400, { ok: false, action: "chart-adapt", error: "unit is required" });
      return true;
    }
    const args = ["chart-adapt", "--unit", unit];
    if (body.preferredChart) args.push("--preferred-chart", String(body.preferredChart));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }

  return false;
}
