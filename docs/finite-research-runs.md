# 有限 Research Run

本文件是 AIBI-C 有限研究工作流、不可变计划修订、反例/敏感性检查和统一追踪的唯一设计事实源。它建立在 [探索线程](exploration-threads.md)、[业务理解与分析 Skills](business-understanding-skills.md) 和 [语义查询合同](semantic-query-planning.md) 之上，不新增任意执行权限。

## 用户结果

用户可从一个当前且可续算的 Exploration Anchor 建立有限 Research Run，把一个复杂问题拆成有上限的假设、反例和敏感性检查，并持续附加同一线程内已验证的结果。最终结论明确区分 `supported | challenged | mixed | inconclusive`，同时保留完整的计划版本、证据引用和公开事件轨迹。

Research Run 不是联网研究、聊天摘要或自动结论生成器。它只组织 AIBI-C 当前工作区已经产生的 Run、Receipt、Unit、Turn 和 Anchor，不复制结果行，不让 Provider 生成 SQL、工具调用或写入。

## 核心合同

### `aibi-limited-research-run/v1`

- 绑定当前工作区、Exploration Thread、基线 Anchor 和当前计划修订；
- 保存固定预算、状态、当前 revision、实时 freshness 和 fingerprint；
- 状态只允许 `active | completed | blocked`，历史对象不得原地改写为另一研究；
- 基线或任一已采用证据 stale/missing 时，历史仍可读，但不得继续、修订或完成。

### `aibi-research-plan-revision/v1`

- 第一个 revision 固化目标、方法 Skill、假设、反例、敏感性检查和退出条件；
- 后续修订必须引用父 revision、父 fingerprint 和显式原因，序号单调递增；
- 修订只能在初始预算内收缩或重排研究问题，不能换工作区、基线、线程、Capability 或扩大预算；
- 每个 revision 都不可变；确认前必须用 dry-run `planFingerprint` 防止预演后漂移。

### `aibi-research-observation/v1`

- 每条 Observation 引用同一 Exploration Thread 内一个 current Anchor，并标记 `evidence | counterexample | sensitivity`；
- 保存研究 step、`supports | challenges | inconclusive` verdict、说明、Anchor binding fingerprint 和 revision fingerprint；
- 不保存查询结果行、SQL、Provider 私有推理或绝对路径；
- 同一 Anchor、revision、kind 和 step 幂等，超过预算或绑定漂移时阻断。

### `aibi-research-run-trace/v1`

统一事件序列只公开计划创建、revision 创建、Observation 采纳、完成/阻断和 freshness 变化。事件序号只增不改；每条事件绑定 workspace、Research Run、revision、公开摘要和脱敏 payload，不能携带业务结果行。

## 固定预算与权限

默认上限：12 个计划步骤、10 个声明检查（其中最多 6 个假设、3 个反例检查、3 个敏感性检查）、8 条 Observation、3 个 revision。运行时可选择更小的值，不能超过固定上限。

- 只接受同一工作区、同一 Exploration Thread 的 current Anchor；
- 只组合现有只读分析 Capability；Research Run 自身不执行 Query、不访问网络、不读取主机文件；
- Provider 只能解释已验证摘要，不能改变计划、verdict、绑定或终态；
- 建立、修订、采纳 Observation 和完成均采用 dry-run + 显式确认；
- counterexample 和 sensitivity 至少各有一条 current Observation，才允许形成非 `inconclusive` 结论。

## 失败行为与退出条件

| 场景 | 行为 |
| --- | --- |
| 基线 Anchor stale/missing | 保留历史并标记 blocked；禁止继续或完成，不回退到其他“最新”对象 |
| 计划超过预算 | dry-run 阻断，不截断、不静默丢弃检查 |
| revision 的父 fingerprint 不匹配 | 要求重新读取当前 revision 后再预演 |
| Observation 不属于同一线程或已 stale | 拒绝采纳，不复制其摘要或结果 |
| 缺少反例或敏感性证据 | 只能保持 active 或以 `inconclusive` 完成，不能输出已验证业务结论 |
| 任一证据后来漂移 | 历史结论仍可审计，但 `usableForPlanning=false`，不能继续派生 |

Research Run 在预算耗尽、显式完成、证据漂移或用户停止时退出；它不会无限循环重规划，也不会自动产生新分支。

## 验收门槛

- 计划、revision、Observation、结论和事件可在重启后恢复，且严格工作区隔离；
- revision 历史不可变，错误父 fingerprint、超预算和跨线程证据全部阻断；
- current/stale/missing 由绑定的 Anchor 实时派生，不采用 stale fallback；
- 完成前必须覆盖 counterexample 和 sensitivity，统一 Trace 的事件顺序和 fingerprint 可重放；
- CLI、API 和 UI 展示同一合同，UI 不渲染结果行或隐藏 Provider 权限；
- 工作区删除、schema 迁移/回滚、文档、专项验证和完整 `preflight` 同时通过。
