# AIBI-C

AIBI-C 是面向本地 CSV/Excel 业务数据的证据型 AI BI 工作台。它用确定性运行时完成导入、语义解析、查询、证据和受控写入；可选模型只负责解释，不拥有数据或系统权限。

## 快速开始

```powershell
npm ci
python -m pip install -r requirements.txt
npm run dev
```

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| UI | `http://127.0.0.1:8686` | Vite 开发界面 |
| API | `http://127.0.0.1:8787` | 本地 API 与生产构建入口 |

环境变量写入根目录 `.env`，模板见 `.env.example`；不得提交 `.env` 或密钥文件。

常用运行命令：

```powershell
npm run api
npm run dev:ui
npm run local:start
npm run local:health
npm run local:stop
```

## 验证

```powershell
npm run verify:docs
npm run build
npm run verify
npm run preflight -- --skip-ui
npm run preflight
```

- `verify:docs` 校验 Markdown 索引、相对链接、唯一标题和仓库守卫内容。
- `verify` 覆盖隔离、CLI、语义/关系、Job、Workflow、Analysis Unit、导出、Connector、证据和 Provider 回退。
- `preflight` 是本地交付总入口；不带 `--skip-ui` 时包含真实浏览器闭环。
- 专项命令只在 [实现状态](docs/implementation-status.md) 维护，避免多处清单漂移。

## 本地数据与恢复

运行数据位于被 Git 忽略的本地目录。备份不包含 `.env`、源文件或凭据。

```powershell
npm run local:stop
npm run backup:local
npm run restore:local -- --from <backup-directory>
npm run restore:local -- --from <backup-directory> --confirm
npm run migrate:local
npm run migrate:local -- --confirm
```

恢复和迁移默认只预演；`--confirm` 才写入。迁移先验证隔离副本并创建校验和恢复点，失败时恢复 SQLite 与 DuckDB 原库。

## 文档入口

- [产品定位](PRODUCT.md)
- [产品需求](docs/PRD.md)
- [文档总索引](docs/README.md)
- [当前实现与限制](docs/implementation-status.md)
- [产品验收矩阵](docs/product-acceptance-matrix.md)
- [未来开发队列](docs/development-roadmap.md)
- [验收证据索引](artifacts/README.md)

## 当前边界

当前版本是 single-user and local-only，只监听回环地址。查询和后台任务使用白名单能力合同，不接受任意 SQL、网络请求、文件操作或进程执行。新工作区为空；真实写入必须经过预演和一次显式确认。完整能力与限制以 [实现状态](docs/implementation-status.md) 为准。
