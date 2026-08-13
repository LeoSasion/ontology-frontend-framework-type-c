import type { IncomingMessage, ServerResponse } from "node:http";
import { readBody, sendJson } from "./serverRuntime";

export type ReviewedPublicationCapability =
  | "reviewed-publication:read"
  | "reviewed-publication:owner";

type ReviewedPublicationRoutesOptions = {
  authorize: (capability: ReviewedPublicationCapability, request: IncomingMessage) => boolean | Promise<boolean>;
  cli: (args: string[]) => Promise<Record<string, unknown>>;
  request: IncomingMessage;
  response: ServerResponse;
  url: URL;
};

const PUBLICATION_KEY = /^reviewed_publication_[a-f0-9]{20}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const STATUSES = new Set(["current", "drifted", "deprecated", "integrity_failed"]);

function resultStatus(result: Record<string, unknown>) {
  if (result.ok === false) return 409;
  return result.requiresConfirmation === true ? 202 : 200;
}

function decodedPublicationKey(pathname: string) {
  const suffix = pathname.slice("/api/reviewed-publications/".length);
  const encoded = suffix.replace(/\/(?:export|deprecate)$/, "");
  try {
    return decodeURIComponent(encoded);
  } catch {
    return "";
  }
}

async function authorizeRoute(options: ReviewedPublicationRoutesOptions, capability: ReviewedPublicationCapability) {
  if (await options.authorize(capability, options.request)) return true;
  sendJson(options.response, 403, {
    ok: false,
    code: "REVIEWED_PUBLICATION_CAPABILITY_DENIED",
    error: capability.endsWith(":read")
      ? "Reviewed publications require the local viewer capability."
      : "Deprecating a reviewed publication requires the local owner capability.",
  });
  return false;
}

function validWorkspaceId(value: unknown) {
  const workspaceId = String(value ?? "").trim();
  return workspaceId && workspaceId.length <= 160 ? workspaceId : "";
}

async function activeWorkspace(options: ReviewedPublicationRoutesOptions, requestedWorkspaceId: string) {
  const status = await options.cli(["status"]);
  const workspace = status.workspace;
  const activeWorkspaceId = workspace && typeof workspace === "object" && !Array.isArray(workspace)
    ? String((workspace as Record<string, unknown>).id ?? "")
    : "";
  if (!activeWorkspaceId || activeWorkspaceId !== requestedWorkspaceId) {
    sendJson(options.response, 409, {
      ok: false,
      code: "REVIEWED_PUBLICATION_WORKSPACE_CHANGED",
      error: "The active workspace changed. Refresh reviewed publications before continuing.",
    });
    return "";
  }
  return activeWorkspaceId;
}

function boundResult(
  options: ReviewedPublicationRoutesOptions,
  result: Record<string, unknown>,
  workspaceId: string,
) {
  const publications = Array.isArray(result.reviewedPublications)
    ? result.reviewedPublications
    : result.reviewedPublication && typeof result.reviewedPublication === "object"
      ? [result.reviewedPublication]
      : result.reviewedPublicationExport && typeof result.reviewedPublicationExport === "object"
        ? [((result.reviewedPublicationExport as Record<string, unknown>).publication)]
        : result.publication && typeof result.publication === "object"
          ? [result.publication]
          : [];
  const mismatch = publications.some((item) => (
    item && typeof item === "object" && !Array.isArray(item)
      ? String((item as Record<string, unknown>).workspaceId ?? "") !== workspaceId
      : true
  ));
  if (mismatch) {
    sendJson(options.response, 409, {
      ok: false,
      code: "REVIEWED_PUBLICATION_WORKSPACE_MISMATCH",
      error: "Reviewed publication results do not belong to the active workspace.",
    });
    return false;
  }
  sendJson(options.response, resultStatus(result), { ...result, workspaceId });
  return true;
}

export async function handleReviewedPublicationApi(options: ReviewedPublicationRoutesOptions) {
  const { cli, request, response, url } = options;
  if (!url.pathname.startsWith("/api/reviewed-publications")) return false;

  const listRoute = url.pathname === "/api/reviewed-publications";
  const exportRoute = /^\/api\/reviewed-publications\/[^/]+\/export$/.test(url.pathname);
  const deprecateRoute = /^\/api\/reviewed-publications\/[^/]+\/deprecate$/.test(url.pathname);
  const inspectRoute = /^\/api\/reviewed-publications\/[^/]+$/.test(url.pathname);
  const deprecate = deprecateRoute && request.method === "POST";
  const readRoute = request.method === "GET" && (listRoute || inspectRoute || exportRoute);
  if (!deprecate && !readRoute) return false;
  if (!await authorizeRoute(options, deprecate ? "reviewed-publication:owner" : "reviewed-publication:read")) return true;

  if (listRoute && request.method === "GET") {
    const workspaceId = validWorkspaceId(url.searchParams.get("workspaceId"));
    const limitValue = Number(url.searchParams.get("limit") ?? 30);
    const limit = Number.isInteger(limitValue) ? Math.max(1, Math.min(limitValue, 100)) : 30;
    const status = String(url.searchParams.get("status") ?? "").trim();
    if (!workspaceId || (status && !STATUSES.has(status))) {
      sendJson(response, 400, { ok: false, code: "REVIEWED_PUBLICATION_LIST_INPUT_INVALID", error: "A current workspaceId and valid status are required." });
      return true;
    }
    if (!await activeWorkspace(options, workspaceId)) return true;
    const args = ["reviewed-publications", "--limit", String(status ? 100 : limit)];
    const result = await cli(args);
    if (status && Array.isArray(result.reviewedPublications)) {
      const effectiveStatus = status === "drifted" ? "stale" : status;
      const reviewedPublications = result.reviewedPublications
        .filter((item) => item && typeof item === "object" && !Array.isArray(item) && (item as Record<string, unknown>).status === effectiveStatus)
        .slice(0, limit);
      result.reviewedPublications = reviewedPublications;
      result.count = reviewedPublications.length;
    }
    boundResult(options, result, workspaceId);
    return true;
  }

  const publicationKey = decodedPublicationKey(url.pathname);
  if (!PUBLICATION_KEY.test(publicationKey)) {
    sendJson(response, 400, { ok: false, code: "REVIEWED_PUBLICATION_KEY_INVALID", error: "A valid reviewed publication key is required." });
    return true;
  }

  if (request.method === "GET") {
    const workspaceId = validWorkspaceId(url.searchParams.get("workspaceId"));
    if (!workspaceId) {
      sendJson(response, 400, { ok: false, code: "REVIEWED_PUBLICATION_WORKSPACE_REQUIRED", error: "A current workspaceId is required." });
      return true;
    }
    if (!await activeWorkspace(options, workspaceId)) return true;
    const args = exportRoute
      ? ["reviewed-publication-export", "--publication", publicationKey]
      : ["reviewed-publications", "--publication", publicationKey];
    const result = await cli(args);
    boundResult(options, result, workspaceId);
    return true;
  }

  const body = await readBody(request);
  const workspaceId = validWorkspaceId(body.workspaceId);
  const reason = String(body.reason ?? "").trim();
  const confirm = body.confirm === true;
  const expectedHeadHash = String(body.expectedHeadHash ?? "").trim();
  if (!workspaceId || !reason || reason.length > 500 || (confirm && !SHA256.test(expectedHeadHash))) {
    sendJson(response, 400, {
      ok: false,
      code: "REVIEWED_PUBLICATION_DEPRECATION_INPUT_INVALID",
      error: "Deprecation requires workspaceId, a bounded reason, and the exact ledger head when confirmed.",
    });
    return true;
  }
  if (!await activeWorkspace(options, workspaceId)) return true;
  const args = ["reviewed-publication-deprecate", "--publication", publicationKey, "--reason", reason];
  if (confirm) args.push("--yes", "--expected-head", expectedHeadHash);
  const result = await cli(args);
  boundResult(options, result, workspaceId);
  return true;
}
