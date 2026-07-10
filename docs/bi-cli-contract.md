# BI CLI Contract

Schema: `aibi-bi-cli-contract/v1`
Entrypoint: `python tools/bi_cli.py --json <command>`
Command count: `84`

This file is generated from the live argparse surface. Keep `tools/bi_cli.py` as the source of truth and regenerate this document after changing CLI commands.

## Summary

| Domain | Commands |
|---|---:|
| `agent` | 3 |
| `config` | 3 |
| `connector` | 4 |
| `dashboard` | 19 |
| `evidence` | 3 |
| `formula` | 4 |
| `import` | 7 |
| `integration` | 1 |
| `metric` | 3 |
| `navigation` | 2 |
| `performance` | 2 |
| `query` | 3 |
| `relationship` | 6 |
| `semantic` | 4 |
| `settings` | 2 |
| `source` | 5 |
| `system` | 4 |
| `view` | 4 |
| `workbench` | 1 |
| `workspace` | 4 |

| Mutation mode | Commands |
|---|---:|
| `action-confirmation` | 1 |
| `action-draft` | 2 |
| `artifact-export` | 1 |
| `dry-run-confirm` | 44 |
| `evidence-receipt` | 3 |
| `read-only` | 32 |
| `runtime-receipt` | 1 |

## Commands

| Command | Domain | Mutation | Confirmation | Evidence | Key arguments |
|---|---|---|---|---|---|
| `action-drafts` | `agent` | `read-only` | `no` | `no` | `--limit`, `--all` |
| `add-filter` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--field`, `--operator`, `--value`, `--disabled`, `--yes` |
| `add-metric` | `metric` | `dry-run-confirm` | `yes` | `no` | `--id`, `--name`, `--table`, `--field`, `--agg`, `--dimension`, `--time-field`, `--filter`, `...` |
| `add-recommended-widgets` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--table`, `--limit`, `--allow-duplicates`, `--yes` |
| `add-relationship-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--widget`, `--relationship`, `--type`, `--title`, `--subtitle`, `--group`, `--measure`, `...` |
| `add-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--widget`, `--type`, `--table`, `--view`, `--title`, `--subtitle`, `--dimension`, `...` |
| `apply-config` | `config` | `dry-run-confirm` | `yes` | `no` | `input`, `--yes` |
| `ask` | `agent` | `action-draft` | `yes` | `no` | `--read-only`, `prompt` |
| `b-cli-capabilities` | `integration` | `read-only` | `no` | `no` | - |
| `business-dashboard` | `dashboard` | `dry-run-confirm` | `yes` | `yes` | `--op`, `--dashboard`, `--name`, `--table`, `--template`, `--limit`, `--yes` |
| `clear-filters` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--yes` |
| `cli-contract` | `system` | `artifact-export` | `no` | `no` | `--format`, `--output`, `--command` |
| `confirm-action` | `agent` | `action-confirmation` | `yes` | `no` | `action_key`, `--reject`, `--yes` |
| `copy-view` | `view` | `dry-run-confirm` | `yes` | `no` | `--view`, `--name`, `--tag`, `--yes` |
| `copy-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--widget`, `--dashboard`, `--title`, `--clear-filters`, `--yes` |
| `create-index` | `performance` | `dry-run-confirm` | `yes` | `no` | `--table`, `--field`, `--index`, `--yes` |
| `dashboard-op` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--op`, `--dashboard`, `--source`, `--name`, `--table`, `--yes` |
| `dashboard-widget-catalog` | `dashboard` | `read-only` | `no` | `no` | - |
| `dashboards` | `dashboard` | `read-only` | `no` | `no` | `--dashboard` |
| `delete-formula` | `formula` | `dry-run-confirm` | `yes` | `no` | `formula`, `--yes` |
| `delete-source` | `source` | `dry-run-confirm` | `yes` | `no` | `source`, `--yes` |
| `delete-view` | `view` | `dry-run-confirm` | `yes` | `no` | `--view`, `--yes` |
| `erp-unit-library` | `dashboard` | `read-only` | `no` | `no` | `--table`, `--limit`, `--select`, `--summary` |
| `export-config` | `config` | `runtime-receipt` | `no` | `no` | `output` |
| `field-update` | `semantic` | `dry-run-confirm` | `yes` | `no` | `--table`, `--field`, `--role`, `--usage`, `--confidence`, `--yes` |
| `formula-preview` | `formula` | `read-only` | `no` | `no` | `expression`, `--table`, `--mode` |
| `import-commit` | `import` | `dry-run-confirm` | `yes` | `no` | `file`, `--table`, `--name`, `--mode`, `--unique-fields`, `--conflict-rule`, `--yes` |
| `import-folder` | `import` | `dry-run-confirm` | `yes` | `no` | `path`, `--limit`, `--no-recursive`, `--yes` |
| `infer-metrics` | `metric` | `dry-run-confirm` | `yes` | `no` | `--table`, `--yes` |
| `infer-semantics` | `semantic` | `dry-run-confirm` | `yes` | `no` | `--table`, `--overwrite-manual`, `--yes` |
| `inspect-table` | `source` | `read-only` | `no` | `no` | `table` |
| `list-commands` | `system` | `read-only` | `no` | `no` | `--domain`, `--mutation-mode`, `--writes` |
| `list-connectors` | `connector` | `read-only` | `no` | `no` | `--type`, `--status`, `--search` |
| `list-filters` | `dashboard` | `read-only` | `no` | `no` | `--dashboard` |
| `list-formulas` | `formula` | `read-only` | `no` | `no` | `--table`, `--all` |
| `list-import-jobs` | `import` | `read-only` | `no` | `no` | `--table`, `--status`, `--search`, `--limit` |
| `list-metrics` | `metric` | `read-only` | `no` | `no` | `--table`, `--all` |
| `list-navigation` | `navigation` | `read-only` | `no` | `no` | `--all` |
| `list-relationships` | `relationship` | `read-only` | `no` | `no` | - |
| `list-semantics` | `semantic` | `read-only` | `no` | `no` | `--table` |
| `list-tables` | `source` | `read-only` | `no` | `no` | - |
| `list-views` | `view` | `read-only` | `no` | `no` | `--table` |
| `navigation-op` | `navigation` | `dry-run-confirm` | `yes` | `no` | `--module`, `--op`, `--name`, `--sort`, `--yes` |
| `preferences` | `settings` | `dry-run-confirm` | `yes` | `no` | `--theme-key`, `--require-delete-name-confirmation`, `--auto-save-dashboard-on-switch`, `--agent-can-manage-generated-assets`, `--agent-can-manage-manual-assets`, `--yes` |
| `preview-import` | `import` | `evidence-receipt` | `no` | `yes` | `file`, `--table`, `--unique-fields`, `--conflict-rule` |
| `preview-import-folder` | `import` | `evidence-receipt` | `no` | `yes` | `path`, `--limit`, `--no-recursive` |
| `quality-doctor` | `system` | `read-only` | `no` | `no` | - |
| `query` | `query` | `read-only` | `no` | `no` | `--table`, `--group`, `--measure`, `--agg`, `--limit` |
| `query-metric` | `query` | `read-only` | `no` | `no` | `metric`, `--group`, `--filter`, `--sort`, `--limit` |
| `query-relationship` | `relationship` | `read-only` | `no` | `no` | `--relationship`, `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--join-type`, `--group`, `--measure`, `...` |
| `query-table` | `query` | `read-only` | `no` | `no` | `--table`, `--view`, `--mode`, `--column`, `--filter`, `--sort`, `--search`, `--offset`, `...` |
| `recommend-indexes` | `performance` | `read-only` | `no` | `no` | `--table`, `--limit` |
| `recommend-relationships` | `relationship` | `read-only` | `no` | `no` | `--limit` |
| `recommend-widgets` | `dashboard` | `read-only` | `no` | `no` | `--table`, `--all`, `--limit` |
| `relationship-preview` | `relationship` | `read-only` | `no` | `no` | `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--join-type`, `--limit` |
| `relationship-save` | `relationship` | `dry-run-confirm` | `yes` | `no` | `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--join-type`, `--limit`, `--yes` |
| `remove-connector` | `connector` | `dry-run-confirm` | `yes` | `no` | `--connector`, `--yes` |
| `remove-filter` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--filter`, `--yes` |
| `remove-import-job` | `import` | `dry-run-confirm` | `yes` | `no` | `--job`, `--yes` |
| `remove-relationship` | `relationship` | `dry-run-confirm` | `yes` | `no` | `--relationship`, `--yes` |
| `remove-stale-filters` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--yes` |
| `remove-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--widget`, `--yes` |
| `rename-source` | `source` | `dry-run-confirm` | `yes` | `no` | `source`, `--name`, `--yes` |
| `save-connector` | `connector` | `dry-run-confirm` | `yes` | `no` | `--connector`, `--name`, `--type`, `--provider`, `--status`, `--endpoint`, `--import-mode`, `--target-table`, `...` |
| `save-dashboard-modules` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--name`, `--default-table`, `--canvas-width-mode`, `--widgets-json`, `--layout-json`, `--filters-json`, `--yes` |
| `save-formula` | `formula` | `dry-run-confirm` | `yes` | `no` | `--id`, `--name`, `--table`, `--expression`, `--mode`, `--dimension`, `--time-field`, `--value-format`, `...` |
| `save-view` | `view` | `dry-run-confirm` | `yes` | `no` | `--view`, `--table`, `--name`, `--tag`, `--mode`, `--columns`, `--filter`, `--sort`, `...` |
| `set-filter` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--filter`, `--field`, `--operator`, `--value`, `--disabled`, `--yes` |
| `set-import-policy` | `import` | `dry-run-confirm` | `yes` | `no` | `--table`, `--unique-fields`, `--conflict-rule`, `--yes` |
| `set-semantic` | `semantic` | `dry-run-confirm` | `yes` | `no` | `table`, `field`, `--role`, `--tag`, `--usage`, `--confidence`, `--note`, `--yes` |
| `set-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--widget`, `--type`, `--table`, `--view`, `--title`, `--subtitle`, `--dimension`, `--measure`, `...` |
| `source-dashboard-draft` | `evidence` | `action-draft` | `yes` | `no` | `--run`, `--name`, `--limit` |
| `source-intelligence` | `evidence` | `evidence-receipt` | `no` | `yes` | `inputs`, `--output-dir`, `--label` |
| `source-intelligence-runs` | `evidence` | `read-only` | `no` | `no` | `--limit`, `--all` |
| `source-run` | `source` | `read-only` | `no` | `no` | `source_run_id` |
| `status` | `system` | `read-only` | `no` | `no` | - |
| `sync-connector` | `connector` | `dry-run-confirm` | `yes` | `no` | `--connector`, `--allow-paused`, `--yes` |
| `theme-palettes` | `settings` | `dry-run-confirm` | `yes` | `no` | `--action`, `--theme-key`, `--name`, `--mode`, `--tokens-json`, `--sort`, `--yes` |
| `validate-config` | `config` | `read-only` | `no` | `no` | - |
| `workbench` | `workbench` | `read-only` | `no` | `no` | `--limit` |
| `workspace-create` | `workspace` | `dry-run-confirm` | `yes` | `no` | `--name`, `--yes` |
| `workspace-delete` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--yes` |
| `workspace-rename` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--name`, `--yes` |
| `workspace-select` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--yes` |
