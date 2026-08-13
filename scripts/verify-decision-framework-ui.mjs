import { readFileSync } from "node:fs";

function source(relativePath) {
  return readFileSync(new URL(`../${relativePath}`, import.meta.url), "utf8");
}

const entry = source("src/components/DecisionFrameworkEntry.tsx");
const editor = source("src/components/DecisionFrameworkEditor.tsx");
const loader = source("src/components/decisionFrameworkLoader.ts");
const api = source("src/apiDecisionFrameworks.ts");
const css = source("src/components/decisionFramework.css");

const checks = [
  {
    label: "editor-is-user-triggered-and-dynamically-loaded",
    ok: entry.includes("lazy(() => loadDecisionFrameworkEditor()")
      && loader.includes('import("./DecisionFrameworkEditor")')
      && entry.includes("onMouseEnter")
      && entry.includes("onFocus"),
  },
  {
    label: "data-fetches-subscribe-only-to-unit-and-selected-framework-keys",
    ok: editor.includes("}, [unitKey]);")
      && editor.includes("}, [selectedKey]);")
      && editor.includes("new AbortController()")
      && !/\[[^\]]*(?:framework|draftClaims|summaries)[^\]]*\]\);/.test(editor),
  },
  {
    label: "facts-judgments-and-hypotheses-have-distinct-visible-contracts",
    ok: editor.includes('evidence_fact: { zh: "证据事实"')
      && editor.includes('user_judgment: { zh: "用户判断"')
      && editor.includes('hypothesis: { zh: "待验证假设"')
      && editor.includes("verificationRequirement")
      && editor.includes("Does not count as a proven conclusion"),
  },
  {
    label: "evidence-candidates-require-explicit-category-and-fact-text-is-locked",
    ok: editor.includes("candidateCategories[candidate.claimKey]")
      && editor.includes("disabled={disabled || fact}")
      && editor.includes("Choose a category for candidate")
      && editor.includes("cannot be rewritten into an unsupported conclusion"),
  },
  {
    label: "stale-evidence-unloads-numbers-and-disables-editing-and-publishing",
    ok: editor.includes("evidenceFactsUnloaded")
      && editor.includes("Old evidence facts and numbers were unloaded")
      && editor.includes("framework?.canEdit && framework.freshness.current")
      && editor.includes("framework.canPublish"),
  },
  {
    label: "publication-uses-one-preview-confirmation-boundary",
    ok: editor.includes("previewPublication")
      && editor.includes("confirmPublication")
      && editor.includes("publicationPlan.planFingerprint")
      && editor.includes("One explicit confirmation"),
  },
  {
    label: "published-or-existing-framework-does-not-trap-user-without-a-new-draft-path",
    ok: editor.includes("setShowCreate((current) => !current)")
      && editor.includes("New framework")
      && editor.includes("Cancel new"),
  },
  {
    label: "keyboard-and-long-text-controls-use-native-semantics",
    ok: editor.includes("<fieldset")
      && editor.includes("<legend>")
      && editor.includes("<textarea")
      && editor.includes('type="button"')
      && editor.includes("aria-live")
      && editor.includes('role="alert"'),
  },
  {
    label: "layout-supports-720-short-edge-and-long-content-without-fixed-width",
    ok: css.includes("@container viewport-stage (max-width: 720px)")
      && css.includes("@container viewport-stage (max-height: 720px) and (min-width: 721px)")
      && css.includes("content-visibility: auto")
      && css.includes("overflow-wrap: anywhere")
      && css.includes("min-height: 44px")
      && !/(?:^|[;{]\s*)width:\s*\d{3,}px/m.test(css),
  },
  {
    label: "api-is-key-scoped-and-does-not-send-workspace-or-raw-rows",
    ok: api.includes("encodeURIComponent(input.frameworkKey)")
      && api.includes("encodeURIComponent(frameworkKey)")
      && !/workspaceId|rawRows|businessRows|providerContext/.test(api),
  },
];

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-decision-framework-ui-verify/v1",
  generatedBy: "scripts/verify-decision-framework-ui.mjs",
  checks,
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
