# 【S1-SOP-016】会员空间平台 · 客服转人工 SOP：转接规则与响应时限

本目录为工单 3322 的交付件。所有岗位、时段、时限与条款**全部虚构**，不含会员姓名、手机号、真实企业信息或客户名称。

## 交付物在哪

| 路径 | 内容 |
| --- | --- |
| `files/docs/cs_transfer_sop.md` | SOP 主文档：转接规则表、双时段响应时限表、处理流程图、待办与两级升级、知识缺口回写、责任矩阵、8 个响应时限判定示例 |
| `files/docs/transfer_rules.csv` | 转接规则表（6 条，含触发条件 / 接手岗位 / 档位 / 时长 / 是否回写） |
| `files/docs/transfer_tables.xlsx` | 5 页签：转接规则表 / 响应时限表 / 升级与待办 / 知识缺口字段 / 说明 |
| `files/docs/transfer_flow.md` | 处理流程图（Mermaid，11 节点 12 条带条件边，含两级升级） |
| `files/docs/knowledge_gap.md` | 知识缺口回写 7 字段 + 5 条规则 + 虚构示例 |
| `files/docs/cs_expected.csv` | 8 个示例 14 列期望值（含时段与响应截止），可直接喂断言 |
| `files/docs/coverage.csv` | 8 类情形覆盖对照表 |
| `files/ACCEPTANCE.md` | 三条 AC 的四元组：原文 / 判定方式 / 复核命令 / 实际输出原文 |
| `files/DATA_PROVENANCE.md` | 数据来源：生成脚本 sha256、无随机、重跑命令、PII 扫描数 |
| `cs3322.zip` | 上述全部内容 + 引擎与自检工具的压缩包 |
| `verify_logs/` | Windows 与 Ubuntu 两侧全新目录实跑日志 + 跨平台一致性核对 |

## 一条命令复跑（解压 `cs3322.zip` 后在包根目录执行）

```
python tools/gen.py             # 重新生成 docs/ 下全部交付物
python tools/verify.py          # 23 条 AC 断言，任一失败即非零退出
python -m pytest tests -q       # 用例逐条比对 CSV 期望值（9 个）
python tools/mutate.py          # 变异测试：改坏引擎 7 处，每处都必须让 verify 变红
python tools/pii_scan.py        # PII 扫描（手机/邮箱/身份证/银行卡）
```

## 实测结果

```
Windows 11 / Python 3.11.7 : verify 23/23 PASS · pytest 9 passed · mutate 7/7 被抓到 · pii scanned=31 hits=0
Ubuntu 24.04 / Python 3.12.3: verify 23/23 PASS · pytest 9 passed · mutate 7/7 被抓到 · pii scanned=31 hits=0
两侧 docs/ 七个产物 sha256 逐一致；gen 重跑幂等
```

## 核心口径（与工单一致）

- 转接触发 6 种：管家答不上来 / 会员主动要求 / 价格谈判 / 合同承诺 / 他人信息 / 投诉升级，每种写明接手岗位
- 响应时限双时段：**普通档 30 分钟、紧急档 15 分钟**，时长只在工作日 9:00–18:00 内消耗；非工作时间起算自动顺延到下一工作日 09:00
- 待办生成：会话 ID / 规则编号 / 接手岗位 / 截止时间四字段
- 超时两级升级：超时 → 值班主管（C7）→ 客服负责人（C8），不允许跳级
- 处理完成后回写知识缺口：R01/R05/R06 三条必回写，接手岗位在 1 个工作日内完成，内容须脱敏
