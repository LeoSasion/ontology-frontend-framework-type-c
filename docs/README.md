# AIBI-C 文档索引

文档按单一职责组织。产品方向、需求、交互、验收、实现、路线和历史证据分别维护，禁止在多个文件复制同一份可变事实。

## 使用入口

| 文档 | 唯一职责 |
| --- | --- |
| [仓库执行约束](../AGENTS.md) | AIBI-C 身份守卫、跨仓库隔离和执行边界 |
| [根 README](../README.md) | 安装、运行、验证、数据恢复和文档入口 |
| [产品定位](../PRODUCT.md) | 用户、核心任务、产品层级、边界和非目标 |
| [产品需求](PRD.md) | 当前版本必须满足的功能与发布条件 |
| [产品体验标准](product-ux-standard.md) | 页面职责、渐进展示、路由、确认和删除交互 |
| [产品验收矩阵](product-acceptance-matrix.md) | 用户可观察的稳定行为与验收信号 |
| [实现状态](implementation-status.md) | 当前能力、已知限制、架构归属和验证入口 |
| [未来开发队列](development-roadmap.md) | 尚未交付事项、优先级和退出条件 |
| [语义查询合同](semantic-query-planning.md) | 字段消歧、粒度、关系路径与执行阻塞 |
| [Agent 知识包](agent-knowledge-packs.md) | 模型无关业务规则、证据和扩展要求 |
| [Agent Provider](agent-provider-runtime.md) | 可选外部模型的数据边界、降级和验证 |
| [ERP 看板单元库](erp-dashboard-unit-library.md) | Beta 单元选择、遗漏和晋级边界 |
| [BI CLI 合同](bi-cli-contract.md) | 由实时 CLI 自动生成的命令与突变合同 |
| [验收证据索引](../artifacts/README.md) | 当前发布回执、专项回执和历史视觉证据 |

## 事实归属

| 事实 | 维护位置 |
| --- | --- |
| 产品是什么、为谁服务 | `PRODUCT.md` |
| 当前版本必须做什么 | `docs/PRD.md` |
| 当前已经做到什么 | `docs/implementation-status.md` |
| 接下来做什么 | `docs/development-roadmap.md` |
| 用户如何验收 | `docs/product-acceptance-matrix.md` |
| 某次验证是否通过 | `artifacts/` 中对应日期回执 |
| CLI 命令数和参数 | 实时 `cli-contract` 生成结果 |

## 维护规则

- 当前事实必须能由代码、运行边界或自动化验收支持；历史回执不能冒充当前状态。
- 已完成开发流水账不长期保留，稳定结论进入实现状态，日期证据进入 `artifacts/`。
- UX 文档只写用户可观察约束，不抄组件结构；技术合同只写对应运行边界。
- 易漂移的文件数、测试数、命令数和性能值由脚本或日期回执维护。
- `npm run preflight` 是本地交付前总入口；专项命令集中维护在实现状态。
- 新增、删除或改名 Markdown 后必须更新本索引或 `artifacts/README.md`，并运行 `npm run verify:docs`。
