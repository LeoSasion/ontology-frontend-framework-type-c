# AIBI-C Implementation Status

Current stage: local production baseline for a single-user workstation. The release is single-user and local-only; user data may live outside the repository in configured local paths.

## Current Release Boundary

| Layer | Implementation | Boundary |
| --- | --- | --- |
| Client | React 19 + Vite desktop workbench | Progressive disclosure; no mobile-native client |
| Local API | Node/TypeScript route facade | Loopback, bounded body, exact-origin optional CORS |
| BI runtime | Python CLI + SQLite metadata + DuckDB analytics | Whitelisted parameters; no arbitrary user SQL |
| Storage | Local databases and user-selected files | No cloud sync, tenant storage or repository seeding |
| Agent | Deterministic resolution with optional model provider | Read-only answers and confirmed write drafts remain separate |
| Evidence | Source, query, action, delete and recovery receipts | Business summary first; raw diagnostics collapsed |

## Capability Status

| Capability | Status | Current contract |
| --- | --- | --- |
| Clean first run | Stable | No tables, charts, dashboards, answers or sample shortcuts. Product activation shows only the current necessary step. |
| File/folder import and profiling | Stable | CSV/XLSX/XLSM preview, same-type grouping, merge and dedup impact, key quality, confirmation, field/quality/relationship evidence. |
| AI one-chart flow | Stable | Generic questions do not choose domain fields; vague charts clarify once; explicit requests create one confirmable draft. |
| Details and saved views | Stable | Whitelisted query, search, filter, sort, save/copy/delete and contextual handoff. |
| Dashboard editor | Stable advanced | Metric, bar, line, pie, table, text, slicer, relationship, filter, drilldown, lifecycle and style controls remain progressively disclosed. |
| Full industry dashboard | Beta | Evidence-matched units, omitted-unit disclosure, preview and existing confirmation boundary. |
| Controlled writes and deletes | Stable | Dry-run or draft first; one confirmation; explicit rejection, dependency impact and receipt. |
| Trusted analysis | Stable advanced | Scoped Context Pack, Query Plan Receipt, redacted evidence export, explicitly saved query memory and confirmed-parent analysis branches. |
| Model-independent Agent knowledge | Stable initial pack | Platform-commerce rules cover refund, dedup, logistics, version, traceability and percent thresholds; current schemas bind to read-only SQL, while unsupported compound metrics block. |
| Object continuity | Stable | URL-addressable table, view, dashboard, evidence and action context survives refresh and browser history. |
| Local operations | Stable | Loopback startup, health, security gates, checksum backup and guarded restore. |

## Known Limitations

- 不支持认证、角色、协作、远程托管、云同步或移动端交付。
- 整套行业看板仍是 Beta；晋级条件见 `development-roadmap.md`。
- 旧 XLS 仅支持画像读取，确认导入前需转换为 XLSX 或 CSV。
- 可选模型质量不属于确定性本地能力承诺，模型不可用不得阻断本地查询与证据。
- 备份不是远程灾备；视觉回归只覆盖 1440x900、900x1440、1100x1100 PC 比例。

## Architecture Ownership

| Path | Owns |
| --- | --- |
| `src/components/` | 页面与可见工作流 |
| `src/*Model.ts`, `src/*ViewModel.ts` | 派生状态、标签、就绪判断与安全转换 |
| `src/appNavigationModel.ts`, `src/api*.ts` | 对象级路由上下文与类型化客户端边界 |
| `server/` | 本地 HTTP、安全边界与 CLI 调用 |
| `tools/` | 确定性 BI、证据、动作草案和公共 CLI |
| `scripts/` | 构建、浏览器、发布、安全、备份与回归 |

组件级约束由 import 边界与 `scripts/verify.mjs` 检查，不在文档手抄文件清单。

## Verification Entry Points

```powershell
npm run build
npm run verify
npm run verify:ui
npm run verify:production
npm run verify:backup
npm run verify:platform-knowledge
npm run verify:platform-materials
npm run verify:platform-behavior
npm run verify:platform-commerce -- --root C:\Users\Administrator\Documents\AIBI-B\data\platform-research
npm run preflight
python tools/bi_cli.py --json status
python tools/bi_cli.py --json cli-contract
```

开发时选择最小相关命令，本地交付前运行 `npm run preflight`。真实导入与第二领域验证读取外部文件并使用临时数据库，不把数据复制进仓库；精确检查数由最新回执负责。
