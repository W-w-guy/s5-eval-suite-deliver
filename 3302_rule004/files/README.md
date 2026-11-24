# 折扣审批路由表与 12 个越权审批场景

本包为「折扣审批路由表与越权审批场景」交付物：7 列路由表（Excel）+ 12 个虚构审批场景的逐步判定与期望审批链 + 情形覆盖对照表与边界判定说明。全部数据为**虚构**。

## 一条命令复跑

```
python tools/gen.py             # 重新生成 docs/ 下全部交付物
python tools/verify.py          # 逐条断言 AC（20 条），任何一条失败即非零退出
python -m pytest tests -q       # 用例逐条比对 CSV 期望值
python tools/mutate.py          # 变异测试：改坏引擎 7 处，每处都必须让 verify 变红
python tools/build_docs.py      # 由实跑结果重生成 README / DATA_PROVENANCE / ACCEPTANCE
python tools/make_zip.py        # 打包 + SHA256SUMS
```

## 目录

| 路径 | 内容 |
| --- | --- |
| `pkg/engine.py` | 业务规则引擎 + 示例定义 + 情形编号 |
| `pkg/render.py` | 逐例 Markdown 渲染 |
| `docs/discount_routing.xlsx` | 审批路由表（7 列 6 条）+ 角色上限 + 边界判定说明 + 说明，共 4 页签 |
| `docs/discount_routing.md` | 12 个场景示例（发起人与报价摘要、逐步判定、边界说明、期望审批链） |
| `docs/discount_expected.csv` | CSV 期望值（输入列 + 期望输出列，12 行 18 列） |
| `docs/boundary_rules.csv` | 边界判定说明（11 条，含左开右闭与超时/改价口径） |
| `docs/coverage.csv` | 8 类情形覆盖对照表 |
| `tools/verify.py` | AC 断言器（20 条，非零退出可接 CI） |
| `tools/mutate.py` | 变异测试（7 处） |
| `tools/pii_scan.py` | PII 扫描（手机 / 邮箱 / 身份证 / 银行卡） |
| `report/` | 本次双平台实跑日志（打包时快照，不参与校验和） |

## 口径说明

- 角色折扣上限：招商业务员 5.0%；招商主管 10.0%；运营总监 15.0%；总经理 20.0%（虚构值）。
- 超出 = 折扣率 − 发起人上限；超出 = 0（恰好等于上限）不需审批。
- 折扣区间左开右闭：0<超出≤5 → R01 招商主管；5<超出≤10 → R02 运营总监；超出>10 → R03 总经理。
- 特殊条款：免押金 → R04 运营总监；延期付款 → R05 运营总监；免租期超过 30 天 → R06 总经理。
- 同时命中折扣与特殊条款：取层级更高的一条，不叠加串行。
- 审批首节点与发起人同角色：跳过该节点，从下一节点起。
- 节点超时：提醒并自动上升一级；任何情况下不允许自动通过。
- 审批中途修改报价：原审批作废，按新口径重新审批。
- 未命中任一条件 → 不需审批，直接生效。
- 百分点以「百分点×10」的整数参与运算，不使用浮点。
