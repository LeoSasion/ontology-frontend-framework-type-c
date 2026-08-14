import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type ExportRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

const nonEmpty = (value: unknown) => String(value ?? "").trim();

export async function handleExportApi({ cli, request, response, url }: ExportRoutesOptions) {
  if (url.pathname === "/api/exports/analysis" && request.method === "POST") {
    const body = await readBody(request);
    const receipt = nonEmpty(body.receipt ?? body.queryReceiptKey);
    const unit = nonEmpty(body.unit ?? body.unitKey);
    if (!receipt || !unit) {
      sendJson(response, 400, { ok: false, action: "export-analysis", error: "receipt and unit are required" });
      return true;
    }
    const args = ["export-analysis", "--receipt", receipt, "--unit", unit];
    if (body.output) args.push("--output", String(body.output));
    const formats = Array.isArray(body.formats) ? body.formats.map(nonEmpty).filter(Boolean) : [];
    if (formats.length > 4 || formats.some((format) => !["xlsx", "docx", "pptx", "md"].includes(format))) {
      sendJson(response, 400, { ok: false, action: "export-analysis", code: "ANALYSIS_EXPORT_FORMAT_INVALID", error: "formats must contain only xlsx, docx, pptx, or md" });
      return true;
    }
    for (const format of formats) args.push("--format", format);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 409 : 200, result);
    return true;
  }
  return false;
}
