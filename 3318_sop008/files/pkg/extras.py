# -*- coding: utf-8 -*-
"""商机撮合 SOP 的附加交付物：步骤 JSON、引荐流程图、会前简报模板、话术卡、表格 xlsx。"""
import json
import os

import engine as E
from kitlib import sop
from kitlib import tables as T
from kitlib import xlsx


def write_extras(docs):
    # 1) 步骤 JSON
    steps = [dict(id=s["id"], name=s["name"], role=s["role"], support=s.get("support") or [],
                  tmode=s["tmode"], sla_value=s["sla_hours"],
                  sla_unit=("工作日" if s["tmode"] == "workdays" else "小时"),
                  sla_desc=s["sla_desc"], outputs=s["outputs"], checklist=s["checklist"])
             for s in E.STEPS]
    p1 = os.path.join(docs, "match_steps.json")
    with open(p1, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"roles": E.ROLES, "base": E.BASE.strftime("%Y-%m-%dT%H:%M"),
                   "contact_policy": "双方均明确同意前，不向任一方透露对方的手机号/微信/邮箱/企业全称",
                   "flow": {"nodes": E.FLOW_NODES, "edges": E.FLOW_EDGES},
                   "steps": steps}, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # 2) 引荐流程图
    L = ["# 引荐对接流程图", "",
         "> 铁律：双方均同意前不透露联系方式。N4 → N5 是唯一允许交换联系方式的入口。", ""]
    L += sop.mermaid_flow(E.FLOW_NODES, E.FLOW_EDGES)
    L += ["", "| 边 | 条件 |", "| --- | --- |"]
    L += ["| %s → %s | %s |" % (a, b, c) for a, b, c in E.FLOW_EDGES]
    L += ["", "## 不透露联系方式的三种落点", "",
          "1. **S03 向供给方说明需求**：只给需求画像，不给需求方身份与联系方式；",
          "2. **S06 会前简报**：分需求方版/供给方版两版，两版都只写对方「画像」；",
          "3. **流程图结构**：N5（交换联系方式）的唯一入边来自 N4（双方均同意）。", ""]
    p2 = T.write_text(os.path.join(docs, "referral_flow.md"), L)

    # 3) 会前简报模板
    L = ["# 会前简报模板（两版，全部虚构）", "",
         "> 使用说明：同一场洽谈必须**两版齐发**，且洽谈前 1 个工作日发出。",
         "> 两版都只写对方「画像」，不写对方身份、企业全称与任何联系方式。", "",
         "## 通用字段", "",
         "| 字段 | 名称 | 内容要求 | 备注 |", "| --- | --- | --- | --- |"]
    L += ["| `%s` | %s | %s | %s |" % (a, b, c, d) for a, b, c, d in E.BRIEF_FIELDS]
    L += ["", "## 需求方版（发给需求方，介绍候选方）", "", "```markdown"]
    L += ["# 会前简报 · 需求方版",
          "- 简报版本：需求方版",
          "- 候选方画像：{候选方画像}（行业 / 规模区间 / 可交付能力标签）",
          "- 匹配点：{匹配理由}（3 条以内，可验证）",
          "- 建议议题：{建议议题}（3~5 条）",
          "- 联系方式口径：**双方均同意前不透露**，本简报不含对方任何联系方式",
          "- 本次负责人：{负责人}"]
    L += ["```", "", "## 供给方版（发给供给方，说明需求）", "", "```markdown"]
    L += ["# 会前简报 · 供给方版",
          "- 简报版本：供给方版",
          "- 需求画像：{需求画像}（行业 / 规模区间 / 核心诉求 / 时间窗）",
          "- 匹配点：{匹配理由}（3 条以内，可验证）",
          "- 建议议题：{建议议题}（3~5 条）",
          "- 联系方式口径：**双方均同意前不透露**，本简报不含对方任何联系方式",
          "- 本次负责人：{负责人}"]
    L += ["```", "", "## 填写检查", ""]
    L += ["- [ ] 两版是否都已发出（缺一版即不合规）",
          "- [ ] 两版是否都不含对方联系方式与企业全称",
          "- [ ] 匹配理由是否 3 条以内且可验证（不能写「感觉合适」）",
          "- [ ] 建议议题是否 3~5 条，且两版不同", ""]
    p3 = T.write_text(os.path.join(docs, "pre_brief_template.md"), L)

    # 4) 话术卡 CSV
    p4 = T.write_csv_rows(
        os.path.join(docs, "match_scripts.csv"),
        ["script_id", "kind", "scene", "channel", "version", "vars", "var_count", "body"],
        [[s["id"], s["kind"], s["scene"], s["channel"], s["version"],
          "、".join(s["vars"]), len(sop.vars_in(s["body"])), s["body"]] for s in E.SCRIPTS])

    # 5) 表格 xlsx
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "步骤表"
    ws.append(["步骤", "名称", "负责岗位", "协作岗位", "时限口径", "时限值", "单位",
               "推算截止", "必填输出数", "检查项数"])
    for s in E.STEPS:
        ws.append([s["id"], s["name"], s["role"], "、".join(s.get("support") or []) or "无",
                   s["tmode"], s["sla_hours"],
                   "工作日" if s["tmode"] == "workdays" else "小时",
                   E.due(E.BASE, s["sla_hours"], s["tmode"]).strftime("%Y-%m-%d %H:%M"),
                   len(s["outputs"]), len(s["checklist"])])
    ws2 = wb.create_sheet("话术卡")
    ws2.append(["编号", "场景", "版本", "渠道", "变量", "正文"])
    for s in E.SCRIPTS:
        ws2.append([s["id"], s["scene"], s["version"], s["channel"],
                    "、".join(s["vars"]), s["body"]])
    ws3 = wb.create_sheet("超时升级")
    ws3.append(["级别", "触发条件", "承接岗位", "时限", "动作"])
    ws3.append(["一级", "S09 到期未完成首次联系", "招商主管", "8 个工作小时",
                "介入并记录超时原因、补救动作与新时限"])
    ws3.append(["二级", "一级升级后再次超时", "运营总监", "再 8 个工作小时",
                "直接接手并复盘流程卡点"])
    ws4 = wb.create_sheet("说明")
    for line in ["时限三种口径不混用：work=工作日 9-18 内消耗、natural=自然小时、workdays=工作日数（含当日为第 1 天）。",
                 "S09 首次联系为 3 个工作日；周三 10:00 起算 → 周五 10:00；周五起算 → 下周二 10:00。",
                 "铁律：双方均明确同意前不透露对方手机号、微信、邮箱、企业全称。",
                 "全部岗位、企业、姓名与时间均为虚构；不含真实客户信息。",
                 "本表由 pkg/extras.py 生成，重跑 python tools/gen.py 可完整复现。"]:
        ws4.append([line])
    p5 = os.path.join(docs, "match_tables.xlsx")
    wb.save(p5)
    xlsx.normalize(p5)
    return [p1, p2, p3, p4, p5]
