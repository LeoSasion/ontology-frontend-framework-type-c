# 通用扩展运行框架

本文件是 AIBI-C 扩展运行时的唯一技术合同，统一维护 Core、Domain Pack、Knowledge Pack、Connector Adapter、Provider 和领域分析单元的边界。产品要求见 [PRD](PRD.md)，当前完成度见 [实现状态](implementation-status.md)。

## 分层职责

| 层级 | 负责 | 禁止 |
| --- | --- | --- |
| Core | 工作区、结构角色、关系证据、查询、Receipt、Unit、Job、草案与确认 | 行业别名、业务公式、厂商或客户默认值 |
| Domain Pack | 领域语义、指标、规则、分析单元、确认问法和适用证据 | 自动启用、直接写库、任意代码或绕过验证 |
| Knowledge Pack | Pack 可引用的版本化业务粒度、状态、去重和连接规则 | 训练数据、固定答案、会话记忆或脱离字段证据运行 |
| Connector Adapter | 来源发现、凭据引用、只读预览、同步计划和确认导入 | 注入领域语义、自动启用 Pack、预览阶段写入 |
| Provider | 解释本地结果或提出一次必要澄清 | 工具权限、事实裁决、确认写入或生成无证据数字 |
| 领域单元库 | 根据当前字段证据选择可解释的指标与图表单元 | 固定模板、缺字段补零或默认进入新手路径 |

## 通用 Core

- 只自动推断 `identifier`、`time`、`numeric`、`category`、`status`、`text` 等结构角色。
- 关系候选只使用名称、类型、值重叠、基数、复合键、版本和行膨胀；行业 token 只能由已启用 Pack 追加。
- 默认分析只生成行数、安全数值聚合、时间趋势、分类拆分和明细核查。
- 相同结构证据必须得到相同优先级，不能因销售、资金、订单、售后等名称静默偏置。
- 只有当前工作区启用清单可以把 Pack 注入一次请求的运行上下文。

## Domain Pack

### Manifest 与安装

每个 Pack 使用稳定 `packId` 和版本，声明显示名称、用途、Core 兼容范围、来源、字段角色、别名、指标、规则、分析单元、入口、冲突与测试。Manifest 不得包含凭据、业务数据、绝对路径或任意可执行代码。

外部 Pack 只接受声明式 JSON 与静态资源，并提供规范化来源、`keyId` 和 HMAC-SHA256 签名；Python、JavaScript、SQL、HTML 和第三方运行时代码在注册阶段阻断。内置 Pack 使用 `builtin` 来源，不伪装成外部签名包。

安装、升级、卸载和工作区启停都先 dry-run，列出版本、冲突、受影响工作区与对象。升级只有在 Manifest 声明兼容迁移时保留启用状态；卸载不改写历史 Receipt 或证据。冲突按声明和证据解析，禁止按目录或加载顺序决胜。

```powershell
python tools/bi_cli.py --json domain-pack-lint --package <package-directory>
python tools/bi_cli.py --json domain-pack-install --package <package-directory>
python tools/bi_cli.py --json domain-pack-install --package <package-directory> --yes
python tools/bi_cli.py --json domain-pack-set --pack <pack-id> --state enabled --yes
python tools/bi_cli.py --json domain-pack-uninstall --pack <pack-id> --yes
```

信任键由 `AIBI_DOMAIN_PACK_TRUST_KEYS` 提供，安装目录可用 `AIBI_DOMAIN_PACK_ROOT` 覆盖；真实密钥只存在本地环境。

### 工作区状态与迁移

- 新工作区和迁移后的旧工作区都保持 `enabledDomainPacks=[]`。
- 启停只影响后续计划；历史 Receipt、Unit 和结果保留创建时的 Pack 版本。
- 显式字段选择优先于手工语义，手工语义优先于 Pack 建议；仍冲突时集中澄清一次。
- 停用后不再展示该 Pack 的建议；依赖对象进入复核状态，不自动删除。
- `workspace_domain_packs` 属于 SQLite 版本化 schema 和配置导出合同；表结构变化必须提升 `user_version`，备份/恢复必须保留启用状态。

## Knowledge Pack

当前内置资产 `knowledge/platform-commerce.v1.json` 是 `platform-commerce` Pack 的只读知识源，只有当前工作区显式启用后才参与匹配。它描述抖音、淘宝/天猫和聚水潭导出中的退款、主单去重、多包裹、虚拟商品、订单版本、可归属售后、物流异常和阈值口径；这些规则不是默认知识，也不证明存在平台直连。

运行顺序固定为：验证 Pack 已启用 -> 匹配当前字段结构 -> 匹配窄意图 -> 验证粒度、状态、去重与关系 -> 执行审阅过的只读查询 -> 在 Receipt 中记录规则和证据。缺少分子、分母、键或状态时阻断，不能近似聚合。

新增或修改知识规则必须提供结构匹配条件、统计口径、白名单只读查询、正向/阻塞/不匹配测试以及来源与版本说明。禁止只增加提示词或固定答案。

```powershell
npm run verify:platform-knowledge
npm run verify:platform-commerce
```

## Connector Adapter

前端只展示后端声明为可用的 Adapter，不维护第二份能力状态。所有 Adapter 的预览和同步计划只返回有界标量；确认同步时才把相同来源指纹交给通用导入边界。

- `local-tabular/v1`：当前工作区登记的 CSV/XLSX/XLSM。
- `http-json/v1`：仅 allowlist origin、GET、UTF-8 JSON、可选点路径和有界分页；凭据只允许 `env:NAME`。
- `sqlite-table/v1`：仅 allowlist 本地文件和显式非系统表；不接受 SQL。
- ERP 直连 Adapter 当前保持 `unavailable`。

HTTP allowlist 使用 `AIBI_HTTP_CONNECTOR_ALLOWLIST`，SQLite allowlist 使用 `AIBI_SQLITE_CONNECTOR_ALLOWLIST`。跨工作区、符号链接链、其他 AIBI 仓库、任意请求、字面凭据和未允许资源在访问前阻断。

## Provider

默认 `AIBI_AGENT_PROVIDER=deterministic`，从不发送外部请求。显式选择 `deepseek` 后，AIBI-C 先在本地完成字段、关系、查询和 Receipt，再发送有界、脱敏、证据优先的 `aibi-agent-provider-context/v1`；无密钥、超时、限流或无效响应直接降级。

可以出站：当前问题、本地答案摘要、有界指标值、显示名称、已选择字段/聚合/筛选/关系、规则标识和证据状态。

不得出站：源文件、原始行、编译 SQL、动作 payload、数据库、密钥、凭据引用、绝对路径、其他 AIBI 仓库标识和模型私有推理。

Provider 生成的数字必须存在于本地证据；结构错误或瞬态故障最多重试一次。Context Budget 优先保留口径、阻塞、确认边界和 Receipt，必要上下文本身超限时跳过 Provider。配置项和默认值只由根目录 [.env.example](../.env.example) 维护。

```powershell
npm run verify:provider
npm run verify:provider-live
```

普通回归只使用确定性 mock；`verify:provider-live` 仅在显式验证真实外部路径时运行。

## ERP 领域单元库

`tools/erp_dashboard_unit_library.py` 是 ERP 单元、字段别名组、评分、省略规则和公开参考的唯一事实源。只有 `erp-units` Pack 已启用时，系统才按当前字段证据选择指标、图表、表格和筛选器；缺少必需字段的单元必须省略并解释，不能渲染为零值。

选择流程：读取当前工作区字段 -> 验证 Pack -> 匹配角色 -> 删除缺必需字段单元 -> 按证据评分 -> 在上限内选择 -> 返回命中、覆盖、省略原因和所需字段。每个组件保存 Pack 版本、单元 key、匹配字段、来源和证据引用。

```powershell
python tools/bi_cli.py --json erp-unit-library --summary
python tools/bi_cli.py --json erp-unit-library --select --summary --table <table-key> --limit 24
python tools/bi_cli.py --json business-dashboard --template erp-units --op draft --limit 24
npm run verify:erp-units
npm run verify:multi-domain-beta
```

整套 ERP 看板保持 Beta，不与默认可信单图入口竞争。

## 证据、新鲜度与隔离

- Source Intelligence Run、Query Receipt、Analysis Unit、Pack 建议和导出绑定工作区、表版本、schema/source/data 指纹和 Pack 版本集合。
- 来源变化、删除或不可读都会使旧 Run 失效；没有 current Run 时返回空的当前规划输入，不回退到最新 stale Run。
- 直接 Query 与 Agent Query 使用同一 Pack 上下文并记录相同 provenance。
- 历史对象不被新 Pack 版本重解释；清理前 dry-run，列出引用者和影响，确认后保留回执。
- 自动化使用临时工作区和临时数据库，验证输入不得写入用户当前工作区。
- 旧 Dashboard Action 的确认回放显式传递其工作区，不能依赖当前活动工作区。

## 完成标准

- 中性数据默认不出现任何行业语义。
- 启用一个 Pack 只增加其声明能力，停用后恢复通用结果。
- 多 Pack 并存时冲突可解释且不按加载顺序决胜。
- 前端、API、CLI、Agent 和 Job 对 Pack 与 Adapter 状态一致。
- 用户工作区、临时验证工作区与历史证据之间无数据或“最新运行”串扰。
