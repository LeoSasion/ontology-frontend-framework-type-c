import { lazy } from "react";

const loadActionPanel = () => import("./components/SourceWorkbenchActionPanel");
const loadDataEntryPanel = () => import("./components/SourceWorkbenchDataEntryPanel");
const loadDataManagementPanel = () => import("./components/SourceWorkbenchDataManagementPanel");

export const SourceWorkbenchActionPanel = lazy(() => loadActionPanel().then((module) => ({ default: module.SourceWorkbenchActionPanel })));
export const SourceWorkbenchDataEntryPanel = lazy(() => loadDataEntryPanel().then((module) => ({ default: module.SourceWorkbenchDataEntryPanel })));
export const SourceWorkbenchDataManagementPanel = lazy(() => loadDataManagementPanel().then((module) => ({ default: module.SourceWorkbenchDataManagementPanel })));
