import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

type WorkspaceRoutesOptions = {
  cli: (args: string[]) => Promise<Record<string, any>>;
  port: number;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

export async function handleWorkspaceApi({ cli, port, request, response, url }: WorkspaceRoutesOptions) {
  if (url.pathname === "/api/health" && request.method === "GET") {
    sendJson(response, 200, {
      ok: true,
      service: "aibi-hybrid-api",
      port,
    });
    return true;
  }

  if (url.pathname === "/api/status" && request.method === "GET") {
    const status = await cli(["status"]);
    sendJson(response, 200, status);
    return true;
  }

  if (url.pathname === "/api/workspaces" && request.method === "GET") {
    const status = await cli(["status"]);
    sendJson(response, 200, { ok: true, workspaces: status.workspaces ?? [status.workspace], status });
    return true;
  }

  if (url.pathname === "/api/workspaces" && request.method === "POST") {
    const body = await readBody(request);
    const op = String(body.op ?? "create");
    const args = op === "select"
      ? ["workspace-select", String(body.workspaceId ?? body.workspace ?? "")]
      : op === "rename"
        ? ["workspace-rename", String(body.workspaceId ?? body.workspace ?? ""), "--name", String(body.name ?? "")]
      : op === "delete"
        ? ["workspace-delete", String(body.workspaceId ?? body.workspace ?? "")]
        : ["workspace-create", "--name", String(body.name ?? "New Workspace")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/domain-packs" && request.method === "GET") {
    const args = ["domain-packs"];
    const workspace = url.searchParams.get("workspace");
    if (workspace) args.push("--workspace", workspace);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/domain-packs" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "domain-pack-set",
      "--pack",
      String(body.packId ?? body.pack ?? ""),
      "--state",
      String(body.state ?? ""),
    ];
    if (body.workspaceId ?? body.workspace) args.push("--workspace", String(body.workspaceId ?? body.workspace));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/domain-packs/lint" && request.method === "POST") {
    const body = await readBody(request);
    const result = await cli(["domain-pack-lint", "--package", String(body.package ?? "")]);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/domain-packs/install" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["domain-pack-install", "--package", String(body.package ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/domain-packs/uninstall" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["domain-pack-uninstall", "--pack", String(body.packId ?? body.pack ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/analytical-skills" && request.method === "GET") {
    const args = ["analytical-skills"];
    const workspace = url.searchParams.get("workspace");
    if (workspace) args.push("--workspace", workspace);
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/analytical-skills" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["analytical-skill-set", "--skill", String(body.skillId ?? body.skill ?? ""), "--state", String(body.state ?? "")];
    if (body.workspaceId ?? body.workspace) args.push("--workspace", String(body.workspaceId ?? body.workspace));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/analytical-skills/match" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["analytical-skill-match", "--task-type", String(body.taskType ?? "overview")];
    if (body.workspaceId ?? body.workspace) args.push("--workspace", String(body.workspaceId ?? body.workspace));
    if (body.skillId ?? body.skill) args.push("--skill", String(body.skillId ?? body.skill));
    if (Array.isArray(body.roles)) body.roles.map(String).forEach((role) => args.push("--role", role));
    if (Array.isArray(body.domainPacks)) body.domainPacks.map(String).forEach((pack) => args.push("--domain-pack", pack));
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/workbench" && request.method === "GET") {
    const limit = url.searchParams.get("limit") ?? "12";
    const result = await cli(["workbench", "--limit", limit]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/quality/doctor" && request.method === "GET") {
    const result = await cli(["quality-doctor"]);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/navigation" && request.method === "GET") {
    const args = ["list-navigation"];
    if (url.searchParams.get("all") === "true") args.push("--all");
    const result = await cli(args);
    sendJson(response, result.ok === false ? 400 : 200, result);
    return true;
  }

  if (url.pathname === "/api/navigation/operation" && request.method === "POST") {
    const body = await readBody(request);
    const args = [
      "navigation-op",
      "--module",
      String(body.module ?? body.moduleKey ?? ""),
      "--op",
      String(body.op ?? "rename"),
    ];
    if (body.name) args.push("--name", String(body.name));
    if (body.sort !== undefined && body.sort !== null) args.push("--sort", String(body.sort));
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/sources" && request.method === "GET") {
    const result = await cli(["list-tables"]);
    sendJson(response, 200, result);
    return true;
  }

  if (url.pathname === "/api/sources/inspect" && request.method === "GET") {
    const table = url.searchParams.get("table") ?? "";
    const result = await cli(["inspect-table", table]);
    sendJson(response, result.ok === false ? 404 : 200, result);
    return true;
  }

  if (url.pathname === "/api/sources/rename" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["rename-source", String(body.source ?? body.table ?? ""), "--name", String(body.name ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  if (url.pathname === "/api/sources/delete" && request.method === "POST") {
    const body = await readBody(request);
    const args = ["delete-source", String(body.source ?? body.table ?? "")];
    if (body.confirm === true) args.push("--yes");
    const result = await cli(args);
    sendJson(response, result.requiresConfirmation ? 202 : 200, result);
    return true;
  }

  return false;
}
