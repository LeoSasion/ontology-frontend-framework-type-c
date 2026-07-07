# AIBI-C Development Roadmap

This roadmap is the current execution order for getting the product from the present baseline to a tighter beginner-ready release. It is not a historical changelog.

## Development Order

| Order | Workstream | Goal | Done Signal |
| --- | --- | --- | --- |
| 1 | Production copy and no-demo boundary | Remove user-facing sample-like prompts, temporary labels, and dated shortcuts. | `npm run verify` checks production copy; live UI shows only real-data or import guidance. |
| 2 | First-success flow hardening | Keep the default path to data import, evidence summary, one chart, evidence review, and confirmation. | Empty-workspace and real-import UI checks pass with future steps collapsed. |
| 3 | AI one-chart path | Make the stable default one chart per request, with at most one clarification and clickable field candidates when needed. | Agent and dashboard verification cover vague and explicit chart requests. |
| 4 | Evidence and confirmation clarity | Keep read-only actions confirmation-free while write/delete/import actions show impact and receipts. | Acceptance matrix covers confirmation, rejection, delete impact, and evidence receipt states. |
| 5 | Beta industry dashboard guardrails | Keep full dashboard creation secondary, evidence-matched, and non-faking when fields are missing. | ERP unit verification proves matched, omitted, and previewed units before any write. |
| 6 | Responsive visual QA | Prevent crowded controls, clipped labels, and overlap across common desktop ratios. | Visual verification passes landscape, portrait, square, and targeted changed screens. |
| 7 | Local release operations | Keep validation and startup to a small command set for maintainers. | `npm run preflight` passes locally and CI keeps `npm run verify:ci` green. |

## Current Release Status

| Workstream | Status | Verification |
| --- | --- | --- |
| Production copy and no-demo boundary | Complete for this baseline | `npm run verify` includes production-copy regression checks. |
| First-success flow hardening | Complete for this baseline | Empty-workspace and real-import UI loops pass through `npm run preflight`. |
| AI one-chart path | Complete for this baseline | Ambiguous chart clarification, candidate buttons, and real-import single-chart request are verified. |
| Evidence and confirmation clarity | Complete for this baseline | Draft, confirmation, rejection, delete, and evidence receipt checks are covered by core verification. |
| Beta industry dashboard guardrails | Complete for this baseline | ERP unit and business-dashboard draft checks cover matched, omitted, and previewed units. |
| Responsive visual QA | Complete for this baseline | Landscape, portrait, and square desktop ratios pass live visual verification. |
| Local release operations | Complete for this baseline | `npm run preflight` passes locally and CI keeps the lighter `verify:ci` path. |

## Continuous Development Rules

- Work in this order unless a failing verification blocks a higher-priority path.
- Do not add default data, demo dashboards, bundled examples, or hidden sample shortcuts.
- Prefer routing to the owning page over copying another page's controls.
- Add or update verification before treating a UX cleanup as complete.
- Use `npm run preflight` as the final local acceptance gate; use smaller scripts only while debugging.
