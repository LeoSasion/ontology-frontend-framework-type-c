# AI BI Workbench Product

## Product Definition

AI BI Workbench 是一个本地优先、证据驱动的业务分析工作台。用户可以把本地 CSV/XLS/XLSX 文件或文件夹接入工作区，用自然语言说明想看的业务问题或图表，系统生成字段语义、关系线索、指标计划、单图草案、看板草案和 Agent 可追溯回答。

产品不是展示页，也不是模板生成器。它的价值在于把业务用户熟悉的表格、指标、图表、看板和问答动作放进同一个受控工作区：用户先说目标，系统先给可审阅结果；需要写入时，再确认写入。

## Product Boundary

- 本仓库是产品边界，文档和验证只描述当前仓库内的代码、命令和运行时行为。
- 运行数据默认保存在本地 `data/` 或临时目录，且不进入版本控制。
- 写入动作必须经过 dry-run、草案或显式确认。
- Agent 回答必须能追到数据来源、指标口径、查询回执或阻塞原因。
- ERP 看板由可组合业务单元和当前字段证据选择，不依赖单一固定模板。
- 新工作区默认是干净空态：不自动加载内置素材、不自动运行查询、不自动触发 Agent 问答；无数据时只引导用户导入本地文件或文件夹。

## User Workflow

1. 创建或选择工作区。
2. 沿全局业务路径进入下一步：接入数据、生成图表、核对证据、确认写入。
3. 导入文件或扫描文件夹，先做结构和质量预检。
4. 生成 source-intelligence 证据摘要，识别字段、关系、指标计划和数据缺口。
5. 用户通过 Agent 或看板页说明想看的图表；默认一次对话创建一个可确认的图表草案。
6. 需要整套行业看板时，使用 beta 入口基于当前字段证据预演完整看板。
7. 对新增指标、公式、关系、看板、过滤器、索引、导入提交等写入动作进行确认。
8. 通过证据页和回执追踪每个结论、草案和运行结果。

## Product Spine

```text
workspace
  -> import preview / source run
  -> source-intelligence evidence profile
  -> semantic fields, relationships, metric plans
  -> whitelist query runtime
  -> dashboard, saved view, Agent answer, action draft
  -> confirmation receipt
```

## Current Contract

- 前端：React/Vite 工作台，桌面优先，同时保留响应式约束。
- API：Node 本地 API 作为薄封装，调用 Python CLI 完成业务动作。
- Worker：Python CLI 管理 SQLite 元数据、DuckDB 查询、证据回执和动作草案。
- Agent：全局浮动入口加完整 Agent 工作区，回答和写入都受当前工作区上下文约束。
- Dashboard：AI 优先创建图表，保守路径一次对话生成一个图表；beta 路径一次性预演行业看板；指标、柱线饼、表格、文本、筛选、关系分析、保存视图和 ERP 单元看板仍保留在维护区。
- Evidence：导入、source-intelligence、查询、看板草案和 Agent 动作都保留可审阅回执。
- Empty Runtime：前端 fallback 使用空工作区、空查询、空看板和空 Agent 状态；没有真实接入数据时不伪装成已有业务数据。

## UX Contract

- 默认先展示意图输入和当前结果，不把筛选、维护、样式、页面管理、验证实验同时展开。
- 每个业务动作只有一个主承接页：数据源负责接入，看板负责图表创建，证据页负责追溯，AI 助手负责写入确认；其他页面通过跳转传递步骤。
- Agent 或看板页必须支持用户直接说出想看的图表，并返回字段、口径、证据和可确认草案。
- 单图创建是稳定默认能力；一次性创建整套行业看板是 beta 能力，必须标明预演、缺字段和确认边界。
- 读、解释、推荐、预演不要求额外确认；写入、覆盖、删除、导入提交继续停在草案或 dry-run-confirm。
- 具体页面层级、文案和确认策略由 `docs/product-ux-standard.md` 维护。

## Non-Goals

- 不在仓库中保存真实业务数据或凭据。
- 不把非当前运行契约写入产品文档。
- 不让 Agent 绕过 dry-run 或确认边界直接写入。
- 不把缺失字段或不可执行指标伪装成已验证结论。
- 不把内置素材、历史验证数据或演示表当作默认首页、默认查询或默认看板内容。
