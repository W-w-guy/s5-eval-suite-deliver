# -*- coding: utf-8 -*-
"""客服转人工 SOP 附加交付物：规则表 xlsx、流程图、知识缺口字段表。"""
import os

import engine as E
from kitlib import sop
from kitlib import tables as T
from kitlib import xlsx


def write_extras(docs):
    # 1) 处理流程图
    L = ["# 客服转人工处理流程图", "",
         "> 每条边都标注触发条件；C1 有自环（未命中则继续由管家应答），C9→C11 是无需回写的旁路。", ""]
    L += sop.mermaid_flow(E.FLOW_NODES, E.FLOW_EDGES)
    L += ["", "| 边 | 条件 |", "| --- | --- |"]
    L += ["| %s → %s | %s |" % (a, b, c) for a, b, c in E.FLOW_EDGES]
    L += ["", "## 两条升级路径", "",
          "1. **一级**：C6（超时未响应）→ C7（值班主管）；",
          "2. **二级**：C7 再审仍未响应或已二次超时 → C8（客服负责人）。", "",
          "> 结构上 C7 的唯一入边是 C6、C8 的唯一入边是 C7 —— 不存在「未超时就直接升级」或「跳过一级」的路径。", ""]
    p1 = T.write_text(os.path.join(docs, "transfer_flow.md"), L)

    # 2) 知识缺口字段表
    L = ["# 知识缺口回写字段与规则（必做）", "",
         "> 转接不能只解决问题就结束——**管家答不上来的原因必须回写**，否则下次还会转。", "",
         "## 字段", "", "| 字段 | 名称 | 要求 |", "| --- | --- | --- |"]
    L += ["| `%s` | %s | %s |" % (a, b, c) for a, b, c in E.BACKWRITE_FIELDS]
    L += ["", "## 规则", "",
          "1. 由**接手岗位**在处理完成后 **1 个工作日内**提交，不得转交客服代填；",
          "2. `fail_reason` 为枚举值：知识库缺失 / 条目过时 / 问题歧义 / 超出范围；",
          "3. 回写内容一律**脱敏**：不含会员姓名、手机号、合同金额；",
          "4. 哪些规则必须回写：%s；"
          % "、".join("%s（%s）" % (r["id"], r["trigger"][:14]) for r in E.RULES if r["backwrite"]),
          "5. 知识库负责人每周汇总一次，形成条目补充清单。", "",
          "## 示例（虚构）", "", "```json",
          '{',
          '  "gap_id": "KG-20260506-01",',
          '  "question": "会员询问共享工位能否开具增值税专用发票",',
          '  "attempted": ["说明可开票（置信度低）", "引用会员协议第 7 条（不适用）"],',
          '  "fail_reason": "知识库缺失",',
          '  "suggest": "补充「会员开票类型与申请入口」条目，明确专票/普票适用范围",',
          '  "rule_id": "R01",',
          '  "owner": "管家组客服"',
          '}', "```", ""]
    p2 = T.write_text(os.path.join(docs, "knowledge_gap.md"), L)

    # 3) 规则表 CSV
    p3 = T.write_csv_rows(
        os.path.join(docs, "transfer_rules.csv"),
        ["rule_id", "trigger", "role", "tier", "sla_minutes", "backwrite", "note"],
        [[r["id"], r["trigger"], r["role"], r["tier"],
          int(round(E.tier_hours(r["tier"]) * 60)),
          "是" if r["backwrite"] else "否", r["note"]] for r in E.RULES])

    # 4) xlsx
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "转接规则表"
    ws.append(["规则编号", "触发条件", "接手岗位", "档位", "档位时长（分钟）", "回写知识缺口", "备注"])
    for r in E.RULES:
        ws.append([r["id"], r["trigger"], r["role"], r["tier"],
                   int(round(E.tier_hours(r["tier"]) * 60)),
                   "是" if r["backwrite"] else "否", r["note"]])

    ws2 = wb.create_sheet("响应时限表")
    ws2.append(["档位", "时长（分钟）", "工作时间提出（工作日 9:00–18:00）", "非工作时间提出"])
    ws2.append(["普通转接", 30, "就地起算（如周三 10:00 → 10:30 前）",
                "顺延至下一工作日 09:00 起算（如周三 19:00 → 次日 09:30 前）"])
    ws2.append(["紧急转接", 15, "就地起算（如周三 11:00 → 11:15 前）",
                "顺延至下一工作日 09:00 起算（如周三 19:00 → 次日 09:15 前）"])
    ws2.append(["", "", "非工作时间 = 工作日 18:00–次日 09:00、周六周日、节假日", ""])
    ws2.append(["", "", "实现口径：时长只在工作日 09:00–18:00 内消耗，非工作时间自动顺延", ""])

    ws3 = wb.create_sheet("升级与待办")
    ws3.append(["环节", "规则"])
    for row in [["待办生成", "每次转接生成一条待办：会话 ID、触发规则编号、接手岗位、起算时刻、响应截止、档位"],
                ["一级升级", "到达响应截止仍未响应 → 升级到值班主管，同时通知接手人"],
                ["二级升级", "一级升级后再超时一个档位时长 → 升级到客服负责人"],
                ["关闭条件", "人工已响应且问题解决；或会员明确放弃"],
                ["不计超时", "已响应但问题未解决（转入处理中，不再算响应超时）"]]:
        ws3.append(row)

    ws4 = wb.create_sheet("知识缺口字段")
    ws4.append(["字段", "名称", "要求"])
    for a, b, c in E.BACKWRITE_FIELDS:
        ws4.append([a, b, c])

    ws5 = wb.create_sheet("说明")
    for line in ["双时段：同一时长两种起算点——工作时间就地起算，非工作时间顺延到下一工作日 09:00。",
                 "紧急档（15 分钟）用于涉及他人信息、涉及合同承诺两类。",
                 "处理完成后必须回写知识缺口（哪些规则必回写见「转接规则表」页签）。",
                 "全部岗位、时间与条款均为虚构；不含真实客户信息。",
                 "本表由 pkg/extras.py 生成，重跑 python tools/gen.py 可完整复现。"]:
        ws5.append([line])
    p4 = os.path.join(docs, "transfer_tables.xlsx")
    wb.save(p4)
    xlsx.normalize(p4)
    return [p1, p2, p3, p4]
