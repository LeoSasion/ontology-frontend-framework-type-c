# AI BI Workbench PRD

## Problem

业务用户经常只有本地表格、ERP 导出和零散字段说明，却需要快速回答销售、库存、利润、应收、采购、生产或运营问题。传统 BI 要先建模、写 SQL、配置看板；普通 AI 问答又容易脱离数据证据。

本产品要把本地数据接入、证据分析、图表生成、看板生成、Agent 问答和写入确认放进一个工作台，让用户能从业务问题出发，同时保留可追溯和可控制的执行链。

## Target Users

- 运营、财务、供应链、电商、ERP 使用者，需要从导出表中快速看趋势、异常、对账和缺口。
- 业务负责人，需要用熟悉的看板和问答方式获得结论，但不希望直接改动数据模型。
- 数据/实施人员，需要一个本地可验证的工作台来调试字段语义、关系、公式、指标和看板草案。

## Product Goals

- 导入或扫描本地文件后，自动生成字段、关系、指标计划和数据缺口说明。
- 所有结论都能追到 source-intelligence、查询、指标口径或动作回执。
- 用户可以通过 AI 入口直接描述想看的图表，默认一次对话生成一个可确认单图草案。
- 常见 BI 操作可通过 UI 或 CLI 完成，并在写入前提供 dry-run 或草案。
- Agent 能基于当前工作区回答问题、生成草案、解释阻塞原因。
- ERP 和行业看板保留 beta 能力，通过公开参考和字段证据选择业务单元，而不是强制固定模板。

## Non-Goals

- 不承诺云端同步、多人协作或生产级权限系统。
- 不把真实业务文件、数据库、日志或凭据纳入仓库。
- 不让 Agent 在未确认时执行写入。
- 不为缺失证据的指标生成确定性结论。
- 不维护非当前产品契约文档。

## Primary Workflow

1. 用户进入工作区，看到当前数据、看板、证据和 Agent 状态。
2. 用户选择文件或文件夹，先运行导入预检。
3. 系统生成 source-intelligence 证据摘要，包括字段候选、语义角色、关系线索、指标计划和缺口。
4. 用户在 AI 创建区说明想看的单个图表，系统返回图表草案、字段口径、证据和缺口。
5. 需要更多范围时，用户可以进入行业看板 beta，先预演整套看板再决定是否写入。
6. 用户向 Agent 提问，Agent 返回业务答案、证据路径、查询回执和必要的动作草案。
7. 用户审阅草案影响范围，再确认或拒绝写入。
8. 系统记录回执，证据页展示本次动作的来源、口径和结果。

## Functional Requirements

### Workspace

- 支持创建、选择和读取本地工作区。
- 工作区隔离数据表、字段、指标、关系、保存视图、看板和动作草案。
- 当前页面和当前数据上下文应传给全局 Agent。

### Source And Import

- 支持 CSV/XLS/XLSX 文件导入预检。
- 支持文件夹或多路径 source-intelligence 扫描。
- 预检必须展示可读性、字段、重复键、空键、合并策略和潜在风险。
- 导入提交必须经过确认。

### Semantic And Metrics

- 支持字段角色、业务用途、置信度和手工覆盖。
- 支持公式预览、公式保存、指标推断和指标查询。
- 指标计划必须标明可执行、缺字段或需人工确认。

### Query And Views

- 查询入口只接受白名单参数，不直接暴露任意 SQL。
- 支持表查询、分组聚合、指标查询、关系查询和保存视图。
- 查询结果应带运行时回执，供 Agent 和证据页引用。

### Dashboard

- 支持指标、柱状、折线、饼图、表格、文本、筛选、关系分析、复制、重命名、删除和样式设置。
- 看板页默认提供 AI 创建区：用户描述想看的图表，系统引导生成一个可确认图表草案。
- 单图草案应说明推荐图表类型、字段、指标口径、证据和写入边界。
- 支持基于当前表和证据生成业务看板草案。
- 支持行业看板 beta：一次性预演整套 ERP/行业看板，但必须标明 beta、字段命中、缺字段和 omitted units。
- 支持全局筛选、组件筛选、保存视图绑定和源切换预检。
- 全局筛选、组件维护、页面管理和组件合同默认按需展开，不作为第一屏主操作。
- 看板写入必须是 draft 或 dry-run-confirm。

### ERP Unit Library

- 使用公开 ERP/进销存/电商运营参考建立字段别名和业务单元。
- 根据当前字段匹配选择可解释单元，并给出 omitted unit hints。
- 不把缺失字段的单元渲染为已完成图表。
- Agent 和看板预览应展示选中单元、匹配字段、缺口、下一步可补字段和来源参考。

### Agent

- 支持全局浮动 Agent 和完整 Agent 工作区。
- 回答应包含业务结论、证据路径、查询回执或阻塞说明。
- 写入类意图必须生成动作草案，不能跳过确认。
- 待确认草案应展示目标、风险、证据、影响范围和下一步。
- 模型或本地规则运行方式应有可审阅的 runtime disclosure。

### Evidence

- 证据页优先展示业务摘要和可操作解释。
- 技术细节、回执路径、原始引用和运行时诊断放入可展开区域。
- 证据对象应覆盖导入、source-intelligence、查询、看板草案和 Agent 动作。

## Acceptance

- `npm run build` 通过。
- `npm run verify` 通过。
- `npm run verify:bi-cli-contract` 通过。
- `npm run verify:erp-units` 通过。
- `python tools/bi_cli.py --json status` 返回成功。
- `python tools/bi_cli.py --json source-intelligence validation-inputs --label "Validation evidence profile"` 返回证据回执。
- `python tools/bi_cli.py --json business-dashboard --template erp-units --op draft --limit 24` 返回可审阅草案。
- `docs/product-acceptance-matrix.md` 覆盖空工作区、导入、证据、单图表、Beta 看板、确认/拒绝、删除影响和无样例生产边界。

## UX Principles

- Users should start from business actions and natural-language intent, not from maintenance panels.
- 每个业务能力只有一个主页面承接；其他页面通过全局业务路径跳转传递步骤，不重复展示同一套执行入口。
- Stable default: one conversation creates one chart draft.
- Beta path: one conversation can preview a full industry dashboard, but it must stay visibly beta until evidence matching is consistently reliable.
- 默认展示意图、结果和信任摘要，技术细节按需展开。
- 所有按钮和状态文案要说明当前动作、风险和结果。
- 读、解释、推荐、预演不增加确认；写入、覆盖、删除和导入提交必须确认。
- 桌面布局要信息密度高、层级清楚，避免营销页式展示。
- 不因为 Agent 存在就隐藏确定性 CLI/工作台能力。
- 页面层级、文案和确认策略遵循 `docs/product-ux-standard.md`。
