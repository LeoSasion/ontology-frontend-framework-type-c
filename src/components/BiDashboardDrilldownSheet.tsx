import type { BiDashboardFilterRule, BiDashboardWidget } from "../biDashboardModel";
import type { TableQueryPayload } from "../types";
import { biText } from "./Bilingual";

export type DrilldownPointFilter = {
  field: string;
  value: string;
};

export type DrilldownState = {
  widget: BiDashboardWidget;
  pointFilter?: DrilldownPointFilter;
};

export type BiDrilldownRequest = {
  table: string;
  view?: string;
  mode: "detail";
  columns: string[];
  filters: Array<Pick<BiDashboardFilterRule, "field" | "operator" | "value">>;
  search: string;
  sort: Array<{ field: string; direction?: string }>;
  limit: number;
};

export type DrilldownOperationReceipt = {
  title: string;
  detail: string;
  nextStep: string;
  technical: string;
  tone: "ok" | "warn";
};

type BiDashboardDrilldownSheetProps = {
  drilldown: DrilldownState;
  drilldownRequest: BiDrilldownRequest | null;
  drilldownSearch: string;
  drilldownResult: TableQueryPayload | null;
  drilldownBusy: boolean;
  drilldownSaveResult: Record<string, unknown> | null;
  drilldownReceipt: DrilldownOperationReceipt | null;
  onSearchChange: (value: string) => void;
  onSaveView: (confirm: boolean) => Promise<void>;
  onClose: () => void;
};

export function BiDashboardDrilldownSheet({
  drilldown,
  drilldownRequest,
  drilldownSearch,
  drilldownResult,
  drilldownBusy,
  drilldownSaveResult,
  drilldownReceipt,
  onSearchChange,
  onSaveView,
  onClose,
}: BiDashboardDrilldownSheetProps) {
  const columns = drilldownResult?.tableQuery?.columns ?? drilldownRequest?.columns ?? [];
  const rows = drilldownResult?.tableQuery?.rows ?? [];
  const matchedRows = drilldownResult?.tableQuery?.filteredRows ?? 0;
  const filterCount = drilldownRequest?.filters.length ?? 0;

  return (
    <section className="bDrilldownSheet" data-testid="b-drilldown-sheet" aria-label={biText("组件明细下钻", "Widget drilldown detail")}>
      <div className="bDrilldownHeader">
        <div>
          <span>{biText("明细下钻", "Drilldown")}</span>
          <h4>{drilldown.widget.title}</h4>
          <p>
            {drilldownRequest?.table ?? "-"}
            {drilldown.pointFilter ? ` · ${drilldown.pointFilter.field} = ${drilldown.pointFilter.value}` : ""}
          </p>
        </div>
        <div className="bDrilldownActions">
          <input
            aria-label={biText("搜索明细", "Search detail")}
            placeholder={biText("搜索明细", "Search detail")}
            value={drilldownSearch}
            onChange={(event) => onSearchChange(event.target.value)}
          />
          <button data-testid="b-drilldown-save-dry-run" disabled={!drilldownRequest} onClick={() => onSaveView(false)} type="button">
            {biText("预演保存视图", "Preview save view")}
          </button>
          <button data-testid="b-drilldown-save-confirm" disabled={!drilldownRequest} onClick={() => onSaveView(true)} type="button">
            {biText("确认保存视图", "Save view")}
          </button>
          <button onClick={onClose} type="button">{biText("关闭", "Close")}</button>
        </div>
      </div>
      <div className="bDrilldownMeta">
        <span>{drilldownBusy ? biText("读取中", "Loading") : biText("已读取", "Loaded")}</span>
        <span>{biText(`${matchedRows} 行匹配`, `${matchedRows} matched rows`)}</span>
        <span>{filterCount ? biText(`${filterCount} 条筛选`, `${filterCount} filters`) : biText("无额外筛选", "No extra filter")}</span>
        {drilldownSaveResult ? <strong>{drilldownSaveResult.confirmed ? biText("可在视图页继续分析", "Ready in Views") : biText("确认前不会创建视图", "No view created before confirmation")}</strong> : null}
      </div>
      {drilldownReceipt ? (
        <div className={`bDrilldownReceipt ${drilldownReceipt.tone}`} data-testid="b-drilldown-operation-receipt">
          <div>
            <strong>{drilldownReceipt.title}</strong>
            <span>{drilldownReceipt.detail}</span>
            <small>{drilldownReceipt.nextStep}</small>
          </div>
          <details data-testid="b-drilldown-technical-details">
            <summary>{biText("查看下钻口径", "View drilldown scope")}</summary>
            <span>{drilldownReceipt.technical}</span>
          </details>
        </div>
      ) : null}
      <div className="bDrilldownTable">
        <table>
          <thead>
            <tr>
              {columns.map((column) => <th key={column}>{column}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}
              </tr>
            ))}
            {!drilldownBusy && !rows.length ? (
              <tr><td colSpan={Math.max(1, columns.length)}>{biText("没有匹配明细", "No matching detail rows")}</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
