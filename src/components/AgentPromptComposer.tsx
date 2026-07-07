import type { Dispatch, SetStateAction } from "react";
import { biText } from "./Bilingual";
import { Icon } from "./Icons";

type AgentPromptComposerProps = {
  isAsking: boolean;
  prompt: string;
  setPrompt: Dispatch<SetStateAction<string>>;
  setPromptTouched: Dispatch<SetStateAction<boolean>>;
  submit: () => Promise<void>;
};

export function AgentPromptComposer({ isAsking, prompt, setPrompt, setPromptTouched, submit }: AgentPromptComposerProps) {
  return (
    <div className="agentComposer" data-testid="agent-prompt-composer">
      <textarea
        aria-label={biText("Agent 提问", "Agent prompt")}
        value={prompt}
        onChange={(event) => {
          setPromptTouched(true);
          setPrompt(event.target.value);
        }}
      />
      <button className="primaryButton" disabled={isAsking} onClick={() => void submit()} type="button">
        <Icon name="agent" />
        {isAsking ? biText("规划中", "Planning") : biText("提问", "Ask")}
      </button>
    </div>
  );
}
