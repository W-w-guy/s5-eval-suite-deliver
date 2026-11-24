# 【S1-RULE-004】会员空间平台 · 折扣审批路由表与 12 个越权审批场景

本目录为工单 3302 的交付件。所有数据**全部虚构**，不含任何真实企业、人员、联系方式或客户名称。

## 交付物在哪

| 路径 | 内容 |
| --- | --- |
| `files/docs/discount_routing.xlsx` | 审批路由表 7 列 6 条 + 角色上限 + 边界判定说明 + 说明，共 4 页签 |
| `files/docs/discount_routing.md` | 12 个场景示例，每个含发起人、报价摘要、逐步判定、期望审批链与结果 |
| `files/docs/discount_expected.csv` | 12 行 18 列期望值（输入列 + 期望输出列），供集成方直接喂断言 |
| `files/docs/coverage.csv` | 8 类情形覆盖对照表（情形 → 示例编号） |
| `files/docs/boundary_rules.csv` | 11 条边界判定说明（左开右闭、超时、改价口径） |
| `files/ACCEPTANCE.md` | 四条 AC 的四元组：原文 / 判定方式 / 复核命令 / 实际输出原文 |
| `files/DATA_PROVENANCE.md` | 数据来源：生成脚本 sha256、无随机、重跑命令、PII 扫描数 |
| `dis3302.zip` | 上述全部内容 + 引擎与自检工具的压缩包（同一份，可独立解压复跑） |
| `verify_logs/` | Windows 与 Ubuntu 两侧全新目录实跑日志 + 跨平台一致性核对 |

## 一条命令复跑（解压 `dis3302.zip` 后在包根目录执行）

```
python tools/gen.py             # 重新生成 docs/ 下全部交付物
python tools/verify.py          # 20 条 AC 断言，任一失败即非零退出
python -m pytest tests -q       # 用例逐条比对 CSV 期望值（13 个）
python tools/mutate.py          # 变异测试：改坏引擎 7 处，每处都必须让 verify 变红
python tools/pii_scan.py        # PII 扫描（手机/邮箱/身份证/银行卡）
```

## 实测结果

```
Windows 11 / Python 3.11.7 : verify 20/20 PASS · pytest 13 passed · mutate 7/7 被抓到 · pii scanned=29 hits=0
Ubuntu 24.04 / Python 3.12.3: verify 20/20 PASS · pytest 13 passed · mutate 7/7 被抓到 · pii scanned=29 hits=0
两侧 docs/ 五个产物 sha256 逐一致；gen 重跑幂等
```

## 核心口径（与工单一致）

- 角色折扣上限：招商业务员 5% / 招商主管 10% / 运营总监 15% / 总经理 20%（虚构值）
- 超出 = 折扣率 − 发起人上限；**超出 = 0（恰好等于上限）不需审批**
- 区间左开右闭：`0 < 超出 ≤ 5` → R01 招商主管；`5 < 超出 ≤ 10` → R02 运营总监；`超出 > 10` → R03 总经理
- 特殊条款：免押金 → R04 运营总监；延期付款 → R05 运营总监；免租期超过 30 天 → R06 总经理
- 同时命中折扣与特殊条款：取层级更高的一条，不叠加串行
- 首节点与发起人同角色：跳过该节点，从下一级起
- 节点超时：提醒并自动上升一级，**任何情况下不允许自动通过**
- 审批中途改价：原审批作废，按新口径重走
