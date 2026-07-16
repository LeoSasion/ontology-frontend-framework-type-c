import { readFileSync } from "node:fs";

const read = (path) => readFileSync(path, "utf8");
const answerCard = read("src/components/AgentAnswerCard.tsx");
const panel = read("src/components/ForecastReadinessPanel.tsx");
const api = read("src/apiForecast.ts");
const route = read("server/analysisUnitRoutes.ts");
const types = read("src/typesAgent.ts");
const css = read("src/components/ForecastReadinessPanel.css");

const checks = [
  {
    label: "forecast-panel-is-conditionally-lazy-loaded",
    ok: answerCard.includes('lazy(() => import("./ForecastReadinessPanel")')
      && answerCard.includes("forecastOpen &&")
      && answerCard.includes('data-testid="forecast-readiness-open"'),
  },
  {
    label: "panel-protects-request-order-and-input-consistency",
    ok: panel.includes("requestRef.current !== requestId")
      && panel.includes("requestRef.current += 1")
      && panel.includes("disabled={busy}")
      && panel.includes("initialReadiness?.fingerprint"),
  },
  {
    label: "visible-copy-states-no-forecast-boundary",
    ok: panel.includes("不生成预测或未来数值")
      && panel.includes("Provider 未参与")
      && panel.includes("输入业务行也未进入响应")
      && !panel.includes("readiness.rows")
      && !panel.includes("futureValues"),
  },
  {
    label: "typed-api-calls-workspace-scoped-server-route",
    ok: api.includes("ForecastReadinessPayload")
      && api.includes("readyForEvaluation?: boolean")
      && api.includes("/api/forecast-readiness?")
      && route.includes('url.pathname === "/api/forecast-readiness"')
      && route.includes('cli(["forecast-readiness", "--unit", unit, "--horizon", horizon])'),
  },
  {
    label: "public-contract-has-fixed-safety-flags",
    ok: types.includes("canGenerateForecast: false")
      && types.includes("forecastGenerated: false")
      && types.includes("providerUsed: false")
      && types.includes("rawBusinessRowsExposed: 0"),
  },
  {
    label: "panel-has-narrow-screen-layout",
    ok: css.includes("@media (max-width: 720px)")
      && css.includes("grid-template-columns: repeat(auto-fit")
      && css.includes("grid-column: 1 / -1"),
  },
];

const failedChecks = checks.filter((check) => !check.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-forecast-readiness-ui-verify/v1",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
