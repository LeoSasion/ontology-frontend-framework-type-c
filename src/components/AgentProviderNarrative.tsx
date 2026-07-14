import type { AgentAskResult } from "../types";
import { biText } from "./Bilingual";

type AgentProviderNarrativeProps = {
  response: NonNullable<AgentAskResult["llm"]["response"]>;
};

export function AgentProviderNarrative({ response }: AgentProviderNarrativeProps) {
  return (
    <section className="agentProviderNarrative" data-testid="agent-provider-narrative">
      <div>
        <span className="storyMode">{biText("模型解读", "Model interpretation")}</span>
        <strong>
          {response.certainty === "needs_clarification"
            ? biText("需要补充口径", "Definition needed")
            : biText("基于本地证据解释", "Grounded in local evidence")}
        </strong>
      </div>
      <p>{response.summary}</p>
      {response.rationale.length ? (
        <ul>
          {response.rationale.slice(0, 3).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ul>
      ) : null}
      {response.clarification ? <p className="agentProviderClarification">{response.clarification}</p> : null}
    </section>
  );
}
