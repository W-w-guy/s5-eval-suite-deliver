# -*- coding: utf-8 -*-
"""入会引导 SOP 附加交付物：话术 CSV、资料清单 CSV、检查项表、能力卡问题、xlsx。"""
import os

import engine as E
from kitlib import sop
from kitlib import tables as T
from kitlib import xlsx


def write_extras(docs):
    # 1) 欢迎话术 CSV（含两套字数口径）
    p1 = T.write_csv_rows(
        os.path.join(docs, "welcome_scripts.csv"),
        ["script_id", "channel", "version", "vars", "var_count",
         "chars_vars_as_zero", "raw_length", "limit", "pass_loose", "pass_strict", "body"],
        [[s["id"], s["channel"], s["version"], "、".join(sop.vars_in(s["body"])),
          len(sop.vars_in(s["body"])), sop.char_count(s["body"]), len(s["body"]),
          E.SMS_LIMIT,
          "是" if sop.char_count(s["body"]) <= E.SMS_LIMIT else "否",
          "是" if len(s["body"]) <= E.SMS_LIMIT else "否", s["body"]]
         for s in E.SCRIPTS])

    # 2) 资料清单 CSV
    p2 = T.write_csv_rows(
        os.path.join(docs, "materials.csv"),
        ["material_id", "name", "required", "why", "fallback"],
        [[m["id"], m["name"], "**必填**" if m["required"] else "可选", m["why"], m["fallback"]]
         for m in E.MATERIALS])

    # 3) 检查项表（每步 2~4 条可勾选）
    L = ["# 入会引导各步骤检查项表（可勾选）", "",
         "> 逐条勾选后才可流转下一步；未勾完不得进入下一步。", ""]
    for s in E.STEPS:
        L += ["## %s %s（%s，%d 条）" % (s["id"], s["name"], s["role"], len(s["checklist"])), ""]
        L += ["- [ ] %s" % k for k in s["checklist"]]
        L += [""]
    p3 = T.write_text(os.path.join(docs, "checklists.md"), L)

    # 4) 能力卡引导问题
    L = ["# 能力卡共建：10 个引导问题（全部虚构口径）", "",
         "> 用途：把会员能力梳理成可撮合的结构化字段。按顺序提问，未答项标注「待补」。", "",
         "## 开场话术", "", "```", E.CARD_SCRIPT["body"], "```", "",
         "## 10 个问题", ""]
    grp = ["主营业务", "产业位置", "期望对接", "可提供资源", "近期难题",
           "团队构成", "既有案例", "活动偏好", "跟进节奏", "延伸服务"]
    for i, q in enumerate(E.CARD_QUESTIONS, 1):
        L.append("%d. **%s**：%s" % (i, grp[i - 1], q))
    L += ["", "## 落库字段映射", "",
          "| 问题 | 能力卡字段 | 是否必填 |", "| --- | --- | --- |"]
    for i, q in enumerate(E.CARD_QUESTIONS, 1):
        L.append("| %d | %s | %s |" % (i, grp[i - 1],
                                       "必填" if i <= 5 else "可选"))
    L += ["", "> 前 5 问为能力卡必填字段（主营/产业位置/期望对接/可提供资源/近期难题），",
          "> 后 5 问为可选补充。能力卡须经会员确认后才入库。", ""]
    p4 = T.write_text(os.path.join(docs, "card_questions.md"), L)

    # 5) xlsx
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "欢迎话术"
    ws.append(["编号", "渠道", "变量", "字数(变量计0)", "原始长度", "上限", "两口径均合规", "正文"])
    for s in E.SCRIPTS:
        ws.append([s["id"], s["channel"], "、".join(sop.vars_in(s["body"])),
                   sop.char_count(s["body"]), len(s["body"]), E.SMS_LIMIT,
                   "是" if (sop.char_count(s["body"]) <= E.SMS_LIMIT
                            and len(s["body"]) <= E.SMS_LIMIT) else "否", s["body"]])

    ws2 = wb.create_sheet("入会资料清单")
    ws2.append(["编号", "材料", "必填/可选", "用途", "不提供时的处理"])
    for m in E.MATERIALS:
        ws2.append([m["id"], m["name"], "必填" if m["required"] else "可选",
                    m["why"], m["fallback"]])

    ws3 = wb.create_sheet("检查项表")
    ws3.append(["步骤", "名称", "负责岗位", "检查项"])
    for s in E.STEPS:
        for i, k in enumerate(s["checklist"], 1):
            ws3.append([s["id"], s["name"], s["role"], "%d. %s" % (i, k)])

    ws4 = wb.create_sheet("能力卡问题")
    ws4.append(["序号", "问题", "必填"])
    for i, q in enumerate(E.CARD_QUESTIONS, 1):
        ws4.append([i, q, "必填" if i <= 5 else "可选"])

    ws5 = wb.create_sheet("说明")
    for line in ["话术 3 版（企业微信/短信/邮件），每版 ≤150 字；两套字数口径都必须过线。",
                 "变量计 0 字是最乐观口径；原始长度是最严格口径，两者同时合规才算通过。",
                 "入会资料：4 项必填（必给替代方案）+ 4 项可选（不影响入会）。",
                 "门禁登记只采集姓名/所属企业/人数，证件号一律不收。",
                 "全部企业名称、人名、编号与条款均为虚构。",
                 "本表由 pkg/extras.py 生成，重跑 python tools/gen.py 可完整复现。"]:
        ws5.append([line])
    p5 = os.path.join(docs, "join_tables.xlsx")
    wb.save(p5)
    xlsx.normalize(p5)
    return [p1, p2, p3, p4, p5]
