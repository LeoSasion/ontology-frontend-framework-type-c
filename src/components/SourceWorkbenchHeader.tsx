import { Bilingual, biText } from "./Bilingual";

type SourceWorkbenchHeaderProps = {
  sourceProfileRunning: boolean;
};

export function SourceWorkbenchHeader({
  sourceProfileRunning,
}: SourceWorkbenchHeaderProps) {
  return (
    <div className="panelHeader">
      <div>
        <p className="kicker">{biText("数据", "Data")}</p>
        <h2 id="source-workbench-title">
          <Bilingual zh="接入并准备数据" en="Connect and prepare data" />
        </h2>
        <p className="panelIntro">
          <Bilingual
            zh="粘贴一个文件或文件夹路径，先看导入影响，再生成可用于分析的证据摘要。字段、公式和关系只在需要时展开。"
            en="Paste a file or folder path, review the import impact, then prepare evidence for analysis. Fields, formulas, and relationships appear only when needed."
          />
        </p>
      </div>
      <div className="buttonRow">
        <span aria-live="polite" className="quietText" role="status">
          {sourceProfileRunning
            ? biText("正在只读生成证据摘要", "Creating a read-only evidence summary")
            : biText("所有写入都会先预检并等待确认", "Every write is previewed and waits for confirmation")}
        </span>
      </div>
    </div>
  );
}
