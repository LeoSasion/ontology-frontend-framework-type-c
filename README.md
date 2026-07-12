# AIBI-C

本仓库包含 AIBI-C 本地工作台的代码、文档与验证契约。产品定位见 `PRODUCT.md`。

## Run

```powershell
npm ci
python -m pip install -r requirements.txt
npm run dev
```

打开 `http://127.0.0.1:8686`。`npm run dev` 同时启动本地 API `8787` 和前端 `8686`。环境变量写入仓库根目录 `.env`，可参考 `.env.example`；不要提交 `.env`。

单独调试或管理后台服务：

```powershell
npm run api
npm run dev:ui
npm run local:start
npm run local:health
npm run local:stop
```

## Verify

```powershell
npm run verify
npm run preflight -- --skip-ui
npm run preflight
npm run verify:ci
```

- `npm run verify`：核心、CLI、AI 单图与可信分析契约。
- `npm run preflight -- --skip-ui`：构建与非 UI 交付检查。
- `npm run preflight`：本地交付前总入口，包含完整 UI 闭环；追加 `--stop-after` 可在验收后停止服务。
- `npm run verify:ci`：Windows CI 使用的构建、生产、安全与浏览器检查。

分场景命令只在 `docs/implementation-status.md` 维护。UI 真实导入通过 `AIBI_REAL_IMPORT_FOLDER` 或 `AIBI_REAL_IMPORT_FILE` 指定外部数据；脚本使用临时工作区并在结束后恢复原工作区。

## Data And Recovery

运行数据保存在本地并被 git 忽略。不要提交真实数据库、业务导出、日志、凭据、截图或验证输出。

```powershell
npm run local:stop
npm run backup:local
npm run restore:local -- --from <backup-directory>
npm run restore:local -- --from <backup-directory> --confirm
```

恢复默认只预演影响，`--confirm` 才写入。备份仅包含 SQLite 与 DuckDB 数据库及 SHA-256 清单，不包含 `.env`、源文件或凭据。

## Documentation

- `PRODUCT.md`：定位、用户、能力分层、边界与非目标。
- `docs/PRD.md`：当前可执行需求与发布条件。
- `docs/product-ux-standard.md`：页面职责、渐进交互与确认标准。
- `docs/product-acceptance-matrix.md`：稳定产品行为的验收矩阵。
- `docs/implementation-status.md`：当前能力、限制、架构与验证入口。
- `docs/agent-knowledge-packs.md`：模型无关业务知识、查询证据和扩展约束。
- `docs/development-roadmap.md`：唯一未来开发队列。
- `docs/README.md`：完整文档地图。

## Runtime Boundary

当前版本是 single-user and local-only。服务只允许回环监听；跨进程前端来源只能通过 `AIBI_CORS_ORIGIN` 配置一个明确来源。公共后端命令入口是 `tools/bi_cli.py`，查询优先使用 DuckDB，必要时回退 SQLite。
