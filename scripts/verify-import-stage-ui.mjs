import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const controller = read("src/useSourceWorkbenchImportController.ts");
const panel = read("src/components/SourceWorkbenchImportPanel.tsx");
const styles = read("src/components/sourceWorkbenchCore.css");
const api = read("src/apiImportJobs.ts");
const runtime = read("server/durableJobRuntime.ts");
const service = read("tools/import_stage_service.py");

const checks = [];
const check = (label, condition) => {
  checks.push({ label, ok: Boolean(condition) });
  if (!condition) throw new Error(label);
};

check(
  "single-import-confirmation-reuses-the-preview-stage",
  controller.includes("stageKey: singleImportBinding.stageKey")
    && controller.includes("result.importStage?.stageKey")
    && api.includes("stageKey?: string"),
);
check(
  "folder-import-confirmation-reuses-each-preview-stage",
  controller.includes("stageBindings")
    && controller.includes("item.fileIdentity")
    && runtime.includes('"--stage-bindings"'),
);
check(
  "sealed-stage-is-visible-as-user-facing-safety-not-technical-path",
  panel.includes('data-testid="import-stage-seal"')
    && panel.includes("来源已密封，只解析一次")
    && panel.includes("源文件后续变化不会改写这次导入")
    && !panel.includes("AIBI_IMPORT_STAGE_ROOT"),
);
check(
  "stage-summary-never-exposes-a-local-path",
  service.includes('"sourceName": manifest["sourceName"]')
    && !service.match(/_stage_summary[\s\S]{0,1000}"(?:path|databasePath|root)"/),
);
check(
  "stage-seal-respects-compact-responsive-typography",
  styles.includes(".importStageSeal")
    && styles.includes("font-size: 12px")
    && styles.includes("font-size: 11px"),
);

console.log(JSON.stringify({
  ok: true,
  schema: "aibi-import-stage-ui-verify/v1",
  generatedBy: "scripts/verify-import-stage-ui.mjs",
  checks,
  failedChecks: checks.filter((item) => !item.ok).map((item) => item.label),
}, null, 2));
