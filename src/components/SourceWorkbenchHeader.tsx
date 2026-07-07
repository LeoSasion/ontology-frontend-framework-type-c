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
        <p className="kicker">{biText("数据源治理", "Source governance")}</p>
        <h2 id="source-workbench-title">
          <Bilingual zh="原始数据入口" en="Raw data entry" />
        </h2>
        <p className="panelIntro">
          <Bilingual
            zh="先检查文件，再让系统生成证据摘要和看板建议。字段、公式、关系等高级配置默认收起，所有写入仍需确认。"
            en="Check files first, then let the system create an evidence summary and dashboard suggestions. Advanced fields, formulas, and links stay collapsed by default, and writes still require approval."
          />
        </p>
      </div>
      <div className="buttonRow">
        <span className="quietText">
          {sourceProfileRunning
            ? biText("正在只读生成证据摘要", "Creating a read-only evidence summary")
            : biText("先导入或选择本地数据路径", "Import or choose a local data path first")}
        </span>
      </div>
    </div>
  );
}
