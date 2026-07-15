# AIBI-C 仓库执行约束

本文件只维护仓库级强制规则。产品、实现和验收事实分别由 [产品定位](PRODUCT.md)、[产品需求](docs/PRD.md)、[实现状态](docs/implementation-status.md) 和 [文档索引](docs/README.md) 维护。

## 身份守卫

- 根目录：`C:\Users\Administrator\Documents\AIBI-C`
- Git 远端：`https://github.com/LeoSasion/AIBI-C.git`
- 本地 API：`127.0.0.1:8787`
- 本地 UI：`127.0.0.1:8686`

执行任何读取、编辑、测试、提交或运行操作前，必须确认：

```powershell
git rev-parse --show-toplevel
git remote get-url origin
```

结果与上述身份不一致时立即停止并报告。

## AIBI 系列隔离

- `AIBI-A`、`AIBI-B`、`AIBI-C`、`AIBI-D`、`AIBI-E` 是五个独立产品和 Git 仓库；后缀不是版本或分支。
- 其他仓库只可只读借鉴问题拆解、交互策略和通用架构原则；所有结论必须按 AIBI-C 的合同、技术栈和测试独立实现。
- 禁止跨仓库复制或共享代码、文档、配置、环境文件、数据库、Fixtures、测试、端口、进程和运行回执。
- 旧名 `AIBI项目杂交` 只作为隔离阻断词保留，不得成为路径、依赖或回退来源。

## 操作边界

- 只操作 AIBI-C 的文件、进程、端口、数据库、缓存、Secrets、日志、构建产物和 Git 状态。
- 发现跨仓库绝对路径、符号链接、共享数据库、共享运行状态或外部 AIBI 测试输入时，停止并报告。
- 保留用户已有改动；禁止使用 `reset --hard`、`checkout --` 等破坏性清理。
- 只读操作不得暗含业务写入；写入能力必须经过预演、显式确认、工作区隔离并产生证据回执。
- 用户数据、凭据、真实数据库、业务导出和临时测试产物不得提交到仓库。

## 文档与证据

- 文档总入口为 [docs/README.md](docs/README.md)；同一可变事实只在一个职责文件维护。
- 当前状态以代码、`package.json`、运行时和 [实现状态](docs/implementation-status.md) 为准；日期回执只证明当次范围。
- 新增、删除或改名 Markdown 后必须更新索引并运行 `npm run verify:docs`。
