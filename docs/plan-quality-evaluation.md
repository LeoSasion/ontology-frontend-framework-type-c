# 计划质量评测合同

本文是 Business Expression Case、确定性 Plan Quality Scorecard 和端到端规划评测的唯一技术事实源。业务理解总合同见 [业务理解与分析 Skills](business-understanding-skills.md)，发布状态见 [实现状态](implementation-status.md)。

## 用户结果

数据维护者可以在设置页运行固定业务表达基准，看到助手对字段、口径、时间、关系和澄清边界的质量，而不需要发送真实数据或启用 Provider。一次运行必须回答：

- 哪些表达通过、阻断或需要澄清，以及失败属于哪个质量维度。
- 当前版本是否达到发布门槛；单一总分不能掩盖零容忍违规。
- 相同版本、Case 集和运行合同能否得到相同计划与评分。
- 结果绑定哪个 Case Set、Core 版本、Skill 集和 Domain Pack 作用域。

## Business Expression Case

`aibi-business-expression-case/v1` 是不可变声明式用例，只允许下列内容：

- `caseId`、`caseVersion`、`category`、本地化业务表达和固定夹具引用。
- 显式 `domainPackScope`；空数组表示 Core 中立环境，不能继承当前工作区 Pack。
- 期望计划状态、字段绑定、业务信号、澄清槽位、执行边界和安全不变量。
- 评分维度与稳定权重；不包含 SQL、代码、URL、工具、用户路径、凭据或真实数据。

内置 Core 基准覆盖同义词、同名字段、比率、去重实体、状态、时间比较、跨表路径和 Pack 隔离。Case Catalog 版本变化必须产生新的 Case Set fingerprint；旧 Scorecard 保留原绑定，不能被新 Case 静默重解释。

## 评测运行

`aibi-plan-quality-evaluation/v1` 在 AIBI-C 本地确定性运行时内完成：

1. 为每个 Case 创建独立内存夹具，显式装载字段语义、指标和已验证关系。
2. 依次生成 Semantic Plan、Business Intent Frame、Business Understanding Frame、受约束 Execution Plan 和评测证据。
3. 同一 Case 重放两次，比较规范化计划指纹；时间、随机 key 和展示文案不参与一致性判断。
4. 只把 Case id、合同 fingerprint、分类检查、计数和聚合指标写入当前工作区的 Scorecard。

评测不读取当前工作区业务行，不调用 Provider，不形成动作草案，不执行任意 SQL/代码/网络/进程能力，也不能修改字段、指标、关系、Pack、Skill、Receipt 或 Confirmed Plan Memory。运行失败必须留下终态和失败原因，不能把未运行 Case 计为通过。

## Plan Quality Scorecard

`aibi-plan-quality-scorecard/v1` 至少包含：

- `coreSlotAccuracy`：Case 要求的核心业务槽位被正确解析的比例。
- `fieldBindingPrecision`：所有已绑定字段中符合 Case 期望的比例，额外绑定同样计入错误。
- `safeClarificationRate`：需要澄清的 Case 是否只提出最高价值的一个问题并保持不可执行。
- `evidenceCoverage`：字段、关系和业务定义检查是否具有对应的本地证据引用。
- `replayConsistency`：相同 Case 两次规范化计划是否完全一致。
- `silentDisambiguationCount`、`permissionEscalationCount`、`crossWorkspaceLeakCount`、`domainPackLeakCount`。

发布门槛沿用业务理解合同：核心槽位正确率不低于 95%，已绑定字段 precision 不低于 98%，安全澄清比例不低于 90%，证据覆盖和重放一致性为 100%；静默消歧、越权、跨工作区泄漏和跨 Pack 泄漏必须为 0。任何零容忍项非零时 `releaseReady=false`，即使加权总分较高。

Scorecard 只用于质量证据，不能授权当前用户问题的字段选择、关系路径、执行或写入，也不能作为 Provider 优于本地确定性计划的依据。

## 工作区、Pack 与隐私边界

- Case 在固定隔离夹具中运行；当前工作区只拥有结果记录，不向夹具提供业务数据。
- 每个 Case 必须声明 Pack 作用域；不同作用域分别评分，Pack 不能按加载顺序影响 Core Case。
- API 只接受当前活动工作区，不接受任意工作区覆写；CLI 的显式工作区参数仍受现有隔离门禁。
- 列表只返回有界 Scorecard；不保存原始用户 Prompt、结果行、本地绝对路径或凭据。
- 工作区删除同步删除 Scorecard；配置导出不携带评测历史，因为它是证据而非配置。

## 产品呈现

设置页把“业务理解质量”与“Provider 运行摘要”分开：前者衡量本地计划合同，后者只衡量解释层。默认只显示是否达到门槛、最近运行时间和关键指标；Case 明细按需展开。运行按钮必须提供 loading、失败、空状态和工作区切换防串写，不能用单一大分数制造虚假确定感。

## 失效与验收

下列变化使旧 Scorecard 仅可审计、不可代表当前发布状态：Case Set fingerprint、评测策略、Core 规划合同或内置 Skill fingerprint 变化。列表时必须实时给出 `current` 与 `usableForRelease`，不得把 stale 记录回退为当前结果。

专项验收必须证明：Case Catalog 有界且不可执行；八类表达被覆盖；两次重放一致；阈值和零容忍项按定义计算；Pack、工作区、Provider 和用户数据隔离；数据库迁移、删除级联、CLI/API/UI 与响应式状态完整；全量回归和真实本地运行同时通过。
