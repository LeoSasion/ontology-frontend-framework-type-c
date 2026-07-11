import { lazy } from "react";

const loadSidebarAssetSections = () => import("./components/SidebarAssetSections");

export const SidebarAssetSections = lazy(() => loadSidebarAssetSections().then((module) => ({ default: module.SidebarAssetSections })));
