import type { ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join } from "node:path";

export async function handleStatic(response: ServerResponse, pathname: string, root: string) {
  const dist = join(root, "dist");
  const target = pathname === "/" ? join(dist, "index.html") : join(dist, pathname);
  const fallback = join(dist, "index.html");
  const path = pathname.includes(".") ? target : fallback;
  try {
    const content = await readFile(path);
    const type = extname(path) === ".js" ? "text/javascript" : extname(path) === ".css" ? "text/css" : "text/html";
    response.writeHead(200, { "content-type": `${type}; charset=utf-8` });
    response.end(content);
  } catch {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("Not found");
  }
}
