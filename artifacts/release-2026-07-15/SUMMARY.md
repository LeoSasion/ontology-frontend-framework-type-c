# AIBI-C v0.2.0 发布验收回执

- 日期：2026-07-15（Asia/Shanghai）
- 范围：通用领域框架、Agent 证据链、Session 与比较分支、发布生命周期、性能和响应式 UI
- 基线：`2663043fe5e0a3dd8b9be97dd144643247e775a5`
- 结论：完整 `npm run preflight -- --stop-after` 通过；隔离测试数据已删除，本地服务已停止。
- 机器结果：[receipt.json](receipt.json)

## 交付结果

| 范围 | 结果 |
| --- | --- |
| 通用框架 | 新工作区无默认行业语义；Domain Pack、Knowledge Pack、Connector、Provider 和领域单元职责分离 |
| 查询安全 | 比率无分子/分母时阻断；Run/Receipt/Unit 比较来源与 Pack 指纹；stale 证据不用于当前规划 |
| Agent 证据链 | Agent Turn 在规划前生成可复算 Analysis Unit；Evidence Plan blocker 持久化为可读字符串，旧异常对象也不再渲染为 `[object Object]` |
| Session 与比较 | 普通提问、只读说明和比较共享持久 Session；失效本地 Session 自动清理并仅重试一次；浏览器禁用存储时退化为非持久会话；Analysis Run 分支参数端到端保留且不混淆 Turn 父链 |
| 发布生命周期 | `preflight` 只管理自己启动的服务；Launcher 使用仓库所有权令牌，陈旧 PID 不会误杀无关进程；成功、失败和启动异常均有回归 |
| 配置与迁移 | Pack 状态进入配置导出/恢复；SQLite schema v7、DuckDB schema v1；旧 Dashboard Action 保留工作区 |
| 响应式界面 | 桌面与 390×844 窄屏均保留主导航、工作区切换、高级工具和设置，无全局横向溢出 |
| 文档体系 | 产品链、技术合同和日期证据分离；重复扩展说明合并；全部 Markdown 进入索引与链接门禁 |

## 验证回执

| 门禁 | 结果 | 说明 |
| --- | --- | --- |
| 仓库身份 | 通过 | 根目录与 origin 均指向 AIBI-C；未读取或运行其他 AIBI 仓库 |
| Build | 通过 | TypeScript、Vite 与 bundle budgets 通过；主包 279,977 / 280,000 bytes |
| Core verify | 通过 | 518/518 静态与运行合同通过 |
| CLI 与 Schema | 通过 | 137 条实时命令；SQLite v7、DuckDB v1；备份恢复和迁移回滚通过 |
| Agent | 通过 | Turn 17 项、Session 14 项及前端/路由/阻断渲染聚焦回归通过 |
| Performance | 通过 | 2 次预热、9 次采样；p50 691.6ms，p95 710.7ms；稳态、尾延迟与非法预算清理回归通过 |
| UI | 通过 | 工作区流程、视觉、空态、真实导入、中性三表语义执行与 Connector 六组浏览器验收通过 |
| Manual browser | 通过 | `sites → assets → observations` 两跳得到 North=58、South=26；不可达 Provider 安全回退；刷新后会话 2→3；390×844 无横向溢出；控制台无 warning/error |
| Lifecycle | 通过 | 最终健康检查通过；所有权令牌匹配后自动停止 8686/8787；陈旧 PID 模拟保留无关进程；端口和 PID 文件均释放 |

实时命令参数仍只以 [自动生成的 CLI 合同](../../docs/bi-cli-contract.md) 为准。

## 保留边界

- single-user and local-only；无认证、协作、云同步、远程托管或原生移动客户端。
- 跨表自动执行仅开放一跳和严格线性正向两跳。
- 整套行业看板保持 Beta，外部 Pack 只允许签名声明式资产。
- 报告只生成 Markdown；Analysis Unit 与导出最多冻结 500 行。

本回执只证明上述日期与范围；后续当前状态以 [实现状态](../../docs/implementation-status.md) 为准。
