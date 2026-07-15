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
