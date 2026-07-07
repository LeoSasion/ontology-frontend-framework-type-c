# BI CLI Contract

Schema: `aibi-bi-cli-contract/v1`

Entrypoint:

```powershell
python tools/bi_cli.py --json <command>
```

`tools/bi_cli.py` is the local backend contract for the workbench. JSON commands should return a compatible envelope with command name, mutation mode, confirmation status, artifacts, and evidence references when available.

## Mutation Modes

| Mode | Meaning |
| --- | --- |
| `read-only` | Reads local metadata or query results; no write confirmation needed. |
| `evidence-receipt` | Produces files or manifests that can be cited by the UI and Agent. |
| `runtime-receipt` | Produces a local runtime artifact such as an exported config. |
| `dry-run-confirm` | Previews a write and requires explicit confirmation before applying it. |
| `action-draft` | Creates an Agent-reviewed draft that can be confirmed or rejected. |
| `action-confirmation` | Confirms or rejects an existing action draft. |
| `artifact-export` | Exports command metadata or documentation. |

## Public Command Groups

| Domain | Representative commands |
| --- | --- |
| System | `status`, `quality-doctor`, `cli-contract`, `list-commands` |
| Workspace | `workspace-create`, `workspace-select`, `workbench` |
| Source | `list-tables`, `inspect-table`, `source-run`, `rename-source`, `delete-source` |
| Evidence | `source-intelligence`, `source-intelligence-runs`, `source-dashboard-draft` |
| Import | `preview-import`, `import-commit`, `set-import-policy`, `list-import-jobs`, `remove-import-job` |
| Semantic | `infer-semantics`, `set-semantic`, `list-semantics`, `field-update` |
| Metric and formula | `infer-metrics`, `add-metric`, `list-metrics`, `query-metric`, `formula-preview`, `save-formula`, `list-formulas`, `delete-formula` |
| Relationship | `recommend-relationships`, `relationship-preview`, `relationship-save`, `query-relationship`, `list-relationships`, `remove-relationship` |
| Query and views | `query`, `query-table`, `save-view`, `list-views`, `copy-view`, `delete-view` |
| Dashboard | `dashboards`, `business-dashboard`, `dashboard-widget-catalog`, `recommend-widgets`, `add-widget`, `set-widget`, `remove-widget`, `copy-widget`, `add-filter`, `set-filter`, `clear-filters`, `save-dashboard-modules`, `erp-unit-library` |
| Agent | `ask`, `action-drafts`, `confirm-action` |
| Connector and config | `list-connectors`, `save-connector`, `sync-connector`, `remove-connector`, `export-config`, `validate-config`, `apply-config` |
| Settings | `preferences`, `theme-palettes` |

## Evidence-Producing Commands

| Command | Output |
| --- | --- |
| `source-intelligence` | Field evidence, table coverage, relationship candidates, metric plans, dashboard candidates, and source run manifest. |
| `preview-import` | Import readability, merge policy, key quality, and evidence bundle manifest. |
| `business-dashboard` | Dashboard draft or confirmed dashboard payload with evidence bundle manifest. |
| `source-dashboard-draft` | Agent action draft from a selected source run. |

## Confirmation Rules

- Write commands default to dry-run or draft behavior.
- `--yes` is required only for commands that explicitly support confirmation.
- Agent-created drafts must be confirmed with `confirm-action`.
- Delete, overwrite, import commit, connector sync, config apply, and index creation must never bypass their confirmation path.

## Regeneration

Use the live command contract when changing CLI code:

```powershell
python tools/bi_cli.py --json cli-contract
python tools/bi_cli.py --json cli-contract --format markdown --output docs/bi-cli-contract.md
python tools/bi_cli.py --json list-commands --domain dashboard --writes yes
```
