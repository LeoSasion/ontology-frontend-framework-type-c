# Documentation Map

本目录只保留当前项目文档。

## Current Documents

| File | Owns |
| --- | --- |
| `../README.md` | 安装、运行、验证、数据策略 |
| `../PRODUCT.md` | 产品定义、产品边界、核心运行契约 |
| `PRD.md` | 用户问题、目标工作流、功能需求、验收口径 |
| `product-ux-standard.md` | 交互标准、信息架构、文案标准、确认策略 |
| `product-acceptance-matrix.md` | 新手首次成功、无样例边界、确认/删除/证据验收矩阵 |
| `development-roadmap.md` | 当前剩余开发顺序、完成定义和连续开发节奏 |
| `implementation-status.md` | 当前代码边界、模块归属、验证命令 |
| `bi-cli-contract.md` | 公共 CLI 命令索引、突变模式、证据输出 |
| `erp-dashboard-unit-library.md` | ERP 公开参考、业务单元选择规则、验证方式 |

## Maintenance Rules

- 文档只描述当前项目、当前命令和当前运行边界。
- 产品定位放在 `PRODUCT.md`，需求放在 `PRD.md`，不要在每个文件重复。
- 用户体验、页面层级、文案和确认策略放在 `product-ux-standard.md`，不要散落到实现状态文档。
- 首次成功和生产空状态验收放在 `product-acceptance-matrix.md`，不要用页面样例替代验收标准。
- 当前实现边界放在 `implementation-status.md`，作为代码结构索引而不是历史日志。
- CLI 命令变化后更新 `bi-cli-contract.md` 的公共命令索引。
- ERP 公开参考、字段别名和单元选择规则只放在 `erp-dashboard-unit-library.md`。
- 验证命令优先记录稳定入口：`npm run preflight` 是本地交付前总入口；`npm run build`、`npm run verify`、`npm run verify:ui`、`npm run verify:ui-empty`、`npm run verify:ui-import`、`npm run verify:bi-cli-contract`、`npm run verify:erp-units` 用于分解排查。
- 产品文档不提供内置数据入口；验证材料只服务自动化测试，不作为用户默认路径。
