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
      <summary>{biText("行业场景包 Beta", "Industry scenario packs beta")}</summary>
      <section className="scenarioPackPanel">
        <div className="scenarioPackLead">
          <span className="storyMode"><Bilingual zh="一句话到结果" en="Prompt to result" /></span>
          <h3><Bilingual zh="选择一个业务场景，系统负责检查、起草和留证" en="Choose a business scenario; the system checks, drafts, and cites" /></h3>
          <p>
            <Bilingual
              zh="场景包把字段、指标、模板和证据要求打包好。用户只选业务目标，写入仍会停在草案确认。"
              en="Scenario packs bundle fields, metrics, templates, and evidence needs. Users pick the business goal; writes still stop at draft approval."
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
                  {biText("起草方案", "Draft plan")}
                </button>
                <button className="miniButton" disabled={!pack.template || busy === "dashboardDraft"} onClick={() => onPreviewScenarioTemplate(pack)} type="button">
                  <Icon name="dashboard" />
                  {biText("预演模板", "Preview template")}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </details>
  );
}
