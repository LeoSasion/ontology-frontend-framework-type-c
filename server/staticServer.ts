import { brotliCompress, gzip } from "node:zlib";
import { promisify } from "node:util";
import type { IncomingMessage, ServerResponse } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";

const brotli = promisify(brotliCompress);
const gzipAsync = promisify(gzip);
const MIME_TYPES: Record<string, string> = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml; charset=utf-8",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function cacheControl(pathname: string) {
  return /^\/assets\/[^/]+-[A-Za-z0-9_-]{8,}\.[^.]+$/.test(pathname)
    ? "public, max-age=31536000, immutable"
    : "no-cache";
}

export async function handleStatic(request: IncomingMessage, response: ServerResponse, pathname: string, root: string) {
  const dist = resolve(root, "dist");
  let decoded = pathname;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    response.writeHead(400, { "content-type": "text/plain; charset=utf-8" });
    response.end("Bad request");
    return;
  }
  const requested = resolve(dist, `.${decoded}`);
  if (requested !== dist && !requested.startsWith(`${dist}${sep}`)) {
    response.writeHead(403, { "content-type": "text/plain; charset=utf-8" });
    response.end("Forbidden");
    return;
  }
  const path = decoded === "/" || !decoded.includes(".") ? resolve(dist, "index.html") : requested;
  try {
    const [content, fileStat] = await Promise.all([readFile(path), stat(path)]);
    const etag = `W/\"${fileStat.size.toString(16)}-${Math.trunc(fileStat.mtimeMs).toString(16)}\"`;
    const headers: Record<string, string> = {
      "cache-control": cacheControl(decoded),
      "content-type": MIME_TYPES[extname(path).toLowerCase()] ?? "application/octet-stream",
      etag,
      "x-content-type-options": "nosniff",
    };
    if (request.headers["if-none-match"] === etag) {
      response.writeHead(304, headers);
      response.end();
      return;
    }
    let body = content;
    const compressible = /^(?:text\/|application\/(?:javascript|json))/.test(headers["content-type"]);
    const accepted = String(request.headers["accept-encoding"] ?? "");
    if (request.method !== "HEAD" && compressible && content.byteLength >= 1_024) {
      headers.vary = "accept-encoding";
      if (/\bbr\b/.test(accepted)) {
        body = await brotli(content);
        headers["content-encoding"] = "br";
      } else if (/\bgzip\b/.test(accepted)) {
        body = await gzipAsync(content);
        headers["content-encoding"] = "gzip";
      }
    }
    headers["content-length"] = String(request.method === "HEAD" ? content.byteLength : body.byteLength);
    response.writeHead(200, headers);
    response.end(request.method === "HEAD" ? undefined : body);
  } catch {
    response.writeHead(404, { "cache-control": "no-store", "content-type": "text/plain; charset=utf-8" });
    response.end("Not found");
  }
}
