import { spawn } from "node:child_process";
import type { IncomingMessage, ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { buildActionRecovery } from "../src/actionRecoveryModel";

export type JsonValue = Record<string, unknown> | Array<unknown> | string | number | boolean | null;

function enrichedErrorBody(body: JsonValue): JsonValue {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return body;
  }
  if (body.ok !== false || body.recovery) {
    return body;
  }
  const action = typeof body.action === "string" && body.action
    ? body.action
    : typeof body.command === "string" && body.command
      ? body.command
      : "api";
  const error = typeof body.error === "string" && body.error ? body.error : "Local API action failed";
  const recovery = buildActionRecovery(action, error);
  return {
    ...body,
    action,
    category: body.category ?? recovery.category,
    targetSection: body.targetSection ?? recovery.targetSection,
    safeState: body.safeState ?? recovery.safeState.zh,
    evidence: Array.isArray(body.evidence) ? body.evidence : recovery.evidence,
    next: typeof body.next === "string" && body.next ? body.next : recovery.next.zh,
    recovery,
  };
}

export function sendJson(response: ServerResponse, status: number, body: JsonValue) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type",
  });
  response.end(JSON.stringify(enrichedErrorBody(body), null, 2));
}

export function readBody(request: IncomingMessage): Promise<Record<string, unknown>> {
  return new Promise((resolveBody, reject) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    request.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8").trim();
      if (!text) {
        resolveBody({});
        return;
      }
      try {
        resolveBody(JSON.parse(text));
      } catch (error) {
        reject(error);
      }
    });
    request.on("error", reject);
  });
}

export function runCli(root: string, args: string[]): Promise<Record<string, unknown>> {
  return new Promise((resolveCli, reject) => {
    const child = spawn("python", ["tools/bi_cli.py", "--json", ...args], {
      cwd: root,
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
      },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    child.stdout.on("data", (chunk) => stdout.push(Buffer.from(chunk)));
    child.stderr.on("data", (chunk) => stderr.push(Buffer.from(chunk)));
    child.on("error", reject);
    child.on("close", (code) => {
      const text = Buffer.concat(stdout).toString("utf8");
      const err = Buffer.concat(stderr).toString("utf8");
      try {
        const parsed = JSON.parse(text);
        if (code === 0 || typeof parsed === "object") {
          resolveCli(parsed as Record<string, unknown>);
          return;
        }
      } catch {
        // Fall through to structured error.
      }
      reject(new Error(err || text || `CLI exited with ${code}`));
    });
  });
}

export function pushDashboardWidgetStyleArgs(args: string[], body: Record<string, unknown>) {
  const stringOptions: Array<[string, string]> = [
    ["sortBy", "--sort-by"],
    ["sortDirection", "--sort-direction"],
    ["decimalPlaces", "--decimal-places"],
    ["tableColumnLimit", "--table-column-limit"],
    ["slicerDisplay", "--slicer-display"],
    ["rankingMode", "--ranking-mode"],
    ["colorPalette", "--color-palette"],
    ["barOrientation", "--bar-orientation"],
    ["pieShape", "--pie-shape"],
    ["xAxisTitle", "--x-axis-title"],
    ["yAxisTitle", "--y-axis-title"],
    ["legendTitle", "--legend-title"],
  ];
  for (const [key, flag] of stringOptions) {
    if (body[key] !== undefined && body[key] !== null && String(body[key]) !== "") {
      args.push(flag, String(body[key]));
    }
  }
  const booleanOptions: Array<[string, string, string]> = [
    ["slicerMultiSelect", "--slicer-multi-select", "--single-select"],
    ["slicerSearchable", "--slicer-searchable", "--no-slicer-search"],
    ["showLegend", "--show-legend", "--hide-legend"],
    ["showAxis", "--show-axis", "--hide-axis"],
    ["showDataLabel", "--show-data-label", "--hide-data-label"],
    ["lineSmooth", "--line-smooth", "--line-straight"],
    ["areaFill", "--area-fill", "--no-area-fill"],
    ["crossFilter", "--cross-filter", "--no-cross-filter"],
    ["drillDown", "--drill-down", "--no-drill-down"],
    ["globalFilterTarget", "--global-filter-target", "--no-global-filter-target"],
  ];
  for (const [key, enabledFlag, disabledFlag] of booleanOptions) {
    if (body[key] === true) args.push(enabledFlag);
    if (body[key] === false) args.push(disabledFlag);
  }
}

export function recordValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

export function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export async function readBCostMonitorValidation(root: string) {
  const validationPath = join(root, "data", "validation", "b-cost-monitor", "b-cost-monitor-comparison.json");
  const raw = await readFile(validationPath, "utf8");
  const payload = JSON.parse(raw) as Record<string, unknown>;
  const widgets = Array.isArray(payload.widgets) ? payload.widgets.map(recordValue).filter(Boolean) as Array<Record<string, unknown>> : [];
  const nonTextWidgets = widgets.filter((widget) => widget.chartType !== "text");
  const rowCounts = recordValue(payload.rowCounts) ?? {};
  const rowEntries = Object.entries(rowCounts).map(([tableKey, value]) => {
    const row = recordValue(value) ?? {};
    const rowsMatch = numberValue(row.dbRows) === numberValue(row.sourceRows);
    const columnsMatch = numberValue(row.dbColumns) === numberValue(row.sourceColumns);
    return { tableKey, ...row, rowsMatch, columnsMatch, matches: rowsMatch && columnsMatch };
  });
  return {
    ok: true,
    ...payload,
    summary: {
      sourceCount: Array.isArray(payload.sources) ? payload.sources.length : 0,
      widgetCount: numberValue(recordValue(payload.dashboard)?.widgetCount) || widgets.length,
      matchedWidgets: widgets.filter((widget) => widget.matches === true).length,
      totalWidgets: widgets.length,
      matchedNonTextWidgets: nonTextWidgets.filter((widget) => widget.matches === true).length,
      totalNonTextWidgets: nonTextWidgets.length,
      matchedTables: rowEntries.filter((entry) => entry.matches).length,
      totalTables: rowEntries.length,
      formulaNames: Object.keys(recordValue(payload.formulaDefinitions) ?? {}),
      artifactPath: validationPath,
    },
    rowMatches: rowEntries,
  };
}
