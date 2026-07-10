import { lazy } from "react";

const loadAdvancedPanels = () => import("./components/SourceWorkbenchAdvancedPanels");

export const SourceWorkbenchConnectorPanel = lazy(() => loadAdvancedPanels().then((module) => ({ default: module.SourceWorkbenchConnectorPanel })));
export const SourceWorkbenchFieldMetricPanel = lazy(() => loadAdvancedPanels().then((module) => ({ default: module.SourceWorkbenchFieldMetricPanel })));
export const SourceWorkbenchOperationsPanel = lazy(() => loadAdvancedPanels().then((module) => ({ default: module.SourceWorkbenchOperationsPanel })));
export const SourceWorkbenchQueryFormulaPanel = lazy(() => loadAdvancedPanels().then((module) => ({ default: module.SourceWorkbenchQueryFormulaPanel })));
export const SourceWorkbenchRelationshipPanel = lazy(() => loadAdvancedPanels().then((module) => ({ default: module.SourceWorkbenchRelationshipPanel })));

export function SourceWorkbenchAdvancedLoading() {
  return (
    <div className="workbenchPanel widePanel moduleSkeleton" data-testid="source-advanced-loading" aria-busy="true" aria-label="Loading advanced source configuration">
      <span />
      <span />
      <span />
    </div>
  );
}
