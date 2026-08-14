import { useEffect, useRef, useState } from "react";
import { getWorkflowRecipes, instantiateWorkflowRecipe, previewWorkflowRecipe, publishWorkflowRecipe, type WorkflowRecipeMutation } from "../apiWorkflowRecipes";
import type { WorkflowRecipe, WorkflowRecipeInstantiation, WorkflowRecipePlan } from "../types";
import { Bilingual, biText } from "./Bilingual";
import "./settingsWorkflowRecipePanel.css";

const TEMPLATES = [
  { id: "trusted-answer", name: biText("首个可信答案", "First trusted answer"), description: biText("核对工作台，再生成可追溯分析与答案。", "Inspect the workbench, then build traceable analysis and an answer."), stages: [{ label: biText("核对数据", "Inspect data"), command: "workbench", input: {} }, { label: biText("生成分析单元", "Build Analysis Unit"), command: "analysis-unit-build", input: { receipt: "${receiptKey}", rowsJson: "${rowsJson}" } }] },
  { id: "semantic-release", name: biText("语义发布", "Semantic release"), description: biText("查看提案，再预演并确认语义版本。", "Review proposals, then preview and confirm a semantic version."), stages: [{ label: biText("查看提案", "Review proposals"), command: "semantic-patch-proposals", input: { status: "pending" } }, { label: biText("预演版本", "Preview version"), command: "semantic-release-preview", input: { requestKey: "${requestKey}", proposal: "${proposalKeys}" } }, { label: biText("确认发布", "Confirm publish"), command: "semantic-release-publish", input: { requestKey: "${requestKey}", proposal: "${proposalKeys}", expectedPlan: "${planFingerprint}" } }] },
  { id: "safe-change", name: biText("安全变更", "Safe change"), description: biText("先建恢复点，执行受控变更，再校验配置。", "Create a recovery point, perform a controlled change, then validate configuration."), stages: [{ label: biText("建立恢复点", "Create recovery point"), command: "workspace-recovery-create", input: { reason: "${reason}", requestKey: "${requestKey}" } }, { label: biText("校验配置", "Validate config"), command: "validate-config", input: {} }] },
] as const;

function stableKey(templateId: string) { return `workflow-recipe-ui-${templateId}-v1`; }

export default function SettingsWorkflowRecipePanel() {
  const [recipes, setRecipes] = useState<WorkflowRecipe[]>([]);
  const [templateId, setTemplateId] = useState(TEMPLATES[0].id);
  const [pending, setPending] = useState<{ input: WorkflowRecipeMutation; plan: WorkflowRecipePlan } | null>(null);
  const [instantiation, setInstantiation] = useState<WorkflowRecipeInstantiation | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const requestRef = useRef(0);
  const selected = TEMPLATES.find((item) => item.id === templateId) ?? TEMPLATES[0];

  async function refresh() { const id = ++requestRef.current; const payload = await getWorkflowRecipes(); if (id === requestRef.current) setRecipes(payload.workflowRecipes ?? []); }
  useEffect(() => { void refresh().catch((error) => setNotice(error instanceof Error ? error.message : String(error))); return () => { requestRef.current += 1; }; }, []);

  async function preview() {
    const input: WorkflowRecipeMutation = { requestKey: stableKey(selected.id), name: selected.name, description: selected.description, stages: selected.stages.map((stage) => ({ ...stage, input: { ...stage.input } })) };
    setBusy("preview"); setNotice("");
    try { const payload = await previewWorkflowRecipe(input); setPending({ input, plan: payload.workflowRecipePlan }); setNotice(biText("Recipe 已预演；这里只冻结能力顺序，不自动执行。", "Recipe previewed. This freezes capability order and does not execute it.")); } catch (error) { setNotice(error instanceof Error ? error.message : String(error)); } finally { setBusy(""); }
  }

  async function publish() {
    if (!pending) return; setBusy("publish"); setNotice("");
    try { await publishWorkflowRecipe({ ...pending.input, expectedPlanFingerprint: pending.plan.planFingerprint }); setPending(null); await refresh(); setNotice(biText("Recipe 已保存，可随时生成新的绑定计划。", "Recipe saved and can instantiate a fresh bound plan at any time.")); } catch (error) { setNotice(error instanceof Error ? error.message : String(error)); } finally { setBusy(""); }
  }

  async function instantiate(recipe: WorkflowRecipe) {
    setBusy(`plan-${recipe.recipeKey}`); setNotice("");
    try { const payload = await instantiateWorkflowRecipe(recipe.recipeKey); setInstantiation(payload); setNotice(payload.missingBindings.length ? biText("计划已生成；请在对应业务页面补齐绑定后再执行。", "Plan generated. Complete bindings in the relevant business view before execution.") : biText("计划已生成；写入阶段仍需逐项确认。", "Plan generated. Every write stage still requires confirmation.")); } catch (error) { setNotice(error instanceof Error ? error.message : String(error)); } finally { setBusy(""); }
  }

  return <section className="workflowRecipePanel" data-testid="settings-workflow-recipes"><div className="settingsSectionHeading"><div><strong><Bilingual zh="Workflow Recipe" en="Workflow Recipe" /></strong><p><Bilingual zh="复用步骤和确认边界，不复用旧数据、旧回执或旧授权。" en="Reuse steps and confirmation boundaries, never old data, receipts, or authorization." /></p></div><span className="settingsStatusPill">{recipes.length}</span></div>
    <div className="workflowRecipeBuilder"><label><span>{biText("推荐模板", "Recommended template")}</span><select disabled={Boolean(busy) || Boolean(pending)} onChange={(event) => setTemplateId(event.target.value as typeof templateId)} value={templateId}>{TEMPLATES.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><div><strong>{selected.name}</strong><small>{selected.description}</small></div>{!pending ? <button className="secondaryButton" disabled={Boolean(busy)} onClick={() => void preview()} type="button">{biText("预演 Recipe", "Preview Recipe")}</button> : <div className="workflowRecipeConfirm"><span>{pending.plan.stages.length} {biText("步", "stages")} · {pending.plan.confirmationStageCount} {biText("项确认", "confirmations")}</span><button className="primaryButton" onClick={() => void publish()} type="button">{biText("确认保存", "Confirm save")}</button><button className="secondaryButton" onClick={() => setPending(null)} type="button">{biText("取消", "Cancel")}</button></div>}</div>
    <div className="workflowRecipeList">{recipes.slice(0, 6).map((recipe) => <article key={recipe.recipeKey}><div><strong>{recipe.name} · v{recipe.version}</strong><small>{recipe.stageCount} {biText("步", "stages")} · {recipe.confirmationStageCount} {biText("项确认", "confirmations")}</small></div><button className="secondaryButton" disabled={Boolean(busy)} onClick={() => void instantiate(recipe)} type="button">{biText("生成计划", "Build plan")}</button></article>)}</div>
    {instantiation ? <div className="workflowRecipeResult" data-testid="workflow-recipe-plan-result"><strong>{instantiation.stages.length} {biText("个阶段已规划", "stages planned")}</strong><span>{instantiation.missingBindings.length ? `${biText("待绑定", "Missing")}: ${instantiation.missingBindings.join(" · ")}` : biText("绑定完整", "Bindings complete")}</span><small>{biText("自动执行：否", "Automatic execution: no")}</small></div> : null}
    {notice ? <p className="settingsInlineMessage" role="status">{notice}</p> : null}</section>;
}
