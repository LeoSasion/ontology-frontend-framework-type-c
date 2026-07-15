# AIBI-C 产品验收矩阵

本矩阵只定义用户可观察的稳定行为。脚本拆分、测试数量和历史修复过程不在此重复。

| Scenario | Expected behavior | Acceptance signal |
| --- | --- | --- |
| Repository isolation | 开发、验证和运行不依赖其他 AIBI 工作树。 | root、origin、路径、符号链接和输入门禁通过；默认回归只使用 AIBI-C 的 `validation-inputs` 或系统临时目录。 |
| Empty workspace | 不出现样例、默认对象或隐藏结论，只引导导入。 | Home、Sources、Dashboards、Evidence、AI 均基于真实空态。 |
| Import one file or folder | 写入前能看懂目标、合并、去重、键和风险。 | external real file or folder 在临时工作区完成预演、一次确认、画像、路由和清理，不影响原工作区。 |
| Create one chart | 无看板时也能从当前表生成一个图表。 | 明确请求只产生一个草案；模糊请求最多澄清一次；批准后只创建一个组件。 |
| Generic AI question | 系统不猜行业和指标。 | 普通概览只使用当前表证据，不静默选择销售、退款或渠道字段。 |
| Domain-neutral default | 新工作区只有通用结构能力。 | 中性数据在 UI、API、CLI、Agent、Source Intelligence 和 Receipt 中不出现电商、ERP、资金、订单、售后、保单或客户默认语义。 |
| Domain Pack lifecycle | 领域知识按工作区显式启停且可追踪。 | 新旧工作区启用清单默认为空；启停需预演和确认；历史结果保留创建时 Pack 版本，停用后不再生成新建议。 |
| External Domain Pack package | 外部 Pack 可受控安装和升级，但不能把代码带入 Core。 | lint、来源和签名先通过；安装/升级/卸载均 dry-run + confirm；可执行文件、未知贡献、冲突和未声明迁移在写入前阻断。 |
| Domain Pack portability | 工作区配置迁移后不改变领域行为。 | 配置导出和恢复保留 `workspace_domain_packs`；schema 版本提升可被迁移预演、恢复点和回滚发现。 |
| Multiple Domain Packs | 多领域并存不靠加载顺序猜测。 | 两个 Pack 独立命中；冲突按显式选择、手工语义和证据处理，无法唯一决胜时集中澄清。 |
| Core, Pack and Adapter isolation | 数据接入与领域知识不互相暗含。 | 创建或同步 Connector 不改变 Pack；启用 Pack 不访问来源或凭据；未知能力在注册阶段阻断。 |
| Ambiguous field resolution | 同名或近义字段不会被静默猜测。 | 多个未决字段合并在一个候选面；明确表名后绑定目标字段，回执保留候选与依据。 |
| Multi-dimension semantic plan | 多个维度和指标先形成完整计划。 | 逐项列出字段角色、统计粒度、参与表和未决项，不遗漏后续字段。 |
| Relationship safety | 推荐、复合键、筛选、预聚合和版本变化均受控。 | 名称相似不能单独通过；完整映射与行膨胀可审阅；数据变化使旧验证失效并阻断。 |
| Semantic cross-table execution | 跨表问题只沿当前已验证路径执行。 | 单跳和严格线性两跳结果、计划哈希、最终粒度和 Receipt 一致；三跳、反向或不安全路径明确阻断。 |
| Full industry dashboard Beta | Beta 不抢占单图入口。 | 写入前披露命中、省略、字段缺口与来源；缺字段组件不渲染。 |
| Evidence and audit | 结果可核对、可导出且不重新解释。 | Receipt 关联来源、字段、关系、运行时、动作和缺口；技术诊断默认收起。 |
| Evidence fingerprint compatibility | 最新证据只能属于当前数据与 Pack 上下文。 | 表版本、schema/source fingerprint 或 Pack 集合变化后，旧 Run/Receipt/Unit 只作为历史证据，不参与当前执行或最新结果选择。 |
| Compound ratio safety | 未验证的比率问题不退化为普通聚合。 | 中英文 ratio/rate/占比/转化率/退款率请求缺少分子分母时只返回一次澄清；无 executed Receipt 或 ready Unit。 |
| Verification workspace isolation | 自动化不污染用户工作区。 | 完整回归前后，用户工作区表、Run、Receipt、Unit、Pack 启用清单和当前对象指纹不变。 |
| Trusted reuse and branch | 只有确认过的知识与结果可复用。 | 结构或关系变化使记忆失效；仅确认结果可创建带父级血缘的分支。 |
| Durable background analysis | 长任务不绑死 HTTP，也不在重启后静默重复。 | 状态迁移、单调进度、有序事件、取消、worker 异常和重启恢复均可审计。 |
| Unified workflow capability | 不同入口不能改变同一能力的权限和证据边界。 | CLI/API/Agent/Job 共用 `capabilityId` 与 Stage；未知能力和越权入口在执行前阻断。 |
| Verifiable analysis units | 结论可复算，图表不由模型或字段顺序猜选。 | 六类 Unit 绑定 Receipt 指纹；冻结标量可复算；不兼容图表、替换结果和样本不足明确阻断。 |
| Receipt-driven analysis export | Excel/报告与屏幕上的已验证结论一致。 | 相同 Receipt/Unit 产生确定性 ZIP、结构化工作簿、脱敏快照和哈希；不重新查询或写业务库。 |
| Safe read-only connector adapter | 外部来源先以最小权限读取并形成计划。 | 预览有硬上限且不暴露绝对路径；跨工作区、符号链接、其他 AIBI 路径、字面凭据和任意查询在访问前阻断。 |
| Allowlisted HTTP JSON Adapter | API 接入不会成为任意网络访问器。 | 非 allowlist origin、重定向越界、超时、超字节和字面凭据均阻断；超页/超行按上限截断；回执不含 Secret。 |
| Allowlisted SQLite table Adapter | 数据库接入不接受任意 SQL。 | 仅 allowlist 文件和显式表可读；系统表、附加数据库、查询文本和越界路径在打开前阻断。 |
| Confirm or reject write | 写入受控但没有重复确认。 | 一个审阅面展示目标、影响、证据、确认和拒绝。 |
| Delete source or object | 删除可发现且受保护。 | 主页面先 dry-run 依赖与影响，确认后显示回执并落到有效对象。 |
| Workspace and route isolation | 跨页与刷新不丢失当前对象。 | `table`、`view`、`dashboard`、`run`、`action` 随 URL 和历史恢复，不使用 fabricated fallback。 |
| Production no-demo boundary | 产品不种入用户可见测试内容。 | 自动化可用 `validation-inputs`；生产空态的表、看板、草案和答案均为零。 |
| Desktop visual ratios | 常见 PC 比例可扫描且不挤压。 | 1280×720、1440×900、900×1440、1100×1100 无全局溢出、重叠、裁切或逐字换行。 |
| Local security and recovery | 本地数据不暴露，恢复不盲写。 | 仅回环监听；请求有界；备份含校验和；恢复默认预演并创建安全副本。 |
| Local schema upgrade | 版本升级不静默覆盖工作区。 | 双库先只读检查和隔离预演；确认前创建恢复点；应用或复检失败时回滚，未来版本阻止启动。 |

## Required Verification

- `npm run verify:docs`
- `npm run build`
- `npm run verify`
- `npm run preflight`
