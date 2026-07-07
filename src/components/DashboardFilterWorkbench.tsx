import type { DashboardFilterRule, FieldConfig } from "../types";
import type { DashboardFilterOperationOptions } from "../dashboardCanvasContracts";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardFilterWorkbenchProps = {
  availableFilterFields: FieldConfig[];
  busy: string | null;
  dashboardFilters: DashboardFilterRule[];
  dashboardKey: string;
  filterField: string;
  filterOperator: string;
  filterOperators: readonly string[];
  filterValue: string;
  onFilterFieldChange: (field: string) => void;
  onFilterOperation: (label: string, options: DashboardFilterOperationOptions) => Promise<void>;
  onFilterOperatorChange: (operator: string) => void;
  onFilterValueChange: (value: string) => void;
  operatorLabel: (operator: string) => string;
};

export function DashboardFilterWorkbench({
  availableFilterFields,
  busy,
  dashboardFilters,
  dashboardKey,
  filterField,
  filterOperator,
  filterOperators,
  filterValue,
  onFilterFieldChange,
  onFilterOperation,
  onFilterOperatorChange,
  onFilterValueChange,
  operatorLabel,
}: DashboardFilterWorkbenchProps) {
  return (
    <details className="dashboardFilterWorkbench wide" aria-label={biText("看板筛选", "Dashboard filters")}>
      <summary>{biText("按需调整全局筛选", "Adjust global filters when needed")}</summary>
      <div className="dashboardFilterWorkbenchBody">
        <div className="filterWorkbenchHeader">
          <div>
            <span className="storyMode"><Bilingual zh="工作台筛选" en="Workbench filters" /></span>
            <h3><Bilingual zh="当前看板全局筛选" en="Global filters for this dashboard" /></h3>
          </div>
          <div className="filterWorkbenchActions">
            <button
              className="miniButton"
              data-testid="dashboard-filter-clear"
              disabled={busy === "clear-filter" || dashboardFilters.length === 0}
              onClick={() => onFilterOperation("clear-filter", { op: "clear", dashboardKey, confirm: true })}
              type="button"
            >
              {biText("清空", "Clear")}
            </button>
            <button
              className="miniButton"
              data-testid="dashboard-filter-stale-preview"
              disabled={busy === "remove-stale-filter-dry" || dashboardFilters.length === 0}
              onClick={() => onFilterOperation("remove-stale-filter-dry", { op: "removeStale", dashboardKey, confirm: false })}
              type="button"
            >
              {biText("预检失效", "Preview stale")}
            </button>
            <button
              className="miniButton"
              data-testid="dashboard-filter-stale-remove"
              disabled={busy === "remove-stale-filter" || dashboardFilters.length === 0}
              onClick={() => onFilterOperation("remove-stale-filter", { op: "removeStale", dashboardKey, confirm: true })}
              type="button"
            >
              {biText("清理失效", "Remove stale")}
            </button>
          </div>
        </div>
        <div className="activeFilterRow">
          {dashboardFilters.length ? dashboardFilters.map((filter) => (
            <span className={filter.enabled ? "filterPill" : "filterPill disabled"} key={filter.id}>
              <strong>{filter.field}</strong>
              <em>{operatorLabel(filter.operator)}</em>
              {filter.operator === "empty" || filter.operator === "notEmpty" ? null : <small>{filter.value}</small>}
              <button
                aria-label={biText(`移除 ${filter.field} 筛选`, `Remove ${filter.field} filter`)}
                disabled={busy === `remove-${filter.id}`}
                onClick={() => onFilterOperation(`remove-${filter.id}`, { op: "remove", dashboardKey, filterId: filter.id, confirm: true })}
                type="button"
              >
                x
              </button>
            </span>
          )) : (
            <p className="emptyFilterHint">
              <Bilingual zh="暂无筛选。添加一个条件后，规则会写入当前看板元数据，后续可由 Agent 和组件共同读取。" en="No filters yet. Add one condition and it will be stored in this dashboard metadata for Agent and widgets." />
            </p>
          )}
        </div>
        <div className="filterComposer">
          <label>
            <span>{biText("字段", "Field")}</span>
            <select value={filterField} onChange={(event) => onFilterFieldChange(event.target.value)}>
              {availableFilterFields.map((field) => (
                <option key={field.field_name} value={field.field_name}>{field.field_name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>{biText("条件", "Condition")}</span>
            <select value={filterOperator} onChange={(event) => onFilterOperatorChange(event.target.value)}>
              {filterOperators.map((operator) => (
                <option key={operator} value={operator}>{operatorLabel(operator)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>{biText("值", "Value")}</span>
            <input
              disabled={filterOperator === "empty" || filterOperator === "notEmpty"}
              placeholder={filterOperator === "between" ? "100,500" : biText("输入筛选值", "Filter value")}
              value={filterValue}
              onChange={(event) => onFilterValueChange(event.target.value)}
            />
          </label>
          <div className="filterComposerActions">
            <button
              className="secondaryButton"
              data-testid="dashboard-filter-preview"
              disabled={!filterField || busy === "add-filter-dry"}
              onClick={() => onFilterOperation("add-filter-dry", { op: "add", dashboardKey, field: filterField, operator: filterOperator, value: filterValue, confirm: false })}
              type="button"
            >
              <Icon name="evidence" />
              <Bilingual zh="预检" en="Preview" />
            </button>
            <button
              className="primaryButton"
              data-testid="dashboard-filter-apply"
              disabled={!filterField || busy === "add-filter"}
              onClick={() => onFilterOperation("add-filter", { op: "add", dashboardKey, field: filterField, operator: filterOperator, value: filterValue, confirm: true })}
              type="button"
            >
              <Icon name="check" />
              <Bilingual zh="确认应用" en="Apply" />
            </button>
          </div>
        </div>
      </div>
    </details>
  );
}
