# 本地可信分析后续能力

本文件是 AIBI-C 在本地可信边界内扩展预测准备度、物化快照、Metric Monitor 和只读联邦证明的唯一技术事实源。当前交付状态见 [实现状态](implementation-status.md)，未交付顺序见 [未来开发队列](development-roadmap.md)，既有 Analysis Unit、Receipt 与关系执行边界见 [语义查询合同](semantic-query-planning.md)。

## 共同边界

- 所有能力只作用于当前 AIBI-C 工作区，不读取其他 AIBI 仓库、远程账号或未登记来源。
- 本地确定性运行时拥有字段、关系、计算、刷新与持久化权；Provider 不能生成预测、阈值、查询、快照或监控状态。
- 任何消费入口都实时复核数据、schema、关系、Domain Pack、Receipt 和 Analysis Unit 新鲜度；stale 历史可查看但不能作为当前输入。
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

## P2-B：物化分析快照

物化快照将只冻结 current Receipt/Unit 的有界结果与完整来源绑定，供重复读取和后续监控使用，不充当来源替代品。

- 创建、刷新、替换和删除均为显式确认写入；同一精确输入幂等。
- 快照保留 Unit、Receipt、数据/schema/关系/Pack 指纹、创建原因、行数上限、内容哈希和父快照；不保存任意查询或外部路径。
- 来源漂移后旧快照进入 `stale`；历史仍可审计，但默认消费者不回退到最近旧快照。
- 快照最多保留 Analysis Unit 已允许的有界行数，工作区删除和本地迁移必须完整覆盖。

## P2-C：Metric Monitor

Metric Monitor 只比较同一已确认指标定义、相同粒度和兼容窗口下的物化快照，不直接轮询业务来源，也不自动执行动作。

- 监控定义必须绑定指标、时间节奏、比较策略、阈值来源、当前快照和 Capability 版本。
- 首次运行只建立 baseline；后续运行产生 `normal | warning | breached | blocked` 评估和可重放 Trace。
- 阈值必须由用户明确提供或来自经审查的 Domain Pack；没有阈值时只报告变化，不制造告警。
- 任何口径、粒度、来源或快照漂移都阻断比较；不得把缺失值当零或把异常自动解释为业务原因。
- 本地 UI 只展示状态、差异、证据和下一步；不发送通知、不写业务系统、不后台无限调度。

## P2-D：只读联邦证明

只读联邦证明只验证多个已登记 Adapter 的元数据、语义和关系是否足以形成一个可执行计划；首版不跨源执行结果查询。

- 参与来源必须通过现有 allowlist Adapter，凭据继续只使用服务端引用且不进入回执。
- 证明包含来源可用性、字段投影、类型兼容、实体键、关系路径、粒度、筛选下推能力、预算和 freshness。
- 所有来源当前且证明完整时状态为 `provable`；否则为 `blocked` 并列出缺失条件。
- `provable` 不是执行授权、物化授权或写入授权；不得拼接任意 SQL、跨源复制业务行或绕过 Connector 同步确认。

## 退出条件

每个阶段只有在文档、CLI/API 合同、工作区隔离、新鲜度、专项验证、迁移/删除覆盖、前端状态和完整 `preflight` 同时通过后才可标为稳定。后续阶段不能以 Manifest 存在、静态 UI 或单一 happy-path 测试替代真实运行证明。
