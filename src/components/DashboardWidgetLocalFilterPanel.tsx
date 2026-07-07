import type { DashboardFilterRule, FieldConfig } from "../types";
import type { DashboardWidgetOperationOptions } from "../dashboardCanvasContracts";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardWidgetLocalFilterPanelProps = {
  busy: string | null;
  draftFields: FieldConfig[];
  filterOperators: readonly string[];
  nextWidgetFilters: Array<{ field: string; operator: string; value?: string }>;
  onWidgetOperation: (label: string, options: DashboardWidgetOperationOptions) => Promise<void>;
  operatorLabel: (operator: string) => string;
  selectedWidgetKey: string;
  setWidgetFilterField: (field: string) => void;
  setWidgetFilterOperator: (operator: string) => void;
  setWidgetFilterValue: (value: string) => void;
  widgetFilterField: string;
  widgetFilterOperator: string;
  widgetFilterValue: string;
  widgetFilters: DashboardFilterRule[];
};

export function DashboardWidgetLocalFilterPanel({
  busy,
  draftFields,
  filterOperators,
  nextWidgetFilters,
  onWidgetOperation,
  operatorLabel,
  selectedWidgetKey,
  setWidgetFilterField,
  setWidgetFilterOperator,
  setWidgetFilterValue,
  widgetFilterField,
  widgetFilterOperator,
  widgetFilterValue,
  widgetFilters,
}: DashboardWidgetLocalFilterPanelProps) {
  return (
    <div className="widgetLocalFilterPanel" data-testid="widget-local-filter-panel">
      <div className="tileHeader compact">
        <h3><Bilingual zh="限定这个组件的数据" en="Limit this widget's data" /></h3>
        <span>{biText(`${widgetFilters.length} 条`, `${widgetFilters.length} rules`)}</span>
      </div>
      <div className="activeFilterRow compactFilters">
        {widgetFilters.length ? widgetFilters.map((filter) => (
          <span className={filter.enabled ? "filterPill" : "filterPill disabled"} key={filter.id}>
            <strong>{filter.field}</strong>
            <em>{operatorLabel(filter.operator)}</em>
            {filter.operator === "empty" || filter.operator === "notEmpty" ? null : <small>{filter.value}</small>}
          </span>
        )) : (
          <p className="emptyFilterHint"><Bilingual zh="这个组件暂未设置局部筛选，会跟随看板全局口径。" en="No local filter. This widget follows the dashboard-wide scope." /></p>
        )}
      </div>
      <div className="widgetFilterComposer">
        <label>
          <span>{biText("字段", "Field")}</span>
          <select value={widgetFilterField} onChange={(event) => setWidgetFilterField(event.target.value)}>
            {draftFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("条件", "Condition")}</span>
          <select value={widgetFilterOperator} onChange={(event) => setWidgetFilterOperator(event.target.value)}>
            {filterOperators.map((operator) => <option key={operator} value={operator}>{operatorLabel(operator)}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("值", "Value")}</span>
          <input
            disabled={widgetFilterOperator === "empty" || widgetFilterOperator === "notEmpty"}
            placeholder={widgetFilterOperator === "between" ? "100,500" : biText("输入筛选值", "Filter value")}
            value={widgetFilterValue}
            onChange={(event) => setWidgetFilterValue(event.target.value)}
          />
        </label>
        <div className="widgetFilterActions">
          <button
            className="secondaryButton"
            data-testid="widget-filter-preview-button"
            disabled={!widgetFilterField || busy === "widget-filter-dry"}
            onClick={() => onWidgetOperation("widget-filter-dry", {
              op: "set",
              widgetKey: selectedWidgetKey,
              filters: nextWidgetFilters,
              confirm: false,
            })}
            type="button"
          >
            <Icon name="evidence" />
            <Bilingual zh="预览筛选" en="Preview filter" />
          </button>
          <button
            className="primaryButton"
            data-testid="widget-filter-apply-button"
            disabled={!widgetFilterField || busy === "widget-filter"}
            onClick={() => onWidgetOperation("widget-filter", {
              op: "set",
              widgetKey: selectedWidgetKey,
              filters: nextWidgetFilters,
              confirm: true,
            })}
            type="button"
          >
            <Icon name="check" />
            <Bilingual zh="添加筛选" en="Add filter" />
          </button>
          <button
            className="miniButton dangerButton"
            data-testid="widget-filter-clear-button"
            disabled={widgetFilters.length === 0 || busy === "widget-filter-clear"}
            onClick={() => onWidgetOperation("widget-filter-clear", {
              op: "set",
              widgetKey: selectedWidgetKey,
              clearFilters: true,
              confirm: true,
            })}
            type="button"
          >
            {biText("清空", "Clear")}
          </button>
        </div>
      </div>
    </div>
  );
}
