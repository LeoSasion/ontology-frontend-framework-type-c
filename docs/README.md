# Documentation Map

本目录只保留当前项目文档。

## Current Documents

| File | Owns |
| --- | --- |
| `../README.md` | 安装、运行、验证、数据策略 |
| `../PRODUCT.md` | 唯一产品定位、目标用户、价值主张、产品边界和非目标 |
| `PRD.md` | 当前用户故事、主流程、功能需求和发布条件 |
| `product-ux-standard.md` | 交互标准、信息架构、文案标准、确认策略 |
| `product-acceptance-matrix.md` | 新手首次成功、无样例边界、确认/删除/证据验收矩阵 |
| `development-roadmap.md` | 只记录尚未完成的开发顺序、产品指标和能力晋级条件 |
| `implementation-status.md` | 当前交付边界、能力状态、架构归属、限制和验证入口 |
| `bi-cli-contract.md` | 公共 CLI 命令索引、突变模式、证据输出 |
| `erp-dashboard-unit-library.md` | ERP 公开参考、业务单元选择规则、验证方式 |

## Maintenance Rules

- 文档只描述当前项目、当前命令和当前运行边界。
- 产品定位只放在 `PRODUCT.md`；PRD 引用定位，只维护可执行需求。
- 用户体验、页面层级、文案和确认策略放在 `product-ux-standard.md`，不要散落到实现状态文档。
- 首次成功和生产空状态验收放在 `product-acceptance-matrix.md`，不要用页面样例替代验收标准。
- 当前实现边界放在 `implementation-status.md`，只保留稳定模块级归属，不手抄组件清单。
- `development-roadmap.md` 只保留未来工作；已经完成的事项移出活动队列，不长期保留“全部完成”的状态表。
- CLI 命令变化后更新 `bi-cli-contract.md` 的公共命令索引。
- ERP 公开参考、字段别名和单元选择规则只放在 `erp-dashboard-unit-library.md`。
- 验证命令优先记录稳定入口：`npm run preflight` 是本地交付前总入口；分解命令只放在 README 或 implementation status，不在产品定位和路线图重复。
- 容易漂移的命令数、组件数、字段别名数和测试总数由脚本输出，不手写为长期产品事实。
- 产品文档不提供内置数据入口；验证材料只服务自动化测试，不作为用户默认路径。
