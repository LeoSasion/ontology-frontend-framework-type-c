import { readFileSync } from "node:fs";

const read = (path) => readFileSync(path, "utf8");
const panel = read("src/components/SettingsWorkflowRecipePanel.tsx");
const settings = read("src/components/SettingsPanel.tsx");
const api = read("src/apiWorkflowRecipes.ts");
const routes = read("server/workflowRoutes.ts");
const css = read("src/components/settingsWorkflowRecipePanel.css");
const checks = [
  { label: "recipe-panel-is-lazy-mounted", ok: settings.includes('lazy(() => import("./SettingsWorkflowRecipePanel"))') && settings.includes("<SettingsWorkflowRecipePanel") && settings.includes('testId="settings-workflow-recipe-details"') && settings.includes("opened ? <Suspense") },
  { label: "three-recommended-recipes-exist", ok: ["trusted-answer", "semantic-release", "safe-change"].every((value) => panel.includes(value)) },
  { label: "preview-is-required-before-exact-publish", ok: panel.includes("previewWorkflowRecipe") && panel.includes("pending.plan.planFingerprint") && panel.includes("publishWorkflowRecipe") },
  { label: "instantiation-explicitly-does-not-auto-execute", ok: panel.includes("executesAutomatically") || panel.includes("自动执行：否") && panel.includes("instantiateWorkflowRecipe") },
  { label: "api-and-route-cover-the-lifecycle", ok: api.includes("getWorkflowRecipes") && api.includes("previewWorkflowRecipe") && api.includes("publishWorkflowRecipe") && api.includes("instantiateWorkflowRecipe") && routes.includes('"/api/workflow/recipes/plan"') },
  { label: "responsive-recipe-layout-is-container-aware", ok: css.includes("@container") && css.includes("grid-template-columns:minmax(0,1fr)") && css.includes("min-height:44px") },
];
const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({ ok: failedChecks.length === 0, schema: "aibi-workflow-recipe-ui-verify/v1", checks, failedChecks }, null, 2));
if (failedChecks.length) process.exitCode = 1;
