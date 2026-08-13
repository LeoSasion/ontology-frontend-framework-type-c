import { lazy, Suspense, useState } from "react";
import { biText } from "./Bilingual";
import { loadDecisionFrameworkEditor } from "./decisionFrameworkLoader";
import "./decisionFramework.css";

const DecisionFrameworkEditor = lazy(() => loadDecisionFrameworkEditor().then((module) => ({ default: module.DecisionFrameworkEditor })));

export function DecisionFrameworkEntry({ unitKey }: { unitKey: string }) {
  const [open, setOpen] = useState(false);

  return (
    <section className="decisionFrameworkEntry" data-testid="decision-framework-entry">
      <div>
        <span>{biText("可选决策视图", "Optional decision view")}</span>
        <strong>{biText("把当前证据整理成 SWOT 或流程", "Organize current evidence as SWOT or a process")}</strong>
        <small>{biText("系统只给出结构和已执行证据候选；判断与假设由你明确标注。", "The system provides only structure and executed-evidence candidates; you label judgments and hypotheses explicitly.")}</small>
      </div>
      <button
        className="miniButton secondary"
        onClick={() => setOpen((current) => !current)}
        onFocus={() => { void loadDecisionFrameworkEditor(); }}
        onMouseEnter={() => { void loadDecisionFrameworkEditor(); }}
        type="button"
      >
        {open ? biText("收起决策框架", "Close decision framework") : biText("打开决策框架", "Open decision framework")}
      </button>
      {open ? (
        <Suspense fallback={<p role="status">{biText("正在加载决策框架…", "Loading decision framework…")}</p>}>
          <DecisionFrameworkEditor unitKey={unitKey} />
        </Suspense>
      ) : null}
    </section>
  );
}
