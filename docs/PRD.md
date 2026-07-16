# AIBI-C 产品需求

[产品定位](../PRODUCT.md) 定义方向；本文件只规定当前版本必须满足的用户结果、功能边界和发布条件。

## 用户结果

| 用户 | 必须能够 |
| --- | --- |
| 业务新手 | 导入本地表格，不学习 SQL 或建模即可得到第一个可信图表 |
| 结果使用者 | 看懂来源、口径、可信度、关系路径和缺口，并继续分析 |
| 数据维护者 | 按需维护语义、指标、关系、公式、视图和看板，不干扰默认路径 |
| 工作区所有者 | 预演并确认导入、保存、覆盖和删除，获得可追踪回执 |

## 默认流程

1. 创建或选择本地工作区。
2. 从统一入口检查文件、文件夹或已登记 Connector，预览目标、合并、键和风险后再确认导入。
3. 生成字段、质量、关系和缺口证据。
4. 描述问题或图表；系统检索当前工作区业务上下文后直接回答、形成一个草案，或一次只澄清一个会改变结果的关键歧义。
5. 只读结果直接展示；写入只在唯一确认面批准或拒绝。
6. 完成后打开真实对象；后续分析从已确认结果创建有血缘分支。

## 当前功能要求

### 工作区与导航

- 表、语义、关系、查询、看板、Job、回执、Pack 和 Connector 均按工作区隔离。
- 默认落在“工作区”，主导航为工作区、数据、分析、看板、证据；设置与明细视图为辅助入口。
- “工作区”只显示由真实状态决定的当前任务，不在首页、侧栏和浮层重复同一流程。
- `table`、`view`、`dashboard`、`run`、`action` 使用可恢复 URL；刷新、前进和后退保持真实对象。
- 对象不存在时显示真实空态，不生成样例或猜测对象。

### 数据接入

- 支持 CSV、XLSX、XLSM；旧 XLS 只承诺画像读取，写入前需转换。
- 文件和文件夹共用检查入口；预检已给出影响时不得重复要求预演。
- 文件夹按同类表分组，写入前显示目标、行数、键质量、冲突和去重影响。
- 空工作区只引导接入数据，不展示业务结论、图表或高级维护工具。
- Connector 只执行有界发现、只读预览和同步计划；确认导入复用统一写入边界。
- 跨工作区、符号链接链、其他 AIBI 仓库、未允许来源、任意查询和字面凭据在读取前阻断。
- 凭据仅允许服务端 `env:NAME` 引用，公开响应不得返回引用名或值。

### 语义、关系与查询

- 字段语义记录结构角色、用途、置信度和手工覆盖，自动能力排除内部 `__*` 字段。
- 系统从当前工作区派生只读 Workspace Manifest、Runtime Catalog 和 Business Field Profile；结构画像、自动候选与手工确认必须分层，PII、原始行、凭据和物理路径不得进入公开合同，stale 或 blocked 画像不得作为规划依据。
- 用户纠正、数据字典和说明文档必须先通过声明式 Knowledge Source Adapter 形成工作区隔离的不可变 Semantic Patch Proposal；只有仍然新鲜的提案经人工预演并确认接受后，才成为 reviewed 语义。不得自动学习、静默覆盖或保存原始文档与绝对路径。
- 同名或近义字段跨表竞争时，显式表名优先；证据不足时一次只询问一个最高价值的类型化问题。
- 多维问题完整记录指标、维度、筛选、参与表和统计粒度。
- 关系推荐结合值重叠、基数、复合键、版本和行膨胀；推荐不等于执行许可。
- 跨表执行仅使用当前工作区已保存且验证有效的关系；路径或版本失效时阻断。
- 比率、转化率和占比没有已验证分子/分母计划时必须澄清，不得退化为计数。
- 已确认分析只能先形成复用候选；再次显式提升后才生成 Confirmed Plan Memory。混合召回只排序候选并生成 Recall Receipt，不得替当前计划选字段、关系或执行动作。
- 有限 Research Run 只能从 current Exploration Anchor 建立；计划、修订、反例、敏感性和结论均受固定预算、同线程证据、不可变版本与 freshness 约束，详见 [有限 Research Run](finite-research-runs.md)。
- 预测类请求必须先通过 current Analysis Unit 的确定性 Forecast Readiness 门禁；它只报告样本量、节奏、稳定性、泄漏策略、假设与可解释性，不生成预测值或未来结果。
- 查询只接受白名单参数并返回 Query Plan Receipt，不接受任意 SQL。

工作区上下文、候选/确认、PII 与规划指纹由 [工作区上下文目录](workspace-context-catalog.md) 维护；知识源和审核流程由 [语义补丁与审核收件箱](semantic-review-inbox.md) 维护；历史计划复用由 [确认计划记忆](confirmed-plan-memory.md) 维护；执行细节由 [语义查询合同](semantic-query-planning.md) 维护。

### 图表、看板与连续分析

- 默认请求只创建一个指标卡、柱图、折线图、饼图、表格或文本洞察草案。
- 草案展示来源、字段、聚合、口径、证据、目标和写入影响；真实保存只确认一次。
- 创建空看板只创建容器，不注入组件。
- 已执行查询形成绑定 Receipt 的 Analysis Unit；冻结结果、指纹、形状和验证，不重新猜测口径。
- Chart Adapter 只选择与 Unit 形状兼容的白名单图表；不兼容时解释性阻断。
- 导出只消费已验证 Receipt/Unit，不重新查询或写业务库。
- 分析分支必须保留父结果、查询、动作和拒绝历史；已验证结果可以经预演和确认形成工作区级 Exploration Thread、不可变 Anchor 与结果板。
- 线程恢复必须实时复核 Run、Receipt、Unit、Session/Turn 和来源绑定；失效历史仍可查看但不得继续推导，也不得回退到任意“最新”结果。

探索线程、结果板与恢复边界由 [探索线程与可恢复分析上下文](exploration-threads.md) 维护。

### 通用扩展与 Agent

- 新工作区不启用任何 Domain Pack；Core 只推断结构事实，不静默注入行业语义。
- Agent 必须区分 Structural、Semantic、Business、Operational 与 Behavioral 五层上下文，并生成带来源、版本、新鲜度和未决项的 Business Understanding Frame；个人表达偏好不能改变共享业务事实。
- Domain Pack、Knowledge Pack、Connector Adapter、Provider 和看板单元职责独立，并读取同一工作区运行上下文。
- Pack 启停和版本变化不重解释历史结果；依赖对象进入复核状态。
- 多 Pack 冲突不能按加载顺序决胜；显式选择和手工语义优先，仍有歧义时澄清。
- 本地确定性运行时负责字段、查询、结果和证据；可选 Provider 只能解释或提出必要澄清。
- Runtime Profile 选择按工作区预演并确认；切换 Provider 不得改变 Intent、字段、Capability、Receipt、草案或确认边界。
- Provider 上下文使用固定出站白名单且不包含原始行；输出未通过 JSON、数字和 evidence grounding 时必须静默降级为确定性本地答案并留下脱敏评估回执。
- Agent 计划只使用固定声明式 Operator；只有 Orchestrator 能提交已登记 Capability，Planner、Semantic Reviewer、Evidence Reviewer 和 Narrator 不得调用工具或形成独立执行链。
- Analytical Skill 必须版本化并通过运行时合同、触发槽位、语义 Guard 和 Capability Registry 校验；Skill 只能收缩权限，不能添加 SQL、代码、URL、MCP 或 Registry 外工具。
- 方法型 Analytical Skill 必须由可审计的专用信号命中，声明其必需业务槽位、证据、失败行为和有界步骤；漏斗、留存、异常分诊、分群贡献、驱动调查和决策看板不得退化为同名的单次通用聚合，也不得在关键槽位缺失时静默执行。
- 业务理解发布必须通过固定 Business Expression Case 与确定性 Plan Quality Scorecard；评测不读取用户业务行、不调用 Provider，旧 Case Set 或规划合同的 Scorecard 不得冒充当前结果。
- 互不依赖的只读节点可以并行，但公开事件顺序必须确定；写入和运行回执节点保持串行。Join 必须核对工作区、计划版本、数据/Pack 指纹和证据完整性，任一专家异常时降级为单 Orchestrator 固定复核。
- 只读回答不创建动作草案；写入意图只生成待确认草案。

业务理解合同、首批 Skills 与专题验收见 [业务理解与分析 Skills](business-understanding-skills.md)，质量门见 [计划质量评测](plan-quality-evaluation.md)；完整扩展、Provider、ERP 单元和迁移合同见 [通用扩展框架](extensible-domain-framework.md)。

### Job、安全与本地运行

- 长任务使用工作区隔离 Durable Job，公开状态、阶段、单调进度、事件、结果、错误和证据。
- 取消必须预演并确认，只作用于 AIBI-C 登记 worker；重启中断形成可审计终态。
- Agent、API、CLI 和 Job 复用同一 Capability Contract；越权资源在执行前阻断。
- API 与 UI 只监听回环地址；请求体有上限，CORS 只允许显式来源。
- SQLite 与 DuckDB 使用显式 schema 版本；迁移先验证隔离副本，确认前创建恢复点，失败时恢复双库。
- 备份不包含 `.env`、源文件、业务导出或凭据。

## 需求事实归属

| 内容 | 唯一事实源 |
| --- | --- |
| 体验和页面职责 | [产品体验标准](product-ux-standard.md) |
| 可观察验收行为 | [产品验收矩阵](product-acceptance-matrix.md) |
| 当前实现与限制 | [实现状态](implementation-status.md) |
| 未交付事项 | [未来开发队列](development-roadmap.md) |
| 业务理解合同与 Skills | [业务理解与分析 Skills](business-understanding-skills.md) |
| 工作区上下文与字段画像合同 | [工作区上下文目录](workspace-context-catalog.md) |
| 知识源、语义提案与人工审核合同 | [语义补丁与审核收件箱](semantic-review-inbox.md) |
| 计划记忆与召回合同 | [确认计划记忆](confirmed-plan-memory.md) |
| 业务表达与计划质量评测 | [计划质量评测](plan-quality-evaluation.md) |
| 探索线程、分析锚点与结果板 | [探索线程与可恢复分析上下文](exploration-threads.md) |
| 有限研究、不可变计划修订与统一 Trace | [有限 Research Run](finite-research-runs.md) |
| 预测准备度、物化快照、Metric Monitor 与只读联邦证明 | [本地可信分析后续能力](local-trusted-analytics.md) |
| CLI 命令与突变模式 | [BI CLI 合同](bi-cli-contract.md) |
| 某次验证结果 | [证据索引](../artifacts/README.md) |

## 发布条件

- 仓库身份与隔离门禁通过，默认构建和测试不读取其他 AIBI 工作树。
- `npm run preflight` 通过，作为本地交付前总入口。
- [产品验收矩阵](product-acceptance-matrix.md) 的稳定场景全部通过。
- 新工作区为空；生产 UI 不出现测试素材、默认问题或默认业务结论。
- 中性数据不出现行业语义；Pack 启停、并存、冲突和版本失效行为可解释。
- 浏览器覆盖真实导入、单图、证据、跨表、Connector、响应式窗口和干净控制台。
- 当前能力与限制已更新到 [实现状态](implementation-status.md)，日期结果写入 [证据索引](../artifacts/README.md)。
