# 服装电商可信查询 v1

本文是 `Apparel Commerce Trusted Query v1` 的唯一技术合同，规定 current 数据绑定、导入计划、服装实体证明、分析方法和结果状态。它不复制任何其他 AIBI 仓库的实现，也不把领域规则注入 Core 默认行为。

## 目标与边界

v1 只承诺一条可审计闭环：

`current workspace sources -> current sourceRun -> semantic / relationship proof -> deterministic query -> Query Plan Receipt -> executed result`

只有 `executed` 且具备 current binding、非空结果和计划/结果证据的 Receipt 可以支撑金额、排名、比例或趋势。`draft`、`blocked`、`simulation` 与 `stale` 不得投影为确定经营结论。

## M1｜Trusted Execution Gate

### Typed QueryIntent

`aibi-trusted-query-intent/v1` 固定记录以下会改变数字的槽位：

- `method`：overview、ranking、concentration、pareto 或 decile；
- `entity` 与 `grain`；
- `measure` 与 `aggregation`；
- `filters` 与 `timeRange`；
- `sort` 与 `limit`；
- 每个槽位的来源、状态和未决原因。

measure 不明确时不得选择首个字段；aggregation 不明确且会改变含义时不得默认 `SUM` 或 `COUNT`。`Top 20` 与 `Top 20%` 是不同意图。

### Execution Coverage

`aibi-query-execution-coverage/v1` 逐项核对 QueryIntent 与真实执行计划：

- measure、aggregation、grain 已编译；
- 每个显式 filter 和 time range 已下推；
- sort 与 limit 语义一致；
- 未使用静默字段或聚合回退。

任一显式槽位未进入执行计划时必须在查询前阻断，不得执行全表聚合后附加说明。

### Current Binding 与结果状态

可信执行至少绑定：

- `workspaceId`；
- `sourceRunId`，且等于工作区 current sourceRun；
- 参与表及 `dataVersion`；
- workspace planning / semantic fingerprint；
- QueryIntent、Execution Plan 与 Result fingerprint。

结果状态固定为 `executed | draft | blocked | simulation | stale`。来源、语义、关系、计划或结果任一漂移后，历史对象只可审计并投影为 `stale`。

## M2｜Atomic Import Plan

`aibi-atomic-import-plan/v1` 的规范化 fingerprint 至少包含：

- 按稳定顺序排列的来源 identity、相对标签和 content hash；
- 文件到逻辑表的分组；
- schema 与类型决策；
- unique-key candidate 及 `auto_candidate | owner_confirmed` authority；
- 空键、部分空键、文件内与跨文件重复键；
- conflict policy；
- 每文件及每逻辑表的 insert、update、skip 与 final row count；
- PII classification；
- workspace 与 parent/current sourceRun binding。

自动键只能用于预检。键未由 owner 确认、键质量不满足门槛或提交前 fingerprint 漂移时不得 commit。所有逻辑表必须在一个事务中完成；只有全部成功后才创建并切换 current sourceRun。

SQLite schema v15 通过 `source_run_tables` 保存同一原子批次的全部逻辑表成员；查询请求的所有参与表都必须属于该 current sourceRun，不能用多个独立导入的“各自最新表”拼成伪 current 批次。

## M2｜Apparel Entity Mapping Proof

服装实体至少分为三层：

1. `style_spu`：款式、SPU、款号，用于商品企划与生命周期；
2. `product_id` / `product_link`：平台商品或上架链接，用于流量、转化与平台运营；
3. `merchant_sku`：颜色乘尺码的可售单元，用于库存、履约、退款规格与补货。

`color`、`size` 与 `barcode` 是 merchant SKU 的属性或外部标识，不自动等同于任一实体层级。

`aibi-apparel-entity-mapping-proof/v1` 必须复用 Core 关系证明并补充：

- 非空覆盖率与 distinct overlap；
- 左右唯一性、基数和 fan-out；
- 时间覆盖；
- 平台与店铺作用域；
- PII / 敏感等级；
- 数据版本、relationship fingerprint 与 blockers。

字段名、别名或 Provider 判断只能产生 candidate，不能授权映射。

该证明只在当前工作区显式启用 `platform-commerce` Domain Pack 后适用。Pack 未启用时返回 `not-applicable`，不得用服装实体规则阻断通用表；启用后，实体 candidate 仍必须通过值重合、唯一性、基数、fan-out、时间、作用域和隐私门禁。

## M3｜服装商品分析方法

### 排行 / Top N

必须返回逐实体结果、稳定业务键、排序方向、Top N、同额名次规则与完整全集大小。销售名次不得与复盘优先级混用。

### 集中度

必须使用完整有效实体全集和正的总额分母，返回逐实体贡献与累计贡献。Top 百分比按实体数量向上取整，并列边界实体保持同组，同时披露实际实体覆盖比例。

### Pareto / 二八

必须同时回答：

- 前 20% 实体贡献多少；
- 达到 80% 累计贡献需要多少实体及其占比。

缺少任一部分时不得声称二八成立。

### 十分位、ABC 与经营角色

- 十分位只在有效实体不少于 10 且并列边界规则完整时启用，否则降级为 `concentration_only`；
- ABC 在 v1 只定义槽位与 blocker，不执行分类；
- 爆款、潜力款、常销款、滞销款在 v1 只定义必需的趋势、库存/库龄、生命周期、利润和退款证据；缺证据时只能输出高贡献或复盘候选。

## UI 与证据

UI 固定显示 `executed | draft | blocked | simulation | stale` 五态，并同时展示 Receipt key、sourceRunId 与关键 blocker。该状态描述 Query Receipt / 经营结论资格；一个 `blocked` 查询可以同时产生供用户核对的 Action Draft，但确认草稿只改变 UI 对象，不能把未执行 Receipt、经营数字或 Confirmed Query Candidate 提升为可信结果。真实客户式验收必须将截图与同次 Receipt/sourceRun 对齐；旧截图、ERP 输出或长期答案库不得冒充当前回执。

### 可视化投影合同

- 可视化层只读消费同次 Query Receipt、Analysis Unit、Chart Adapter 与方法证据，不发起查询、不重新聚合、不按提示词猜图型或单位；
- 必须严格校验 `executed`、`canSupportBusinessConclusion === true`、完整执行覆盖、正行数、current sourceRun，以及 Receipt/Unit/Adapter 的 key 与结果指纹一致；任一条件缺失都不挂载数值图形；
- 排行与比较保留运行时行顺序、稳定业务键和并列边界；趋势保留时间顺序；非法数值和空值不得静默变成 0；
- Pareto 只展示当前结果集中已经绑定的贡献和累计贡献。若结果只覆盖头部或 80% 边界，标题、图注和可访问文本必须明确这是“边界证据”，并披露显示实体数 / 完整实体数，不能绘成或声称完整 Pareto 曲线；
- ABC、经营角色、预测、补货以及任何 `draft | blocked | simulation | stale` 结果均不得通过图表恢复为确定经营结论；状态切换后旧 SVG、tooltip、数值与可访问文本必须一并卸载。

## v1 暂时关闭

- 任意或未保存跨表 Join、超过三跳、非线性关系树、反向 LEFT JOIN 和未证明安全的 M:N；
- 自动键直接提交、文件夹部分成功和 fingerprint 漂移后继续写入；
- Agent 或 Provider 批准字段、关系、阈值、指标或自己的答案；
- 任意 SQL、任意代码、模型自主工具循环和隐式 Domain Pack 启用；
- ABC、经营角色、预测、补货和自动业务动作；
- draft、blocked、simulation 或 stale 结果进入经营结论。

已保存、current、validated 且通过逐跳证明的一至三跳线性关系仍可执行，不因本合同退化。

## 发布与验收

每次只针对一个 gap 使用一次性工作区或一次性运行库，按 owning contract 判断失败归属。发布证据至少包括：

- 合同级确定性回归；
- current sourceRun 与漂移阻断；
- filter/time 下推正反例；
- 原子导入与失败回滚；
- Apparel Entity Mapping Proof；
- 排行、集中度与 Pareto 数值对照；
- 五态 UI 的桌面和窄屏客户路径、截图、控制台与 Receipt/sourceRun 对齐。
