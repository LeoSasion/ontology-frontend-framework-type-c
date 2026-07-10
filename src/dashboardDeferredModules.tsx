import { lazy, Suspense, type ReactNode } from "react";

const loadDeferredPanels = () => import("./components/DashboardDeferredPanels");

export const DashboardAdvancedWidgetWorkbench = lazy(() => loadDeferredPanels().then((module) => ({ default: module.DashboardAdvancedWidgetWorkbench })));
export const DashboardBeginnerEditor = lazy(() => loadDeferredPanels().then((module) => ({ default: module.DashboardBeginnerEditor })));
export const DashboardContractBoundaryPanel = lazy(() => loadDeferredPanels().then((module) => ({ default: module.DashboardContractBoundaryPanel })));
export const DashboardFilterWorkbench = lazy(() => loadDeferredPanels().then((module) => ({ default: module.DashboardFilterWorkbench })));
export const DashboardPageAdminPanel = lazy(() => loadDeferredPanels().then((module) => ({ default: module.DashboardPageAdminPanel })));

export function DashboardDeferredLoading() {
  return (
    <div className="moduleSkeleton" data-testid="dashboard-deferred-loading" aria-busy="true" aria-label="Loading dashboard editor">
      <span />
      <span />
      <span />
    </div>
  );
}

export function DashboardDeferredBoundary({ children }: { children: ReactNode }) {
  return <Suspense fallback={<DashboardDeferredLoading />}>{children}</Suspense>;
}
