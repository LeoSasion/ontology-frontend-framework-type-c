import { fetchJsonStrict } from "./apiClient";
import type { WorkflowRecipe, WorkflowRecipeInstantiation, WorkflowRecipePlan } from "./types";

export type WorkflowRecipeMutation = { requestKey: string; name: string; description?: string; stages: Array<{ label?: string; command: string; input?: Record<string, unknown> }> };
export function getWorkflowRecipes() { return fetchJsonStrict<{ ok: boolean; workflowRecipes: WorkflowRecipe[]; count: number }>("/api/workflow/recipes"); }
export function previewWorkflowRecipe(input: WorkflowRecipeMutation) { return fetchJsonStrict<{ ok: boolean; workflowRecipePlan: WorkflowRecipePlan }>("/api/workflow/recipes/preview", { method: "POST", body: JSON.stringify(input) }); }
export function publishWorkflowRecipe(input: WorkflowRecipeMutation & { expectedPlanFingerprint: string }) { return fetchJsonStrict<{ ok: boolean; workflowRecipe: WorkflowRecipe }>("/api/workflow/recipes/publish", { method: "POST", body: JSON.stringify({ ...input, confirm: true }) }); }
export function instantiateWorkflowRecipe(recipeKey: string, bindings: Record<string, unknown> = {}) { return fetchJsonStrict<WorkflowRecipeInstantiation>("/api/workflow/recipes/plan", { method: "POST", body: JSON.stringify({ recipeKey, bindings }) }); }
