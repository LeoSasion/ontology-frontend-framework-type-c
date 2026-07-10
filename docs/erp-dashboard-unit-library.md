# AIBI-C ERP Dashboard Unit Library

## Purpose

The ERP path is a selectable evidence library, not a fixed dashboard template. Public ERP field and report patterns are represented as small metric, chart, table, slicer, and evidence units. Agent scores the active table and includes only units whose required fields are present.

This allows differently named Chinese ERP, e-commerce, finance, inventory, production, retail, apparel, WMS, and cross-border exports to use one mechanism without forcing every user into the same dashboard.

## Source Of Truth

`tools/erp_dashboard_unit_library.py` is the only source of truth for:

- public reference ids, titles, URLs, and covered signals,
- field alias groups,
- selectable unit definitions and required roles,
- scoring and omission rules,
- live unit, category, alias, and reference counts.

Do not copy the full reference catalog or numeric totals into Markdown. Inspect the live catalog instead:

```powershell
python tools/bi_cli.py --json erp-unit-library --summary
```

External references are design evidence, not claims that a vendor integration exists. A source URL may change; update the executable catalog and its verification together.

## Product Behavior

- `business-dashboard --template erp-units` creates a preview or confirmable dashboard draft from selected units.
- Dashboard previews show selected units, matched fields, omitted directions, fields needed next, category coverage, and public reference ids before any write.
- Agent carries the same `erpUnitLibrary` explanation in the task packet when a prompt prefers ERP units.
- Missing-field units are omitted. They are never rendered as completed charts.
- The library stays behind the full-dashboard Beta path and does not compete with stable one-chart creation.

## Selection Rule

1. Read the active workspace table registry and field semantics.
2. Match field names against alias groups and unit-required roles.
3. Drop units whose required measure or dimension is missing.
4. Score remaining units by required fields, optional fields, and signals.
5. Select only the highest evidence-backed units within the requested limit.
6. Return category coverage, omitted hints, unavailable count, and deduplicated fields needed next.
7. Preserve unit key, matched fields, source ids, and evidence references in each widget payload.

A sales/outbound workbook therefore does not receive manufacturing cards, and a procurement/inventory workbook is not forced into an order-sales dashboard.

## Promotion Boundary

The full-dashboard path remains Beta until it passes the promotion gate in `development-roadmap.md` across independent real business schemas. Catalog size alone is not evidence of product readiness.

## Verification

```powershell
python tools/bi_cli.py --json erp-unit-library --summary
python tools/bi_cli.py --json erp-unit-library --select --summary --table <table-key> --limit 24
python tools/bi_cli.py --json business-dashboard --template erp-units --op draft --limit 24
npm run verify:erp-units
```

`npm run verify:erp-units` validates catalog integrity, field selection, omitted-unit behavior, dashboard drafts, and Agent-confirmable dashboard creation. Verification data stays in temporary or ignored runtime paths and is never a production default.
