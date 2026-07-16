import { useEffect, useRef, useState } from "react";
import { getForecastReadiness } from "../apiForecast";
import type { ForecastReadiness } from "../types";
import { biText } from "./Bilingual";
import "./ForecastReadinessPanel.css";

type ForecastReadinessPanelProps = {
  unitKey: string;
  initialReadiness?: ForecastReadiness;
};

const gateLabels: Record<string, string> = {
  source: biText("来源", "Source"),
  sample: biText("样本", "Sample"),
  cadence: biText("时间节奏", "Cadence"),
  stability: biText("稳定性", "Stability"),
  leakage: biText("泄漏防护", "Leakage"),
  assumptions: biText("假设", "Assumptions"),
  explainability: biText("可解释性", "Explainability"),
};

export function ForecastReadinessPanel({ unitKey, initialReadiness }: ForecastReadinessPanelProps) {
  const [horizon, setHorizon] = useState(initialReadiness?.horizon ?? 1);
  const [readiness, setReadiness] = useState<ForecastReadiness | null>(initialReadiness ?? null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const requestRef = useRef(0);

  useEffect(() => {
    requestRef.current += 1;
    setHorizon(initialReadiness?.horizon ?? 1);
    setReadiness(initialReadiness ?? null);
    setMessage("");
  }, [initialReadiness?.fingerprint, unitKey]);

  useEffect(() => () => { requestRef.current += 1; }, []);

  async function assess() {
    const requestId = ++requestRef.current;
    setBusy(true);
    setMessage("");
    const payload = await getForecastReadiness(unitKey, horizon);
    if (requestRef.current !== requestId) return;
    if (payload.forecastReadiness) {
      setReadiness(payload.forecastReadiness);
    } else {
      setMessage(payload.error || biText("无法完成准备度检查。", "Readiness assessment failed."));
    }
    setBusy(false);
  }

  return (
    <section className="forecastReadinessPanel" data-testid="forecast-readiness-panel">
      <div className="forecastReadinessLead">
        <div>
          <span>{biText("只读门禁", "Read-only gate")}</span>
          <strong>{biText("预测准备度", "Forecast readiness")}</strong>
          <small>{biText("只判断能否进入有界评测，不生成预测或未来数值。", "Checks readiness for bounded evaluation; never generates a forecast or future values.")}</small>
        </div>
        <label>
          <span>{biText("预测跨度", "Horizon")}</span>
          <input disabled={busy} max="24" min="1" onChange={(event) => setHorizon(Math.max(1, Math.min(24, Number(event.target.value) || 1)))} type="number" value={horizon} />
        </label>
        <button className="miniButton" disabled={busy} onClick={() => void assess()} type="button">
          {busy ? biText("检查中…", "Checking…") : biText("检查准备度", "Check readiness")}
        </button>
      </div>
      {readiness ? (
        <>
          <div className={`forecastReadinessStatus ${readiness.status === "ready-for-evaluation" ? "ready" : "blocked"}`}>
            <strong>{readiness.status === "ready-for-evaluation" ? biText("可进入受限评测", "Ready for bounded evaluation") : biText("暂不适合进入评测", "Not ready for evaluation")}</strong>
            <span>{readiness.nextAction}</span>
            <small>{readiness.fingerprint.slice(0, 16)}</small>
          </div>
          <div className="forecastReadinessGates" data-testid="forecast-readiness-gates">
            {readiness.gates.map((gate) => (
              <article className={gate.status} key={gate.key}>
                <span>{gateLabels[gate.key] ?? gate.key}</span>
                <strong>{gate.status === "passed" ? biText("通过", "Passed") : biText("阻断", "Blocked")}</strong>
                <small>{gate.summary}</small>
                {gate.blockers.length ? <em>{gate.blockers.join(" · ")}</em> : null}
              </article>
            ))}
          </div>
          <p className="forecastReadinessBoundary">{biText("本次没有生成预测；Provider 未参与，输入业务行也未进入响应。", "No forecast was generated; no Provider or input business rows entered this response.")}</p>
        </>
      ) : null}
      {message ? <p className="forecastReadinessMessage" role="status">{message}</p> : null}
    </section>
  );
}
