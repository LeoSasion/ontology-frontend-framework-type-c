# AIBI-C Product Roadmap

This roadmap contains future work only. Completed implementation details belong in `implementation-status.md`; durable behavior belongs in the acceptance matrix.

## Delivered Baseline

The current baseline already provides a clean empty workspace, guided import, evidence summaries, AI one-chart drafts, controlled writes, responsive Details, local backup/recovery, and Windows CI browser checks. These are regression constraints, not active roadmap items.

## Current Development Order

| Order | Priority | Workstream | Product outcome | Done signal |
| --- | --- | --- | --- | --- |
| 1 | P0 | Generalization acceptance | Prove that arbitrary imports work beyond the current real-data shape. | At least two additional independent schemas across at least two business domains complete import -> evidence -> one chart -> evidence -> confirmation without code or bundled-data changes. |
| 2 | P0 | Brand and release identity | Remove the remaining `AIBI Hybrid` runtime name and present one product identity: `AIBI-C`. | UI title, default workspace, CLI metadata, API logs, docs, package metadata, and repository name use the agreed identity; compatibility migration is documented. |
| 3 | P1 | First trusted chart efficiency | Measure and reduce the work required to reach the first evidence-backed chart. | Empty-workspace acceptance records the path; no advanced panel is required; clarification is at most one turn; a write uses one confirmation surface. |
| 4 | P1 | Semantic confidence | Improve arbitrary-schema metric, date, status, identity, and relationship selection without domain fallback. | Unknown fields never silently fall back; relationship recommendations pass overlap/cardinality checks; confidence and blockers are visible in business language. |
| 5 | P1 | Evidence handoff | Make validated answers and charts usable outside the live workspace without exposing raw internals. | A deliberate export/share artifact includes result, source, metric definition, query time, gaps, and workspace identity, with no secret or absolute source-path leak. |
| 6 | P1 | Local release durability | Make upgrades and recovery predictable for non-developer users. | Versioned local schema migration, pre-upgrade backup, rollback receipt, and clean-install verification are automated. |
| 7 | P2 | Full-dashboard Beta promotion gate | Decide whether the industry dashboard deserves stable status based on evidence, not feature count. | It passes multiple independent industries, omits unsupported units, explains every selection, meets visual budgets, and does not increase default-screen complexity. |

## Product Metrics

- First trusted chart completion rate in the acceptance workflow.
- Median user decisions from import start to reviewed chart; maintenance clicks are tracked separately.
- Percentage of answers and chart drafts with source, metric/query evidence, and explicit gap status.
- Silent-field-fallback count: target zero.
- Unnecessary confirmation count for read-only actions: target zero.
- Confirmed writes with one complete impact summary: target 100%.
- Visual regressions with overflow, overlap, or clipped text across supported desktop ratios: target zero.

These metrics may be collected in local verification receipts. The product must not add hidden cloud telemetry to satisfy them.

## Promotion Rules

- Stable paths cannot depend on bundled examples, fixtures, or a specific customer's field names.
- A Beta capability is not promoted because its UI exists; it must pass independent real-data and evidence-quality gates.
- New advanced controls remain collapsed until user research or acceptance evidence proves they belong in the default path.
- A new page is justified only when it owns a distinct business object or workflow; otherwise pass context to the existing owner.
- Use `npm run preflight` as the final local acceptance gate and GitHub Actions as the remote release gate.
