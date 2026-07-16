# 探索线程与可恢复分析上下文

本合同定义如何把已经执行或确认的分析组织为可恢复、可比较的探索过程。Analysis Run、Query Plan Receipt 和 Analysis Unit 仍是分析事实源；Exploration Thread 只保存不可变血缘引用与结果板编排，不复制业务结果行，也不获得新的执行权限。

## 用户结果

用户可以从一个当前且已验证的结果建立探索线程，沿父结果创建比较分支，把多个结果固定在同一结果板，并在重启后恢复“从哪里来、比较了什么、哪些结果仍可继续”。历史锚点即使失效也保留审计价值，但不会被重新解释为当前证据。

## 对象合同

| 对象 | 责任 | 不负责 |
| --- | --- | --- |
| Exploration Thread | 工作区内的探索标题、根锚点、当前锚点和生命周期 | 保存聊天全文、业务行或自动选择字段 |
| Exploration Anchor | 不可变绑定 Run、Receipt、Unit、可选 Session/Turn 及其指纹 | 重新执行查询、改写父链或覆盖旧结果 |
| Result Board Item | 决定某个锚点是否固定及其展示顺序 | 复制 Unit rows、保存任意图表代码或绕过 Chart Adapter |

线程、锚点和结果板均按工作区隔离。锚点一旦创建不允许修改绑定；新结论只能创建新锚点。结果板只允许固定或移除既有锚点，并保留对应操作回执。

## 建立与扩展

1. 根结果必须属于当前工作区，Analysis Run 状态为 `executed` 或 `confirmed`，Receipt 为 `executed`，Analysis Unit 为 `ready` 且实时新鲜度检查通过。
2. 建立线程先返回 dry-run，展示工作区、Run、Receipt、Unit、来源绑定和是否可恢复；只有显式确认才写入线程、根锚点和首个结果板项。
3. 新锚点必须引用同一线程的父锚点；其 Analysis Run 的 `parent_run_key` 必须等于父锚点绑定的 Run，禁止把无关结果拼入同一血缘。
4. 一个 Run 在同一线程最多对应一个锚点；重复提交返回既有对象，不产生重复板项。
5. 结果板固定或移除先预演再确认。移除只改变展示编排，不删除 Anchor、Run、Receipt、Unit 或 Session 历史。

## 恢复与新鲜度

读取线程时逐锚点实时复核：

- Run、Receipt、Unit 是否仍存在于当前工作区，且三者引用一致；
- Unit 冻结结果与计算是否仍匹配，Receipt 的数据、schema、关系路径、Domain Pack 和 Workspace Planning Binding 是否仍当前；
- 锚点保存的 Run、Receipt、Unit、结果和图表输入指纹是否仍匹配；
- 已绑定的 Session/Turn 是否存在且属于同一工作区、同一会话，并仍引用该 Run；
- 父锚点与 Analysis Run 父链是否一致。

检查结果分为：

- `current`：可在当前锚点上继续创建分析分支；
- `stale`：历史仍可查看，但 `usableForContinuation=false`，不得进入 Agent 规划、图表适配、导出或新分支；
- `missing`：引用对象缺失，保留锚点和明确缺失原因，不回退到“最新”对象。

线程恢复只返回类型化引用、业务标题、分析形状、Chart Adapter 摘要、新鲜度和阻塞原因。Provider 不参与新鲜度判断，不能创建、选择、固定或恢复锚点。

## 界面流程

- 当前结果满足门禁时，在高级比较区显示“建立探索线程”或“加入当前线程”。
- 第一次操作展示一份紧凑预演；确认后在同一区域出现结果板和可继续比较入口，不增加第二个全局确认面。
- 结果板默认展示业务标题、父子关系、指标/维度、图表类型和当前/失效状态；技术键与指纹按需展开，原始结果行不在此重复展示。
- 窄屏按血缘顺序纵向排列；不依赖横向拖拽才能访问固定、移除或继续比较。
- 工作区切换后丢弃在途响应和预演，重新读取目标工作区线程；客户端不得传入任意 workspace 覆盖服务端活动工作区。

## 安全边界

- Exploration Thread 是本地运行证据，不属于配置导出；工作区删除时必须一并删除。
- 所有读取 API 绑定服务端活动工作区；所有写入命令必须支持 dry-run 与 `--yes` 确认。
- 结果板只接受登记的 Analysis Unit 与其 Chart Adapter，不接受用户 SQL、脚本、URL、任意 JSON 图表执行器或 Provider 生成配置。
- 不自动把聊天偏好、线程标题或分支标签提升为共享业务事实、Context Rule、Semantic Patch、Confirmed Plan Memory 或 Analytical Skill。

## 验收门槛

- 根线程、父子锚点、去重、板项固定/移除、重启恢复和工作区删除均有确定性专项验证。
- 数据、schema、关系、Pack、Receipt、Unit、Session 或 Turn 漂移后，历史可见但继续操作被阻断，且不存在 stale fallback。
- 跨工作区 Run/Receipt/Unit/Session/Turn、错误父链和未确认草案均在任何写入前失败。
- CLI 合同、API、类型化客户端、桌面与窄屏 UI 同源；API 不接受客户端 workspace 覆盖。
- `npm run verify:exploration-threads`、`npm run verify`、`npm run build` 和本地交付前 `npm run preflight` 通过。
