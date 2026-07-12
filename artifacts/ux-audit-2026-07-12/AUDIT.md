# AIBI-C 新手全流程修复计划

> 执行状态：已完成（2026-07-12）。Phase 0-7 已落地；清单中的 `[x]` 表示实现与对应回归均已完成。

## 0. 完成回执

- 核心与合同：`npm run verify`，516/516 通过；AI 单图保真 9/9 通过。
- 生产门禁：`npm run verify:production`、`npm run verify:backup`、`npm run verify:workspace-flow` 均通过。
- UI 闭环：`npm run verify:ui-flow`、`npm run verify:ui-visual`、`npm run verify:ui-empty`、`npm run verify:ui-import` 均通过。
- 真实数据 UI：完成导入、自动证据、单图草案、唯一确认、结果优先与证据跳转；四种 PC 比例无横向溢出、文字挤压或重复确认组。
- 工作区安全：创建后自动进入；删除必须先在应用内 dry-run，显示目标和依赖计数，再出现唯一最终删除按钮；无 `window.confirm`。
- 可访问性：空态导入区自然键盘顺序为路径输入、检查文件、检查文件夹、高级设置，且无正数 `tabindex` 干预。
- 清洁性：临时工作区由回归生命周期删除，截图写入系统临时目录，真实数据未复制到仓库。

> 本文件是 Coding Agent 的执行合同，替代原审计报告。截图保留为回归证据，不作为实现说明。

## 1. 任务目标

把当前主流程修复为可重复、可恢复、结果正确的新手闭环：

`创建工作区 -> 导入文件或文件夹 -> 自动生成证据 -> 描述一个图表 -> 审阅唯一草案 -> 确认写入 -> 核对证据 -> 返回结果`

完成后必须满足：

1. 用户输入的指标、维度、聚合和图表类型完整进入最终组件。
2. 工作区、数据表、证据运行、动作草案和看板上下文在异步请求、跳转、刷新和历史导航中保持一致。
3. 导入来源只选择一次，普通写入只确认一次，同一草案只显示一组操作。
4. 有结果时优先展示结果；技术计划、匹配详情和高级维护默认收起。
5. 1280x720、1440x900、900x1440、1100x1100 均无逐字换行、重叠、裁切和全局横向溢出。

## 2. 不可破坏的产品边界

- 保持 single-user、local-only、loopback-only。
- 不增加样例数据、默认问题、行业字段回退或内置数据入口。
- 不开放任意 SQL、任意 Python/Shell 或绕过确认的写入。
- 只读回答、证据查看和预演不增加确认。
- 整套行业看板继续保持 Beta，不进入默认单图路径。
- 手工语义、指标、关系、公式、视图和看板不得被自动清理。
- 不为修复本流程复制第二套查询、证据、路由或动作草案模型。
- 保留当前工作树中的既有改动；禁止用 reset、checkout 或批量回退清理无关文件。

## 3. 已确认的根因入口

| Failure | Confirmed code signal | Primary files |
| --- | --- | --- |
| 单图意图丢失 | `build_agent_dashboard_create_draft()` 在单图模式仍从通用业务模板选择第一个组件，没有使用已经解析出的 `widget_action`。 | `tools/bi_cli.py`, `tools/business_dashboard_service.py`, `tools/agent_prompt_resolution.py` |
| Agent 输入被替换 | Dashboard 传入原始问题后，`AgentPanel` 的 `promptTouched=false` 会按 workbench 更新重新生成默认问题。 | `src/components/DashboardBusinessTaskStrip.tsx`, `src/useAppAgentActions.ts`, `src/components/AgentPanel.tsx`, `src/agentPanelModel.ts` |
| 证据过程上下文错位 | Source Intelligence 请求和响应没有显式 `workspaceId`；长任务结束后直接把并行刷新的 status/workbench 写回 UI。 | `src/sourceIntelligenceRunModel.ts`, `src/apiSource.ts`, `server/sourceRoutes.ts`, `tools/bi_cli_parser.py`, `tools/bi_cli_source_commands.py`, `src/useAppDataActions.ts` |
| 导入后重复填路径 | 导入路径只保存在 `useSourceWorkbenchImportController`，证据输入是 `useSourceWorkbenchState` 中独立的空字符串。 | `src/useSourceWorkbenchImportController.ts`, `src/useSourceWorkbenchState.ts`, `src/components/SourceWorkbenchDataEntryPanel.tsx` |
| 两套确认按钮 | `AgentPendingChangesPanel` 同时渲染当前草案操作和包含同一草案的队列操作。 | `src/components/AgentPendingChangesPanel.tsx`, `src/components/AgentPanel.tsx` |
| 中文逐字换行 | `agentTargetBoundary` 使用 `1fr auto`，但断点只看整个 main panel，不看该卡片在嵌套网格中的实际宽度。 | `src/components/AgentContextPlanPanel.tsx`, `src/components/agentEvidenceDrafts.css`, `src/components/agentEvidenceWorkspace.css` |
| 结果被创建区压到首屏下方 | `DashboardBusinessTaskStrip` 始终排在 widget kit 之前。 | `src/components/DashboardCanvas.tsx`, `src/components/DashboardBusinessTaskStrip.tsx`, `src/components/dashboardCanvasCore.css` |
| 工作区删除风险 | 管理区列出所有非当前工作区，使用 `window.confirm`，没有在 UI 中展示 dry-run 依赖。 | `src/components/SidebarWorkspaceCard.tsx`, `src/components/Sidebar.tsx`, `src/useAppWorkspaceActions.ts`, `server/workspaceRoutes.ts` |
| 空工作区仍显示“可分析” | TopBar 和 rail 只读取 `status.health.ok`，把服务健康误当成产品就绪。 | `src/components/TopBar.tsx`, `src/components/Sidebar.tsx`, `src/productActivationModel.ts` |
| 证据页自动宣称已核对 | 页面进入即显示“证据已核对”，没有用户动作或明确状态依据。 | `src/components/EvidenceView.tsx`, `src/evidenceViewModel.ts` |

## 4. 执行规则

1. 严格按 Phase 0 到 Phase 7 执行；P0 行为缺陷未通过前不得先做视觉润色。
2. 每个 Phase 先增加失败回归，再修改实现，再运行该 Phase 的退出命令。
3. 每次只改当前问题需要的模块；共享模型只在能消除真实重复时抽取。
4. API/CLI 返回值必须类型化，新增字段同步更新 TypeScript 类型、CLI contract 和验证脚本。
5. 不用静态文案或 CSS 隐藏错误状态；结果不一致必须在状态层阻止渲染。
6. 不以检查总数作为长期文档事实；本文件只记录命令和行为门槛。
7. 每个 Phase 完成后更新本文件对应复选框，但不要追加流水账。

## 5. Phase 0: 建立失败基线

### 目标

先让现有自动化稳定复现本轮浏览器发现，防止修复过程中用新的假成功覆盖旧问题。

### 工作项

- [x] 在 `scripts/verify-ai-chart-reliability.mjs` 增加明确意图用例：
  - `按渠道汇总净销售额，生成柱状图` -> `bar + sum(net_sales) + channel`。
  - `按订单日期查看净销售额趋势` -> `line + sum(net_sales) + order_date`。
  - `查看净销售额` -> 允许 `metric + sum(net_sales)`。
  - 未知指标或缺少必要维度 -> clarification，且不创建草案。
- [x] 扩展 `scripts/verify-ui-real-import.mjs`，不再只检查“一个组件”，还要检查组件类型、measure、dimension、aggregation 与原始问题一致。
- [x] 增加工作区异步一致性断言：Source Intelligence 运行前后 `workspace.id` 不变，响应 `workspaceId`、status 和 workbench 相同。
- [x] 增加 DOM 断言：活动草案只能出现一个 `预演/确认/拒绝` 操作组。
- [x] 增加 1280x720 确认页布局断言：目标边界标题可见宽度不小于 160px，中文不得逐字换行。
- [x] 增加工作区创建后自动激活断言，不允许测试脚本再手工 select 才继续。
- [x] 增加删除预演断言：不得调用原生 confirm，确认前必须显示目标和依赖计数。

### 退出条件

- 新增用例在旧实现上能准确失败，失败标签能指出具体合同。
- 不删除或放宽现有生产无样例、证据和写入边界断言。

### 验证命令

```powershell
npm run verify:ai-reliability
node scripts/verify.mjs
```

## 6. Phase 1: 修复工作区与异步上下文

### 目标

任何异步结果只能写回发起请求时的工作区。响应过期或工作区已切换时，丢弃响应并重新读取当前状态。

### 数据合同

为 Source Intelligence 请求增加：

```ts
type SourceIntelligenceRunRequest = {
  workspaceId: string;
  inputs: string[];
  label?: string;
  outputDir?: string;
};
```

成功响应至少包含：

```ts
type SourceIntelligenceRunResult = {
  ok: true;
  workspaceId: string;
  runKey: string;
  tableKey?: string;
  inputRoots: string[];
};
```

### 工作项

- [x] `src/sourceIntelligenceRunModel.ts` 定义严格请求/响应类型，移除该路径上的 `Record<string, unknown>` 主合同。
- [x] `src/apiSource.ts` 发送发起时的 `workspaceId`。
- [x] `server/sourceRoutes.ts` 将 workspace 参数传给 CLI，不依赖请求执行时的全局 active workspace。
- [x] `tools/bi_cli_parser.py` 为 `source-intelligence` 增加 `--workspace`。
- [x] `tools/bi_cli_source_commands.py` 验证工作区存在，并把证据运行写入指定工作区；返回 `workspaceId` 和规范化 `inputRoots`。
- [x] `src/useAppDataActions.ts` 捕获发起时 workspace；仅当响应 workspace 与当前 workspace 一致时更新状态并跳转。
- [x] 把 status/workbench/dashboards/drafts 作为同一次 surface refresh 应用，避免先写默认状态再写真实对象。
- [x] 路由跳转必须同时携带 `table`、`run`，且两者属于响应 workspace。
- [x] Agent ask 和 action confirm 至少返回 `workspaceId`；确认前验证草案仍属于当前工作区。
- [x] 工作区切换时取消或失效前一个工作区的请求令牌，不能让旧 Promise 覆盖新工作区 UI。

### 验收标准

- 生成证据过程中切换工作区，旧结果不出现在新工作区。
- 不切换工作区时，证据完成后直接进入原工作区的真实 table/run。
- UI 不再同时出现“0 张表”和“当前数据 orders”。
- 刷新不是恢复正确状态的必要步骤。

### 验证命令

```powershell
npm run verify:workspace-flow
npm run verify:context
node scripts/verify.mjs
```

## 7. Phase 2: 合并导入与证据步骤

### 目标

用户只选择一次来源。导入成功后系统自动对本次已确认来源生成证据；手工路径输入只保留为高级重跑入口。

### 工作项

- [x] `useSourceWorkbenchImportController` 在确认导入结果中保留 `committedInputRoots`，文件导入和文件夹导入使用同一字段。
- [x] `handleCommitImport` / `handleCommitFolderImport` 成功后，用同一 workspace 和 committed roots 自动调用 Source Intelligence。
- [x] 自动画像是只读后处理，不增加第二次确认；导入失败时不得启动画像。
- [x] 画像运行中显示一个连续状态：`正在导入 -> 正在生成证据 -> 可以生成图表`。
- [x] `SourceWorkbenchDataEntryPanel` 从新手主路径移到“重新生成或补充证据”折叠区。
- [x] 自动画像失败时保留已导入数据，提供“按本次来源重试”和“更换来源”两个动作。
- [x] 文件夹预演的确认按钮放在计划标题行或 sticky action bar，不能被内层滚动区遮挡。
- [x] 导入成功后清理旧 preview，但保留本次来源回执和可审计 input roots。

### 验收标准

- 导入确认后不再出现空白“本地文件夹或文件”输入框作为必经步骤。
- 证据运行使用的路径与导入回执一致。
- 失败后重试不需要重新粘贴路径。
- 两张表导入只产生一个连贯的下一步，不同时展示导入、画像和高级配置入口。

### 验证命令

```powershell
$env:AIBI_REAL_IMPORT_FOLDER = (Resolve-Path validation-inputs).Path
npm run verify:ui-import
node scripts/verify.mjs
```

## 8. Phase 3: 单图意图保真

### 目标

同一份解析结果同时驱动回答、草案预览、确认写入和最终组件，禁止每一步重新猜测字段。

### 目标合同

单图草案必须保存：

```json
{
  "originalPrompt": "按渠道汇总净销售额，生成柱状图",
  "tableKey": "orders",
  "widget": {
    "type": "bar",
    "measure": "net_sales",
    "dimension": "channel",
    "aggregation": "sum"
  },
  "selectionConfidence": {
    "type": "explicit",
    "measure": "explicit",
    "dimension": "explicit"
  }
}
```

### 工作项

- [x] 在 `tools/business_dashboard_service.py` 增加单一职责 helper，例如 `build_single_chart_dashboard_draft(resolved_widget, ...)`。
- [x] `build_agent_dashboard_create_draft()` 的单图分支必须使用 `resolve_prompt_widget_action()` 的结果，不再从通用模板列表取第一个组件。
- [x] Full dashboard Beta 继续使用业务单元/模板选择，不与单图 helper 合并。
- [x] `tools/bi_cli.py` 保证 `matched.widget`、`answerCard.query`、`dashboardDraft.previewWidgets[0]` 和最终 widget 使用相同字段。
- [x] 图表类型、measure 或必需 dimension 置信度不足时返回 clarification，不创建 action draft。
- [x] 原始问题写入 Agent response 和 action payload；`AgentPanel` 显示本次请求，不用默认问题覆盖。
- [x] `AgentPanel` 仅在没有本次请求、没有草案且输入未触碰时生成建议问题。
- [x] 确认后校验创建结果与草案哈希或关键字段一致，防止确认阶段再次选模板。

### 验收标准

- 柱图请求最终为柱图，且使用用户指定的 measure/dimension。
- 趋势请求使用可执行日期维度；无日期字段时澄清，不用任意分类字段替代。
- metric 请求可以不带 dimension。
- 不存在目标看板时，只创建一个容器和一个已解析组件。
- Agent 页显示原始问题，不变成“orders 行数”或其他建议问题。

### 验证命令

```powershell
npm run verify:ai-reliability
npm run verify:query-receipts
npm run verify:ui-import
node scripts/verify.mjs
```

## 9. Phase 4: 唯一草案审阅与响应式布局

### 目标

待确认页默认只回答四个问题：要做什么、写到哪里、影响什么、确认还是拒绝。

### 工作项

- [x] `AgentPendingChangesPanel` 只渲染一组活动草案按钮。
- [x] 队列列表排除当前活动草案；只有剩余草案大于 0 时显示“其他待处理”。
- [x] 影响摘要只显示非零类别；零值类别进入详情，不占第一屏四列。
- [x] `AgentTaskPacket` 合并目标、组件预览和证据摘要，不再与 `AgentContextPlanPanel` 重复目标信息。
- [x] 匹配置信度、计划、查询回执、命令和编号全部进入关闭的 progressive details。
- [x] 活动草案使用 sticky action row，按钮顺序固定为 `预演`、`确认`、`拒绝`。
- [x] `agentTargetBoundary` 使用自身 container query；可用宽度不足时改为单列，禁止 `1fr auto` 挤压正文。
- [x] 长工作区、表、看板和动作名称使用单行省略或合理多行，禁止 `overflow-wrap:anywhere` 造成中文逐字竖排。
- [x] 删除重复 accessible name；活动草案确认按钮全页只能有一个。

### 验收标准

- 一个草案只有一组操作按钮。
- 1280x720 首屏能看到草案目标、一个组件摘要和操作按钮。
- 任何正文容器不出现单字一行。
- 技术信息默认关闭，但仍可展开审计。

### 验证命令

```powershell
npm run verify:ui-flow
npm run verify:ui-visual
node scripts/verify.mjs
```

## 10. Phase 5: 结果优先、状态和证据文案

### 目标

用户确认后立即看到结果；系统状态描述业务就绪程度，不把服务健康冒充数据可分析。

### 工作项

- [x] `DashboardCanvas` 在有 widgets 时先渲染结果，再渲染紧凑“生成新图表”工具条。
- [x] 无 widgets 时保留当前大号创建入口；同一组件根据 `hasResult` 使用两种密度，不复制逻辑。
- [x] 已确认结果首屏展示标题、核心图表、证据入口和明细入口。
- [x] 提取统一 `productReadiness`：`service-ready`、`needs-data`、`needs-evidence`、`ready-to-analyze`、`pending-confirmation`。
- [x] TopBar、Sidebar 和 ProductActivationPanel 使用同一 readiness，不再仅判断 `status.health.ok`。
- [x] 空工作区显示“待接入”，有表无证据显示“待生成证据”，可查询后才显示“可分析”。
- [x] Evidence 页面将“证据已核对”改为“证据可核对”或基于真实用户动作的状态。
- [x] `18/24` 改成带对象的表达，例如“24 个候选问题中 18 个可执行”，并为不足项提供解释入口。
- [x] 全局 AI 浮动按钮补充稳定 aria-label。

### 验收标准

- 确认后无需滚动即可看到真实结果。
- 空工作区任意页面不出现“可分析”。
- 证据页不自动替用户宣称已经完成核对。
- 比值、状态和风险无需阅读技术回执即可理解。

### 验证命令

```powershell
npm run verify:ui-empty
npm run verify:ui-flow
npm run verify:ui-visual
node scripts/verify.mjs
```

## 11. Phase 6: 工作区创建与删除安全

### 目标

创建后立即进入新工作区；删除时明确目标和影响，不在当前上下文中平铺其他工作区的危险按钮。

### 工作项

- [x] `handleWorkspaceCreate` 使用创建响应中的 workspace id 校验 active workspace；必要时显式 select，再原子刷新 surface。
- [x] 创建成功后清空旧 table/view/dashboard/run/action URL 上下文，并进入新工作区 Home。
- [x] 显示一次非阻塞完成状态“已进入新工作区”，不增加确认。
- [x] `SidebarWorkspaceCard` 的管理区先提供“选择要管理的工作区”，不直接平铺多个删除按钮。
- [x] 删除动作先调用现有 dry-run API，把 workspace 名称、表、看板、草案、证据和总影响展示在应用内面板。
- [x] 移除 `window.confirm`；只有 dry-run 成功后显示一个最终删除按钮。
- [x] 当前工作区不可删除时明确说明“请先切换到其他工作区”，不要悄悄改为删除另一个工作区。
- [x] 默认工作区保持不可删除；服务端继续做最终权限校验。
- [x] 长名称在目标选择器中省略，在预演面板中完整可读。
- [x] 删除完成后显示回执并停留在仍有效的当前工作区。

### 验收标准

- 创建操作后不需要手动切换下拉框。
- 用户永远不会在“当前工作区管理”中误以为删除按钮针对当前对象，实际却删除其他对象。
- 删除前能看到准确依赖，取消不产生写入。
- 删除完成后 URL 不保留已删除工作区对象。

### 验证命令

```powershell
npm run verify:workspace-flow
node scripts/verify.mjs
```

## 12. Phase 7: 全流程视觉与可访问性回归

### 目标

在行为修复完成后统一检查信息密度、长文本、焦点和常见 PC 比例。

### 视口

| Key | Size | Purpose |
| --- | --- | --- |
| compact-landscape | 1280x720 | 本轮确认页挤压复现 |
| landscape | 1440x900 | 常规横屏 |
| portrait-pc | 900x1440 | 竖屏 PC |
| square | 1100x1100 | 正方形 PC |

### 工作项

- [x] 对空态、导入预演、画像运行、单图输入、草案审阅、已确认结果、证据和删除预演逐一截图。
- [x] 检查 document、main panel 和内层工具无非预期横向滚动。
- [x] 检查按钮文字完整，不因父级宽度变化改成逐字换行。
- [x] 检查 loading、error、empty、blocked、draft、confirmed 状态尺寸稳定。
- [x] 检查键盘 Tab 顺序：主要动作 -> 次要动作 -> 折叠详情。
- [x] 所有 icon-only 按钮有可读 aria-label 和 tooltip。
- [x] 重复按钮、重复 heading id、无标签输入和焦点不可见均视为失败。
- [x] 更新 `scripts/verify-ui-visual.mjs` 与 `scripts/verify-ui-real-import.mjs` 的截图和几何断言。

### 验收标准

- 四个视口全部通过，无人工忽略项。
- 主流程可仅用键盘完成，危险操作焦点不会默认落在最终确认。
- 截图中无重叠、裁切、逐字竖排、错误状态混合和结果被首屏工具遮挡。

### 验证命令

```powershell
npm run build
npm run verify
npm run verify:ui
npm run verify:production
npm run verify:backup
npm run preflight
```

## 13. 最终 Definition Of Done

- [x] Phase 0 到 Phase 7 的工作项和退出条件全部满足。
- [x] `按渠道汇总净销售额，生成柱状图` 从 UI 到最终 widget 完整保真。
- [x] 导入后自动生成证据，没有第二次路径输入。
- [x] 任意异步结果不会写入错误工作区 UI。
- [x] 一个草案只有一组预演、确认、拒绝。
- [x] 有结果的看板首屏先显示结果。
- [x] 工作区创建自动进入，删除有应用内 dry-run 和一次最终确认。
- [x] 四种 PC 比例和键盘主流程通过。
- [x] 生产空态没有样例、默认问题或领域字段。
- [x] `npm run preflight` 通过。
- [x] `git diff --check` 通过。
- [x] 临时工作区、验证数据库、截图输出和真实数据均未进入提交范围。

## 14. 建议提交边界

为降低回滚成本，按以下顺序提交，禁止把全部修改压成一次提交：

1. `test: lock full-flow regression failures`
2. `fix: bind source intelligence to workspace context`
3. `fix: continue import into evidence automatically`
4. `fix: preserve resolved single-chart intent`
5. `refactor: make agent draft review single-purpose`
6. `fix: prioritize results and unify readiness copy`
7. `fix: add guarded workspace management`
8. `test: close responsive and accessibility regression`

每次提交只包含对应 Phase 的实现、测试和必要文档更新。

## 15. 视觉证据索引

| Evidence | File |
| --- | --- |
| 空工作区 | `02-empty-workspace-home.jpg` |
| 数据源空态 | `03-empty-sources.jpg` |
| 导入预演确认位于内层底部 | `05-import-preview.jpg` |
| 导入后重复输入来源 | `06-post-import-evidence-required.jpg` |
| 证据完成后的工作区错位 | `07-evidence-context-loss.jpg` |
| 柱图请求变成指标卡 | `08-chart-draft-review.jpg` |
| 确认页逐字换行 | `10-confirmation-overload.jpg` |
| 同一草案两套操作 | `11-confirm-buttons.jpg` |
| 结果被创建入口压到下方 | `12-confirmed-result.jpg` |
| 证据页状态与比值文案 | `13-evidence-review.jpg` |
| 工作区删除目标混淆 | `14-workspace-delete-target.jpg` |

## 16. 本轮不做

- 云端账号、多人协作、远程托管或权限系统。
- 新行业模板、新图表类型或整套看板 Beta 晋级。
- 全局视觉重做、配色重做或导航重构。
- 与主流程无关的 CLI 命令拆分和大规模文件改名。
- 为通过测试硬编码 `orders`、`channel`、`net_sales` 或任何验证字段到生产默认逻辑。
