import type { Dispatch, SetStateAction } from "react";
import type { RelationshipSaveOptions } from "../dashboardCanvasContracts";
import type { FieldConfig } from "../types";
import { biText } from "./Bilingual";

type RelationshipSafetyControlsProps = {
  disabled?: boolean;
  relationshipForm: RelationshipSaveOptions;
  rightFields: FieldConfig[];
  setRelationshipForm: Dispatch<SetStateAction<RelationshipSaveOptions>>;
};

export default function RelationshipSafetyControls({ disabled = false, relationshipForm, rightFields, setRelationshipForm }: RelationshipSafetyControlsProps) {
  const rightMappings = relationshipForm.fieldMappings?.length
    ? relationshipForm.fieldMappings.map((mapping) => mapping.rightField)
    : [relationshipForm.rightField].filter(Boolean);
  const filter = relationshipForm.filters?.[0];
  const measure = relationshipForm.preaggregation?.measures?.[0];
  return (
    <details className="advancedDetails compactAdvanced relationshipTechnicalDetails" data-testid="relationship-safety-controls">
      <summary>{biText("过滤与预聚合安全策略", "Filter and pre-aggregation safety")}</summary>
      <div className="formGrid">
        <label><span>{biText("右表前置过滤字段", "Right pre-filter field")}</span>
          <select disabled={disabled} value={filter?.field ?? ""} onChange={(event) => setRelationshipForm((current) => ({ ...current, filters: event.target.value ? [{ phase: "pre", side: "right", field: event.target.value, operator: current.filters?.[0]?.operator ?? "eq", value: String(current.filters?.[0]?.value ?? "") }] : [] }))}>
            <option value="">{biText("不使用过滤", "No filter")}</option>{rightFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
          </select>
        </label>
        <label><span>{biText("过滤条件", "Filter operator")}</span>
          <select disabled={disabled || !filter} value={filter?.operator ?? "eq"} onChange={(event) => setRelationshipForm((current) => ({ ...current, filters: current.filters?.length ? [{ ...current.filters[0], operator: event.target.value }] : [] }))}>
            <option value="eq">=</option><option value="neq">≠</option><option value="gt">&gt;</option><option value="gte">≥</option><option value="lt">&lt;</option><option value="lte">≤</option>
          </select>
        </label>
        <label><span>{biText("过滤值", "Filter value")}</span><input disabled={disabled || !filter} value={String(filter?.value ?? "")} onChange={(event) => setRelationshipForm((current) => ({ ...current, filters: current.filters?.length ? [{ ...current.filters[0], value: event.target.value }] : [] }))} /></label>
        <label><span>{biText("右表预聚合指标", "Right pre-aggregation measure")}</span>
          <select disabled={disabled} value={measure?.field ?? ""} onChange={(event) => setRelationshipForm((current) => ({ ...current, preaggregation: event.target.value ? { side: "right", groupFields: rightMappings, measures: [{ field: event.target.value, aggregation: current.preaggregation?.measures?.[0]?.aggregation ?? "sum" }] } : undefined }))}>
            <option value="">{biText("不使用预聚合", "No pre-aggregation")}</option>{rightFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
          </select>
        </label>
        <label><span>{biText("聚合方式", "Aggregation")}</span>
          <select disabled={disabled || !measure} value={measure?.aggregation ?? "sum"} onChange={(event) => setRelationshipForm((current) => current.preaggregation ? ({ ...current, preaggregation: { ...current.preaggregation, measures: current.preaggregation.measures.map((item, index) => index === 0 ? { ...item, aggregation: event.target.value } : item) } }) : current)}>
            <option value="sum">sum</option><option value="avg">avg</option><option value="min">min</option><option value="max">max</option><option value="count">count</option><option value="count-distinct">count-distinct</option>
          </select>
        </label>
      </div>
      <p className="quietText">{biText("前置过滤在连接前生效；预聚合按全部右侧连接键分组，避免一对多放大。", "Pre-filters run before the join; pre-aggregation groups by every right-side join key to prevent inflation.")}</p>
    </details>
  );
}
