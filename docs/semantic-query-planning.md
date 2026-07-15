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

- 一跳：关系为当前 `validated`，指标使用白名单聚合。
- 两跳：严格线性正向路径，每跳版本匹配且 `rowExpansion <= 1`。

当前阻断：三跳、反向路径、跨跳筛选和跨跳预聚合。

执行前必须重新构建计划并比对 SHA-256。关系被删除、替换或改版时返回 `semantic-plan-changed-before-execution`，不得回退到单表猜测。

## 验证

```powershell
npm run verify:semantic-plan
npm run verify:agent-intent
npm run verify:agent-turns
npm run verify:agent-sessions
npm run verify:analytical-skills
npm run verify:runtime-profiles
npm run verify:composite-relationships
npm run verify:ui-semantic
```

跨仓库隔离统一遵循根目录 [AGENTS.md](../AGENTS.md)。
