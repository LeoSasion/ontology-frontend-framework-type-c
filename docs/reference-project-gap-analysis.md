# AIBI-C Reference Decisions

本文件是架构决策记录，不是当前需求、实现状态或未来路线图。候选来自本地研究文档的前七名项目，只保留影响 AIBI-C 产品边界的结论。

## Adopted Mechanisms

| Reference | Adopted mechanism | AIBI-C decision |
| --- | --- | --- |
| [WrenAI](https://github.com/Canner/WrenAI) | 可治理的业务语境 | Context Pack 中的术语与规则必须有作用域、证据、冲突检查和版本 |
| [Microsoft Data Formulator](https://github.com/microsoft/data-formulator) | 从结果继续、回退与分支 | 只有已确认结果能创建带父级、回执和动作血缘的 Analysis Run |
| [DB-GPT](https://github.com/eosphoros-ai/DB-GPT) | 计划、执行、验证与交付合同 | Query Plan Receipt 记录可复核事实，证据包复用回执并提供哈希 |
| [SQLBot](https://github.com/dataease/SQLBot) | 中文语境辅助字段理解 | 只使用已确认且作用域匹配的别名；模糊字段仍需澄清 |

## Explicit Rejections

| Direction | Reason |
| --- | --- |
| Chat2DB 式数据库管理与 SQL 工作区 | 会把数据运维和 SQL 暴露为新手默认产品结构 |
| Open Interpreter 式任意代码执行 | 扩大数据与系统风险，破坏白名单查询边界 |
| 无来源的对话、统计与报告拼装 | 无法满足来源、口径、查询和动作证据要求 |

## Resulting Product Boundary

1. 语境是有作用域和证据的可信输入，不是提示词碎片。
2. 查询计划保存可验证事实，不保存模型私有推理。
3. 记忆来自显式确认，不来自聊天历史；结构变化后失效。
4. 分支只从已确认结果创建，导出只复用现有回执。
5. 高级能力默认折叠，稳定入口仍是一问一图。

AIBI-C 因此不扩展为通用数据库客户端、任意代码 Agent 或多智能体平台。
