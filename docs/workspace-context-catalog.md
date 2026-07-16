# 工作区上下文目录合同

本文件是 Workspace Manifest、Runtime Catalog、Business Field Profile 及其规划绑定的唯一技术事实源。业务理解分层见 [业务理解与分析 Skills](business-understanding-skills.md)，查询和跨表执行见 [语义查询合同](semantic-query-planning.md)，当前交付状态见 [实现状态](implementation-status.md)。

## 目标与边界

这组合同把“当前工作区有什么、运行时能做什么、字段证据能说明什么”整理成确定性只读上下文，供数据工作台、证据页和 Agent 共同读取。它们从既有工作区注册表、画像、语义、关系、Context、Pack、Skill、Capability 和运行时状态派生，不新增业务事实权威，也不形成另一份可编辑配置。

- Workspace Manifest 回答当前工作区是否具备可规划的完整上下文。
- Runtime Catalog 回答当前运行时可见的对象、声明能力和安全边界。
- Business Field Profile 回答字段形状及候选含义有哪些证据。
- Workspace Planning Binding 保存计划复用所需的稳定指纹子集；数据、schema、画像、语义、关系、Context、Pack 或 Skill 漂移时，旧计划和新生成 Receipt 不得继续被当作当前结果。

三者均为工作区隔离的只读派生结果，不进入配置导出，不需要独立持久化表或 schema 迁移。手工确认的字段语义仍由既有语义配置维护；原始业务数据仍留在本地数据层。

## 四个合同

| 合同 | 职责 | 主要内容 | 明确不负责 |
| --- | --- | --- | --- |
| `aibi-workspace-manifest/v1` | 汇总当前工作区的数据、语义、运行时和证据状态 | 表与字段引用、状态计数、Catalog/Planning Binding 引用、组件指纹、blocker 和 warning | 保存原始行、修改语义或授权执行 |
| `aibi-runtime-catalog/v1` | 列出当前可解析和可调用的运行对象 | 表、字段引用、指标、公式、关系、Context、Pack、Skill、Runtime Profile、Connector Adapter 和 Capability | 返回凭据、任意 SQL、业务数据或其他工作区对象 |
| `aibi-business-field-profile/v1` | 为单个字段形成有界、可追溯的结构画像 | 类型证据、空值、基数、时间覆盖、角色/状态候选、敏感性、绑定对象、新鲜度和证据引用 | 把样例推断升级成业务口径或关系许可 |
| `aibi-workspace-planning-binding/v1` | 绑定计划复用前必须保持一致的语义材料 | schema、数据、字段画像、指标、公式、关系、Context、Pack 和 Skill 指纹 | 替代完整 Manifest、保存 SQL 或绕过 Receipt 复核 |

Manifest 的 `current | stale | incomplete` 表示工作区整体可用性；Business Field Profile 的 `ready | ambiguous | blocked | stale` 表示单字段画像状态。消费者必须同时读取 blocker、warning、freshness 和 `usableForPlanning`，不能仅凭状态标签继续执行。

## Candidate 与 Confirmed

字段画像严格区分观测、候选和确认：

1. `observedShape` 只描述存储类型、逻辑类型证据、空值、基数、有限样本规模和时间覆盖，不声明业务意义。
2. 导入画像和自动语义只形成 `roleCandidates` 或分类基数统计；authority 保持 candidate-only 或 statistics-only，绝不输出分类原值。
3. 来源为 `manual` 的已保存字段语义形成 `manual-confirmed`；经 Review Inbox 接受的来源形成 `reviewed-confirmed`。两者都生成 `confirmedSemanticRef` 并受自动推断覆盖保护。Domain Pack 可通过业务上下文提供有来源的规则，但不会把字段画像候选静默晋级为确认。
4. 候选不能授权 Join、指标公式、筛选口径、统计粒度或写入。Runtime Catalog 固定声明 `candidateCanAuthorizeJoin: false`；跨表仍必须使用当前工作区已保存且验证有效的关系。
5. Provider 只能解释已经进入白名单上下文的引用和统计，不能修改候选、确认语义、Capability 或规划指纹。

## PII 与公开响应

画像可在本地使用有界值读取来计算类型、时间和敏感性，但公开合同遵循以下边界：

- 不返回原始行、无限制样例、物理表名、数据库路径、源文件绝对路径、Credential Ref 或 Secret。
- 对邮箱、手机号、地址等可能敏感字段，只返回敏感级别、原因码和统计；`rawValuesExposed` 固定为 `false`。
- `statusCandidates` 只报告不同值数量，`rawValuesWithheld=true`；分类原值无论字段名和低基数判断如何都不进入公开合同、UI 或 Provider 出站上下文。
- 同一张表的有界观察样本通过单次批量读取形成，不按字段重复扫描；Ask 在同一请求内复用唯一 Planning Binding。
- Manifest 和 Runtime Catalog 只携带对象引用、计数、状态和指纹，不复制字段原值。
- 工作区外对象、其他 AIBI 仓库路径、符号链接逃逸和未允许来源在画像生成前继续由仓库与来源隔离门禁阻断。

## Freshness 与规划指纹

Business Field Profile 将当前表注册状态与最新 Source Run 的行列形状绑定。没有来源画像时为 unknown/blocked；形状不匹配时为 stale；只有没有 blocker 的画像才可标记 `usableForPlanning`。状态候选或历史 Source Intelligence 不能覆盖该判断。

Workspace Planning Binding 对下列稳定材料分别计算组件指纹，并生成总 fingerprint：

- 当前工作区 schema 与数据版本；
- 字段画像引用及其 freshness；
- 指标、计算字段和关系定义；
- Context Term/Rule 等已登记上下文；
- 已启用 Domain Pack 与 Analytical Skill 集合。

`aibi-semantic-context-bundle/v1` 保存该绑定的 schema、fingerprint、画像数量以及 candidate 不得授权 Join 的声明。新生成 Query Plan Receipt 同样绑定 Planning Binding；执行、重放、Analysis Unit、图表适配和导出前重新计算，发现工作区不符或指纹漂移时返回 blocker 并重新规划。完整 Manifest 还额外记录 Runtime Catalog 和 Evidence 状态，用于工作区可见性与诊断，不用易变展示顺序替代规划绑定。

## 读取入口

CLI 与 HTTP 读取同一服务；不需要确认，也不产生业务写入：

| 目的 | CLI | HTTP |
| --- | --- | --- |
| 工作区清单 | `workspace-manifest [--workspace ID]` | `GET /api/workspace/manifest` |
| 运行时目录 | `runtime-catalog [--workspace ID]` | `GET /api/runtime/catalog` |
| 字段画像 | `business-field-profiles [--workspace ID] [--table KEY] [--field NAME]` | `GET /api/business-field-profiles?table=KEY&field=NAME` |

HTTP 使用服务端当前活动工作区，不接受客户端用任意 workspace id 越过隔离边界。CLI 的 `--workspace` 仍必须解析为本地已登记工作区；表或字段过滤只能缩小结果，不能跨工作区查找同名对象。

界面只展示用户完成当前判断所需的摘要：数据工作台查看字段画像，证据页查看 Workspace Manifest，设置页查看运行 Profile 与安全边界。Runtime Catalog 是它们共享的运行时事实源，不要求用户阅读完整内部对象列表。

## 失败行为与验收

| 场景 | 必须行为 |
| --- | --- |
| 空工作区 | 返回有效但 incomplete 的 Manifest 和空 Catalog/Profile，不生成样例或业务结论 |
| 字段只有自动候选 | 展示候选及来源，保持 ambiguous；不得自动确认或执行跨表 |
| 敏感字段 | 只展示风险和统计，不展示原值或出站 |
| 数据或 schema 变化 | 相关画像和 Planning Binding 指纹变化，旧计划进入 stale 或阻断 |
| 关系、Context、Pack 或 Skill 变化 | Planning Binding 变化并重新规划；历史结果不被重解释 |
| 跨工作区请求 | 按未知对象或越界请求阻断，不回退到默认工作区同名对象 |
| Provider 不可用或越界 | 本地确定性目录仍可读；Provider 不获得写入或语义晋级能力 |

用户可观察场景只在 [产品验收矩阵](product-acceptance-matrix.md) 维护；实时 CLI 参数只在 [BI CLI 合同](bi-cli-contract.md) 维护。日期回执进入 [证据索引](../artifacts/README.md)，不在本文复制检查数量。
