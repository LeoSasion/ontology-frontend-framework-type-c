import { lazy } from "react";

const loadWidgetKit = () => import("./components/BiDashboardWidgetKit");

export const BiDashboardWidgetKit = lazy(() => loadWidgetKit().then((module) => ({ default: module.BiDashboardWidgetKit })));
