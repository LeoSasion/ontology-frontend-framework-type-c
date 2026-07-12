import { lazyWithRetry } from "./lazyWithRetry";

const loadActionPanel = () => import("./components/SourceWorkbenchActionPanel");
const loadDataManagementPanel = () => import("./components/SourceWorkbenchDataManagementPanel");

export const SourceWorkbenchActionPanel = lazyWithRetry(() => loadActionPanel().then((module) => ({ default: module.SourceWorkbenchActionPanel })));
export const SourceWorkbenchDataManagementPanel = lazyWithRetry(() => loadDataManagementPanel().then((module) => ({ default: module.SourceWorkbenchDataManagementPanel })));
