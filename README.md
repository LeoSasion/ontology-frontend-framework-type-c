# AIBI-C

AIBI-C 是本地优先的证据型 AI BI 工作台：确定性运行时负责数据、计算、权限和回执，可选模型只负责解释与必要澄清。

## 启动

```powershell
npm ci
python -m pip install -r requirements.txt
npm run dev
```

| 服务 | 地址 |
| --- | --- |
| UI | `http://127.0.0.1:8686` |
| API | `http://127.0.0.1:8787` |

环境变量使用根目录 `.env`，模板见 [.env.example](.env.example)；不得提交密钥。

按需单独运行：

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
npm run preflight
```

`preflight` 是本地交付总入口，包含构建、核心回归和真实浏览器闭环；开发时可从 [实现状态](docs/implementation-status.md) 选择与改动面对应的专项验证。

## 本地数据与恢复

运行数据位于 Git 忽略目录，备份不包含 `.env`、源文件或凭据。恢复和迁移默认只预演，`--confirm` 才写入。

```powershell
npm run local:stop
npm run backup:local
npm run restore:local -- --from <backup-directory>
npm run restore:local -- --from <backup-directory> --confirm
npm run migrate:local
npm run migrate:local -- --confirm
```

## 文档

- [产品定位](PRODUCT.md)
- [文档总索引](docs/README.md)
- [验收证据索引](artifacts/README.md)

当前版本为 single-user and local-only，只监听回环地址。新工作区为空；查询和后台任务仅使用白名单能力，真实写入必须经过预演和一次显式确认。
