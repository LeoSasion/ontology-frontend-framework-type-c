# 本地可信分析后续能力

本文件是 AIBI-C 在本地可信边界内扩展预测准备度、物化快照、Metric Monitor 和只读联邦证明的唯一技术事实源。当前交付状态见 [实现状态](implementation-status.md)，未交付顺序见 [未来开发队列](development-roadmap.md)，既有 Analysis Unit、Receipt 与关系执行边界见 [语义查询合同](semantic-query-planning.md)。

## 共同边界

- 所有能力只作用于当前 AIBI-C 工作区，不读取其他 AIBI 仓库、远程账号或未登记来源。
- 本地确定性运行时拥有字段、关系、计算、刷新与持久化权；Provider 不能生成预测、阈值、查询、快照或监控状态。
- 任何消费入口都实时复核数据、schema、关系、Domain Pack、Receipt 和 Analysis Unit 新鲜度；stale 历史可查看但不能作为当前规划输入。Metric Monitor 的 baseline 是唯一受限例外：它只能作为内容哈希、原 Unit/Receipt 绑定均完整的历史比较证据，不能续算、规划或替代当前快照。
- 新能力不接受任意 SQL、Python、Shell、脚本、插件或无限重试；有界 Adapter 和 Capability 是唯一执行面。
- 只读评估不要求确认；创建、替换、刷新或删除持久对象必须 dry-run、精确 fingerprint 和一次显式确认。
- 公开合同默认只返回统计、指纹、状态和证据引用，不复制业务结果行、源文件路径、凭据或 Provider 推理。

## P2-A：Forecast Readiness（已交付）

`aibi-forecast-readiness/v1` 只回答“当前序列是否足以进入受限的预测评估”，不回答未来数值。

输入必须是当前工作区内 current、ready、Receipt 绑定的单序列 Analysis Unit，并声明正整数 `horizon`。评估固定覆盖：

1. `source`：Unit、Receipt 和全部来源仍然 current；
2. `sample`：至少 24 个可用、唯一、可排序的时间点，预测跨度不超过历史长度的四分之一；
3. `cadence`：时间值可解析，间隔足够规律，推断缺口率不超过 10%；
4. `stability`：数值完整率、极端跳变率和前后窗口水平漂移位于保守门槛内；
5. `leakage`：只允许目标滞后值，固定 rolling-origin 评估，不接受未来字段或任意特征声明；
6. `assumptions`：单序列、当前截止点、推断节奏和有界 horizon 均显式进入合同；
7. `explainability`：至少存在 last-value baseline，输出只允许 baseline、lag 和稳定性诊断。

状态只有 `ready-for-evaluation | blocked`。即使全部通过，`canGenerateForecast` 仍为 `false`，下一步也只能建立有界 backtest 计划；未通过时返回逐门禁 blocker 和修复方向。响应不包含输入行、未来时间点或预测值，fingerprint 由 Unit/Receipt 绑定、horizon、门禁版本和确定性统计共同生成。

`forecast-readiness` Analytical Skill 只在明确的预测准备度信号下参与匹配；预测目标、时间字段、粒度、截止点和 horizon 任一缺失时只提出一个最高价值问题。Skill 不能获得查询以外的新权限，方法计划也不构成已执行预测。

CLI、API、Agent 与按需展开的分析面板消费同一合同。诊断命令成功与门禁结果分离：成功评估返回 `ok=true`，是否可进入受限评测由 `readyForEvaluation` 和合同 `status` 表达；`blocked` 是有效诊断，不是运行故障。

## P2-B：物化分析快照（已交付）

`aibi-analysis-snapshot/v1` 只冻结 current、ready、Receipt 绑定 Analysis Unit 的有界结果与完整来源绑定，供重复读取和后续监控使用，不充当来源替代品。

- `create | refresh | replace | delete` 都先返回 `aibi-analysis-snapshot-plan/v1`，只有精确 `planFingerprint` 与显式确认同时满足才写入；同一精确输入幂等且不重复新增。
- 快照保留 Unit/Receipt key 与定义、结果、数据、schema、关系、来源、Domain Pack、Workspace Manifest 指纹，以及创建原因、行数上限、内容哈希和父快照。公开列表只返回摘要、状态和指纹，不返回冻结行、任意查询、外部路径或 Provider 内容。
- `refresh` 只接受指标、维度、聚合、筛选、参与表、关系路径和结果形状相同的新 Unit，并追加不可变子快照；语义变化必须显式 `replace`，同样追加子快照而不覆盖父对象。
- 来源漂移、Unit/Receipt 缺失或绑定变化后旧快照进入 `stale | missing`；历史仍可审计，但 `usableForPlanning=false` 且所有消费者固定 `staleFallbackUsed=false`。
- 删除只擦除冻结内容并保留 lineage tombstone；快照最多保存 500 行，工作区删除会清理全部快照，SQLite schema v14 的隔离迁移、恢复点和回滚覆盖该表。

CLI、API 与 Analysis Unit 下按需展开的面板消费同一合同。面板在操作期间禁用重复提交并拒绝晚到请求；创建原因和行数上限可核对，确认成功后保留明确结果消息。Provider 不参与快照生成、刷新、替换或删除。

## P2-C：Metric Monitor（已交付）

`aibi-metric-monitor/v1` 只比较同一已确认指标定义、相同粒度和兼容窗口下的单值物化快照，不直接轮询业务来源，也不自动执行动作。

- `create | replace | delete` 都先返回 `aibi-metric-monitor-plan/v1`，精确 `planFingerprint` 与显式确认同时满足才改变定义；定义绑定指标字段、复核节奏、比较策略、方向、用户阈值、warning ratio、baseline Snapshot、Capability 版本和定义指纹。replace 追加不可变子定义并退休父定义，delete 保留 tombstone 与历史评估。
- 首次手动运行只建立 `baseline`；后续手动运行产生 `normal | warning | breached | blocked` 的 `aibi-metric-monitor-evaluation/v1`，Trace 固定保存定义、baseline/current 快照内容哈希、兼容性、比较规则、blocker 与零副作用回执。
- baseline 必须在定义创建时 current；后续数据版本变化使其 stale 时，只要冻结内容、原 Unit/Receipt 绑定仍完整，仍可作为历史比较证据。current Snapshot 必须实时 current；两者的 semantic fingerprint、参与表身份、关系路径与 Domain Pack 必须一致。数据内容版本可以变化，已使用字段或结果形状变化会进入 semantic fingerprint 并阻断比较。
- 首版阈值只接受用户明确输入，未配置阈值时只报告变化并保持 `normal`，不制造告警。缺失值、非数值、多行结果、百分比基线为零、语义或关系漂移都产生 `blocked`，从不把缺失值当零或把异常状态解释为业务原因。
- CLI、API 与快照面板消费同一合同。cadence 只记录人工复核意图；没有后台 scheduler、来源轮询、通知、Webhook、业务系统写入或 Provider 参与。运行只写工作区隔离的本地评估证据，不要求业务写入确认。

## P2-D：只读联邦证明（已交付）

`aibi-federation-proof/v1` 只验证多个已登记 Adapter 的元数据、语义和关系是否足以形成一个可执行计划；首版不跨源执行结果查询。

- CLI、API 与数据工作台高级面板消费同一确定性合同；请求只绑定当前活动工作区，不接受客户端指定工作区。输入只允许 2–4 个连接、逐连接字段投影、已保存关系 key、安全粒度、`table.field` 实体键、声明式过滤和显式预算。
- 参与来源必须为 active、同步成功且目标表仍存在，并通过既有 allowlist Adapter 的实时元数据发现。文件与 SQLite 来源的当前资源指纹必须等于最近一次确认同步的资源指纹；HTTP 来源目前没有可比的整源 freshness 指纹，因此保持 `blocked`，不能因接口可访问而误报 current。
- 字段投影必须存在于实时 Adapter 列目录并具有当前工作区语义；粒度必须绑定所选目标表或其实体键，实体键必须是 `identity_key | identifier` 字段。类型兼容只接受保存关系的 validated 证据，不用字段名相似度替代。
- 关系必须只连接所选来源的不同目标表、形成连通路径、无 validation blocker，且保存的 `dataVersions` 与当前表版本完全一致。任何来源变化或关系版本变化立即阻断。
- 过滤只接受固定操作符 allowlist 和真实来源字段，不接受值表达式、SQL、脚本或 Provider 生成语句；来源数、投影字段数、关系数和过滤数均受预算门禁。
- 所有来源当前且十个门禁完整时状态为 `provable`；否则为 `blocked` 并列出逐门禁缺失条件。证明 fingerprint 由当前工作区、来源元数据、关系版本、计划和门禁共同确定，可重放但不持久化业务行。
- `provable` 不是执行、物化或写入授权。公开结果固定声明 `crossSourceQuery=false`、`rowCopy=false`，不返回业务行、源路径、凭据引用名或凭据值，也不绕过 Connector 同步确认。

## 退出条件

每个阶段只有在文档、CLI/API 合同、工作区隔离、新鲜度、专项验证、迁移/删除覆盖、前端状态和完整 `preflight` 同时通过后才可标为稳定。后续阶段不能以 Manifest 存在、静态 UI 或单一 happy-path 测试替代真实运行证明。
