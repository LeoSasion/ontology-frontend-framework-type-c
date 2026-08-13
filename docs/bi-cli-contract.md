# BI CLI Contract

Schema: `aibi-bi-cli-contract/v1`
Entrypoint: `python tools/aibi_cli.py --json <command>`
Command count: `204`

This file is generated from the live argparse surface. Keep `tools/aibi_cli.py` as the source of truth and regenerate this document after changing CLI commands.

## Summary

| Domain | Commands |
|---|---:|
| `agent` | 18 |
| `analysis` | 37 |
| `analytical-skill` | 6 |
| `config` | 3 |
| `connector` | 18 |
| `context` | 9 |
| `dashboard` | 19 |
| `domain-pack` | 5 |
| `evidence` | 8 |
| `formula` | 4 |
| `import` | 7 |
| `job` | 11 |
| `metric` | 3 |
| `navigation` | 2 |
| `performance` | 2 |
| `query` | 4 |
| `relationship` | 6 |
| `semantic` | 8 |
| `settings` | 2 |
| `source` | 5 |
| `system` | 6 |
| `view` | 4 |
| `workbench` | 1 |
| `workflow` | 4 |
| `workspace` | 6 |
| `workspace-recovery` | 6 |

| Mutation mode | Commands |
|---|---:|
| `action-confirmation` | 1 |
| `action-draft` | 2 |
| `artifact-export` | 2 |
| `dry-run-confirm` | 81 |
| `evidence-receipt` | 15 |
| `read-only` | 88 |
| `runtime-receipt` | 15 |

## Commands

| Command | Domain | Mutation | Confirmation | Evidence | Key arguments |
|---|---|---|---|---|---|
| `action-drafts` | `agent` | `read-only` | `no` | `no` | `--limit`, `--all` |
| `add-filter` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--field`, `--operator`, `--value`, `--disabled`, `--yes` |
| `add-metric` | `metric` | `dry-run-confirm` | `yes` | `no` | `--id`, `--name`, `--table`, `--field`, `--agg`, `--dimension`, `--time-field`, `--filter`, `...` |
| `add-recommended-widgets` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--table`, `--limit`, `--allow-duplicates`, `--yes` |
| `add-relationship-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--widget`, `--relationship`, `--type`, `--title`, `--subtitle`, `--group`, `--measure`, `...` |
| `add-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--widget`, `--type`, `--table`, `--view`, `--title`, `--subtitle`, `--dimension`, `...` |
| `agent-context-compact` | `agent` | `runtime-receipt` | `no` | `no` | `--session`, `--level`, `--workspace` |
| `agent-provider-evaluation-record` | `agent` | `runtime-receipt` | `no` | `no` | `--workspace`, `--profile`, `--profile-fingerprint`, `--provider`, `--model`, `--request-fingerprint`, `--context-fingerprint`, `--status`, `...` |
| `agent-provider-evaluations` | `agent` | `read-only` | `no` | `no` | `--workspace`, `--limit` |
| `agent-runtime-profile-set` | `agent` | `dry-run-confirm` | `yes` | `no` | `--profile`, `--workspace`, `--yes` |
| `agent-runtime-profiles` | `agent` | `read-only` | `no` | `no` | `--workspace` |
| `agent-session-create` | `agent` | `runtime-receipt` | `no` | `no` | `--title`, `--workspace` |
| `agent-session-fork` | `agent` | `runtime-receipt` | `no` | `no` | `session`, `--from-turn`, `--title`, `--workspace` |
| `agent-session-resume` | `agent` | `read-only` | `no` | `no` | `session`, `--workspace` |
| `agent-sessions` | `agent` | `read-only` | `no` | `no` | `--session`, `--workspace`, `--limit` |
| `agent-turn-cancel` | `agent` | `runtime-receipt` | `no` | `no` | `turn`, `--workspace` |
| `agent-turn-run` | `agent` | `runtime-receipt` | `no` | `no` | `prompt`, `--workspace`, `--parent-turn`, `--parent-run`, `--branch-label`, `--session`, `--review-stale-context`, `--read-only` |
| `agent-turns` | `agent` | `read-only` | `no` | `no` | `--workspace`, `--turn`, `--after-sequence`, `--limit` |
| `agent-workflow-graph` | `workflow` | `read-only` | `no` | `no` | `--turn`, `--workspace` |
| `analysis-runs` | `evidence` | `read-only` | `no` | `no` | `--run`, `--limit` |
| `analysis-snapshot-create` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--unit`, `--reason`, `--row-limit`, `--expected-plan`, `--yes` |
| `analysis-snapshot-delete` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--snapshot`, `--expected-plan`, `--yes` |
| `analysis-snapshot-refresh` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--snapshot`, `--unit`, `--reason`, `--row-limit`, `--expected-plan`, `--yes` |
| `analysis-snapshot-replace` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--snapshot`, `--unit`, `--reason`, `--row-limit`, `--expected-plan`, `--yes` |
| `analysis-snapshots` | `analysis` | `read-only` | `no` | `no` | `--snapshot`, `--unit`, `--status`, `--limit` |
| `analysis-unit-build` | `analysis` | `evidence-receipt` | `no` | `yes` | `--receipt`, `--kind`, `--rows-json`, `--title`, `--preferred-chart` |
| `analysis-unit-verify` | `analysis` | `read-only` | `no` | `no` | `--unit` |
| `analysis-units` | `analysis` | `read-only` | `no` | `no` | `--unit`, `--receipt`, `--limit` |
| `analytical-skill-install` | `analytical-skill` | `dry-run-confirm` | `yes` | `no` | `--manifest`, `--yes` |
| `analytical-skill-lint` | `analytical-skill` | `read-only` | `no` | `no` | `--manifest` |
| `analytical-skill-match` | `analytical-skill` | `read-only` | `no` | `no` | `--task-type`, `--role`, `--domain-pack`, `--skill`, `--workspace` |
| `analytical-skill-set` | `analytical-skill` | `dry-run-confirm` | `yes` | `no` | `--skill`, `--state`, `--workspace`, `--yes` |
| `analytical-skill-uninstall` | `analytical-skill` | `dry-run-confirm` | `yes` | `no` | `--skill`, `--yes` |
| `analytical-skills` | `analytical-skill` | `read-only` | `no` | `no` | `--workspace` |
| `apply-config` | `config` | `dry-run-confirm` | `yes` | `no` | `input`, `--yes` |
| `ask` | `agent` | `action-draft` | `yes` | `no` | `--read-only`, `--parent-run`, `--branch-label`, `--workspace`, `prompt` |
| `business-dashboard` | `dashboard` | `dry-run-confirm` | `yes` | `yes` | `--op`, `--dashboard`, `--name`, `--table`, `--template`, `--limit`, `--yes` |
| `business-expression-cases` | `agent` | `read-only` | `no` | `no` | - |
| `business-field-profiles` | `semantic` | `read-only` | `no` | `no` | `--workspace`, `--table`, `--field` |
| `capability-contracts` | `system` | `read-only` | `no` | `no` | `--command`, `--domain` |
| `chart-adapt` | `analysis` | `read-only` | `no` | `no` | `--unit`, `--preferred-chart` |
| `clear-filters` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--yes` |
| `cli-capabilities` | `system` | `read-only` | `no` | `no` | - |
| `cli-contract` | `system` | `artifact-export` | `no` | `no` | `--format`, `--output`, `--command` |
| `confirm-action` | `agent` | `action-confirmation` | `yes` | `no` | `action_key`, `--reject`, `--yes`, `--workspace` |
| `confirm-query` | `context` | `dry-run-confirm` | `yes` | `no` | `--query`, `--status`, `--yes` |
| `confirmed-plans` | `context` | `read-only` | `no` | `no` | `--status`, `--limit` |
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
| `decision-framework-create` | `analysis` | `runtime-receipt` | `no` | `no` | `--unit`, `--framework-type`, `--title`, `--request-key` |
| `decision-framework-export` | `analysis` | `read-only` | `no` | `no` | `--framework` |
| `decision-framework-publish` | `analysis` | `dry-run-confirm` | `yes` | `yes` | `--framework`, `--yes`, `--expected-plan` |
| `decision-framework-save` | `analysis` | `runtime-receipt` | `no` | `no` | `--framework`, `--title`, `--claims-json`, `--expected-content` |
| `decision-frameworks` | `analysis` | `read-only` | `no` | `no` | `--framework`, `--unit`, `--limit` |
| `delete-formula` | `formula` | `dry-run-confirm` | `yes` | `no` | `formula`, `--yes` |
| `delete-source` | `source` | `dry-run-confirm` | `yes` | `no` | `source`, `--yes` |
| `delete-view` | `view` | `dry-run-confirm` | `yes` | `no` | `--view`, `--yes` |
| `discover-connector` | `connector` | `read-only` | `no` | `no` | `--connector` |
| `domain-pack-install` | `domain-pack` | `dry-run-confirm` | `yes` | `no` | `--package`, `--yes` |
| `domain-pack-lint` | `domain-pack` | `read-only` | `no` | `no` | `--package` |
| `domain-pack-set` | `domain-pack` | `dry-run-confirm` | `yes` | `no` | `--pack`, `--state`, `--workspace`, `--yes` |
| `domain-pack-uninstall` | `domain-pack` | `dry-run-confirm` | `yes` | `no` | `--pack`, `--yes` |
| `domain-packs` | `domain-pack` | `read-only` | `no` | `no` | `--workspace` |
| `erp-unit-library` | `dashboard` | `read-only` | `no` | `no` | `--table`, `--limit`, `--select`, `--summary` |
| `evidence-retrieval-evaluate` | `analysis` | `evidence-receipt` | `no` | `yes` | `--provider-profile` |
| `evidence-retrieval-receipts` | `analysis` | `read-only` | `no` | `no` | `--limit` |
| `evidence-retrieval-status` | `analysis` | `read-only` | `no` | `no` | - |
| `exploration-anchor-add` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--thread`, `--parent-anchor`, `--run`, `--unit`, `--session`, `--turn`, `--label`, `--expected-plan`, `...` |
| `exploration-board-set` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--thread`, `--anchor`, `--state`, `--position`, `--expected-plan`, `--yes` |
| `exploration-thread-create` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--run`, `--unit`, `--session`, `--turn`, `--title`, `--label`, `--expected-plan`, `--yes` |
| `exploration-threads` | `analysis` | `read-only` | `no` | `no` | `--thread`, `--limit` |
| `export-analysis` | `evidence` | `artifact-export` | `no` | `no` | `--receipt`, `--unit`, `--output` |
| `export-config` | `config` | `runtime-receipt` | `no` | `no` | `output` |
| `export-evidence` | `evidence` | `evidence-receipt` | `no` | `yes` | `--receipt`, `--output` |
| `federation-proof` | `connector` | `read-only` | `no` | `no` | `--connectors`, `--projections`, `--relationships`, `--grain`, `--entity-key`, `--filters`, `--max-sources`, `--max-fields`, `...` |
| `field-update` | `semantic` | `dry-run-confirm` | `yes` | `no` | `--table`, `--field`, `--role`, `--usage`, `--confidence`, `--yes` |
| `forecast-readiness` | `analysis` | `read-only` | `no` | `no` | `--unit`, `--horizon` |
| `formula-preview` | `formula` | `read-only` | `no` | `no` | `expression`, `--table`, `--mode` |
| `import-commit` | `import` | `dry-run-confirm` | `yes` | `no` | `file`, `--table`, `--name`, `--mode`, `--unique-fields`, `--conflict-rule`, `--expected-plan`, `--require-plan`, `...` |
| `import-folder` | `import` | `dry-run-confirm` | `yes` | `no` | `path`, `--limit`, `--no-recursive`, `--unique-fields`, `--conflict-rule`, `--expected-plan`, `--yes` |
| `import-job-create` | `job` | `evidence-receipt` | `no` | `yes` | `--import-kind`, `--path`, `--request-key`, `--expected-plan`, `--workspace`, `--label`, `--table`, `--name`, `...` |
| `import-job-process-exit` | `job` | `evidence-receipt` | `no` | `yes` | `--job`, `--workspace`, `--exit-code`, `--signal`, `--lease-token` |
| `import-job-recover` | `job` | `evidence-receipt` | `no` | `yes` | `--workspace`, `--all` |
| `import-job-resume` | `job` | `evidence-receipt` | `no` | `yes` | `--job`, `--workspace` |
| `import-job-run` | `job` | `evidence-receipt` | `no` | `yes` | `--job`, `--workspace`, `--lease-token` |
| `infer-metrics` | `metric` | `dry-run-confirm` | `yes` | `no` | `--table`, `--yes` |
| `infer-semantics` | `semantic` | `dry-run-confirm` | `yes` | `no` | `--table`, `--overwrite-manual`, `--yes` |
| `inspect-table` | `source` | `read-only` | `no` | `no` | `table` |
| `job-cancel` | `job` | `dry-run-confirm` | `yes` | `no` | `job`, `--reason`, `--yes` |
| `job-process-exit` | `job` | `runtime-receipt` | `no` | `no` | `--job`, `--workspace`, `--exit-code`, `--signal` |
| `job-recover` | `job` | `dry-run-confirm` | `yes` | `no` | `--all`, `--yes` |
| `jobs` | `job` | `read-only` | `no` | `no` | `--job`, `--status`, `--limit`, `--include-events`, `--events-after`, `--event-limit` |
| `knowledge-source-adapters` | `context` | `read-only` | `no` | `no` | - |
| `knowledge-sources` | `context` | `read-only` | `no` | `no` | `--workspace`, `--limit` |
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
| `metric-monitor-create` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--snapshot`, `--label`, `--metric`, `--cadence`, `--strategy`, `--direction`, `--threshold`, `--warning-ratio`, `...` |
| `metric-monitor-delete` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--monitor`, `--expected-plan`, `--yes` |
| `metric-monitor-replace` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--monitor`, `--snapshot`, `--label`, `--metric`, `--cadence`, `--strategy`, `--direction`, `--threshold`, `...` |
| `metric-monitor-run` | `analysis` | `evidence-receipt` | `no` | `yes` | `--monitor`, `--snapshot` |
| `metric-monitors` | `analysis` | `read-only` | `no` | `no` | `--monitor`, `--status`, `--limit` |
| `navigation-op` | `navigation` | `dry-run-confirm` | `yes` | `no` | `--module`, `--op`, `--name`, `--sort`, `--yes` |
| `plan-connector-sync` | `connector` | `read-only` | `no` | `no` | `--connector` |
| `plan-quality-evaluate` | `agent` | `runtime-receipt` | `no` | `no` | `--workspace` |
| `plan-quality-scorecards` | `agent` | `read-only` | `no` | `no` | `--workspace`, `--limit` |
| `preferences` | `settings` | `dry-run-confirm` | `yes` | `no` | `--theme-key`, `--require-delete-name-confirmation`, `--auto-save-dashboard-on-switch`, `--agent-can-manage-generated-assets`, `--agent-can-manage-manual-assets`, `--yes` |
| `preview-connector` | `connector` | `read-only` | `no` | `no` | `--connector`, `--limit` |
| `preview-import` | `import` | `evidence-receipt` | `no` | `yes` | `file`, `--table`, `--unique-fields`, `--conflict-rule` |
| `preview-import-folder` | `import` | `evidence-receipt` | `no` | `yes` | `path`, `--limit`, `--no-recursive`, `--unique-fields`, `--conflict-rule` |
| `quality-doctor` | `system` | `read-only` | `no` | `no` | - |
| `query` | `query` | `evidence-receipt` | `no` | `yes` | `--table`, `--group`, `--measure`, `--agg`, `--limit`, `--request` |
| `query-metric` | `query` | `read-only` | `no` | `no` | `metric`, `--group`, `--filter`, `--sort`, `--limit` |
| `query-receipts` | `evidence` | `read-only` | `no` | `no` | `--receipt`, `--limit` |
| `query-relationship` | `relationship` | `read-only` | `no` | `no` | `--relationship`, `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--map`, `--map-json`, `--join-type`, `...` |
| `query-table` | `query` | `read-only` | `no` | `no` | `--table`, `--view`, `--mode`, `--column`, `--filter`, `--sort`, `--search`, `--offset`, `...` |
| `recall-receipts` | `evidence` | `read-only` | `no` | `no` | `--receipt`, `--limit` |
| `recommend-indexes` | `performance` | `read-only` | `no` | `no` | `--table`, `--limit` |
| `recommend-relationships` | `relationship` | `read-only` | `no` | `no` | `--limit` |
| `recommend-widgets` | `dashboard` | `read-only` | `no` | `no` | `--table`, `--all`, `--limit` |
| `relationship-preview` | `relationship` | `read-only` | `no` | `no` | `--workspace`, `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--map`, `--map-json`, `--filter`, `...` |
| `relationship-save` | `relationship` | `dry-run-confirm` | `yes` | `no` | `--workspace`, `--left-table`, `--right-table`, `--left-field`, `--right-field`, `--map`, `--map-json`, `--filter`, `...` |
| `remove-connector` | `connector` | `dry-run-confirm` | `yes` | `no` | `--connector`, `--yes` |
| `remove-filter` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--filter`, `--yes` |
| `remove-import-job` | `import` | `dry-run-confirm` | `yes` | `no` | `--job`, `--yes` |
| `remove-relationship` | `relationship` | `dry-run-confirm` | `yes` | `no` | `--relationship`, `--yes` |
| `remove-stale-filters` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--yes` |
| `remove-widget` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--widget`, `--yes` |
| `rename-source` | `source` | `dry-run-confirm` | `yes` | `no` | `source`, `--name`, `--yes` |
| `research-run-create` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--thread`, `--anchor`, `--goal`, `--skill`, `--hypothesis`, `--counterexample`, `--sensitivity`, `--max-observations`, `...` |
| `research-run-finalize` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--research`, `--expected-revision`, `--expected-plan`, `--yes` |
| `research-run-observe` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--research`, `--anchor`, `--kind`, `--step`, `--verdict`, `--note`, `--expected-revision`, `--expected-plan`, `...` |
| `research-run-revise` | `analysis` | `dry-run-confirm` | `yes` | `no` | `--research`, `--reason`, `--goal`, `--skill`, `--hypothesis`, `--counterexample`, `--sensitivity`, `--clear-hypotheses`, `...` |
| `research-runs` | `analysis` | `read-only` | `no` | `no` | `--research`, `--limit` |
| `restricted-workflow-operators` | `workflow` | `read-only` | `no` | `no` | - |
| `restricted-workflow-validate` | `workflow` | `read-only` | `no` | `no` | `--graph-json`, `--workspace` |
| `reviewed-publication-deprecate` | `analysis` | `dry-run-confirm` | `yes` | `yes` | `--publication`, `--reason`, `--expected-head`, `--yes` |
| `reviewed-publication-export` | `analysis` | `read-only` | `no` | `no` | `--publication`, `--skill-fingerprint`, `--forensic` |
| `reviewed-publication-plan` | `analysis` | `read-only` | `no` | `no` | `--memory`, `--unit`, `--title`, `--content-json`, `--skill-fingerprint` |
| `reviewed-publication-publish` | `analysis` | `dry-run-confirm` | `yes` | `yes` | `--memory`, `--unit`, `--title`, `--content-json`, `--skill-fingerprint`, `--expected-plan`, `--yes` |
| `reviewed-publications` | `analysis` | `read-only` | `no` | `no` | `--publication`, `--status`, `--skill-fingerprint`, `--limit` |
| `runtime-catalog` | `workspace` | `read-only` | `no` | `no` | `--workspace` |
| `save-connector` | `connector` | `dry-run-confirm` | `yes` | `no` | `--connector`, `--name`, `--type`, `--provider`, `--status`, `--endpoint`, `--resource`, `--page-param`, `...` |
| `save-dashboard-modules` | `dashboard` | `dry-run-confirm` | `yes` | `no` | `--dashboard`, `--name`, `--default-table`, `--canvas-width-mode`, `--widgets-json`, `--layout-json`, `--filters-json`, `--yes` |
| `save-formula` | `formula` | `dry-run-confirm` | `yes` | `no` | `--id`, `--name`, `--table`, `--expression`, `--mode`, `--dimension`, `--time-field`, `--value-format`, `...` |
| `save-view` | `view` | `dry-run-confirm` | `yes` | `no` | `--view`, `--table`, `--name`, `--tag`, `--mode`, `--columns`, `--filter`, `--sort`, `...` |
| `semantic-patch-proposals` | `semantic` | `read-only` | `no` | `no` | `--workspace`, `--proposal`, `--status`, `--limit` |
| `semantic-patch-propose` | `semantic` | `dry-run-confirm` | `yes` | `no` | `--workspace`, `--input`, `--adapter`, `--source-type`, `--source-name`, `--kind`, `--term`, `--name`, `...` |
| `semantic-patch-review` | `semantic` | `dry-run-confirm` | `yes` | `no` | `--workspace`, `--proposal`, `--decision`, `--note`, `--yes` |
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
| `sqlserver-adapter-activate` | `connector` | `dry-run-confirm` | `yes` | `yes` | `--connector`, `--workspace`, `--request-key`, `--expected-plan`, `--expected-manifest`, `--yes` |
| `sqlserver-adapter-activation-finalize` | `connector` | `dry-run-confirm` | `yes` | `yes` | `--job`, `--workspace`, `--all`, `--yes` |
| `sqlserver-adapter-activation-status` | `connector` | `read-only` | `no` | `no` | `--connector`, `--workspace`, `--request-key`, `--expected-plan`, `--expected-manifest` |
| `sqlserver-adapter-discover` | `connector` | `runtime-receipt` | `no` | `no` | `--connector`, `--max-tables`, `--max-columns`, `--timeout` |
| `sqlserver-adapter-plan` | `connector` | `runtime-receipt` | `no` | `no` | `--connector`, `--request-key`, `--catalog`, `--selections-json`, `--budget-json` |
| `sqlserver-adapter-preview` | `connector` | `read-only` | `no` | `no` | `--connector`, `--catalog`, `--resources`, `--sample-rows`, `--timeout` |
| `sqlserver-adapter-probe` | `connector` | `read-only` | `no` | `no` | `--connector` |
| `sqlserver-adapter-snapshot` | `connector` | `dry-run-confirm` | `yes` | `yes` | `--connector`, `--request-key`, `--expected-plan`, `--yes` |
| `sqlserver-adapter-test` | `connector` | `read-only` | `no` | `no` | `--connector`, `--timeout` |
| `status` | `system` | `read-only` | `no` | `no` | - |
| `sync-connector` | `connector` | `dry-run-confirm` | `yes` | `no` | `--connector`, `--allow-paused`, `--yes` |
| `theme-palettes` | `settings` | `dry-run-confirm` | `yes` | `no` | `--action`, `--theme-key`, `--name`, `--mode`, `--tokens-json`, `--sort`, `--yes` |
| `validate-config` | `config` | `read-only` | `no` | `no` | - |
| `workbench` | `workbench` | `read-only` | `no` | `no` | `--limit` |
| `workflow-plan` | `workflow` | `read-only` | `no` | `no` | `target_command`, `--entrypoint`, `--workspace`, `--input-json`, `--confirmed` |
| `workspace-create` | `workspace` | `dry-run-confirm` | `yes` | `no` | `--name`, `--yes` |
| `workspace-delete` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--request-key`, `--expected-plan`, `--yes` |
| `workspace-manifest` | `workspace` | `read-only` | `no` | `no` | `--workspace` |
| `workspace-recovery-create` | `workspace-recovery` | `dry-run-confirm` | `yes` | `no` | `--workspace`, `--reason`, `--request-key`, `--expected-plan`, `--yes` |
| `workspace-recovery-delete` | `workspace-recovery` | `dry-run-confirm` | `yes` | `no` | `--workspace`, `--recovery-point`, `--request-key`, `--expected-plan`, `--yes` |
| `workspace-recovery-inspect` | `workspace-recovery` | `read-only` | `no` | `no` | `--workspace`, `--recovery-point` |
| `workspace-recovery-list` | `workspace-recovery` | `read-only` | `no` | `no` | `--workspace`, `--limit`, `--verify` |
| `workspace-recovery-reconcile` | `workspace-recovery` | `runtime-receipt` | `no` | `no` | `--all` |
| `workspace-recovery-restore` | `workspace-recovery` | `dry-run-confirm` | `yes` | `no` | `--workspace`, `--recovery-point`, `--request-key`, `--expected-plan`, `--yes` |
| `workspace-rename` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--name`, `--yes` |
| `workspace-select` | `workspace` | `dry-run-confirm` | `yes` | `no` | `workspace`, `--yes` |
