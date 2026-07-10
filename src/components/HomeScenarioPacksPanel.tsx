import type { ScenarioPack } from "../productIntelligenceModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type HomeScenarioPacksPanelProps = {
  busy: string | null;
  scenarioPacks: ScenarioPack[];
  onPreviewScenarioTemplate: (pack: ScenarioPack) => void;
  onRunScenarioPrompt: (pack: ScenarioPack) => void;
};

export function HomeScenarioPacksPanel({ busy, scenarioPacks, onPreviewScenarioTemplate, onRunScenarioPrompt }: HomeScenarioPacksPanelProps) {
  return (
    <details className="advancedDetails scenarioPackDetails" data-testid="home-scenario-packs">
      <summary>{biText("证据看板 Beta", "Evidence dashboard beta")}</summary>
      <section className="scenarioPackPanel">
        <div className="scenarioPackLead">
          <span className="storyMode"><Bilingual zh="一句话到结果" en="Prompt to result" /></span>
          <h3><Bilingual zh="用已验证分析一次起草整套看板" en="Draft a full dashboard from verified analyses" /></h3>
          <p>
            <Bilingual
              zh="只有查询成功且证据完整的分析才会进入草案；未验证的图表不会默认展示。"
              en="Only analyses with successful queries and complete evidence enter the draft; unverified charts stay hidden."
            />
          </p>
        </div>
        <div className="scenarioPackGrid">
          {scenarioPacks.map((pack) => (
            <article className={`scenarioPackCard ${pack.readiness}`} data-testid={`scenario-pack-${pack.key}`} key={pack.key}>
              <div>
                <span>{pack.readiness === "ok" ? biText("可直接起草", "ready to draft") : pack.readiness === "warn" ? biText("先补数据", "needs data") : biText("可先预演", "preview first")}</span>
                <h4>{pack.title}</h4>
                <p>{pack.detail}</p>
              </div>
              <div className="scenarioPackFacts">
                {pack.facts.map((fact) => <small key={fact}>{fact}</small>)}
              </div>
              <div className="scenarioPackActions">
                <button className="miniButton" disabled={busy === "ask"} onClick={() => onRunScenarioPrompt(pack)} type="button">
                  <Icon name="agent" />
                  {biText("起草整套看板", "Draft full dashboard")}
                </button>
                {pack.template ? <button className="miniButton" disabled={busy === "dashboardDraft"} onClick={() => onPreviewScenarioTemplate(pack)} type="button">
                  <Icon name="dashboard" />
                  {biText("预演模板", "Preview template")}
                </button> : null}
              </div>
            </article>
          ))}
        </div>
      </section>
    </details>
  );
}
