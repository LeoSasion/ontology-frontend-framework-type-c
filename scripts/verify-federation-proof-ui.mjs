import { readFileSync } from "node:fs";

function source(relativePath) {
  return readFileSync(new URL(`../${relativePath}`, import.meta.url), "utf8");
}

const api = source("src/apiFederation.ts");
const types = source("src/typesFederation.ts");
const panel = source("src/components/FederationProofPanel.tsx");
const modules = source("src/sourceWorkbenchAdvancedModules.tsx");
const view = source("src/components/SourceWorkbenchView.tsx");

const checks = [
  {
    label: "federation-client-contract-is-typed-and-post-only",
    ok: api.includes("fetchJsonStrict<FederationProof>")
      && api.includes('"/api/connectors/federation-proof"')
      && api.includes('method: "POST"')
      && types.includes('schema: "aibi-federation-proof/v1"'),
  },
  {
    label: "federation-proof-is-a-separate-lazy-chunk",
    ok: modules.includes('lazy(() => import("./components/FederationProofPanel"))')
      && view.includes("<FederationProofPanel")
      && !view.includes('from "../apiFederation"'),
  },
  {
    label: "workspace-switch-aborts-and-rejects-cross-scope-proof",
    ok: panel.includes("requestRef.current?.controller.abort()")
      && panel.includes("requestRef.current?.id !== id")
      && panel.includes("requestRef.current.workspaceId !== expectedWorkspace")
      && panel.includes("result.workspaceId !== expectedWorkspace")
      && panel.includes('reason.name === "AbortError"'),
  },
  {
    label: "ui-separates-proof-from-execution-and-write-authority",
    ok: panel.includes("不执行 · 不落库 · 不复制业务行")
      && panel.includes("不授予执行、物化或写入权限")
      && panel.includes('data-testid="federation-proof-result"'),
  },
  {
    label: "ui-never-renders-raw-business-rows-or-credentials",
    ok: !/\b(?:rawRows|sampleRows|businessRows|credentialRef|credentialValue|rowValues)\b/.test(panel)
      && !panel.includes("JSON.stringify(proof)"),
  },
];

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-federation-proof-ui-verify/v1",
  generatedBy: "scripts/verify-federation-proof-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
