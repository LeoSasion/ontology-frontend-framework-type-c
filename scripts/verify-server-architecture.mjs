import { readdirSync, readFileSync } from "node:fs";
const serverDir = new URL("../server/", import.meta.url);
const files = readdirSync(serverDir).filter((name) => name.endsWith(".ts"));
const sources = new Map(files.map((name) => [name, readFileSync(new URL(name, serverDir), "utf8")]));
const routeOwners = new Map();
const routePattern = /url\.pathname\s*===\s*["']([^"']+)["'][\s\S]{0,180}?request\.method\s*===\s*["']([A-Z]+)["']/g;

for (const [file, source] of sources) {
  for (const match of source.matchAll(routePattern)) {
    const key = `${match[2]} ${match[1]}`;
    const owners = routeOwners.get(key) ?? [];
    owners.push(file);
    routeOwners.set(key, owners);
  }
}

const duplicateRoutes = [...routeOwners]
  .filter(([, owners]) => owners.length > 1)
  .map(([route, owners]) => ({ route, owners }));
const serverRuntime = sources.get("serverRuntime.ts") ?? "";
const runtimeHost = sources.get("runtimeHost.ts") ?? "";
const serverIndex = sources.get("index.ts") ?? "";
const staticServer = sources.get("staticServer.ts") ?? "";
const directUiImports = [...sources]
  .filter(([, source]) => /from\s+["']\.\.\/src\//.test(source))
  .map(([file]) => file);

const checks = [
  { label: "api-route-method-pairs-have-one-owner", ok: duplicateRoutes.length === 0, detail: duplicateRoutes },
  { label: "server-does-not-import-ui-source", ok: directUiImports.length === 0, detail: directUiImports },
  {
    label: "api-uses-long-lived-runtime-host",
    ok: runtimeHost.includes("export class RuntimeHostPool")
      && runtimeHost.includes('tools/aibi_runtime_host.py')
      && serverRuntime.includes("new RuntimeHostPool(root)")
      && !serverRuntime.includes("tools/aibi_cli.py"),
  },
  {
    label: "runtime-host-has-single-writer-read-pool-and-capacity",
    ok: runtimeHost.includes('"runtime-writer"')
      && runtimeHost.includes("`runtime-reader-${index + 1}`")
      && runtimeHost.includes("MAX_QUEUE_DEPTH")
      && runtimeHost.includes("RuntimeHostCapacityError"),
  },
  {
    label: "api-exposes-separate-live-and-ready-probes",
    ok: serverIndex.includes('url.pathname === "/api/live"')
      && serverIndex.includes('url.pathname === "/api/ready"')
      && serverIndex.includes("runtimeHostHealth(root)"),
  },
  {
    label: "browser-mutations-have-caller-and-idempotency-boundaries",
    ok: serverIndex.includes("browser-command-envelope-required")
      && serverIndex.includes("runtime-token-invalid")
      && serverIndex.includes("idempotency-key-required")
      && serverIndex.includes("withJsonResponseCapture"),
  },
  {
    label: "static-delivery-has-validators-and-immutable-assets",
    ok: staticServer.includes('"if-none-match"')
      && staticServer.includes("immutable")
      && staticServer.includes("brotli")
      && staticServer.includes('request.method === "HEAD"'),
  },
];

const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-server-architecture-verify/v1",
  generatedBy: "scripts/verify-server-architecture.mjs",
  routeCount: routeOwners.size,
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
