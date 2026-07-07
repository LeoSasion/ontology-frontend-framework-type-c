import type { IncomingMessage, ServerResponse } from "node:http";
import {
  pushDashboardWidgetStyleArgs,
  readBCostMonitorValidation,
  readBody,
  sendJson,
} from "./serverRuntime";

type DashboardRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  root: string;
  url: URL;
};

export async function handleDashboardApi(options: DashboardRoutesOptions) {
  const { cli, request, response, root, url } = options;

  if (url.pathname === "/api/dashboard/widget-catalog" && request.method === "GET") {
    const result = await cli(["dashboard-widget-catalog"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/dashboard/recommend-widgets" && request.method === "GET") {
    const args = ["recommend-widgets"];
    const table = url.searchParams.get("table");
    const limit = url.searchParams.get("limit") ?? "7";
    if (table) args.push("--table", table);
    args.push("--limit", limit);
    const result = await cli(args);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/dashboard/modules" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["save-dashboard-modules", "--dashboard", String(body.dashboardKey ?? "default")];
    if (body.dashboardName) args.push("--name", String(body.dashboardName));
    if (body.defaultTableKey) args.push("--default-table", String(body.defaultTableKey));
    if (body.canvasWidthMode) args.push("--canvas-width-mode", String(body.canvasWidthMode));
    args.push("--widgets-json", JSON.stringify(Array.isArray(body.widgets) ? body.widgets : []));
    args.push("--layout-json", JSON.stringify(Array.isArray(body.layout) ? body.layout : []));
    args.push("--filters-json", JSON.stringify(Array.isArray(body.filters) ? body.filters : []));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/dashboard/business-template" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["business-dashboard", "--op", String(body.op ?? "draft")];
    if (body.dashboardKey) args.push("--dashboard", String(body.dashboardKey));
    if (body.name) args.push("--name", String(body.name));
    if (body.table) args.push("--table", String(body.table));
    if (body.template) args.push("--template", String(body.template));
    if (body.limit) args.push("--limit", String(body.limit));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/validation/b-cost-monitor" && request.method === "GET") {
    try {
      const result = await readBCostMonitorValidation(root);
      sendJson(response, 200, result);
    } catch (error) {
      const message = error instanceof Error && error.message ? error.message : "Cost monitor validation is not available";
      sendJson(response, 404, { ok: false, error: message });
    }
    return true;
  }

  if (url.pathname === "/api/dashboard/widgets" && request.method === "POST") {
    const body = await readBody(request);
    const op = String(body.op ?? "recommend");
    const args = op === "recommend"
      ? ["recommend-widgets"]
      : op === "addRecommended"
        ? ["add-recommended-widgets", "--dashboard", String(body.dashboardKey ?? "default")]
        : op === "add"
          ? ["add-widget", "--dashboard", String(body.dashboardKey ?? "default"), "--type", String(body.type ?? "bar")]
          : op === "addRelationship"
            ? ["add-relationship-widget", "--dashboard", String(body.dashboardKey ?? "default"), "--type", String(body.type ?? "bar")]
            : op === "set"
              ? ["set-widget", "--widget", String(body.widgetKey ?? "")]
              : op === "copy"
                ? ["copy-widget", "--widget", String(body.widgetKey ?? "")]
                : op === "remove"
                  ? ["remove-widget", "--widget", String(body.widgetKey ?? "")]
                  : [];
    if (!args.length) {
      sendJson(response, 400, { ok: false, error: `Unsupported widget operation: ${op}` });
      return true;
    }
    if (op === "recommend" || op === "addRecommended") {
      if (body.table) args.push("--table", String(body.table));
      if (body.limit) args.push("--limit", String(body.limit));
      if (body.allowDuplicates === true) args.push("--allow-duplicates");
    }
    if (op === "add" || op === "set") {
      if (body.table) args.push("--table", String(body.table));
      if (body.view) args.push("--view", String(body.view));
      if (body.title) args.push("--title", String(body.title));
      if (body.subtitle) args.push("--subtitle", String(body.subtitle));
      if (body.dimension) args.push("--dimension", String(body.dimension));
      if (body.measure) args.push("--measure", String(body.measure));
      if (body.aggregation) args.push("--agg", String(body.aggregation));
      if (body.topN) args.push("--top-n", String(body.topN));
      if (body.valueFormat) args.push("--value-format", String(body.valueFormat));
      if (body.textContent) args.push("--text-content", String(body.textContent));
      pushDashboardWidgetStyleArgs(args, body);
      if (Array.isArray(body.filters)) {
        for (const filter of body.filters) {
          if (filter && typeof filter === "object") {
            const item = filter as Record<string, unknown>;
            args.push("--filter", `${String(item.field ?? "")}:${String(item.operator ?? "contains")}:${String(item.value ?? "")}`);
          }
        }
      }
      if (body.clearFilters === true) args.push("--clear-filters");
      if (op === "add" && body.widgetKey) args.push("--widget", String(body.widgetKey));
      if (op === "set" && body.type) args.push("--type", String(body.type));
    }
    if (op === "addRelationship") {
      if (body.widgetKey) args.push("--widget", String(body.widgetKey));
      if (body.relationship || body.relation) args.push("--relationship", String(body.relationship ?? body.relation));
      if (body.title) args.push("--title", String(body.title));
      if (body.subtitle) args.push("--subtitle", String(body.subtitle));
      if (body.group || body.dimension) args.push("--group", String(body.group ?? body.dimension));
      if (body.measure) args.push("--measure", String(body.measure));
      if (body.aggregation) args.push("--agg", String(body.aggregation));
      if (body.topN) args.push("--top-n", String(body.topN));
      if (body.valueFormat) args.push("--value-format", String(body.valueFormat));
      pushDashboardWidgetStyleArgs(args, body);
    }
    if (op === "copy") {
      if (body.dashboardKey) args.push("--dashboard", String(body.dashboardKey));
      if (body.title) args.push("--title", String(body.title));
      if (body.clearFilters === true) args.push("--clear-filters");
    }
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/b-cli/capabilities" && request.method === "GET") {
    const result = await cli(["b-cli-capabilities"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/dashboards" && request.method === "GET") {
    const result = await cli(["dashboards"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/dashboards" && request.method === "POST") {
    const body = await readBody(request);
    const prompt = String(body.prompt ?? "创建一个经营证据看板");
    const result = await cli(["ask", prompt]);
    sendJson(response, 202, result);
    return true;
  }

  if (url.pathname === "/api/dashboards/operation" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["dashboard-op", "--op", String(body.op ?? "create")];
    if (body.dashboardKey) args.push("--dashboard", String(body.dashboardKey));
    if (body.sourceDashboardKey) args.push("--source", String(body.sourceDashboardKey));
    if (body.name) args.push("--name", String(body.name));
    if (body.table) args.push("--table", String(body.table));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/dashboards/filters" && request.method === "POST") {
    const body = await readBody(request);
    const op = String(body.op ?? "list");
    const dashboard = String(body.dashboardKey ?? body.dashboard ?? "default");
    const args = op === "list"
      ? ["list-filters", "--dashboard", dashboard]
      : op === "add"
        ? ["add-filter", "--dashboard", dashboard]
        : op === "set"
          ? ["set-filter", "--dashboard", dashboard]
          : op === "remove"
            ? ["remove-filter", "--dashboard", dashboard]
            : op === "removeStale"
              ? ["remove-stale-filters", "--dashboard", dashboard]
              : op === "clear"
                ? ["clear-filters", "--dashboard", dashboard]
                : [];
    if (!args.length) {
      sendJson(response, 400, { ok: false, error: `Unsupported filter operation: ${op}` });
      return true;
    }
    if (op === "add" || op === "set") {
      if (op === "set") args.push("--filter", String(body.filterId ?? body.filter ?? ""));
      args.push("--field", String(body.field ?? ""));
      if (body.operator) args.push("--operator", String(body.operator));
      if (body.value !== undefined) args.push("--value", String(body.value));
      if (body.disabled === true) args.push("--disabled");
    }
    if (op === "remove") args.push("--filter", String(body.filterId ?? body.filter ?? ""));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  return false;
}
