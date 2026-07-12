# Agent Knowledge Packs

## Purpose

Agent Knowledge Pack 把已验证的业务粒度、状态、去重、连接和指标规则保存为版本化项目资产。它不是模型训练数据，也不保存固定业务答案。任何模型提供者都必须通过同一知识匹配、只读查询和证据回执边界工作。

## Runtime Contract

1. 根据当前工作区字段集合匹配表角色，字段不完整时不套用规则。
2. 根据用户问题匹配窄业务意图；宽规则必须声明排除条件，不能覆盖更具体的跨表口径。
3. 仅执行仓库内审阅过的 `SELECT` / `WITH` 查询，表名只能来自当前工作区注册表。
4. 答案返回 `agentKnowledge`、`knowledgeRule`、统计粒度、参与表和编译后 SQL。
5. 查询回执保存知识规则、筛选和跨表角色；结果仍由当前数据计算。
6. 涉及未确认的分子、分母、去重或连接粒度时返回阻塞说明，不执行近似聚合。

## Current Pack

`knowledge/platform-commerce.v1.json` 覆盖抖音电商、淘宝/天猫和聚水潭 ERP 的以下高风险问题：

- 成功退款状态与金额口径，以及按商家编码汇总退款额和退款率。
- 主单金额去重和关闭订单排除。
- 一单多包裹、拆单物流、仓库/物流公司履约和异常订单追溯。
- 虚拟商品空运单例外。
- 淘宝主单实付减成功退款。
- 聚水潭订单版本按 `o_id + max(ts)` 取最新事实。
- 聚水潭来源平台实付、可唯一归属的已确认售后和物流同步异常。
- 百分比阈值统一转换为小数，例如 `20%` 在查询中绑定为 `0.2`。

来源边界保存在知识包 `source` 字段。公开资料用于定义分析方法，生产答案只能引用当前工作区表和查询回执。

## Provider Independence

可选模型不需要了解 Codex 会话。服务端在模型调用前后都可以使用以下稳定字段：

- `agentKnowledge.packId/version/matchedRuleId`
- `context.knowledgeRules`
- `answerCard.knowledgeRule`
- `answerCard.evidenceRefs`
- `queryPlanReceipt.selection.knowledgeRule`

模型可以解释结果、提出澄清或起草图表，但不能修改知识 SQL、跳过字段结构匹配、伪造回执或在阻塞状态下给出近似数字。

## Verification

```powershell
npm run verify:platform-knowledge
npm run verify:platform-materials
npm run verify:platform-behavior
npm run verify:platform-commerce -- --root C:\Users\Administrator\Documents\AIBI-B\data\platform-research
```

第一条验证知识包结构、安全边界和 Agent 注入。第二条核对三份多工作表母版、十二份独立表、资料出处和关系膨胀指标。第三条验证闭环计划中的产品行为合同。第四条在临时数据库导入研究包，检查固定答案和“无可靠答案时阻断”；均不会修改用户当前工作区。

新增知识规则时必须同时提供：字段角色、匹配条件、统计粒度、只读 SQL、可复算测试和来源边界。禁止只添加提示词或硬编码答案。
