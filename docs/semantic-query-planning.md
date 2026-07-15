# 语义查询与跨表执行合同

生产问数必须先解决字段歧义和统计粒度，再判断关系路径是否可执行。规划器只生成结构化证据，不接受任意 SQL 或写入。

## 业务意图与上下文合同

`aibi-agent-intent-frame/v1` 将问题规范化为任务类型、指标、维度、时间、筛选、比较、输出、粒度和未决项。字段概念必须保留 `tableKey`、字段、角色、来源与置信度；Provider 不是必需依赖，也不能静默消歧。

`aibi-semantic-context-bundle/v1` 在当前工作区统一整理字段候选、Context Term/Rule、Confirmed Query、Domain Pack、Analytical Skill 与知识规则。路由固定为 deterministic-first；可选 reranker 只能调整候选顺序，不能移除歧义门禁。Bundle 使用 SHA-256 绑定意图、语义计划和来源。

`aibi-agent-clarification/v1` 把全部未决字段合并为一次澄清，每个候选都必须声明表级来源。前端“我理解的问题”默认显示任务类型、指标、维度、时间、输出和粒度；只有存在歧义时自动展开。

## Evidence Plan 与 Agent Turn

`aibi-agent-evidence-plan/v1` 将意图、上下文、语义规划、白名单查询、草案、完成复核和答案组织为类型化 Step。Step 必须引用固定 Agent Capability，声明依赖、输入/输出指纹、mutation mode、所需证据、阻塞项和完成检查；不存在任意 Operator 或模型工具调用。

`aibi-agent-turn/v1` 与 `aibi-agent-turn-event/v1` 持久化在当前工作区。事件序号严格递增，支持从 `after-sequence` 续读；公开事件不包含私有推理、密钥或原始行。`POST /api/agent/turns` 创建回合，`GET /api/agent/turns/:id/events` 以 SSE 回放事件；现有 `/api/agent/ask` 和 `/api/agent/explain` 复用同一 Turn 服务。

完成前必须生成 `aibi-agent-completion-validation/v1`，检查计划、工作区、Intent/Context schema、上下文新鲜度、指纹和答案。语义歧义是可安全呈现的 `blocked`，合同损坏是 `failed`；二者不能退化为无证据答案。

## 受限工作流图与专家视图

`aibi-agent-workflow-graph/v1` 只允许 `context`、`resolve`、`clarify`、`query`、`validate`、`unit`、`chart`、`explain`、`export`、`branch`、`join` 十一个声明式 Operator。节点不得携带代码、脚本、SQL、URL、任意工具或处理器；只有 Orchestrator 可以提交已登记 Capability，请求写入或产生运行回执的节点必须串行。

Planner、Semantic Reviewer、Evidence Reviewer 和 Narrator 是同一 Turn 的只读结构化角色视图，不是拥有独立权限的 Agent。它们只能返回 `pass`、`block` 或 `revise` 以及证据引用，工具权限固定为零。互不依赖的只读节点可以并行计算，但公开事件按图的确定性顺序发布；任一专家异常或越权输出会被固定 Orchestrator 复核替代。

`aibi-agent-workflow-join/v1` 在合并前逐项核对父节点齐全、工作区、plan version、数据指纹、Domain Pack 指纹和证据完整性。图包含循环、未知 Operator、专家 Capability、并行写入或指纹漂移时必须阻断，不能以可执行结果代替合同通过。

## Session、Fork 与 Context Snapshot

`aibi-agent-session/v1` 将 Turn 链绑定到单一工作区；连续提问自动引用当前 Turn，重启后可由 SQLite 恢复。Fork 创建新的 Session，并以父 Turn 作为第一回合的显式父引用，父 Session 的当前 Turn、上下文指纹和历史不被修改。

`aibi-agent-context-snapshot/v1` 提供四级压缩合同：保留少量展示主题、仅保留对象引用、生成结构化摘要、Provider overflow 后反应式压缩。任何级别都不删除 Turn，也不丢失 Receipt、Plan、Skill、未决项和阻塞引用；聊天摘要不会自动成为 Context Term、Rule、Confirmed Query 或手工语义。

Resume 会实时核对引用对象。缺失 Turn、Receipt、Analysis Run 或 Action Draft 进入 `staleRefs`，未经显式复核不能继续同一 Session；跨工作区查询始终按未知 Session 处理。

## Analytical Skill 与 Policy Hook

`aibi-analytical-skill/v1` 是独立于 Domain Pack 的声明式分析方法。内置目录覆盖概览、趋势比较、构成、排名、异常复核、双表核对和数据质量解释；外部 Manifest 必须先 lint、确认安装，再按工作区确认启用。匹配只使用已解析 `taskType`、语义角色和显式 Pack 依赖，不按文件顺序或模型偏好静默决胜。

Skill 只能引用已登记 Agent Capability，并声明步骤模板、必需证据、阻塞规则、输出 schema、确认模式和固定资源上限。Python、JavaScript、Shell、SQL、HTML、URL、任意工具键和跨 AIBI 仓库路径在安装前阻断。`aibi-agent-policy-hooks/v1` 使用固定校验器复核工作区、能力、声明纯度、资源和证据引用；Hook 本身不是脚本扩展点。

## Agent Runtime Profile 与 Provider 评估

`aibi-agent-runtime-profile/v1` 将 Provider、模型、wire API、结构化输出、context window、输出预算、超时和重试从业务语义中分离。工作区默认选择 `deterministic`；可选 `deepseek` 或显式 loopback `local-openai`。Profile 切换先预演再确认，只改变解释层，不能改变 Intent、字段、Capability、SQL/Receipt、草案或确认边界。

Provider 只接收 `aibi-agent-provider-context/v1` 白名单字段；原始行、样例记录、密钥、本地路径、邮箱和手机号不出站。返回值必须精确匹配固定 JSON shape，并通过数字 grounding、evidence ref、动作声明和 Capability/字段声明门禁；任一失败回落到本地确定性答案。

`aibi-agent-provider-evaluation/v1` 只保存脱敏 request/context fingerprint、Profile、模型、耗时、token、估算成本、重试、降级和校验状态。Shadow evaluation 可用同一上下文比较已审查 Profile，但 Provider 写 Receipt/草案计数固定为零；设置页只展示工作区选择和回归摘要，不暴露凭据或上下文。

## 规划流程

1. 从当前工作区注册表、字段语义和指标构建候选，排除内部 `__*` 字段。
2. 记录命中的字段、指标和别名；跨表竞争时返回 `needs-clarification`。
3. 为每个字段声明表、角色和统计粒度，保留全部指标、维度与筛选。
4. 只在当前工作区已保存关系图中寻找路径，并记录版本、方向和行膨胀。
5. 缺路径返回 `needs-relationship`；低置信、版本过期或放大风险返回 `needs-validation`。
6. Receipt 保存候选、选择、未决项、参与表、路径、风险、版本和计划哈希。

## 消歧与粒度

- 同名字段不能按导入顺序、列顺序或模型偏好决胜；别名只能召回候选。
- 用户明确表名后可在目标表内选择，依据必须进入 Receipt。
- 多个未决字段合并为一个候选面；一次澄清后仍不安全时明确阻断。
- 复合业务键必须整体保存和验证，不能退化为第一列。
- 比率、转化率和占比必须有已验证分子、分母、筛选与粒度，否则澄清。
- 筛选只接受字段、白名单操作符和值；右表预聚合覆盖完整连接键。
- 数据导入、覆盖或合并递增 `data_version` 并复验关系；过期关系标记 `stale`。
- 跨表金额必须先证明每张表的粒度、函数依赖和无放大。

## 执行边界

语义计划使用 `aibi-semantic-query-plan/v1`，状态为 `not-applicable`、`ready`、`needs-clarification`、`needs-relationship` 或 `needs-validation`。受控执行使用 `aibi-semantic-query-execution-plan/v1`。

当前开放：

- 一至三跳线性路径；每条关系都必须来自当前工作区、状态为 `validated`，并同时保存和匹配两侧 `data_version`。
- 正向关系按保存的 `INNER` 或 `LEFT` 执行；反向关系只允许 `INNER`，且必须具备反向行膨胀证据。
- 指标只能位于路径末端；维度可来自根表或中间表。规划器必须选择一条覆盖全部必需表的全局线性路径，不能给每张表各选一条局部最短路径；自然问句优先选择能完整覆盖“维度到指标”路径的根表，多个同等根或同表异键路径必须澄清。候选枚举达到安全上限且无法证明穷尽时标记 `pathSearchIncomplete` 并 fail closed；只有用户提供完整 `relationKey` 序列后才可绕过通用枚举继续验证。
- 根表与路径澄清面必须分别展示可选根表，以及每条路径的表序列、连接键和 `relationKey`；用户选择后，客户端保留原问题并附加显式根表或完整关系键序列，CLI、API 与 Agent 都按该选择重规划，不能静默采用候选顺序。
- 请求筛选和关系筛选可作用于任一跳；白名单 pre-filter 在对应表进入连接前执行，post-filter 在完整路径上执行。
- 已保存的右表预聚合可跨跳复用。`sum`、`count`、`min`、`max` 只有在部分聚合与最终 rollup 可证明一致时执行；预聚合后的 `avg` 与 `count-distinct` 保持阻断。
- `count` 统计事实行而不是可空字段值；LEFT JOIN 的空侧计数为 0，真实但指标字段为 NULL 的事实仍计为一行。`sum`、`avg`、`min`、`max` 的空侧必须保留 NULL 并展示为“无数据”，不能伪装成已验证的零值。

每次运行生成 `aibi-relationship-path-proof/v1`，逐跳记录输入/输出粒度、行数、基数、函数依赖、筛选、预聚合、版本和 blocker，并额外证明所有作用域内末端事实都能从根表到达。任何中间孤儿链、迟到维度、M:N 放大、关系版本缺失/漂移或末端事实不可达都必须 fail closed。

直接 `query-relationship` 同样受当前版本和扇出合同约束：1:N 路径上的 one-side 指标不得静默重复，many-side 指标只有在验证有效时执行。请求若覆盖筛选或预聚合，必须在同一事务和数据快照内按最终有效形状重新预演，旧关系的扇出证明不得复用。

当前阻断：超过三跳、非线性关系树、反向 `LEFT JOIN`、未证明安全的 M:N、多个等价业务路径、未穷尽的高密度路径搜索、无法安全 rollup 的预聚合，以及指标不在路径末端的计划。

执行前必须在同一事务内重新构建计划、读取当前版本、生成运行时证明、执行查询并写入 Receipt。关系被删除、替换或改版时返回 `semantic-plan-changed-before-execution`，不得回退到单表猜测。Receipt、Analysis Unit、图表适配、导出和 Confirmed Query 都要重新核对全部源表、路径证明、关系定义、数据版本和 Domain Pack 指纹。

## 验证

```powershell
npm run verify:semantic-plan
npm run verify:receipt-freshness
npm run verify:relationship-safety
npm run verify:agent-intent
npm run verify:agent-turns
npm run verify:agent-sessions
npm run verify:analytical-skills
npm run verify:runtime-profiles
npm run verify:restricted-workflow
npm run verify:composite-relationships
npm run verify:ui-semantic
```

跨仓库隔离统一遵循根目录 [AGENTS.md](../AGENTS.md)。
