# AIBI-C Implementation Status

当前阶段：single-user and local-only 的通用可信分析基线。M0–M11、外部 Domain Pack SDK 与受控 HTTP/SQLite Connector Adapter 已进入当前代码基线；新工作区默认不启用任何领域知识。最新归档发布验收见 [2026-07-14 发布回执](../artifacts/release-2026-07-14/SUMMARY.md)。

## Current Release Boundary

| 层级 | 当前实现 | 边界 |
| --- | --- | --- |
| Client | React 19 + Vite 桌面工作台 | 渐进展示；无移动端原生客户端 |
| Local API | Node/TypeScript 路由层 | 回环监听、有界请求、可选精确 CORS |
| BI runtime | Python CLI + SQLite metadata + DuckDB analytics | 白名单参数；无任意用户 SQL |
| Storage | 本地数据库和用户选择文件 | 无云同步、多租户或仓库预置数据 |
| Domain runtime | 工作区级 Domain Pack 注册表与外部静态包 SDK | 空默认；签名、来源、冲突、版本迁移、预演和确认；历史证据不原地重解释 |
| Connector runtime | 统一 Adapter 能力目录 | 文件、allowlist HTTP JSON 与 allowlist SQLite table 可用；接入能力不授予领域语义 |
| Agent | 本地确定性解析 + 可选 DeepSeek 解释 | 本地证据权威；模型无工具权限 |
| Evidence | Query、Action、Job、导出和恢复回执 | 业务摘要优先；原始诊断默认折叠 |

## Capability Status

| Capability | Status | Current contract |
| --- | --- | --- |
| Repository and workspace isolation | Stable | root、origin、输入路径、符号链接、运行目录和工作区对象均有隔离门禁。 |
| Clean first run and navigation | Stable | Product activation shows only the current necessary step；空工作区无样例，URL 恢复真实对象。 |
| Import, profiling and connectors | Stable controlled | CSV/XLSX/XLSM、`http-json/v1` 与 `sqlite-table/v1` 支持有界只读发现/预览/计划；确认后才进入通用导入边界。 |
| Semantic and relationship safety | Stable controlled | 字段组合消歧、复合键、筛选、预聚合、数据版本和失效阻断共享 Query Plan Receipt。 |
| Query and dashboard | Stable | 白名单查询、保存视图、可信单图和高级看板编辑可用；整套行业看板保持 Beta。 |
| Agent, evidence and optional Provider | Stable advanced | 本地答案权威；可信语境、查询回执、确认问法和分支有证据与失效规则；Provider 可降级。 |
| Durable jobs and workflow | Stable initial | 工作区 Job 状态机、事件、取消、异常对账、Capability Contract、Workflow Stage 和 Context Budget 已闭环。 |
| Verifiable analysis units | Stable initial | 六类 Unit 绑定 Query Receipt 标量指纹，可精确复算；Chart Adapter 只选择兼容白名单图表。 |
| Receipt-driven analysis export | Stable initial | 已验证 Receipt/Unit 导出确定性 ZIP、XLSX、Markdown、脱敏快照和哈希；零重新查询、零业务写入。 |
| Safe read-only connector adapter | Stable controlled | 文件、HTTP JSON 与 SQLite table 的元数据、预览和同步计划与确认导入分离；origin/文件 allowlist、字面凭据、任意 SQL、符号链接和跨仓库路径阻断。 |
| Generic domain extension framework | Stable controlled | 外部静态 Pack 支持 HMAC 签名、来源、lint、安装/升级/卸载预演、迁移回执、冲突和通用 UI contribution；内置包仍默认停用。 |
| Domain-neutral Core | Stable | Core 只使用类型、分布、唯一性、时间、聚合、关系和版本证据；中性数据默认不出现电商、ERP、资金、订单、售后或保单语义。 |
| Evidence compatibility | Stable controlled | Run、Query Receipt 和 Analysis Unit 绑定工作区、source/schema/data/Pack 指纹；不兼容记录标记为 stale 或历史，不作为当前证据。 |
| Local operations | Stable | SQLite schema v3、DuckDB schema v1；启动兼容检查、隔离迁移、校验和恢复点和双库回滚可用。 |

BI CLI 的命令、参数和突变模式以自动生成的 [CLI 合同](bi-cli-contract.md) 为准，不在状态文档复制数量。

## Known Limitations

- 不支持认证、角色、协作、远程托管、云同步、移动端或远程灾备。
- 整套行业看板仍是 Beta；晋级条件见 [未来开发队列](development-roadmap.md)。
- 旧 XLS 只支持画像读取；确认导入前需转换为 XLSX 或 CSV。
- 跨表执行开放一跳和严格线性正向两跳；三跳、反向路径和跨跳筛选/预聚合保持阻断。
- 重启中断的 Job 不自动续跑；旧 Job 进入 `runtime-restarted` 失败终态，当前后台白名单只含 Source Intelligence。
- Analysis Unit 与导出最多冻结 500 行；旧 Receipt 没有 `resultBinding` 时必须重新执行查询。
- 报告格式为 Markdown，不生成 PDF/Word；Excel 只对兼容图表生成原生图表。
- HTTP Adapter 仅支持 allowlist origin、GET、UTF-8 JSON、可选点路径和有界页码；不支持任意请求体、任意 Header、Webhook 或 OAuth 流程。ERP Adapter 保持 `unavailable`。
- 数据库 Adapter 当前只支持 allowlist 本地 SQLite 文件和一个显式非系统表；不接受 SQL、视图定义、远程数据库或驱动插件。
- 外部 Domain Pack 只接受签名声明式 JSON 与静态资源，不加载 Python、JavaScript、SQL、HTML 或第三方运行时代码。
- 通用语义贡献由 Manifest 驱动；ERP 等专用复杂 UI 仍由 AIBI-C 自有可选模块渲染，只有对应 Pack 启用且返回该领域结果时才加载。
- 视觉回归覆盖四种 PC 比例，不承诺移动端布局。

## Architecture Ownership

| 路径 | 责任 |
| --- | --- |
| `src/components/` | 页面与可见工作流 |
| `src/*Model.ts`, `src/*ViewModel.ts` | 派生状态、标签、就绪判断与安全转换 |
| `src/api*.ts`, `src/appNavigationModel.ts` | 类型化客户端和对象级路由 |
| `server/` | 本地 HTTP、安全边界和 CLI 调用 |
| `domain-packs/` | AIBI-C 自有可选领域能力 Manifest；不得承载 Core 默认行为 |
| `tools/` | 确定性 BI、领域运行上下文、语义、证据、Job、导出和公共 CLI |
| `scripts/` | 构建、迁移、浏览器、发布、安全与回归 |

组件级依赖由代码和验证脚本维护，不在 Markdown 抄写文件清单。

## Verification Entry Points

```powershell
npm run verify:docs
npm run build
npm run verify
npm run verify:domain-packs
npm run verify:domain-regressions
npm run verify:connector-adapters
npm run verify:domain-neutrality
npm run verify:ui
npm run verify:migration
npm run verify:production
npm run verify:ci
npm run preflight
python tools/bi_cli.py --json status
python tools/bi_cli.py --json cli-contract
```

开发时运行与改动面对应的 `verify:*`，本地交付前运行完整 `npm run preflight`。精确检查数、命令数和性能值只在脚本输出或日期回执中记录。
