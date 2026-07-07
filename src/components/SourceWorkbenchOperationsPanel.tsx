import type { Dispatch, SetStateAction } from "react";
import { Bilingual, biText } from "./Bilingual";

type NavigationModule = {
  moduleKey: string;
  name: string;
  type: string;
  sort: number;
  tableKey?: string;
  dashboardKey?: string;
};

type SourceWorkbenchOperationsPanelProps = {
  busy: string | null;
  navigationModules: NavigationModule[];
  activeNavigationModule?: NavigationModule;
  navigationModuleKey: string;
  navigationName: string;
  navigationSort: string;
  navigationResult: Record<string, unknown> | null;
  setNavigationModuleKey: Dispatch<SetStateAction<string>>;
  setNavigationName: Dispatch<SetStateAction<string>>;
  setNavigationSort: Dispatch<SetStateAction<string>>;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  runNavigationOperation: (op: "rename" | "move" | "hide" | "show", confirm?: boolean) => Promise<void>;
};

export function SourceWorkbenchOperationsPanel({
  busy,
  navigationModules,
  activeNavigationModule,
  navigationModuleKey,
  navigationName,
  navigationSort,
  navigationResult,
  setNavigationModuleKey,
  setNavigationName,
  setNavigationSort,
  runBusy,
  runNavigationOperation,
}: SourceWorkbenchOperationsPanelProps) {
  return (
      <article className="workbenchPanel" data-testid="navigation-module-workbench">
        <div className="tileHeader">
          <h3><Bilingual zh="整理左侧入口" en="Organize sidebar entries" /></h3>
          <span>{navigationModules.length}</span>
        </div>
        <p className="quietText">
          {biText("只调整用户看到的入口名称、顺序和显示状态；预览不会直接改动工作区。", "Only adjust the entry name, order, and visibility that users see. Preview does not change the workspace.")}
        </p>
        <div className="formGrid oneCol">
          <label>
            <span>{biText("要整理的入口", "Entry to organize")}</span>
            <select value={activeNavigationModule?.moduleKey ?? navigationModuleKey} onChange={(event) => setNavigationModuleKey(event.target.value)}>
              {navigationModules.map((module) => (
                <option key={module.moduleKey} value={module.moduleKey}>
                  {module.name} · {module.type}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{biText("入口名称", "Entry name")}</span>
            <input value={navigationName} onChange={(event) => setNavigationName(event.target.value)} />
          </label>
        </div>
        <details className="advancedDetails compactAdvanced navigationTechnicalDetails" data-testid="navigation-technical-details">
          <summary>{biText("页面显示和顺序", "Page display and order")}</summary>
          <div className="formGrid oneCol">
            <label>
              <span>{biText("显示顺序", "Display order")}</span>
              <input inputMode="numeric" value={navigationSort} onChange={(event) => setNavigationSort(event.target.value)} />
            </label>
          </div>
          <div className="formulaMeta">
            <span>{biText("类型", "Type")}: {activeNavigationModule?.type ?? "-"}</span>
            <span>{biText("目标", "Target")}: {activeNavigationModule?.tableKey || activeNavigationModule?.dashboardKey || "-"}</span>
          </div>
        </details>
        <div className="navigationActionGrid" data-testid="navigation-action-grid">
          <button className="miniButton" data-testid="navigation-rename-dry-run" disabled={busy === "navigation-rename-dry"} onClick={() => runBusy("navigation-rename-dry", () => runNavigationOperation("rename", false))} type="button">
            {biText("预览改名", "Preview rename")}
          </button>
          <button className="miniButton" data-testid="navigation-rename-confirm" disabled={busy === "navigation-rename"} onClick={() => runBusy("navigation-rename", () => runNavigationOperation("rename", true))} type="button">
            {biText("确认改名", "Confirm rename")}
          </button>
          <button className="miniButton" data-testid="navigation-move-dry-run" disabled={busy === "navigation-move-dry"} onClick={() => runBusy("navigation-move-dry", () => runNavigationOperation("move", false))} type="button">
            {biText("预览排序", "Preview order")}
          </button>
          <button className="miniButton" data-testid="navigation-move-confirm" disabled={busy === "navigation-move"} onClick={() => runBusy("navigation-move", () => runNavigationOperation("move", true))} type="button">
            {biText("确认排序", "Confirm order")}
          </button>
          <button className="miniButton" data-testid="navigation-hide-dry-run" disabled={busy === "navigation-hide-dry"} onClick={() => runBusy("navigation-hide-dry", () => runNavigationOperation("hide", false))} type="button">
            {biText("预览隐藏", "Preview hide")}
          </button>
          <button className="miniButton" data-testid="navigation-hide-confirm" disabled={busy === "navigation-hide"} onClick={() => runBusy("navigation-hide", () => runNavigationOperation("hide", true))} type="button">
            {biText("确认隐藏", "Confirm hide")}
          </button>
          <button className="miniButton" data-testid="navigation-show-dry-run" disabled={busy === "navigation-show-dry"} onClick={() => runBusy("navigation-show-dry", () => runNavigationOperation("show", false))} type="button">
            {biText("预览恢复", "Preview show")}
          </button>
          <button className="miniButton" data-testid="navigation-show-confirm" disabled={busy === "navigation-show"} onClick={() => runBusy("navigation-show", () => runNavigationOperation("show", true))} type="button">
            {biText("确认恢复", "Confirm show")}
          </button>
        </div>
        <div className="formulaMeta">
          {navigationResult?.requiresConfirmation ? <strong>{biText("入口改动预览已生成", "Entry change preview ready")}</strong> : null}
          {navigationResult?.confirmed ? <strong>{biText("左侧入口已更新", "Sidebar entry updated")}</strong> : null}
        </div>
      </article>
  );
}
