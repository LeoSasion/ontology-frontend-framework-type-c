# ERP 看板单元库

## 定位

ERP 路径是证据驱动的可选单元库，不是固定模板。系统根据当前表字段选择指标、图表、表格、筛选器和证据单元；缺少必需字段的单元必须省略并解释。

该能力位于整套行业看板 Beta 路径，不与默认可信单图入口竞争。

## 唯一事实源

`tools/erp_dashboard_unit_library.py` 唯一维护：

- 公开参考标识、标题、链接和信号；
- 字段别名组和可选单元定义；
- 必需/可选角色、评分和省略规则；
- 实时单元、类别、别名和参考数量。

Markdown 不复制完整目录或数量。查看实时摘要：

```powershell
python tools/bi_cli.py --json erp-unit-library --summary
```

外部参考只证明设计方法，不表示已经接入对应厂商或 API。

## 选择合同

1. 读取当前工作区表注册和字段语义。
2. 用别名组和业务信号匹配角色。
3. 删除缺少必需指标或维度的单元。
4. 按必需字段、可选字段和领域锚点评分。
5. 在请求上限内选择证据最充分的单元。
6. 返回命中、类别覆盖、省略原因和下一步所需字段。
7. 在每个组件 payload 保留单元 key、匹配字段、来源标识和证据引用。

因此，销售导出不会获得制造卡片，采购/库存导出也不会被强制套入订单销售看板。

## 写入与晋级边界

- `business-dashboard --template erp-units` 只生成预览或待确认草案。
- 缺字段单元不落盘，不渲染为零值或确定结论。
- Agent 与 CLI 复用同一选择说明和证据。
- 是否从 Beta 晋级由 [未来开发队列](development-roadmap.md) 的产品门槛决定，目录规模不是晋级证据。

## 验证

```powershell
python tools/bi_cli.py --json erp-unit-library --select --summary --table <table-key> --limit 24
python tools/bi_cli.py --json business-dashboard --template erp-units --op draft --limit 24
npm run verify:erp-units
npm run verify:multi-domain-beta
```
