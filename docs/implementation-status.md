# AIBI-C 实现状态

## 当前发布边界

当前发布版本为 v0.3.0，是 single-user and local-only 的通用可信分析工作台。新工作区为空且不启用领域包；本地确定性运行时拥有数据与写入边界，可选 Provider 仅解释。当前交付状态以本文件、当前提交和 `npm run preflight` 为准；已被当前回归覆盖的旧版日期回执不再保留。

“工作区”只显示当前必要任务：无数据时接入来源；导入确认后由应用级 Journey Runtime 自动运行或恢复 Source Intelligence；证据可用后发起分析；已有结果时核对结论与回执；有草案时核对确认。高级工具和设置按需展开。

## 能力状态

| 能力 | 级别 | 当前边界 |
| --- | --- | --- |
| 工作区与导航 | 稳定 | 工作区隔离；对象级 URL 可恢复；统一 Journey 模型把接入、自动理解、提问、结果核对和写入确认映射为一个主任务，刷新后从持久 Run、Job 和当前 Agent 结果恢复 |
| 导入、画像与来源激活 | 稳定受控 | CSV/XLSX/XLSM、文件与文件夹统一预检；受支持文件先进入工作区隔离的 Sealed Import Stage，一次原始解析后由预检、确认和 Durable Job 复用同一哈希绑定，TTL、配额、符号链接和跨工作区访问 fail closed；整表替换逐字段列出新增、移除、保留及完整下游依赖，字段结构变化需在冻结计划上额外确认；确认路径绑定规范化 Import Plan fingerprint、来源哈希、父版本、依赖影响指纹与 `requestKey`；全局单写者队列、lease token/epoch、跨进程写锁和 Activation Journal 对账完成 DuckDB 发布与 current sourceRun 原子切换，刷新或进程退出后可查询、取消或恢复；旧 XLS 仅画像读取 |
| 跨引擎查询正确性 | 稳定门禁 | SQLite 权威控制面与已发布 DuckDB 分析副本使用固定等价性矩阵核对公式、关系、筛选、排序、分页、NULL、版本和 Receipt 绑定；查询路径只读已发布副本，副本缺失、manifest 漂移、半发布或旧版本均阻断，不隐式整表同步或回退 SQLite |
| 工作区恢复 | 稳定受控 | 工作区隔离恢复点支持创建、校验、表版本/来源指纹影响对比、预演恢复、确认恢复、删除与启动期未完成恢复对账；对比不读取或展示业务行；恢复仅回退正向 allowlist 内的当前业务配置和物理数据，Publication/Ledger、Receipt、来源历史、Job/Event 与 Activation Journal 原样保留并按 current binding 变 stale；manifest 和内容哈希不一致、跨工作区或非服务端路径请求 fail closed，恢复失败保留确定性后续动作，高级 UI 按需加载 |
| 工作区上下文目录 | 首版已接入 | Workspace Manifest、Runtime Catalog 与 Business Field Profile 从当前工作区只读派生，并通过 CLI/API 供证据页、数据工作台和 Agent 使用；候选与手工确认分离，敏感字段只公开风险和统计，规划绑定覆盖数据、画像、语义、关系、Context、Pack 与 Skill 指纹 |
| Connector Adapter | 稳定受控 / SQL Server 可选 | 本地表格、allowlist HTTP JSON 与 allowlist SQLite table 支持有界预览、计划和确认导入；可选 SQL Server 路径完成驱动/策略 probe、只读 test、catalog discover、snapshot plan、密封 stage、标准 Durable Import 与 Activation Journal 激活，凭据只使用 Secret Ref；UI 显示 Job/Journal 进度，只有 `succeeded + finalized/committed` 才显示 active |
| 语义与关系 | 稳定受控 | 一至三跳全局线性覆盖、INNER 反向遍历、跨跳筛选/预聚合、组合字段消歧、复合键、版本失效、根到事实可达性、NULL 语义和放大阻断进入 Receipt；等价根表、同表异键或未穷尽的高密度路径搜索必须由用户显式选择 |
| 查询与可信单图 | 稳定 | 白名单查询、保存视图、单图草案、一次确认和真实对象跳转可用；Typed QueryIntent、current workspace/sourceRun binding、槽位执行覆盖和 `executed | draft | blocked | simulation | stale` 五态门禁阻止未执行结果进入经营结论 |
| 服装电商可信查询 | 稳定受控 v1 | `platform-commerce` Domain Pack 显式启用后提供 style/SPU、product/link、merchant SKU 三层实体映射证明，以及排行、集中度、Pareto 和有条件十分位；ABC 与爆款/潜力款/滞销款等经营角色只定义合同并保持阻断 |
| 看板 | 稳定核心 / Beta 领域 | 空看板不注入组件；高级编辑可用；整套领域方案保持 Beta |
| Agent 与证据 | 稳定高级 | Intent/Context、Evidence Plan、Turn Event、Policy Hook 与 Completion Validation 同源；Analysis Unit 在计划持久化前补全；blocker 保持可读字符串；工作区 Session 可重启恢复和 Fork，失效持久 key 只恢复重试一次，浏览器禁用存储时安全退化；Analysis Run 比较分支与 Turn 父链独立；工作流图随 Turn 持久化并可回读 |
| 业务理解与分析 Skills | 稳定初版 | 五层上下文、`aibi-business-understanding-frame/v1`、类型化单问题澄清、六个业务理解 Skill，以及漏斗、队列留存、异常分诊、分群贡献、驱动调查、决策看板和 Forecast Readiness 七个方法 Skill 已接入 CLI/API/UI；专用信号不会抢占普通分析，`aibi-analysis-method-plan/v1` 把步骤、槽位、证据、Guard、资源和 Capability 交集带入 Evidence Plan |
| 计划质量评测 | 稳定初版 | 15 个固定中立 Business Expression Case 在内存夹具中确定性重放；评分卡覆盖槽位、字段、澄清、证据、重放及零容忍隔离指标，不读取用户业务行或调用 Provider；设置页可运行并查看当前/失效回执，Case Set、Policy 或运行时漂移后旧回执不用于发布 |
| 语义补丁、知识源与语义发布 | 稳定受控 | 设置页只接收本地受限 JSON/Markdown 知识源，网络、SQL、代码、原文和业务行不进入快照；声明式 Adapter 形成不可变提案，接受/拒绝均需预演与确认；多个不冲突且 current 的提案可分组预演并以精确指纹原子发布为版本，发布历史区分 current/stale/rolled_back，回滚继续复核目标漂移 |
| Confirmed Plan Memory 与混合召回 | 稳定初版 | 成功动作先生成候选，显式提升后才形成证据绑定计划记忆；lexical、字符 n-gram、结构化计划和 freshness 联合排序并生成 Recall Receipt；召回仅提供候选，不改变 Semantic Plan，漂移后同步 stale |
| 审核制品与证据召回 | 稳定初版 | current executed 证据可显式发布为审核制品；追加式 Ledger 同时复核链、内容和输入合同指纹，篡改、跨工作区引用或输入漂移后只允许历史审计；Evidence 高级区已接入按工作区绑定的惰性列表、选中复核、安全导出和绑定精确 Ledger head 的两阶段停用，读取与写入分别执行 viewer/owner 门禁且鉴权早于请求体解析；工作区删除先验证全链、追加 tombstone、创建并复核审计恢复点，再以四阶段持久回执完成双库清理和启动重放；Provider-neutral 混合召回、固定离线评测、隐私门禁与 Retrieval Receipt 已接入，当前默认 `lexical_degraded`，不会自动启用向量通道 |
| 证据绑定决策框架 | 稳定初版 | SWOT/流程框架区分 `evidence_fact`、`user_judgment` 与 `hypothesis`，事实必须绑定 current evidence；CLI/API 与分析结果后的惰性 UI 已接入，无证据或漂移时卸载已证明事实，不自动生成因果或行动建议 |
| 探索线程与结果板 | 稳定初版 | 已执行或已确认结果可经预演和确认建立不可变 Anchor，并按 Analysis Run 父链追加分支；结果板只保存业务字段、形状与图表摘要，不复制结果行；Run、Receipt、Unit、Turn 或来源漂移后保留历史但阻断续算，不回退旧结果 |
| 有限 Research Run 与统一追踪 | 稳定初版 | current Anchor 可经预演和确认建立固定预算的研究账本；计划修订只追加不可变版本，Observation 仅采纳同线程 current Anchor，且旧修订证据不计入当前覆盖；结论区分 supported、challenged、mixed、inconclusive，统一 Trace 可重放且不复制业务结果行 |
| Durable Job、Workflow 与 Recipe | 稳定受控 | 状态机、事件、取消、异常对账、Capability Contract、Workflow Stage 与 Context Budget 已闭环；应用级 Source Intelligence 轮询在刷新后重新挂接当前工作区任务；固定 11 个 Operator、Orchestrator 唯一提交权、四个只读角色视图、确定性事件序列和 Join 指纹/证据校验可用；Workflow Recipe 可版本化保存 1–12 个登记 Capability 的顺序、占位输入和确认边界，实例化只生成当前工作区的新计划且永不自动执行 |
| Analysis Unit 与图表适配 | 稳定初版 | 六类 Unit 绑定结果指纹；Chart Adapter 只选择兼容白名单图表；Agent 对 current `executed` Receipt、完整覆盖、正行数和 Receipt/Unit/Adapter 键与指纹做严格门禁后，惰性投影指标、比较/排名、趋势、构成、表格和 Pareto 边界证据；非执行五态卸载经营图形，全部读取与适配入口继续复核多源、关系、版本和 Pack 当前性 |
| Forecast Readiness | 稳定初版 | current 趋势或异常 Unit 可按明确 horizon 执行来源、样本、节奏、稳定性、泄漏、假设和可解释性七门禁；CLI/API/Agent/UI 同源，blocked 仍是成功诊断，响应固定不生成预测、不调用 Provider、不返回业务行 |
| 物化分析快照 | 稳定初版 | current Receipt/Unit 可经精确预演确认冻结最多 500 行；refresh/replace 追加不可变子快照，delete 擦除内容并保留 lineage tombstone；公开 CLI/API/UI 不返回冻结行，stale/missing 历史不用于规划且不回退旧快照 |
| Metric Monitor | 稳定初版 | 用户确认的单值快照可建立不可变本地监控定义；首次手动运行建立 baseline，后续只比较语义、表身份、关系和 Pack 兼容的 current 快照，输出 baseline/normal/warning/breached/blocked 与可重放 Trace；无后台调度、通知、Provider 或业务系统写入 |
| Metric Contract v2 | 稳定受控 | 指标版本显式绑定 population、grain、unit、null policy、dedup key、direction 与 owner；最多 12 个 current DuckDB 场景先预演后发布 baseline，重放分别归因 definition drift、data drift 或二者同时变化，筛选值只公开指纹 |
| 只读联邦证明 | 稳定初版 | 2–4 个 active 且同步成功的 Adapter 连接可按字段投影、实体键、validated 关系连通路径、粒度、过滤 allowlist、预算和资源/关系 freshness 生成 `provable | blocked` 证明；只验证计划，不执行跨源查询、不复制业务行、不授予物化或写入权限 |
| 分析导出 | 稳定初版 | 当前且已验证的 Receipt/Unit 可导出确定性 ZIP、XLSX、Markdown、原生 DOCX、四页 PPTX、脱敏快照与哈希；所有格式只消费冻结结果且共享路径/凭据脱敏，漂移对象在导出前阻断 |
| 通用扩展 | 稳定受控 | Domain Pack 管业务语义，既有通用 Analytical Skill 管分析方法；两者独立 lint、版本化和工作区启停，Skill 只能引用登记 Capability，不能携带代码、SQL、URL 或任意工具；业务理解扩展状态以上一行和 [专题设计](business-understanding-skills.md) 为准 |
| Provider | 稳定受控 | 工作区 Runtime Profile 分离 Provider、模型、wire API 与预算；deterministic 默认，DeepSeek 和显式 loopback OpenAI-compatible 只解释有界证据；严格 JSON/数字/evidence 校验、零原始行出站、失败降级、shadow evaluation 与持久评估摘要可用 |
| 证据兼容性 | 稳定受控 | Run、Receipt、Unit 绑定工作区、数据、来源、schema、Pack 与 Workspace Planning Binding 指纹；证据制品按内容哈希寻址并复核完整性，stale 记录不用于当前规划 |
| 本地运维 | 稳定 | SQLite schema v17、DuckDB schema v1；长驻 Runtime Host 固定一个写者与两个读者，提供有界队列、命令截止时间和健康状态；DuckDB 分析副本按来源版本发布、由 manifest 和逻辑视图原子切换，工作区清理同步移除视图、版本表和 manifest，并由 `prepared → duckdb_deleted → sqlite_deleted → completed` 回执支持崩溃续作；兼容检查、配置可移植、隔离迁移、恢复点和双库回滚可用；`preflight` 只停止本轮拥有且令牌验证通过的服务，陈旧 PID 不会直接触发终止 |
| 响应式 Web | 稳定 | 横向 1280×720、竖向 720×1280 及以上按可用空间响应式排版与缩放字体；短边低于 720 时冻结基准布局并整体缩放，保留主导航、工作区切换、高级工具与设置；请求失败显示明确错误且不回退陈旧业务结果；不提供原生移动客户端 |

BI CLI 的实时命令、参数和突变模式只由 [CLI 合同](bi-cli-contract.md) 维护。

## 已知限制

- 不支持认证、角色、协作、远程托管、云同步、原生移动客户端或远程灾备。
- 不支持自由多 Agent、专家直接调用工具、任意 Operator 或循环重规划；专家失败只降级到单 Orchestrator 的固定复核。
- 跨表执行限一至三跳线性路径；超过三跳、非线性关系树、反向 LEFT JOIN、未证明安全的 M:N、等价业务路径歧义和不可安全 rollup 的预聚合保持阻断。
- 通用 Job 重启后不盲目自动续跑；Source Intelligence 仍按白名单恢复，Import Job 则先用 Activation Journal 和 current binding 对账，只有可证明安全的阶段才重新排队，未知提交状态进入 `needs_attention`。
- Analysis Unit 与导出最多冻结 500 行；旧 Receipt 缺少结果绑定时必须重新执行。
- 不生成 PDF；DOCX/PPTX 只投影冻结 Analysis Unit 的有界结果，Excel 仅对兼容形状生成原生图表。
- HTTP Adapter 仅支持 allowlist origin、GET、UTF-8 JSON、可选点路径和有界分页；无任意 Header、请求体、Webhook 或 OAuth。
- 通用数据库 Adapter 仍只接受 allowlist 本地 SQLite 文件和显式非系统表；SQL Server 是独立的可选只读快照边界，不接受任意 SQL、不自动安装驱动或回退其他来源。fake-driver 已走完 stage → Durable Import → Journal → active；本轮没有启用真实 SQL Server opt-in，因此不宣称外部环境 E2E 已执行。
- 外部 Domain Pack 仅接受签名声明式 JSON 与静态资源，不加载脚本、SQL、HTML 或第三方运行时代码。
- 外部 Analytical Skill 仅接受单个声明式 JSON；安装后默认停用，必须按工作区确认启用，固定 Policy Hook 会在完成前再次复核能力、资源和证据边界。
- 业务理解合同、六个理解 Skill、六个第二批方法 Skill 与有限 Research Run 已进入稳定初版；方法计划仍不是已执行结论，Research Run 也只组织当前线程内的已验证锚点，不自动生成分析分支或扩大执行权限。
- Forecast Readiness 只判断是否可进入受限评测；至少需要 24 个 current Unit 时间点，且不提供 backtest、模型训练、预测值、预测图或可靠性承诺。
- 物化分析快照最多保留 current Unit 的 500 行；它不重查来源、不替代来源、不发送通知，stale 或 missing 历史只能审计，不能继续规划。
- Metric Monitor 首版只接受单行数值快照和用户显式阈值；cadence 不触发后台任务，历史 baseline 仅用于完整性校验后的比较证据，不可作为当前规划输入，也不发送通知或自动解释异常原因。
- 只读联邦证明首版不执行跨源结果查询；文件与 allowlist SQLite 可用同步资源指纹证明 freshness，HTTP Adapter 尚无可比整源指纹，因此即使元数据发现成功也保持 `blocked`。
- Session Resume 只在同一工作区开放；缺失 Receipt、Run、Draft 或 Turn 会先显示失效引用并阻断静默续跑，显式复核后才可继续。
- 远程 OpenAI-compatible origin 默认拒绝；当前只允许 DeepSeek 官方端点和显式 loopback endpoint，Provider 无字段绑定、Capability、SQL、工具或写入权限。
- ERP 等专用复杂 UI 仍由 AIBI-C 自有可选模块提供，仅在对应 Pack 启用且证据满足时加载。

## 架构归属

| 路径 | 责任 |
| --- | --- |
| `src/` | 页面、可见工作流、派生状态、类型化客户端和对象路由 |
| `server/` | 本地 HTTP、安全边界、幂等突变入口、Trace、静态资源缓存/压缩和长驻 Runtime Host 编排 |
| `domain-packs/` | AIBI-C 自有可选领域 Manifest；不得承载 Core 默认行为 |
| `analytical-skills/` | AIBI-C 内置中性分析方法 Manifest；只组合登记能力，不承载业务口径或执行代码 |
| `knowledge/` | 版本化只读知识资产；只有已启用 Pack 才能引用 |
| `tools/aibi_cli.py` | 公共 CLI 薄适配器；只负责进入统一运行时，不承载命令实现 |
| `tools/aibi_runtime/` | CLI parser、命令注册表、Control/Analysis/Data/Delivery 四个领域分发器、统一生命周期与显式 Application Use Cases；`kernel.py` 只保留兼容组合出口 |
| `tools/aibi_runtime_host.py` | 长驻 CLI 进程协议；一次装载命令目录，通过逐行 JSON envelope 服务 Runtime Host，不承载 HTTP 或业务授权 |
| `tools/*.py` | 确定性 BI、语义、关系、证据、Job、导出、扩展和基础设施服务 |
| `scripts/` | 构建、迁移、浏览器、发布、安全与回归门禁 |

Web 生产入口固定为 `src/main.tsx` 和 `server/index.ts`，自动化与诊断入口固定为 `tools/aibi_cli.py`。P0-A 首批拆分已把组合内核缩为只含兼容导出的组合面，运行时调用者直接依赖 `use_cases/` 下的 Control、Analysis、Data、Delivery、Lifecycle 与 Agent Interaction 边界；其中 Agent Interaction 仍是下一批继续拆分 Prompt Resolution、Answer Composition 与 Action Confirmation 的主要对象，类型化 Command/Result 也尚未完成。HTTP API 只接受 loopback Host/Origin，本地会话令牌约束突变请求，幂等键防止重试重复写入；非成功状态保留为非 2xx，并携带可关联 Trace。组件依赖、CLI 注册完整性和文件清单由代码与自动化维护，不在 Markdown 复制；`npm run verify:architecture` 会阻断入口不可达的 TypeScript、JavaScript 与 CSS 源码，也会阻断旧 CLI 路径回流、parser/registry 不一致、Use Case 清单漂移、领域依赖倒退和组合内核重新膨胀。

## 验证入口

```powershell
npm run verify:docs
npm run verify:architecture
npm run build
npm run verify
npm run verify:federation-proof
npm run verify:analytical-skills
npm run verify:plan-quality
npm run verify:exploration-threads
npm run verify:agent-sessions
npm run verify:runtime-profiles
npm run verify:restricted-workflow
npm run verify:trusted-capabilities
npm run verify:cross-engine
npm run verify:durable-import
npm run verify:workspace-recovery
npm run verify:reviewed-publication
npm run verify:evidence-retrieval
npm run verify:decision-frameworks
npm run verify:sqlserver-snapshot
npm run verify:domain-packs
npm run verify:domain-regressions
npm run verify:connector-adapters
npm run verify:domain-neutrality
npm run verify:ui
npm run verify:migration
npm run verify:production
npm run preflight
python tools/aibi_cli.py --json status
python tools/aibi_cli.py --json cli-contract
```

开发时运行与改动面对应的 `verify:*`；本地交付前运行完整 `npm run preflight`。检查数、命令数和性能值只记录在脚本输出或日期回执。
