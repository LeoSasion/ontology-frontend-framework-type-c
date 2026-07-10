# AIBI-C Product UX Standard

This document owns the interaction and documentation standard for the current product. It is not a historical design note.

## Product Experience Contract

- The default user path is AI-assisted: the user states the business question or chart they want, and the workbench turns it into a reviewed result without hiding deterministic import, query, evidence, or confirmation behavior.
- One business capability has one owning surface. Data intake belongs to Sources, chart creation belongs to Dashboards, evidence review belongs to Evidence, and write approval belongs to AI. Other screens should route into that surface instead of repeating the same operation.
- The conservative default is one conversation to one chart. The assistant may ask at most one necessary clarification before drafting a line chart, bar chart, metric card, table, or text insight.
- A vague chart request must ask for fields instead of guessing. "图表/chart" means one chart; "看板/仪表盘/dashboard" means a dashboard container or full dashboard draft.
- Chart clarification should be actionable. When the assistant cannot safely choose a measure or dimension, it should show candidate field buttons that resubmit a more explicit chart request, not ask the user to copy field names manually.
- Chart candidates and auto metrics must use business fields only. Internal fields such as canonical dates and import source markers may power time windows or evidence lineage, but they must not appear as user-facing measures, default dimensions, or field-choice buttons.
- The beta path is one conversation to a full industry dashboard. It must be labeled Beta, generated from field evidence, and previewed before any write.
- A fresh workspace must be empty by default. Do not auto-load bundled data, run placeholder queries, create placeholder dashboards, or ask Agent warmup questions before the user imports data.
- Folder import is a first-class intake path. It should preview how files will be grouped into business tables and write only after confirmation.
- The first screen of a workflow should expose one primary action, the current result, and the minimum status needed to trust it.
- Advanced controls stay available through progressive disclosure: filters, data-source switch, widget maintenance, relationship tools, style controls, contract details, and validation labs should not all be open by default.
- Confirmation is reserved for real writes. Drafting, explanation, preview, and evidence lookup should not require extra confirmation clicks.
- Write actions still stop at draft or dry-run-confirm. The simplification goal is fewer unnecessary clicks, not weaker control.

## Screen Priority Standard

Every main screen should order content this way:

1. Intent capture: a business action, natural-language prompt, or direct import action.
2. Result preview: chart, table, dashboard, answer, or draft summary.
3. Trust summary: source, metric definition, evidence count, gaps, or blocker.
4. Next best action: create one chart, ask Agent, review evidence, or confirm draft.
5. Advanced maintenance: filters, style, page admin, field semantics, relationships, raw receipts, validation labs.

If a screen starts by showing maintenance controls before the result or intent capture, it should be refactored.

## First Success Flow Standard

The product default is a guided first-success loop:

1. Connect data in Sources.
2. Create an evidence summary from the imported data.
3. Create one chart in Dashboards.
4. Review evidence in Evidence.
5. Approve or reject any write draft in AI.

Only the current necessary step should be visually primary. Locked future steps may be visible as status, but they must not expose their full controls before the prerequisite exists. The shared product activation panel owns this status so pages do not each write their own onboarding flow.

## Object Ownership Matrix

| Object | Owning surface | Other surfaces may do |
| --- | --- | --- |
| Source table, import job, connector | Sources | Route to Sources, show read-only count or latest receipt |
| Field semantic, metric definition, relationship, formula | Sources | Show trust summary or blocker, then route to Sources |
| Saved view | Details | Add to chart context, route to Details for edits |
| Chart widget and dashboard page | Dashboards | Link to focused dashboard, show evidence reference |
| Evidence run, query receipt, action receipt | Evidence | Show short trust summary, route to Evidence for details |
| Action draft, confirmation, rejection | AI | Show pending count, route to AI for approval |
| Workspace, theme, config portability | System | Show current workspace identity only |

If a page needs another object, it should navigate with context instead of duplicating that object's create/edit/delete workflow.

## Route Handoff Standard

- Use the global business path to pass the user between steps: connect data, create chart, review evidence, approve writes.
- A page may summarize another step, but its primary button should navigate to the owning page instead of duplicating the same operation locally.
- Guidance panels may explain the next step, but they must not duplicate the owning panel's write buttons. For example, file import confirmation belongs to the import panel, not the next-action guide.
- Homepage actions should be orientation and handoff only. They should not run source scans, dashboard templates, Agent questions, or confirmations directly unless the user opens an advanced validation lab.
- Empty states must route to data import. They should not offer built-in data shortcuts in the product UI.
- Importing a folder should show only file count, business-table groups, key fields, and the confirm action by default. Raw file lists and policy receipts belong in details.
- Relationship recommendations must require real sample overlap and avoid low-cardinality or many-to-many exploding joins as primary suggestions. Name similarity alone is not enough.
- Automatic metric repair may delete and rebuild stale auto-generated metrics, but only when the metric is marked `source=auto`. Manual metric definitions are user-owned and must not be removed by cleanup.
- Creating an empty dashboard creates only the dashboard container. Widgets require imported data, field evidence, or an explicit AI/recommendation draft; do not inject default chart templates.
- Repeated expert shortcuts stay behind details, beta labels, or validation labs; they should not compete with the main path.
- The active page owns its own confirmation logic. Navigation itself does not add confirmation.

## Documentation Standard

- `PRODUCT.md` owns positioning, product category, users, value proposition, boundaries, and non-goals.
- `docs/PRD.md` owns current user stories, workflows, functional requirements, and release acceptance.
- `docs/product-ux-standard.md` owns interaction, information architecture, and documentation standards.
- `docs/product-acceptance-matrix.md` owns durable executable scenarios.
- `docs/implementation-status.md` owns current release boundaries, capability status, architecture ownership, and known limitations.
- `docs/development-roadmap.md` contains future work only; completed baseline work is summarized once and removed from the active queue.
- CLI, ERP references, and implementation receipts stay in their dedicated docs. Do not repeat them in product docs unless the product contract changes.

## Copy Standard

- Use business language first: "生成一个图表", "查看证据", "确认写入", "行业看板 Beta".
- Avoid internal labels as primary copy: source-intelligence, widget payload, module save, stale cleanup, and receipt paths belong in details.
- Button labels must state the outcome. Prefer "生成一个图表" over "提交", and "预演行业看板" over "运行".
- Status text should explain what happened and whether anything was written.
- Empty states should offer one next action, not a list of every possible action.

## Confirmation Standard

- Read-only answer: no confirmation.
- Draft or preview: no confirmation, but clearly state that nothing was written.
- Write: one confirmation surface that shows target, impact, evidence, and rollback or rejection path.
- Dangerous overwrite/delete: keep explicit confirmation, but do not add redundant confirmation before the draft.

## Delete And Rollback Standard

- Delete entry points stay on the owning surface: source deletes in Sources, view deletes in Details, dashboard/widget deletes in Dashboards, workspace deletes in System.
- A destructive action must first show target, dependent objects, expected impact, and whether the result is a dry run or confirmed write.
- Rejection is the rollback path for drafts that have not been written.
- After a confirmed delete, the UI should show a receipt and route the user to the nearest still-valid object instead of leaving them on a broken selection.
- Do not hide delete forever inside raw technical details; place it in a clearly labeled management section that is collapsed by default.

## Acceptance Matrix Standard

The durable product acceptance matrix lives in `docs/product-acceptance-matrix.md`. Product or UX changes are not done until the matrix still covers empty workspace, import, evidence, one-chart creation, beta dashboard preview, confirmation/rejection, delete impact, workspace isolation, and no-demo production boundaries.

## Beta Dashboard Standard

The full industry dashboard path remains beta until it can reliably:

- select units from current field evidence,
- omit missing-field charts instead of faking them,
- explain matched and omitted units,
- show source references,
- preview impact before creation or overwrite,
- preserve the same confirmation boundary as other writes.
