# AIBI-C

本项目是一个本地优先的 AI BI 工作台。它面向本地表格、业务导出和轻量数据建模场景：导入或扫描文件，生成证据摘要，查看看板，向全局 Agent 提问，并在确认前审阅所有写入草案。

核心原则是证据先行、写入受控、运行本地化。代码、文档和运行时数据都以本仓库为边界。

## Run

```powershell
npm ci
python -m pip install -r requirements.txt
npm run dev
```

打开 `http://127.0.0.1:8686`。

`npm run dev` 会启动本地 API `8787` 和前端 `8686`。API 会读取仓库根目录的 `.env`，可从 `.env.example` 复制后填写本机路径和密钥；不要提交 `.env`。需要单独调试时使用：

```powershell
npm run api
npm run dev:ui
```

本地交付验收建议使用后台启停脚本：

```powershell
npm run local:start
npm run local:health
npm run local:stop
```

`local:stop` 只会停止命令行中包含当前仓库路径的 `8686`/`8787` 监听进程，避免误关其他项目。

## Verify

```powershell
npm run preflight
npm run verify:ci
npm run build
npm run verify
npm run verify:ui
npm run verify:ui-empty
npm run verify:ui-import
npm run verify:bi-cli-contract
npm run verify:ai-reliability
npm run verify:production
npm run verify:security-runtime
npm run verify:backup
npm run verify:erp-units
python tools/bi_cli.py --json status
python tools/bi_cli.py --json cli-contract
python tools/bi_cli.py --json business-dashboard --template erp-units --op draft --limit 24
```

`npm run preflight` 是本地交付前的单入口：先跑核心构建和契约验证，再启动本地服务、检查健康状态，并执行完整 UI 闭环。只想快速检查核心契约时使用 `npm run preflight -- --skip-ui`；希望验收后自动停服务时追加 `--stop-after`。

GitHub Actions 执行 `npm run verify:ci`，覆盖安装、构建、核心契约、AI 单图可靠性、备份恢复和生产边界验证；随后启动仅回环监听的本地服务，检查安全响应与浏览器主流程。

`npm run verify:ui` 需要本地 `8686` 前端和 `8787` API 已运行。它包含已有真实数据只读流程、三种 PC 比例视觉检查、空工作区检查，以及一个临时工作区真实导入闭环。真实导入优先读取 `C:\Users\Administrator\Documents\财务报表\真实数据` 并走文件夹合并导入，可用 `AIBI_REAL_IMPORT_FOLDER` 覆盖；目录不存在时回退到 `AIBI_REAL_IMPORT_FILE` 指定的单文件。脚本会恢复原工作区并删除临时工作区。

`tools/bi_cli.py` 是本地 BI 后端入口。它负责工作区元数据、导入预检、语义字段、公式、关系、查询、看板、Agent 草案和证据回执。`query` 优先使用 DuckDB 分析运行时，必要时回退到 SQLite。

## Docs

- `PRODUCT.md`: 产品定义、边界和核心运行契约。
- `docs/README.md`: 当前文档地图和维护规则。
- `docs/PRD.md`: 产品需求和用户工作流。
- `docs/implementation-status.md`: 当前代码边界和验证口径。
- `docs/bi-cli-contract.md`: 公共 CLI 命令索引。
- `docs/erp-dashboard-unit-library.md`: ERP 单元库、公开参考和选择规则。

## Data Policy

运行数据保存在本地并被 git 忽略。用户数据通过界面或 CLI 明确导入；不要把真实数据库、业务导出、日志、凭据或个人工作文件提交进仓库。

备份前先停止本项目服务，避免复制写入中的数据库：

```powershell
npm run local:stop
npm run backup:local
```

恢复默认只展示影响，不写入。确认备份目录和校验结果后再执行：

```powershell
npm run restore:local -- --from <backup-directory>
npm run restore:local -- --from <backup-directory> --confirm
```

备份只包含本地 SQLite 和 DuckDB 数据库，清单记录文件大小与 SHA-256；不会复制 `.env`、源文件或凭据。可用 `AIBI_BACKUP_ROOT` 指定备份根目录。

## Deployment Notes

正式部署前只需要提交代码、文档和配置模板。不要提交 `data/local`、真实导出文件、`.env`、浏览器截图或验证输出。服务默认只监听 `127.0.0.1`，不会接受 `0.0.0.0`；需要跨进程前端来源时，只能通过 `AIBI_CORS_ORIGIN` 配置一个明确来源。新环境启动后先执行 `npm ci` 和 `python -m pip install -r requirements.txt`，再运行 `npm run preflight` 做核心与 UI 验收。
