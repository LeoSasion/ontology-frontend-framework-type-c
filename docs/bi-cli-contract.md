# BI CLI Contract

Schema: `aibi-bi-cli-contract/v1`
Entrypoint: `python tools/bi_cli.py --json <command>`
Command count: `111`

This file is generated from the live argparse surface. Keep `tools/bi_cli.py` as the source of truth and regenerate this document after changing CLI commands.

## Summary

| Domain | Commands |
|---|---:|
| `agent` | 3 |
| `analysis` | 4 |
| `config` | 3 |
| `connector` | 8 |
| `context` | 6 |
| `dashboard` | 19 |
| `evidence` | 7 |
| `formula` | 4 |
| `import` | 7 |
| `job` | 6 |
| `metric` | 3 |
| `navigation` | 2 |
| `performance` | 2 |
| `query` | 4 |
| `relationship` | 6 |
| `semantic` | 4 |
| `settings` | 2 |
| `source` | 5 |
| `system` | 6 |
| `view` | 4 |
| `workbench` | 1 |
| `workflow` | 1 |
| `workspace` | 4 |

| Mutation mode | Commands |
|---|---:|
| `action-confirmation` | 1 |
| `action-draft` | 2 |
| `artifact-export` | 2 |
| `dry-run-confirm` | 49 |
| `evidence-receipt` | 8 |
| `read-only` | 46 |
| `runtime-receipt` | 3 |

## Commands

| Command | Domain | Mutation | Confirmation | Evidence | Key arguments |
|---|---|---|---|---|---|
| `action-drafts` | `agent` | `read-only` | `no` | `no` | `--limit`, `--all` |
| `add-filter` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--field`, `--operator`, `--value`, `--disabled`, `--yes` |
| `add-metric` | `metric` | `dry-run-confirm` | `yes` | `no` | `--id`, `--name`, `--table`, `--field`, `--agg`, `--dimension`, `--time-field`, `--filter`, `...` |
| `add-recommended-widgets` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--table`, `--limit`, `--allow-duplicates`, `--yes` |
| `add-relationship-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--widget`, `--relationship`, `--type`, `--title`, `--subtitle`, `--group`, `--measure`, `...` |
| `add-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--widget`, `--type`, `--table`, `--view`, `--title`, `--subtitle`, `--dimension`, `...` |
| `analysis-runs` | `evidence` | `read-only` | `no` | `no` | `--run`, `--limit` |
| `analysis-unit-build` | `analysis` | `evidence-receipt` | `no` | `yes` | `--receipt`, `--kind`, `--rows-json`, `--title`, `--preferred-chart` |
| `analysis-unit-verify` | `analysis` | `read-only` | `no` | `no` | `--unit` |
| `analysis-units` | `analysis` | `read-only` | `no` | `no` | `--unit`, `--receipt`, `--limit` |
| `apply-config` | `config` | `dry-run-confirm` | `yes` | `no` | `input`, `--yes` |
| `ask` | `agent` | `action-draft` | `yes` | `no` | `--read-only`, `--parent-run`, `--branch-label`, `--workspace`, `prompt` |
| `business-dashboard` | `dashboard` | `dry-run-confirm` | `yes` | `yes` | `--op`, `--dashboard`, `--name`, `--table`, `--template`, `--limit`, `--yes` |
| `capability-contracts` | `system` | `read-only` | `no` | `no` | `--command`, `--domain` |
| `chart-adapt` | `analysis` | `read-only` | `no` | `no` | `--unit`, `--preferred-chart` |
| `clear-filters` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--yes` |
| `cli-capabilities` | `system` | `read-only` | `no` | `no` | - |
| `cli-contract` | `system` | `artifact-export` | `no` | `no` | `--format`, `--output`, `--command` |
| `confirm-action` | `agent` | `action-confirmation` | `yes` | `no` | `action_key`, `--reject`, `--yes`, `--workspace` |
| `confirm-query` | `context` | `dry-run-confirm` | `yes` | `no` | `--query`, `--status`, `--yes` |
| `confirmed-queries` | `context` | `read-only` | `no` | `no` | `--status`, `--limit` |
| `context-budget` | `context` | `read-only` | `no` | `no` | `--segments-json`, `--max-chars` |
| `context-pack` | `context` | `read-only` | `no` | `no` | - |
| `context-rule` | `context` | `dry-run-confirm` | `yes` | `no` | `--rule`, `--title`, `--statement`, `--type`, `--applies-to`, `--status`, `--source`, `--evidence`, `...` |
| `context-term` | `context` | `dry-run-confirm` | `yes` | `no` | `--term`, `--name`, `--definition`, `--alias`, `--scope-type`, `--scope-ref`, `--status`, `--source`, `...` |
| `copy-view` | `view` | `dry-run-confirm` | `yes` | `no` | `--view`, `--name`, `--tag`, `--yes` |
| `copy-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--widget`, `--dashboard`, `--title`, `--clear-filters`, `--yes` |
| `create-index` | `performance` | `dry-run-confirm` | `yes` | `no` | `--table`, `--field`, `--index`, `--yes` |
| `dashboard-op` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--op`, `--dashboard`, `--source`, `--name`, `--table`, `--yes` |
| `dashboard-widget-catalog` | `dashboard` | `read-only` | `no` | `no` | - |
| `dashboards` | `dashboard` | `read-only` | `no` | `no` | `--dashboard` |
| `delete-formula` | `formula` | `dry-run-confirm` | `yes` | `no` | `formula`, `--yes` |
| `delete-source` | `source` | `dry-run-confirm` | `yes` | `no` | `source`, `--yes` |
| `delete-view` | `view` | `dry-run-confirm` | `yes` | `no` | `--view`, `--yes` |
| `discover-connector` | `connector` | `read-only` | `no` | `no` | `--connector` |
| `erp-unit-library` | `dashboard` | `read-only` | `no` | `no` | `--table`, `--limit`, `--select`, `--summary` |
| `export-analysis` | `evidence` | `artifact-export` | `no` | `no` | `--receipt`, `--unit`, `--output` |
| `export-config` | `config` | `runtime-receipt` | `no` | `no` | `output` |
| `export-evidence` | `evidence` | `evidence-receipt` | `no` | `yes` | `--receipt`, `--output` |
| `field-update` | `semantic` | `dry-run-confirm` | `yes` | `no` | `--table`, `--field`, `--role`, `--usage`, `--confidence`, `--yes` |
| `formula-preview` | `formula` | `read-only` | `no` | `no` | `expression`, `--table`, `--mode` |
| `import-commit` | `import` | `dry-run-confirm` | `yes` | `no` | `file`, `--table`, `--name`, `--mode`, `--unique-fields`, `--conflict-rule`, `--yes` |
| `import-folder` | `import` | `dry-run-confirm` | `yes` | `no` | `path`, `--limit`, `--no-recursive`, `--yes` |
| `infer-metrics` | `metric` | `dry-run-confirm` | `yes` | `no` | `--table`, `--yes` |
| `infer-semantics` | `semantic` | `dry-run-confirm` | `yes` | `no` | `--table`, `--overwrite-manual`, `--yes` |
| `inspect-table` | `source` | `read-only` | `no` | `no` | `table` |
| `job-cancel` | `job` | `dry-run-confirm` | `yes` | `no` | `job`, `--reason`, `--yes` |
| `job-process-exit` | `job` | `runtime-receipt` | `no` | `no` | `--job`, `--workspace`, `--exit-code`, `--signal` |
| `job-recover` | `job` | `dry-run-confirm` | `yes` | `no` | `--all`, `--yes` |
| `jobs` | `job` | `read-only` | `no` | `no` | `--job`, `--status`, `--limit`, `--include-events`, `--events-after`, `--event-limit` |
| `list-commands` | `system` | `read-only` | `no` | `no` | `--domain`, `--mutation-mode`, `--writes` |
| `list-connector-adapters` | `connector` | `read-only` | `no` | `no` | - |
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
| `plan-connector-sync` | `connector` | `read-only` | `no` | `no` | `--connector` |
| `preferences` | `settings` | `dry-run-confirm` | `yes` | `no` | `--theme-key`, `--require-delete-name-confirmation`, `--auto-save-dashboard-on-switch`, `--agent-can-manage-generated-assets`, `--agent-can-manage-manual-assets`, `--yes` |
| `preview-connector` | `connector` | `read-only` | `no` | `no` | `--connector`, `--limit` |
| `preview-import` | `import` | `evidence-receipt` | `no` | `yes` | `file`, `--table`, `--unique-fields`, `--conflict-rule` |
| `preview-import-folder` | `import` | `evidence-receipt` | `no` | `yes` | `path`, `--limit`, `--no-recursive` |
| `quality-doctor` | `system` | `read-only` | `no` | `no` | - |
| `query` | `query` | `evidence-receipt` | `no` | `yes` | `--table`, `--group`, `--measure`, `--agg`, `--limit`, `--request` |
| `query-metric` | `query` | `read-only` | `no` | `no` | `metric`, `--group`, `--filter`, `--sort`, `--limit` |
| `query-receipts` | `evidence` | `read-only` | `no` | `no` | `--receipt`, `--limit` |
| `query-relationship` | `relationship` | `read-only` | `no` | `no` | `--relationship`, `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--map`, `--map-json`, `--join-type`, `...` |
| `query-table` | `query` | `read-only` | `no` | `no` | `--table`, `--view`, `--mode`, `--column`, `--filter`, `--sort`, `--search`, `--offset`, `...` |
| `recommend-indexes` | `performance` | `read-only` | `no` | `no` | `--table`, `--limit` |
| `recommend-relationships` | `relationship` | `read-only` | `no` | `no` | `--limit` |
| `recommend-widgets` | `dashboard` | `read-only` | `no` | `no` | `--table`, `--all`, `--limit` |
| `relationship-preview` | `relationship` | `read-only` | `no` | `no` | `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--map`, `--map-json`, `--filter`, `--filter-json`, `...` |
| `relationship-save` | `relationship` | `dry-run-confirm` | `yes` | `no` | `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--map`, `--map-json`, `--filter`, `--filter-json`, `...` |
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
| `semantic-query` | `query` | `evidence-receipt` | `no` | `yes` | `prompt`, `--table`, `--limit` |
| `set-filter` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--filter`, `--field`, `--operator`, `--value`, `--disabled`, `--yes` |
| `set-import-policy` | `import` | `dry-run-confirm` | `yes` | `no` | `--table`, `--unique-fields`, `--conflict-rule`, `--yes` |
| `set-semantic` | `semantic` | `dry-run-confirm` | `yes` | `no` | `table`, `field`, `--role`, `--tag`, `--usage`, `--confidence`, `--note`, `--yes` |
| `set-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--widget`, `--type`, `--table`, `--view`, `--title`, `--subtitle`, `--dimension`, `--measure`, `...` |
| `source-dashboard-draft` | `evidence` | `action-draft` | `yes` | `no` | `--run`, `--name`, `--limit` |
| `source-intelligence` | `evidence` | `evidence-receipt` | `no` | `yes` | `inputs`, `--workspace`, `--output-dir`, `--label` |
| `source-intelligence-job-create` | `job` | `runtime-receipt` | `no` | `no` | `inputs`, `--workspace`, `--output-dir`, `--label` |
| `source-intelligence-job-run` | `job` | `evidence-receipt` | `no` | `yes` | `--job`, `--workspace` |
| `source-intelligence-runs` | `evidence` | `read-only` | `no` | `no` | `--limit`, `--all` |
| `source-run` | `source` | `read-only` | `no` | `no` | `source_run_id` |
| `status` | `system` | `read-only` | `no` | `no` | - |
| `sync-connector` | `connector` | `dry-run-confirm` | `yes` | `no` | `--connector`, `--allow-paused`, `--yes` |
| `theme-palettes` | `settings` | `dry-run-confirm` | `yes` | `no` | `--action`, `--theme-key`, `--name`, `--mode`, `--tokens-json`, `--sort`, `--yes` |
| `validate-config` | `config` | `read-only` | `no` | `no` | - |
| `workbench` | `workbench` | `read-only` | `no` | `no` | `--limit` |
| `workflow-plan` | `workflow` | `read-only` | `no` | `no` | `target_command`, `--entrypoint`, `--workspace`, `--input-json`, `--confirmed` |
| `workspace-create` | `workspace` | `dry-run-confirm` | `yes` | `no` | `--name`, `--yes` |
| `workspace-delete` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--yes` |
| `workspace-rename` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--name`, `--yes` |
| `workspace-select` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--yes` |
