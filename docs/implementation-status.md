# AIBI-C Implementation Status

Project boundary: this repository owns the product code, documentation, and verification contract. User data may live in configured local paths outside the repository.

Current stage: local production baseline for a single-user workstation. The stable product path is import -> evidence -> one chart -> evidence review -> confirmed write. Full industry dashboards remain Beta.

## Current Release Boundary

| Layer | Current implementation | Boundary |
| --- | --- | --- |
| Client | React 19 and Vite desktop-first workbench | Progressive disclosure; no server-rendered or mobile-native client |
| Local API | Node/TypeScript route facade | Loopback only, bounded request bodies, exact-origin optional CORS |
| BI runtime | Python CLI, SQLite metadata, DuckDB analytics | Whitelisted query parameters; no arbitrary user SQL |
| Storage | Local database files and user-selected source files | No cloud sync, multi-tenant storage, or repository data seeding |
| Agent | Deterministic local resolution with optional model configuration | Workspace scoped; read-only answers and confirmed write drafts stay distinct |
| Evidence | Source runs, query runtime, metric definitions, action and delete receipts | Business summary first; raw diagnostics remain collapsed |

## Capability Status

| Capability | Status | Current contract |
| --- | --- | --- |
| Clean first run | Stable | New workspaces contain no tables, charts, dashboards, answers, or sample shortcuts. Product activation shows only the current necessary step. |
| File and folder import | Stable | CSV/XLSX/XLSM preview, same-type grouping, merge impact, key quality, confirmed commit, and receipts. |
| Source evidence profiling | Stable | Field roles, data quality, metric candidates, relationship evidence, gaps, and source receipts. |
| AI one-chart flow | Stable | Generic overview does not choose domain fields; vague charts clarify once; explicit charts create one confirmable draft. |
| Details and saved views | Stable | Whitelisted detail queries, search, filter, sort, save/copy/delete, dashboard and Agent handoff. |
| Dashboard widget set | Stable advanced capability | Metric, bar, line, pie, table, text, slicer, relationship, filters, styles, lifecycle, and source switching. |
| Full industry dashboard | Beta | Evidence-matched ERP units, omitted-unit disclosure, preview, then confirmation. |
| Agent write boundary | Stable | Writes become dry-runs or action drafts; confirmation, rejection, impact, and receipt are explicit. |
| Evidence experience | Stable | Business meaning and gaps are primary; runtime and raw receipts are secondary. |
| Local operations | Stable | Loopback startup, health checks, production/security gates, checksum backup, and guarded restore. |

## Known Limitations

- Current release is single-user and local-only; it does not provide authentication, roles, collaboration, remote hosting, or cloud synchronization.
- The full-dashboard path is Beta and has not met a promotion gate across multiple independent industries.
- Legacy XLS can be profiled by Source Intelligence but is not yet supported by the confirmed import path; convert it to XLSX or CSV before import.
- Real-data acceptance currently proves one local multi-table financial/commerce folder shape. A second independent real dataset is still required for stronger generalization evidence.
- Optional model-provider quality is separate from the deterministic fallback contract; provider availability must never disable local evidence and query behavior.
- Backup protects local SQLite and DuckDB files, but this is not a remote disaster-recovery service.
- UI verification is desktop focused at 1440x900, 900x1440, and 1100x1100; mobile is not a release target.

## Architecture Ownership

| Path | Owns |
| --- | --- |
| `src/components/` | Page surfaces and presentational workflow components |
| `src/*Model.ts`, `src/*ViewModel.ts` | Derived UI state, labels, readiness, and safe transformations |
| `src/api*.ts` | Typed client calls and empty fallbacks |
| `server/` | Thin local HTTP routing, security boundary, and CLI invocation |
| `tools/bi_cli.py`, `tools/*_service.py` | BI CLI bridge, deterministic business actions, evidence, and write drafts |
| `scripts/` | Build, release, browser, backup, security, and regression verification |
| `docs/` | Current product, UX, acceptance, roadmap, and implementation contracts |

Component-level ownership is enforced by imports and `scripts/verify.mjs`; it is intentionally not duplicated as a manual list in this document.

## Verification Entry Points

Use the smallest relevant command while developing and `npm run preflight` before local delivery.

```powershell
npm run build
npm run verify
npm run verify:ai-reliability
npm run verify:ui-visual
npm run verify:ui-empty
npm run verify:ui-import
npm run verify:backup
npm run verify:production
npm run verify:security-runtime
npm run preflight
python tools/bi_cli.py --json status
python tools/bi_cli.py --json cli-contract
```

`npm run verify:ui-import` uses a temporary workspace, restores the original workspace, and removes its imported runtime state after verification. Real source files remain external and are never committed.

## Release Evidence

- Core verification covers the static/runtime contract suite plus the BI CLI Agent contract; the live receipt owns the exact check count.
- AI reliability separately covers empty, generic, ambiguous, explicit bar/line, unknown-field, and missing-dimension cases.
- Views visual verification creates an isolated table and saved view before checking all three desktop ratios; it does not treat an empty-state redirect as a Views pass.
- GitHub Actions repeats build, production, backup, runtime security, and browser smoke checks on Windows.

Exact counts are receipts, not durable product promises. Re-run the commands above instead of copying old totals into planning documents.
