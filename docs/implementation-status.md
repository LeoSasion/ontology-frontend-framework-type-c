# AIBI-C Implementation Status

当前阶段：single-user and local-only 的本地生产基线。M0–M11 已进入当前代码基线；最新合并验收见 [2026-07-14 发布回执](../artifacts/release-2026-07-14/SUMMARY.md)。

## Current Release Boundary

| 层级 | 当前实现 | 边界 |
| --- | --- | --- |
| Client | React 19 + Vite 桌面工作台 | 渐进展示；无移动端原生客户端 |
| Local API | Node/TypeScript 路由层 | 回环监听、有界请求、可选精确 CORS |
| BI runtime | Python CLI + SQLite metadata + DuckDB analytics | 白名单参数；无任意用户 SQL |
| Storage | 本地数据库和用户选择文件 | 无云同步、多租户或仓库预置数据 |
| Agent | 本地确定性解析 + 可选 DeepSeek 解释 | 本地证据权威；模型无工具权限 |
| Evidence | Query、Action、Job、导出和恢复回执 | 业务摘要优先；原始诊断默认折叠 |

## Capability Status

| Capability | Status | Current contract |
| --- | --- | --- |
| Repository and workspace isolation | Stable | root、origin、输入路径、符号链接、运行目录和工作区对象均有隔离门禁。 |
| Clean first run and navigation | Stable | Product activation shows only the current necessary step；空工作区无样例，URL 恢复真实对象。 |
| Import, profiling and connectors | Stable | CSV/XLSX/XLSM 支持预演、一次确认、画像；`local-tabular/v1` 只读 Adapter 有硬上限。 |
| Semantic and relationship safety | Stable controlled | 字段组合消歧、复合键、筛选、预聚合、数据版本和失效阻断共享 Query Plan Receipt。 |
| Query and dashboard | Stable | 白名单查询、保存视图、可信单图和高级看板编辑可用；整套行业看板保持 Beta。 |
| Agent, evidence and optional Provider | Stable advanced | 本地答案权威；可信语境、查询回执、确认问法和分支有证据与失效规则；Provider 可降级。 |
| Durable jobs and workflow | Stable initial | 工作区 Job 状态机、事件、取消、异常对账、Capability Contract、Workflow Stage 和 Context Budget 已闭环。 |
| Verifiable analysis units | Stable initial | 六类 Unit 绑定 Query Receipt 标量指纹，可精确复算；Chart Adapter 只选择兼容白名单图表。 |
| Receipt-driven analysis export | Stable initial | 已验证 Receipt/Unit 导出确定性 ZIP、XLSX、Markdown、脱敏快照和哈希；零重新查询、零业务写入。 |
| Safe read-only connector adapter | Stable initial | 元数据、预览和同步计划与确认导入分离；字面凭据、任意查询、符号链接和跨仓库路径阻断。 |
| Local operations | Stable | SQLite schema v2、DuckDB schema v1；启动兼容检查、隔离迁移、校验和恢复点和双库回滚可用。 |

BI CLI 的命令、参数和突变模式以自动生成的 [CLI 合同](bi-cli-contract.md) 为准，不在状态文档复制数量。

## Known Limitations

- 不支持认证、角色、协作、远程托管、云同步、移动端或远程灾备。
- 整套行业看板仍是 Beta；晋级条件见 [未来开发队列](development-roadmap.md)。
- 旧 XLS 只支持画像读取；确认导入前需转换为 XLSX 或 CSV。
- 跨表执行开放一跳和严格线性正向两跳；三跳、反向路径和跨跳筛选/预聚合保持阻断。
- 重启中断的 Job 不自动续跑；旧 Job 进入 `runtime-restarted` 失败终态，当前后台白名单只含 Source Intelligence。
- Analysis Unit 与导出最多冻结 500 行；旧 Receipt 没有 `resultBinding` 时必须重新执行查询。
- 报告格式为 Markdown，不生成 PDF/Word；Excel 只对兼容图表生成原生图表。
- Connector 仅启用本地 CSV/XLSX/XLSM；API、ERP 和数据库 Adapter 保持 `unavailable`。
- 视觉回归覆盖四种 PC 比例，不承诺移动端布局。

## Architecture Ownership

| 路径 | 责任 |
| --- | --- |
| `src/components/` | 页面与可见工作流 |
| `src/*Model.ts`, `src/*ViewModel.ts` | 派生状态、标签、就绪判断与安全转换 |
| `src/api*.ts`, `src/appNavigationModel.ts` | 类型化客户端和对象级路由 |
| `server/` | 本地 HTTP、安全边界和 CLI 调用 |
| `tools/` | 确定性 BI、语义、证据、Job、导出和公共 CLI |
| `scripts/` | 构建、迁移、浏览器、发布、安全与回归 |

组件级依赖由代码和验证脚本维护，不在 Markdown 抄写文件清单。

## Verification Entry Points

```powershell
npm run verify:docs
npm run build
npm run verify
npm run verify:ui
npm run verify:migration
npm run verify:production
npm run preflight
python tools/bi_cli.py --json status
python tools/bi_cli.py --json cli-contract
```

开发时运行与改动面对应的 `verify:*`，本地交付前运行完整 `npm run preflight`。精确检查数、命令数和性能值只在脚本输出或日期回执中记录。
