# AIBI-C 文档索引

本索引是文档唯一入口。产品链回答“为什么、做什么、如何验收、当前做到哪里”；技术链只维护跨模块运行合同；日期证据独立存放。

## 产品与交付链

| 文档 | 唯一职责 |
| --- | --- |
| [仓库执行约束](../AGENTS.md) | 仓库身份、AIBI 系列隔离和操作边界 |
| [根说明](../README.md) | 安装、启动、验证和恢复入口 |
| [产品定位](../PRODUCT.md) | 用户、价值、原则、边界和非目标 |
| [产品需求](PRD.md) | 当前版本必须满足的用户结果与发布条件 |
| [产品体验标准](product-ux-standard.md) | 页面职责、渐进展示、路由、确认和删除交互 |
| [产品验收矩阵](product-acceptance-matrix.md) | 用户可观察的稳定行为与验收信号 |
| [实现状态](implementation-status.md) | 当前能力、限制、架构归属和验证入口 |
| [未来开发队列](development-roadmap.md) | 尚未交付事项、优先级和退出条件 |

## 技术合同与证据

| 文档 | 唯一职责 |
| --- | --- |
| [业务理解与分析 Skills](business-understanding-skills.md) | 五层业务上下文、业务理解合同、理解与方法 Skills、专题验收与后续顺序 |
| [工作区上下文目录](workspace-context-catalog.md) | Workspace Manifest、Runtime Catalog、字段画像、PII 边界、新鲜度与规划绑定 |
| [语义补丁与审核收件箱](semantic-review-inbox.md) | 知识源适配、不可变语义提案、人工审核、漂移阻断与配置可移植 |
| [确认计划记忆](confirmed-plan-memory.md) | 证据绑定的混合召回、Recall Receipt、显式提升和 stale 边界 |
| [计划质量评测](plan-quality-evaluation.md) | Business Expression Case、确定性 Scorecard、发布门槛、重放与隔离边界 |
| [探索线程与可恢复分析上下文](exploration-threads.md) | 分析锚点、父子血缘、结果板、新鲜度与恢复边界 |
| [有限 Research Run](finite-research-runs.md) | 有限研究预算、不可变计划修订、反例/敏感性证据与统一追踪 |
| [语义查询合同](semantic-query-planning.md) | 字段消歧、统计粒度、关系路径和执行阻塞 |
| [通用扩展框架](extensible-domain-framework.md) | Core、Domain Pack、Knowledge Pack、Connector、Provider 与领域单元合同 |
| [BI CLI 合同](bi-cli-contract.md) | 由实时 CLI 自动生成的命令、参数与突变合同 |
| [验收证据索引](../artifacts/README.md) | 当前发布回执、专项机器回执和历史视觉证据 |

## 事实归属

| 问题 | 维护位置 |
| --- | --- |
| 产品是什么、为谁服务 | `PRODUCT.md` |
| 当前版本必须做什么 | `docs/PRD.md` |
| 当前已经做到什么 | `docs/implementation-status.md` |
| 接下来做什么 | `docs/development-roadmap.md` |
| 用户如何验收 | `docs/product-acceptance-matrix.md` |
| 助手如何理解业务、选择 Skill | `docs/business-understanding-skills.md` |
| 工作区对象、字段画像与规划指纹如何派生 | `docs/workspace-context-catalog.md` |
| 用户纠正和外部知识如何进入受信语义 | `docs/semantic-review-inbox.md` |
| 已确认计划如何安全召回和失效 | `docs/confirmed-plan-memory.md` |
| 业务表达与计划质量如何评测 | `docs/plan-quality-evaluation.md` |
| 已验证结果如何形成可恢复分支与结果板 | `docs/exploration-threads.md` |
| 某次验证是否通过 | `artifacts/` 中对应日期回执 |
| CLI 当前命令与参数 | `docs/bi-cli-contract.md` 的实时生成结果 |

## 维护规则

- 同一可变事实只写一次；其他文档链接到事实源，不复制清单。
- 历史流水账不长期保留：稳定结论进入实现状态，日期证据进入 `artifacts/`。
- UX 文档只写用户可观察约束；技术合同不复制组件或测试文件目录。
- 易漂移的数量、耗时和性能值只出现在脚本输出或日期回执。
- `npm run preflight` 是本地交付前总入口。
- Markdown 增删改名后必须更新本索引或证据索引，并运行 `npm run verify:docs`。
