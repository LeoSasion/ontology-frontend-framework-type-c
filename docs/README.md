# Documentation Map

每类信息只在一个文件维护。

| File | Single responsibility |
| --- | --- |
| `../PRODUCT.md` | 产品定位、用户、能力分层、边界、成功标准 |
| `PRD.md` | 当前版本的用户结果、功能需求、发布条件 |
| `product-ux-standard.md` | 页面职责、渐进展示、路由、文案、确认与删除 |
| `product-acceptance-matrix.md` | 用户可观察的稳定验收行为 |
| `implementation-status.md` | 当前实现、限制、架构归属与分项验证入口 |
| `development-roadmap.md` | 唯一未来队列、顺序与退出条件 |
| `bi-cli-contract.md` | 公共 CLI 命令、突变模式与输出合同 |
| `erp-dashboard-unit-library.md` | ERP 单元选择规则与公开参考 |
| `reference-project-gap-analysis.md` | 外部项目取舍形成的架构决策记录 |
| `agent-knowledge-packs.md` | 模型无关业务知识包、证据合同与验证方式 |
| `../README.md` | 安装、运行、验证、数据与恢复 |

## Maintenance Rules

- 产品事实必须能由当前代码、运行边界或验收场景支持。
- 当前能力不进入路线图；研究结论不冒充当前功能；实现细节不进入产品定位。
- UX 规则只描述可观察约束，不手抄组件结构。
- 容易漂移的文件数、测试数和字段数由脚本回执负责。
- `npm run preflight` 是本地交付前总入口；其他命令只在 README 或 implementation status 维护。
- 验证数据可位于 `validation-inputs` 或仓库外部，但生产 UI 不提供样例入口。
