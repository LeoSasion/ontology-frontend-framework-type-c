# AIBI-C Product Acceptance Matrix

This matrix defines the minimum product behavior for a clean, extensible AIBI workspace.

| Scenario | User expectation | Acceptance signal |
| --- | --- | --- |
| Empty workspace | No sample chart, table, dashboard, or answer appears. | Home, Sources, Dashboards, Evidence, and AI route the user to import real data. |
| Import one file | The user previews impact before writing. | Import preview shows target, row impact, key health, and confirm state. |
| Import folder or connector | The system profiles real sources after import. | Folder preview groups files into business tables with row counts and keys; UI verification imports a real folder when available and checks merged row counts before deleting the temporary workspace. |
| Create one chart | The default dashboard action is one guided chart, even when no dashboard exists yet. | AI asks at most one necessary question when fields are unclear; otherwise it drafts exactly one chart, uses one confirmation surface, and creates a one-widget dashboard after approval. |
| Generic AI question | The system answers from the active table without assuming an industry or metric. | A generic overview uses row count and source evidence; it never silently defaults to sales, refund, channel, or another bundled business field. |
| Field and metric hygiene | Users see business fields, not implementation artifacts. | Auto metrics skip internal `__*` fields, stale auto metrics are cleaned without touching manual metrics, and Agent candidate buttons exclude internal fields. |
| Save business relationship | Only trustworthy cross-table links become primary recommendations. | Relationship recommendations require sample overlap, sufficient key cardinality, and non-exploding joins before save; confirmed relationships keep preview coverage and warnings. |
| Create full industry dashboard Beta | The beta path is visibly secondary. | The flow previews matched and omitted units before any dashboard write. |
| Review evidence | Users can see why a result is trustworthy. | Evidence page defaults to business summary and keeps raw receipts collapsed. |
| Confirm or reject write | Writes are controlled without redundant clicks. | Draft review shows target, impact, evidence, confirm, and reject paths. |
| Delete source or object | Delete is available but guarded. | Owning page provides dry-run impact before confirmed delete and shows a receipt after completion. |
| Workspace isolation | Imported data and generated objects remain scoped. | Status, workbench, dashboards, action drafts, and evidence resolve from the active workspace. |
| Production no-demo boundary | The product never seeds user-facing content. | Verification uses `validation-inputs`, while production empty state reports zero tables, dashboards, and drafts. |
| Real-data UI path | Users can complete the primary read-only loop from current data. | Live UI verification checks Home -> Dashboard -> Evidence -> Sources -> Agent without writes, error boundaries, or sample copy. |
| Desktop visual ratios | The Views query workspace stays usable across common PC shapes. | Verification creates an isolated imported table and saved view, then live browser screenshots pass at 1440x900, 900x1440, and 1100x1100 with the Views route and query panel mounted and no global overflow, visible overlap, or clipped text. |
| Empty-workspace UI path | A new workspace exposes only the next necessary step. | Temporary-workspace UI verification proves Home, Sources, Dashboards, Evidence, and Agent guide to import without seeded sample content. |
| Temporary real import loop | An external real file or folder can complete the beginner path without touching the user's active workspace. | UI verification creates a temporary workspace, imports declared non-fixture data, generates evidence, requests one chart before any dashboard exists, confirms the one-widget draft once, opens evidence, restores the original workspace, and deletes the temporary workspace. |
| Local network boundary | A local-first install is not exposed to the LAN by default. | API and UI bind to loopback, wildcard CORS is absent, invalid JSON returns 400, oversized bodies return 413, and security/request-id headers are present. |
| Backup and recovery | A maintainer can protect local workspaces without copying secrets. | Backup refuses while the service is running, includes only SQLite/DuckDB with SHA-256 manifest entries, restore previews by default, and confirmed restore verifies checksums plus creates a safety backup. |

## Required Verification

- `npm run preflight`
- `npm run build`
- `npm run verify`
- `npm run verify:ui`
- `npm run verify:ui-empty`
- `npm run verify:ui-import`
- `npm run verify:bi-cli-contract`
- `npm run verify:ai-reliability`
- `npm run verify:production`
- `npm run verify:security-runtime`
- `npm run verify:backup`
- `npm run verify:erp-units`
- `python tools/bi_cli.py --json status`
- `python tools/bi_cli.py --json source-intelligence validation-inputs --label "Validation evidence profile"`
- `python tools/bi_cli.py --json business-dashboard --template erp-units --op draft --limit 24`
