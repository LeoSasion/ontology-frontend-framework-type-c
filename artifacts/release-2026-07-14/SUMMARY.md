# AIBI-C M0–M11 发布验收回执

- 日期：2026-07-14（Asia/Shanghai）
- 范围：单用户本地版本 M0–M11
- 仓库：`C:\Users\Administrator\Documents\AIBI-C`
- 远端：`https://github.com/LeoSasion/AIBI-C.git`
- 结论：完整 `npm run preflight` 退出码为 0；API 8787 与 UI 8686 健康。

## 交付范围

| 里程碑 | 稳定结果 |
| --- | --- |
| M0–M3 | 仓库隔离、关系安全、受控跨表执行和组合字段消歧 |
| M4–M6 | 双库迁移/回滚、多领域 Beta 验证和本地发布加固 |
| M7 | 工作区级 Durable Job、事件、取消、异常对账和重启安全终态 |
| M8 | Capability Contract、Workflow Stage 和证据保持型 Context Budget |
| M9 | 六类可复算 Analysis Unit 与确定性 Chart Adapter |
| M10 | Query Receipt 驱动的确定性 Excel/Markdown 导出 |
| M11 | 最小权限只读 Connector Adapter 与工作区复合身份 |

整套行业看板继续保持 Beta，本回执不改变其产品级别。

## 最终门禁

| 门禁 | 结果 | 覆盖 |
| --- | --- | --- |
| 仓库隔离 | 通过 | root、origin、路径、符号链接、输入和运行时只属于 AIBI-C |
| Build | 通过 | TypeScript、Vite 和 bundle budgets |
| Core verify | 通过 | 522/522 静态/运行合同及完整 CLI、语义、关系、证据和 Provider 链路 |
| Workflow/Job | 通过 | 状态机、事件、取消、worker 退出、Stage、能力和 Context Budget |
| Analysis/Export | 通过 | Receipt 指纹、六类 Unit、图表适配、确定性 ZIP、XLSX 和脱敏 |
| Connector | 通过 | 有界元数据/预览/计划、凭据引用、零隐式写入和跨路径阻断 |
| Migration/Recovery | 通过 | SQLite v1→v2、DuckDB v1、隔离预演、恢复点、失败回滚 |
| Browser | 通过 | 空工作区、真实导入、单图、跨表、Connector、四种 PC 比例和干净控制台 |
| Final health | 通过 | `127.0.0.1:8787/api/health` 与 `127.0.0.1:8686` |

本次 CLI 能力快照为 111 个命令；当前数量以自动生成的 `docs/bi-cli-contract.md` 为准。

## 数据与迁移回执

- 正式本地库通过隔离副本预演，`originalUnchanged: true` 后才确认迁移。
- SQLite 元数据升级到 v2，Connector 主键变为 `(workspace_id, connector_key)`；DuckDB 保持 v1。
- 迁移前恢复点：`backups/pre-migration-2026-07-14T11-44-15-724Z`。
- 模拟应用失败和最终复检失败均恢复 SQLite 与 DuckDB；未来 schema 版本阻止启动。
- UI 验收使用临时工作区，结束后恢复原工作区并删除临时表、Job、Connector、回执和物理表。

## 安全边界

- 未复制、运行或修改其他 AIBI 仓库的代码、数据、测试、运行时或 Git 状态。
- Provider 无任意 SQL、文件、网络、进程或写入权限；必要证据超预算时直接跳过。
- Connector 当前仅启用本地 CSV/XLSX/XLSM；API、ERP 和数据库 Adapter 保持 `unavailable`。
- 导出只消费冻结 Receipt/Unit，不重新查询，不写业务库，不包含凭据、绝对路径或无关原始行。

## 保留限制

- 无认证、协作、云同步、远程托管、移动端和远程灾备。
- 跨表自动执行不开放三跳、反向路径和跨跳筛选/预聚合。
- 重启中断 Job 不自动续跑；Analysis Unit 与导出最多冻结 500 行。
- 报告为 Markdown，不生成 PDF/Word；视觉回归只承诺四种 PC 比例。

本回执是日期证据；后续当前状态以 [实现状态](../../docs/implementation-status.md) 为准。
