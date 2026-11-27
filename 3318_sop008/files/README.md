# 商机撮合 SOP：引荐、陪谈与对接话术

本包为「商机撮合 SOP：引荐、陪谈与对接话术」交付物：10 个引荐对接步骤（每步含负责/协作岗位、时限口径与推算截止、必填输出、2~4 条检查项）+ 步骤 JSON + 引荐对接流程图（Mermaid 9 节点，每条边带条件）+ 话术模板 6 条（3 类各 2 版，均带变量占位）+ 会前简报模板（需求方版/供给方版）+ 超时升级表 + 责任矩阵。全部内容为**虚构**。

## 一条命令复跑

```
python tools/gen.py             # 重新生成 docs/ 下全部交付物
python tools/verify.py          # 逐条断言 AC（23 条），任何一条失败即非零退出
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
| `docs/match_sop.md` | SOP 主文档：铁律、三种时限口径、流程图、简报模板、陪谈判断标准、升级表、责任矩阵、访谈提纲、10 个步骤小节 |
| `docs/match_steps.json` | 步骤 JSON（机器可读：岗位/协作/口径/时限/必填输出/检查项 + 联系方式口径常量） |
| `docs/referral_flow.md` | 引荐对接流程图（Mermaid 9 节点，每条边标注条件） |
| `docs/pre_brief_template.md` | 会前简报模板（需求方版/供给方版 + 填写检查） |
| `docs/match_scripts.csv` | 话术模板 6 条（3 类×2 版，含变量占位与变量计数） |
| `docs/match_tables.xlsx` | 步骤表 / 话术卡 / 超时升级 / 说明 共 4 页签 |
| `docs/match_expected.csv` | CSV 期望值（步骤表 10 行 12 列，含口径与推算截止） |
| `docs/coverage.csv` | 8 类情形覆盖对照表 |
| `tools/verify.py` | AC 断言器（23 条，非零退出可接 CI） |
| `tools/mutate.py` | 变异测试（7 处） |
| `tools/pii_scan.py` | PII 扫描（手机 / 邮箱 / 身份证 / 银行卡） |
| `report/` | 本次双平台实跑日志（打包时快照，不参与校验和） |

## 口径说明

- 铁律：双方均明确同意前，不向任一方透露对方的手机号、微信、邮箱与企业全称。
- 需求方只看到候选方的「画像 + 匹配理由」；供给方只看到需求方的「需求画像」。
- 交换联系方式（流程 N5）的唯一入口是 N4「双方均同意」，图中无其他入边。
- 首次联系时限：3 个工作日，**含当日为第 1 个工作日**（workdays 口径）。
- 会后 24 小时内记录纪要：按自然时间（natural 口径），不是工作时段。
- 其余步骤按工作时段（work 口径）：只在工作日 09:00–18:00 内消耗，跨夜与周末顺延。
- 首次联系超时：一级由招商主管在 8 个工作小时内介入；再次超时升运营总监。
- 会前简报必须两版齐发（需求方版/供给方版），洽谈前 1 个工作日发出，两版都不含对方联系方式。
- 陪谈或引荐后离场按四条判断标准执行，不一刀切；离场后仍须按时完成纪要。
- 时间基准为 naive datetime（不含时区），避免依赖系统 tzdata。
