# AIBI-C 实现状态

## 当前发布边界

当前发布版本为 v0.3.0，是 single-user and local-only 的通用可信分析工作台。新工作区为空且不启用领域包；本地确定性运行时拥有数据与写入边界，可选 Provider 仅解释。最近一次已归档的日期证据见 [2026-07-15 发布回执](../artifacts/release-2026-07-15/SUMMARY.md)，v0.3.0 以当前提交的自动化和浏览器验收为准。

“工作区”只显示当前必要任务：无数据时接入来源，有数据无证据时生成摘要，有证据时发起分析，有草案时核对确认。高级工具和设置按需展开。

## 能力状态

| 能力 | 级别 | 当前边界 |
| --- | --- | --- |
| 工作区与导航 | 稳定 | 工作区隔离；对象级 URL 可恢复；简化主导航和状态驱动首页已落地 |
| 导入与画像 | 稳定 | CSV/XLSX/XLSM、文件与文件夹统一预检；旧 XLS 仅画像读取 |
| 工作区上下文目录 | 首版已接入 | Workspace Manifest、Runtime Catalog 与 Business Field Profile 从当前工作区只读派生，并通过 CLI/API 供证据页、数据工作台和 Agent 使用；候选与手工确认分离，敏感字段只公开风险和统计，规划绑定覆盖数据、画像、语义、关系、Context、Pack 与 Skill 指纹 |
| Connector Adapter | 稳定受控 | 本地表格、allowlist HTTP JSON 与 allowlist SQLite table 支持有界预览、计划和确认导入 |
| 语义与关系 | 稳定受控 | 一至三跳全局线性覆盖、INNER 反向遍历、跨跳筛选/预聚合、组合字段消歧、复合键、版本失效、根到事实可达性、NULL 语义和放大阻断进入 Receipt；等价根表、同表异键或未穷尽的高密度路径搜索必须由用户显式选择 |
| 查询与可信单图 | 稳定 | 白名单查询、保存视图、单图草案、一次确认和真实对象跳转可用 |
| 看板 | 稳定核心 / Beta 领域 | 空看板不注入组件；高级编辑可用；整套领域方案保持 Beta |
| Agent 与证据 | 稳定高级 | Intent/Context、Evidence Plan、Turn Event、Policy Hook 与 Completion Validation 同源；Analysis Unit 在计划持久化前补全；blocker 保持可读字符串；工作区 Session 可重启恢复和 Fork，失效持久 key 只恢复重试一次，浏览器禁用存储时安全退化；Analysis Run 比较分支与 Turn 父链独立；工作流图随 Turn 持久化并可回读 |
| 业务理解与首批 Skills | 稳定初版 | 五层上下文、`aibi-business-understanding-frame/v1`、类型化单问题澄清和六个业务理解 Skill 已接入 CLI/API/UI；执行前由语义、证据、权限、新鲜度和工作区隔离门禁共同约束 |
| Durable Job 与 Workflow | 稳定受控 | 状态机、事件、取消、异常对账、Capability Contract、Workflow Stage 与 Context Budget 已闭环；固定 11 个 Operator、Orchestrator 唯一提交权、四个只读角色视图、确定性事件序列和 Join 指纹/证据校验可用；互不依赖的只读节点可并行，写入节点保持串行 |
| Analysis Unit 与图表适配 | 稳定初版 | 六类 Unit 绑定结果指纹；Chart Adapter 只选择兼容白名单图表；全部读取与适配入口复核多源、关系、版本和 Pack 当前性 |
| 分析导出 | 稳定初版 | 当前且已验证的 Receipt/Unit 可导出确定性 ZIP、XLSX、Markdown、脱敏快照与哈希；漂移对象在导出前阻断 |
| 通用扩展 | 稳定受控 | Domain Pack 管业务语义，既有通用 Analytical Skill 管分析方法；两者独立 lint、版本化和工作区启停，Skill 只能引用登记 Capability，不能携带代码、SQL、URL 或任意工具；业务理解扩展状态以上一行和 [专题设计](business-understanding-skills.md) 为准 |
| Provider | 稳定受控 | 工作区 Runtime Profile 分离 Provider、模型、wire API 与预算；deterministic 默认，DeepSeek 和显式 loopback OpenAI-compatible 只解释有界证据；严格 JSON/数字/evidence 校验、零原始行出站、失败降级、shadow evaluation 与持久评估摘要可用 |
| 证据兼容性 | 稳定受控 | Run、Receipt、Unit 绑定工作区、数据、来源、schema、Pack 与 Workspace Planning Binding 指纹；stale 记录不用于当前规划 |
| 本地运维 | 稳定 | SQLite schema v7、DuckDB schema v1；Agent Session、Turn、事件、Context Snapshot、Skill、Runtime Profile 选择与 Provider 评估已版本化；兼容检查、配置可移植、隔离迁移、恢复点和双库回滚可用；`preflight` 只停止本轮拥有且令牌验证通过的服务，陈旧 PID 不会直接触发终止 |
| 响应式 Web | 稳定 | 桌面和窄屏保留主导航、工作区切换、高级工具与设置；不提供原生移动客户端 |

BI CLI 的实时命令、参数和突变模式只由 [CLI 合同](bi-cli-contract.md) 维护。

## 已知限制

- 不支持认证、角色、协作、远程托管、云同步、原生移动客户端或远程灾备。
- 不支持自由多 Agent、专家直接调用工具、任意 Operator 或循环重规划；专家失败只降级到单 Orchestrator 的固定复核。
- 跨表执行限一至三跳线性路径；超过三跳、非线性关系树、反向 LEFT JOIN、未证明安全的 M:N、等价业务路径歧义和不可安全 rollup 的预聚合保持阻断。
- 重启中断 Job 不自动续跑；当前后台白名单只包含 Source Intelligence。
- Analysis Unit 与导出最多冻结 500 行；旧 Receipt 缺少结果绑定时必须重新执行。
- 报告只生成 Markdown，不生成 PDF/Word；Excel 仅对兼容形状生成原生图表。
- HTTP Adapter 仅支持 allowlist origin、GET、UTF-8 JSON、可选点路径和有界分页；无任意 Header、请求体、Webhook 或 OAuth。
- 数据库 Adapter 当前只支持 allowlist 本地 SQLite 文件和显式非系统表；不接受 SQL、远程数据库或驱动插件。
- 外部 Domain Pack 仅接受签名声明式 JSON 与静态资源，不加载脚本、SQL、HTML 或第三方运行时代码。
- 外部 Analytical Skill 仅接受单个声明式 JSON；安装后默认停用，必须按工作区确认启用，固定 Policy Hook 会在完成前再次复核能力、资源和证据边界。
- 业务理解合同和六个首批 Skill 已进入稳定初版；后续扩展仍必须同时具备实现、专项验证、运行回执和产品验收，不能用设计文档替代运行证据。
- Session Resume 只在同一工作区开放；缺失 Receipt、Run、Draft 或 Turn 会先显示失效引用并阻断静默续跑，显式复核后才可继续。
- 远程 OpenAI-compatible origin 默认拒绝；当前只允许 DeepSeek 官方端点和显式 loopback endpoint，Provider 无字段绑定、Capability、SQL、工具或写入权限。
- ERP 等专用复杂 UI 仍由 AIBI-C 自有可选模块提供，仅在对应 Pack 启用且证据满足时加载。

## 架构归属

| 路径 | 责任 |
| --- | --- |
| `src/` | 页面、可见工作流、派生状态、类型化客户端和对象路由 |
| `server/` | 本地 HTTP、安全边界和 CLI 编排 |
| `domain-packs/` | AIBI-C 自有可选领域 Manifest；不得承载 Core 默认行为 |
| `analytical-skills/` | AIBI-C 内置中性分析方法 Manifest；只组合登记能力，不承载业务口径或执行代码 |
| `knowledge/` | 版本化只读知识资产；只有已启用 Pack 才能引用 |
| `tools/` | 确定性 BI、语义、关系、证据、Job、导出、扩展运行时和公共 CLI |
| `scripts/` | 构建、迁移、浏览器、发布、安全与回归门禁 |

组件依赖和文件清单由代码与自动化维护，不在 Markdown 复制。

## 验证入口

```powershell
npm run verify:docs
npm run build
npm run verify
npm run verify:analytical-skills
npm run verify:agent-sessions
npm run verify:runtime-profiles
npm run verify:restricted-workflow
npm run verify:domain-packs
npm run verify:domain-regressions
npm run verify:connector-adapters
npm run verify:domain-neutrality
npm run verify:ui
npm run verify:migration
npm run verify:production
npm run preflight
python tools/bi_cli.py --json status
python tools/bi_cli.py --json cli-contract
```

开发时运行与改动面对应的 `verify:*`；本地交付前运行完整 `npm run preflight`。检查数、命令数和性能值只记录在脚本输出或日期回执。
