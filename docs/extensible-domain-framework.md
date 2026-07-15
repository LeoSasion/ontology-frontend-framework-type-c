# 通用领域扩展框架

本文件定义 AIBI-C 从固定业务假设迁移到自由、通用、可扩展框架时的唯一架构合同。产品结果见 [PRD](PRD.md)，交付顺序见 [未来开发队列](development-roadmap.md)，当前完成度见 [实现状态](implementation-status.md)。

## 目标

AIBI-C 默认只理解结构事实，不默认理解电商、ERP、资金、订单、售后、保单或任何客户名称。领域知识必须以可发现、可启用、可停用、可审计的 Domain Pack 提供；数据接入能力由 Connector Adapter 独立提供，两者不得互相暗含。

## 三层边界

| 层级 | 负责 | 禁止 |
| --- | --- | --- |
| Core | 工作区、表、字段类型、结构角色、关系证据、查询、Receipt、Unit、Job、草案与确认 | 领域字段别名、业务公式、行业缺口、厂商或客户默认值 |
| Domain Pack | 领域语义、角色别名、指标规则、分析单元、确认问法和适用证据 | 自动启用、直接写库、任意 SQL、绕过关系与版本校验 |
| Connector Adapter | 来源发现、凭据引用、只读预览、同步计划和确认导入 | 注入领域语义、自动启用领域包、在预览阶段写业务状态 |

## 通用内核合同

- 字段只自动推断 `identifier`、`time`、`numeric`、`category`、`status`、`text` 等结构角色。
- 关系候选只基于规范化名称、类型兼容、值重叠、基数、复合键、版本和行膨胀；业务 token 只能由已启用领域包追加。
- 默认分析只生成行数、可安全聚合的数值、时间趋势、分类拆分和明细核查，不生成行业专属缺口。
- Agent 不以销售、金额、渠道、退款、成本等名称优先选择字段；相同结构证据必须得到相同优先级。
- Core 不读取 Domain Pack 文件来改变默认行为；只有工作区启用清单可将 Pack 注入一次请求的运行上下文。

## Domain Pack Manifest

每个 Pack 必须有稳定 `packId` 与版本，并声明：

- 显示名称、用途、兼容 Core 版本和来源；
- 字段角色与别名，及每条别名的领域作用域；
- 指标、公式、分析单元和必需/可选语义；
- 可用入口：Agent、Source Intelligence、关系提示、看板单元或确认问法；
- 正向、阻塞、不匹配和多 Pack 冲突测试；
- 不包含凭据、业务数据、绝对路径或可执行任意代码。

Manifest 由统一注册表校验。未知字段、重复 `packId`、越权能力或不兼容版本在注册阶段阻断。

外部 Pack 采用只含声明式 JSON 与静态资源的 package；不得包含 Python、JavaScript、SQL 或其他可执行文件。外部 package 还必须声明规范化来源、`keyId` 和 HMAC-SHA256 签名，签名只使用服务端信任键引用，密钥值不得写入 Manifest、数据库、日志或回执。内置 Pack 以 `builtin` 来源发布，不伪装成外部签名包。

安装、升级和卸载都先返回 dry-run：列出版本变化、冲突、受影响工作区和启用状态。确认升级时，只有 Manifest 显式声明从旧版本到新版本的迁移，才可保留启用状态；否则先停用并要求重新审阅。卸载只移除安装副本并停用相关工作区，不改写历史 Receipt 或证据。

Manifest 的 `conflicts` 必须显式列出互斥 Pack 或互斥贡献；注册表在启用前统一判定，不以目录顺序决胜。`uiContributions` 只允许受限的双语标题、说明、标签和只读卡片，不接受 HTML、脚本、事件处理器、任意组件路径或运行时代码。

最小外部 package 是一个目录，包含 `manifest.json` 和 Manifest 引用的静态文件。签名值为移除 `signature` 后、按 key 排序且无空白的 UTF-8 JSON 的 HMAC-SHA256 十六进制摘要：

```json
{
  "schema": "aibi-domain-pack/v1",
  "packId": "example-domain",
  "version": "1.0.0",
  "displayName": {"zh": "示例领域", "en": "Example domain"},
  "description": {"zh": "只提供声明式语义。", "en": "Declarative semantics only."},
  "source": {"publisher": "Example team", "reference": "urn:example:domain-pack"},
  "coreCompatibility": {"min": 1, "max": 1},
  "capabilities": ["agentKnowledge"],
  "signature": {"algorithm": "hmac-sha256", "keyId": "example-key", "value": "<hex>"}
}
```

开发者链路：

```powershell
python tools/bi_cli.py --json domain-pack-lint --package <package-directory>
python tools/bi_cli.py --json domain-pack-install --package <package-directory>
python tools/bi_cli.py --json domain-pack-install --package <package-directory> --yes
python tools/bi_cli.py --json domain-pack-set --pack example-domain --state enabled --yes
python tools/bi_cli.py --json domain-pack-uninstall --pack example-domain --yes
```

服务端通过 `AIBI_DOMAIN_PACK_TRUST_KEYS` 提供 `keyId -> secret` JSON 映射；安装目录可由 `AIBI_DOMAIN_PACK_ROOT` 覆盖。任何真实密钥都只放本地 `.env` 或进程环境。

## 工作区启用与优先级

- 新工作区 `enabledDomainPacks=[]`，迁移旧工作区也不得静默启用。
- 启用或停用属于工作区配置写入，必须预演、显示影响、显式确认并生成回执。
- Pack 只影响启用后的新计划；既有 Receipt、Unit 和结果保留原 Pack 版本，不被原地重解释。
- 多 Pack 同时命中时，显式表/字段选择优先，其次是手工语义，再其次是 Pack 证据；无法唯一决胜时集中澄清一次。
- 停用 Pack 后，其建议和模板不再出现；依赖该 Pack 的保存对象标记为需要复核，不自动删除。

## 前后端运行合同

后端公开统一目录：可用 Pack、工作区已启用 Pack、可用 Adapter 及其状态。Agent、Source Intelligence、关系推荐和看板单元从同一个运行上下文读取这些信息，不各自维护领域常量。

前端只渲染后端声明为可用的能力。未实现的 API、ERP 或数据库 Adapter 不显示为可操作入口；领域模板只在对应 Pack 已启用且当前字段证据满足时出现。前端不得维护另一份字段别名或业务指标优先级。

P1 首批远程 Adapter 固定为 `http-json/v1` 与 `sqlite-table/v1`。HTTP 只访问服务端 allowlist 中的 origin，限制页数、行数、响应字节和超时，默认不重试，并只通过 `env:NAME` 引用凭据；SQLite 只打开 allowlist 中的本地数据库文件和显式表名，不接受 SQL。两者的预览与同步计划都只返回有界标量，确认同步时才把同一指纹快照交给通用导入边界。

HTTP allowlist 由 `AIBI_HTTP_CONNECTOR_ALLOWLIST` 提供逗号分隔的精确 origin；SQLite allowlist 由 `AIBI_SQLITE_CONNECTOR_ALLOWLIST` 提供逗号分隔的精确文件或目录。典型命令：

```powershell
python tools/bi_cli.py --json save-connector --name RemoteRows --type api --endpoint https://api.example.com/rows --resource data.items --credential-ref env:REMOTE_ROWS_TOKEN --target-table remote_rows --yes
python tools/bi_cli.py --json save-connector --name LocalDb --type database --endpoint C:\data\source.sqlite --resource source_rows --target-table local_rows --yes
python tools/bi_cli.py --json preview-connector --connector RemoteRows --limit 20
python tools/bi_cli.py --json sync-connector --connector RemoteRows
python tools/bi_cli.py --json sync-connector --connector RemoteRows --yes
```

## 证据与隔离

- Source Intelligence Run、Query Receipt、Analysis Unit、Pack 建议和导出必须绑定工作区、表版本、schema fingerprint、source fingerprint 和 Pack 版本集合。
- 当前数据指纹不兼容时，旧运行只可作为历史证据，不得成为“最新可执行结果”。
- 自动化使用临时工作区和临时数据库；验证输入不得写入用户当前工作区。
- 清理不兼容历史运行必须先 dry-run，列出引用者与影响，确认后执行并保留回执。
- 比率、转化率、占比、率值等复合统计在没有已验证分子/分母计划时必须澄清，不能退化为 `COUNT(*)` 或任意单字段聚合。
- `source fingerprint` 必须从当前输入资源重新计算；来源变化、删除或不可读都使旧 Run 失效。没有 current Run 时返回空的当前规划输入，而不是回退到最新 stale Run。
- 直接 Query 与 Agent Query 使用同一 Domain Pack 运行上下文并写入相同来源的 Pack provenance。

## 兼容与迁移

现有 `platform-commerce.v1` 和 ERP 单元库保留为 AIBI-C 自有可选 Pack，不再参与默认路径。迁移分两步：先建立注册表与空默认，再把旧入口改为显式 Pack 调用。旧命令在过渡期可返回弃用提示，但不得靠隐藏默认重新启用。

`workspace_domain_packs` 属于受版本控制的元数据 schema 与配置导出合同。新增或变更该表必须提升 SQLite `user_version`，由隔离迁移、恢复点和双库回滚处理；配置导出/恢复必须保留每个工作区的 Pack 状态。旧 Dashboard Action 的确认回放必须显式传递其工作区，不能依赖当前活动工作区或旧参数位置。

## 完成定义

- 使用完全中性的传感器、项目/教育或科研数据时，默认流程不出现电商、ERP、资金、订单、售后或保单语义。
- 启用某个 Pack 后只增加该 Pack 声明的建议；停用后恢复通用结果。
- 两个 Pack 可同时存在，冲突可解释且不按加载顺序决胜。
- 前端、API、CLI、Agent 和 Job 对 Pack/Adapter 状态一致。
- 用户工作区、临时验证工作区和历史证据之间无数据或“最新运行”串扰。
