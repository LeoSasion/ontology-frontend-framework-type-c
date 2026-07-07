# AI BI Workbench Implementation Status

Project boundary: this repository is the product boundary.

This file is the current implementation index. It records the stable module boundaries that `npm run verify` checks, plus the small set of commands used to prove the workbench is still coherent.

## Current Shape

| Area | Status | Contract |
| --- | --- | --- |
| BI CLI bridge | Active | `tools/bi_cli.py` is the local backend entrypoint for workspace, source, query, dashboard, Agent, config, and evidence commands. |
| Source evidence profiling | Active | `source-intelligence` produces evidence receipts from local fixture or user-selected inputs; folder import previews group same-type files before confirmed writes, field semantics avoid treating contact/system identifiers as measures, and auto metrics clean stale internal-field metrics without touching manual metrics. |
| Dashboard widget set | Active | Dashboard pages support metric, bar, line, pie, table, text, slicer, relationship, filters, style, lifecycle, and source-switch flows. |
| AI-first dashboard creation | Active | Dashboard pages start from a natural-language chart request; vague chart requests ask for fields with clickable business-field candidates, explicit chart requests become one-chart drafts, and full industry dashboards remain a beta preview path. |
| Clean empty runtime | Active | App startup uses empty workspace/query/dashboard/Agent fallbacks and only guides users to import local data when no tables exist. |
| Global business path | Active | A compact route handoff bar owns the steps: connect data, create chart, review evidence, approve writes. Home actions route into these owners instead of duplicating execution. |
| ERP unit library | Active | Public ERP references are mapped to selectable units, field aliases, omitted-unit hints, and confirmable dashboard drafts. |
| Agent confirmation boundary | Active | Agent answers are evidence-aware; write operations become dry-runs or action drafts before confirmation. |
| Evidence surface | Active | Evidence pages summarize business meaning first, with technical details available on demand. |
| UI runtime verification | Active | Live-browser checks cover the real-data Home -> Dashboard -> Evidence -> Sources -> Agent path, Views layout at landscape/portrait/square ratios, empty workspace routing, and a temporary-workspace real folder import loop with file fallback. |
| Local operations and CI | Active | GitHub Actions runs the build plus core verification on Windows; local PowerShell scripts start, stop, and health-check the API/UI without touching workspace data, and `npm run preflight` gives local release validation one command. |

Users should start from business actions. Advanced modeling, query, and command details stay available after the primary workflow is clear.

## Verification

```powershell
npm run preflight
npm run verify:ci
npm run build
npm run verify
npm run verify:ui
npm run verify:ui-empty
npm run verify:ui-import
npm run verify:bi-cli-contract
npm run verify:erp-units
python tools/bi_cli.py --json status
python tools/bi_cli.py --json cli-contract
python tools/bi_cli.py --json source-intelligence validation-inputs --label "Validation evidence profile"
python tools/bi_cli.py --json business-dashboard --template erp-units --op draft --limit 24
npm run local:start
npm run local:health
npm run local:stop
```

`npm run verify:ui` expects the local API and UI to be running through `npm run dev` or equivalent live services on ports 8787 and 8686. The real-import UI check creates a temporary workspace, imports `AIBI_REAL_IMPORT_FOLDER` when present or `AIBI_REAL_IMPORT_FILE` as fallback, exercises evidence and chart entry points, then restores the original workspace and deletes the temporary workspace.

## Verified Boundary Index

These names are intentionally current code ownership markers. They should stay factual and compact.

- Source workbench data entry panel boundary
- Source workbench header boundary
- Source workbench derived model boundary
- Source workbench guidance model boundary
- Source workbench receipt model boundary
- Source workbench command model boundary
- Source Intelligence run model boundary
- Source workbench contracts boundary
- Source workbench draft model boundary
- Source workbench action panel boundary
- Source workbench import panel boundary
- Dashboard value helper boundary
- Dashboard runtime model boundary
- Dashboard widget factory boundary
- Dashboard widget card boundary
- Relationship auto model view-model boundary
- Source visual relationship auto-modeling
- Source workbench operations panel boundary
- Source workbench connector panel boundary
- Source workbench field metric panel boundary
- Source workbench query formula panel boundary
- Source workbench relationship panel boundary
- Dashboard canvas widget model boundary
- Dashboard canvas editor options boundary
- Dashboard canvas summary model boundary
- Dashboard canvas view model boundary
- Dashboard canvas contracts boundary
- Evidence business summary panel component boundary
- Badge fit-content system
- Global business path component boundary
- Business path model boundary
- Product activation model and panel boundary
- Dashboard business task strip component boundary
- Dashboard AI-first creation strip
- Dashboard beginner editor component boundary
- Dashboard advanced widget workbench component boundary
- Dashboard module save panel component boundary
- Dashboard business template panel component boundary
- Dashboard widget recommendation panel component boundary
- Dashboard saved view panel component boundary
- Dashboard relationship recommendation panel component boundary
- Dashboard relationship widget panel component boundary
- Dashboard widget manage panel component boundary
- Dashboard widget editor panel component boundary
- Dashboard widget basic form component boundary
- Dashboard widget style panel component boundary
- Dashboard widget local filter panel component boundary
- Dashboard widget lifecycle panel component boundary
- Dashboard page admin panel component boundary
- Dashboard contract boundary panel component boundary
- Dashboard overview strip component boundary
- Dashboard filter workbench component boundary
- Dashboard canvas source switch model boundary
- Dashboard canvas source switch view model boundary
- Dashboard canvas readiness model boundary
- Dashboard canvas plan model boundary
- Dashboard canvas filter model boundary
- Dashboard canvas field model boundary
- Dashboard canvas state hook boundary
- Dashboard canvas actions hook boundary
- Dashboard canvas action runner boundary
- Dashboard canvas relationship model boundary
- View Agent task strip component boundary
- View dashboard bridge panel component boundary
- View saved list panel component boundary
- App workspace model boundary
- Empty workspace data boundary
- Types workspace contract boundary
- Types dashboard contract boundary
- Types source contract boundary
- Types domain contract boundary
- Types query and Agent contract boundary
- App data actions hook boundary
- API workspace, source, dashboard, settings, views, model, and Agent domain boundary
- Home workspace start guide component boundary
- Home overview model boundary
- Safe value helper boundary
- Server runtime boundary
- Server static boundary
- Server dashboard routes boundary
- Server source routes boundary
- Server settings routes boundary
- Server model routes boundary
- Server query routes boundary
- Server agent routes boundary
- Server workspace routes boundary
- Home action dock component boundary
- Home detailed path panel boundary
- Empty workspace data boundary
- Sidebar workspace card component boundary
- Sidebar asset sections component boundary
- App section model boundary
- Desktop shell fluid width
- Home scenario packs component boundary
- Home product intelligence component boundary
- Evidence number explainer panel component boundary
- Global floating Agent assistant
- Settings sandbox boundary panel component
- Settings theme preference panel component boundary
- Settings acceptance evidence panel component boundary
- Source evidence regression harness
- Agent panel model boundary
- Agent context plan panel boundary
- Agent prompt composer component boundary
- UI Chrome verification harness
- UI real-data flow regression
- UI desktop-ratio visual regression
- UI empty-workspace regression
- UI temporary real-import regression

## Ownership Notes

- `src/components/*` owns presentational panels and small workflow components.
- `src/*Model.ts` files own derived view state, labels, readiness, and UI-safe transformations.
- `server/*` owns local HTTP routing and should remain a thin facade over CLI commands.
- `tools/*` owns deterministic business actions, evidence bundles, runtime receipts, and action drafts.
- `docs/*` owns current project documentation only.
