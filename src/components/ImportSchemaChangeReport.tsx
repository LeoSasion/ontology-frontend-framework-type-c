import { useState } from "react";
import type { ImportSchemaChangeImpactItem, ImportSchemaChangePreview } from "../types";
import { biText } from "./Bilingual";
import "./importSchemaChangeReport.css";

type ImportSchemaChangeReportProps = {
  acknowledged: boolean;
  change: ImportSchemaChangePreview;
  onAcknowledgedChange: (value: boolean) => void;
};

const impactGroups: Array<{
  key: keyof Pick<ImportSchemaChangePreview["impact"], "relationships" | "metrics" | "calculatedFields" | "savedViews" | "dashboardWidgets" | "fieldSemantics">;
  zh: string;
  en: string;
}> = [
  { key: "relationships", zh: "关系", en: "Relationships" },
  { key: "metrics", zh: "指标", en: "Metrics" },
  { key: "calculatedFields", zh: "计算字段", en: "Calculated fields" },
  { key: "savedViews", zh: "保存视图", en: "Saved views" },
  { key: "dashboardWidgets", zh: "看板组件", en: "Dashboard widgets" },
  { key: "fieldSemantics", zh: "字段语义", en: "Field semantics" },
];

function FieldList({ fields, emptyText, label }: { fields: string[]; emptyText: string; label: string }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? fields : fields.slice(0, 8);
  return fields.length ? (
    <div className="schemaChangeListBlock">
      <div className="schemaChangeFieldList">
        {visible.map((field) => <span key={field}>{field}</span>)}
      </div>
      {fields.length > 8 ? (
        <button className="miniButton schemaChangeToggle" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)} type="button">
          {expanded
            ? biText("收起字段", "Show fewer fields")
            : biText(`查看全部 ${fields.length} 个字段`, `View all ${fields.length} fields`)}
          <span className="srOnly"> · {label}</span>
        </button>
      ) : null}
    </div>
  ) : <small className="schemaChangeEmpty">{emptyText}</small>;
}

function ImpactList({ groupKey, items }: { groupKey: string; items: ImportSchemaChangeImpactItem[] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? items : items.slice(0, 4);
  return (
    <div className="schemaChangeListBlock">
      <ul>
        {visible.map((item) => (
          <li key={item.key}>
            <strong>{item.label}</strong>
            <span>{item.fields.join("、")}</span>
          </li>
        ))}
      </ul>
      {items.length > 4 ? (
        <button
          aria-expanded={expanded}
          className="miniButton schemaChangeToggle"
          data-testid={`schema-change-impact-toggle-${groupKey}`}
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
          {expanded
            ? biText("收起清单", "Show fewer items")
            : biText(`查看全部 ${items.length} 项`, `View all ${items.length} items`)}
        </button>
      ) : null}
    </div>
  );
}

function downloadImpact(change: ImportSchemaChangePreview) {
  const payload = {
    schema: "aibi-import-schema-change-impact-export/v1",
    targetTableKey: change.targetTableKey,
    targetDisplayName: change.targetDisplayName,
    fingerprint: change.impact.fingerprint,
    fields: {
      current: change.currentFields,
      incoming: change.incomingFields,
      added: change.addedFields,
      removed: change.removedFields,
      retained: change.retainedFields,
      orderChanged: change.orderChanged,
    },
    impact: {
      relationships: change.impact.relationships,
      metrics: change.impact.metrics,
      calculatedFields: change.impact.calculatedFields,
      savedViews: change.impact.savedViews,
      dashboardWidgets: change.impact.dashboardWidgets,
      fieldSemantics: change.impact.fieldSemantics,
      totalDependencies: change.impact.totalDependencies,
    },
  };
  const fileName = `${change.targetTableKey || "table"}`.replace(/[^a-z0-9_-]+/gi, "-");
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${fileName || "table"}-schema-impact.json`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export default function ImportSchemaChangeReport({
  acknowledged,
  change,
  onAcknowledgedChange,
}: ImportSchemaChangeReportProps) {
  const populatedImpacts = impactGroups.filter((group) => change.impact[group.key].length > 0);
  return (
    <section className="schemaChangeReport" aria-labelledby="schema-change-title" data-testid="import-schema-change-report" role="region">
      <div className="schemaChangeLead">
        <span className="statusBadge warn">{biText("已暂停写入", "Write paused")}</span>
        <div>
          <h4 id="schema-change-title">{biText("替换整表会改变字段结构", "Replacing the table changes its schema")}</h4>
          <p>{biText(
            `系统已逐字段比较“${change.targetDisplayName || change.targetTableKey}”。先核对变化和依赖，再决定是否继续。`,
            `Fields were compared for “${change.targetDisplayName || change.targetTableKey}”. Review the changes and dependencies before continuing.`,
          )}</p>
        </div>
      </div>
      <div className="schemaChangeMetrics" aria-label={biText("字段变化概况", "Schema change summary")}>
        <article className="added"><span>{biText("新增", "Added")}</span><strong>{change.addedFields.length}</strong><small>{biText("个字段", "fields")}</small></article>
        <article className="removed"><span>{biText("移除", "Removed")}</span><strong>{change.removedFields.length}</strong><small>{biText("个字段", "fields")}</small></article>
        <article><span>{biText("保留", "Retained")}</span><strong>{change.retainedFields.length}</strong><small>{biText("个字段", "fields")}</small></article>
        <article><span>{biText("受影响依赖", "Affected dependencies")}</span><strong>{change.impact.totalDependencies}</strong><small>{biText("项", "items")}</small></article>
      </div>
      <div className="schemaChangeColumns">
        <article className="added">
          <strong>{biText("新文件新增", "Added by the new file")}</strong>
          <FieldList fields={change.addedFields} emptyText={biText("没有新增字段", "No added fields")} label={biText("新增字段", "Added fields")} />
        </article>
        <article className="removed">
          <strong>{biText("替换后移除", "Removed after replacement")}</strong>
          <FieldList fields={change.removedFields} emptyText={biText("没有移除字段", "No removed fields")} label={biText("移除字段", "Removed fields")} />
        </article>
      </div>
      {change.orderChanged ? <p className="schemaChangeOrder" role="status">{biText("字段顺序也会按新文件更新。", "Field order will also follow the new file.")}</p> : null}
      <div className="schemaChangeDependencies">
        <div className="schemaChangeDependencyHeader">
          <strong>{biText("下游影响", "Downstream impact")}</strong>
          <button className="miniButton" data-testid="schema-change-impact-download" onClick={() => downloadImpact(change)} type="button">
            {biText("下载完整影响清单", "Download complete impact list")}
          </button>
        </div>
        {populatedImpacts.length ? (
          <>
            <p>{biText("这些对象引用了将被移除的字段；替换后需重新校验，后续查询或验证会阻断不再成立的配置。", "These objects reference fields that will be removed. Revalidate them after replacement; later queries or validation block invalid configurations.")}</p>
            <div className="schemaChangeImpactGroups">
              {populatedImpacts.map((group) => (
                <article key={group.key}>
                  <span>{biText(group.zh, group.en)} · {change.impact[group.key].length}</span>
                  <ImpactList groupKey={group.key} items={change.impact[group.key]} />
                </article>
              ))}
            </div>
            {change.impact.truncated ? <small role="alert">{biText("影响清单不完整，不能在此页面确认；请重新检查来源。", "The impact list is incomplete and cannot be confirmed here. Check the source again.")}</small> : null}
          </>
        ) : <p>{biText("未发现引用被移除字段的已保存对象；字段结构本身仍需确认。", "No saved object references a removed field; the schema change still requires confirmation.")}</p>}
      </div>
      <label className="schemaChangeAcknowledgement">
        <input checked={acknowledged} disabled={change.impact.truncated} onChange={(event) => onAcknowledgedChange(event.currentTarget.checked)} type="checkbox" />
        <span>{biText("我已核对字段变化，并理解清单中的下游对象会在替换后重新校验。", "I reviewed the field changes and understand that the listed downstream objects will be revalidated after replacement.")}</span>
      </label>
      <p className="schemaChangeBoundary">{biText("未勾选不会创建持久导入任务；来源、规则或依赖变化后必须重新预演。", "No durable import job is created until acknowledged; source, rule, or dependency changes require a fresh preview.")}</p>
    </section>
  );
}
