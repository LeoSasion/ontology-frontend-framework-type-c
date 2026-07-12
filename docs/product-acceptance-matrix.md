# AIBI-C Product Acceptance Matrix

本矩阵只定义用户可观察的稳定行为。脚本实现与命令拆分不在此重复。

| Scenario | Expected behavior | Acceptance signal |
| --- | --- | --- |
| Empty workspace | 不出现样例、默认对象或隐藏结论，只引导导入。 | Home、Sources、Dashboards、Evidence、AI 均指向真实数据导入。 |
| Import one file or folder | 写入前能看懂目标、合并、去重、行数、键和风险。 | external real file or folder 在临时工作区完成预演、一次确认、画像与清理，不影响原工作区。 |
| Create one chart | 无看板时也能从当前表生成一个图表。 | 明确请求直接产生一个草案；模糊请求最多澄清一次；批准后只创建一个组件。 |
| Generic AI question | 系统不猜行业和指标。 | 普通概览只使用当前表的行数与来源证据，不静默选择销售、退款或渠道字段。 |
| Business field hygiene | 用户只看到可解释的业务字段。 | 候选和自动指标排除 `__*`；清理自动资产不影响手工资产。 |
| Relationship recommendation | 主推荐来自真实连接证据。 | 需满足值重叠、键基数和非膨胀连接，名称相似不能单独通过。 |
| Full industry dashboard Beta | Beta 不抢占单图入口。 | 写入前披露命中、省略、字段缺口与来源，缺字段组件不渲染。 |
| Evidence and audit | 结果可核对、可导出且不重新计算。 | 业务摘要优先；查询回执关联来源、字段、运行时、语境、动作和未决项；导出不含数据库、密钥或无关原始行。 |
| Trusted reuse and branch | 只有确认过的知识与结果可复用。 | 问法需显式保存，结构变化后失效；仅确认结果可创建带父级血缘的分支。 |
| Confirm or reject write | 写入受控但没有重复确认。 | 一个审阅面展示目标、影响、证据、确认与拒绝。 |
| Delete source or object | 删除可发现且受保护。 | 主页面先 dry-run 依赖与影响，确认后显示回执并落到有效对象。 |
| Workspace and route isolation | 跨页与刷新不丢失当前对象。 | `table`、`view`、`dashboard`、`run`、`action` 随 URL、刷新和浏览器历史恢复，不使用 fabricated fallback。 |
| Production no-demo boundary | 产品不种入用户可见内容。 | 自动化可以使用 `validation-inputs`，生产空态的表、看板和草案均为零。 |
| Desktop visual ratios | 常见 PC 比例可扫描且不挤压。 | 1440x900、900x1440、1100x1100 无全局溢出、重叠、裁切或紧凑控件被迫换行。 |
| Local security and recovery | 本地数据不暴露，恢复不盲写。 | 仅回环监听；请求边界有效；备份含数据库与哈希；恢复默认预演并在确认前创建安全副本。 |

## Required Verification

- `npm run preflight`
