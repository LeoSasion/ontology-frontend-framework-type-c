# 语义查询与跨表执行合同

## 目标

生产问数必须先解决字段歧义和统计粒度，再判断关系路径是否可执行。规划器只生成结构化证据，不输出任意 SQL 或写入。

## 规划阶段

1. **候选构建**：只读取当前工作区注册表、字段语义和指标；排除内部 `__*` 字段。
2. **字段解析**：记录问题命中的字段、指标和别名；显式表名可消歧，跨表竞争时返回 `needs-clarification`。
3. **粒度声明**：每个已选字段标注表、角色和统计粒度；一次问题可包含多个维度和指标。
4. **关系规划**：从显式表或首个已解析表出发，只在当前工作区保存关系图中寻找最多三跳路径。
5. **执行门禁**：缺路径返回 `needs-relationship`；低置信、方向不安全、行膨胀或验证过期返回 `needs-validation`。
6. **Receipt**：保存候选、选择、未决项、参与表、路径、风险、版本和计划哈希。

## 消歧规则

- 同名字段不能用导入顺序、列顺序或模型偏好决胜。
- 别名只帮助召回，不能绕过表级歧义。
- 用户明确表名后可在目标表内选择；依据必须进入 Receipt。
- 多个未决字段合并为一个候选面，全部选择后只提交一次后续请求。
- 一次澄清后仍不安全时明确阻断并引导关系维护，不继续追问。

## 关系与粒度规则

- 多维问题必须保留全部指标、维度和筛选，不得只处理首个命中字段。
- 推荐关系不是执行许可；多跳中任一跳失败，整条路径阻断。
- 复合业务键整体匹配、保存和验证，不得退化为第一列。
- 筛选只接受字段、白名单操作符和值；不接受自由表达式。
- 右表预聚合以完整右侧连接键分组，聚合字段和方式来自白名单。
- 表导入、覆盖或合并递增 `data_version` 并复验关系；字段缺失或复验失败标记 `stale`。
- 跨表金额先证明各表粒度、函数依赖和无放大，再允许聚合。

## 输出合同

语义计划 schema 为 `aibi-semantic-query-plan/v1`，核心字段包括：

- `status`：`not-applicable`、`ready`、`needs-clarification`、`needs-relationship`、`needs-validation`；
- `fieldResolution`：命中、候选、选择和未决项；
- `grain`：指标、维度、筛选和参与表；
- `joinPlan`：根表、目标表、候选/已选路径和每跳风险；
- `executionBoundary`：只产出证据，不产出任意 SQL 或写入。

受控执行 schema 为 `aibi-semantic-query-execution-plan/v1`。当前开放：

- 一跳：关系必须为当前 `validated`，指标使用白名单聚合；
- 两跳：只允许线性正向路径，每跳版本匹配且 `rowExpansion <= 1`；
- 三跳、反向路径、跨跳筛选和跨跳预聚合：保持显式阻断。

执行前重新构建计划并比对 SHA-256；关系被删除、替换或改版时返回 `semantic-plan-changed-before-execution`，不得退回单表猜测。

## 验证

```powershell
npm run verify:semantic-plan
npm run verify:composite-relationships
npm run verify:ui-semantic
```

跨项目借鉴和实现边界统一遵循根目录 [AGENTS.md](../AGENTS.md)，本合同不重复外部项目研究过程。
