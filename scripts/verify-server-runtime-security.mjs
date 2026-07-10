const apiBaseUrl = process.env.AIBI_API_BASE_URL ?? "http://127.0.0.1:8787";

function check(label, ok, detail) {
  return { label, ok: Boolean(ok), detail };
}

const healthResponse = await fetch(`${apiBaseUrl}/api/health`, {
  headers: { "x-request-id": "aibi-security-check" },
});
const health = await healthResponse.json();
const optionsResponse = await fetch(`${apiBaseUrl}/api/health`, {
  method: "OPTIONS",
  headers: { origin: "https://untrusted.invalid" },
});
const invalidJsonResponse = await fetch(`${apiBaseUrl}/api/agent/ask`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: "{invalid",
});
const invalidJson = await invalidJsonResponse.json();
const oversizedResponse = await fetch(`${apiBaseUrl}/api/agent/ask`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ prompt: "x".repeat(1_100_000) }),
});
const oversized = await oversizedResponse.json();

const checks = [
  check("health-readable", healthResponse.ok && health.ok === true, { status: healthResponse.status }),
  check("request-id-preserved", healthResponse.headers.get("x-request-id") === "aibi-security-check", healthResponse.headers.get("x-request-id")),
  check("security-headers-present", healthResponse.headers.get("x-content-type-options") === "nosniff" && healthResponse.headers.get("x-frame-options") === "DENY" && healthResponse.headers.get("referrer-policy") === "no-referrer", Object.fromEntries(["x-content-type-options", "x-frame-options", "referrer-policy"].map((name) => [name, healthResponse.headers.get(name)]))),
  check("cors-disabled-by-default", !healthResponse.headers.get("access-control-allow-origin") && !optionsResponse.headers.get("access-control-allow-origin"), { get: healthResponse.headers.get("access-control-allow-origin"), options: optionsResponse.headers.get("access-control-allow-origin") }),
  check("invalid-json-rejected", invalidJsonResponse.status === 400 && String(invalidJson.error ?? "").includes("valid JSON"), { status: invalidJsonResponse.status, error: invalidJson.error }),
  check("oversized-body-rejected", oversizedResponse.status === 413 && String(oversized.error ?? "").includes("exceeds"), { status: oversizedResponse.status, error: oversized.error }),
];

const failedChecks = checks.filter((item) => !item.ok);
const receipt = {
  ok: failedChecks.length === 0,
  schema: "aibi-server-runtime-security/v1",
  generatedBy: "scripts/verify-server-runtime-security.mjs",
  apiBaseUrl,
  checks,
  failedChecks,
};

console.log(JSON.stringify(receipt, null, 2));
if (failedChecks.length) process.exitCode = 1;
