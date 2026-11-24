# -*- coding: utf-8 -*-
"""路由表 Excel（7 列）+ 边界判定说明 CSV。"""
import os

import engine as E
from kitlib import tables as T
from kitlib import xlsx


def write_extras(docs):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "路由表"
    ws.append(["路由编号", "触发条件", "审批节点序列", "每节点时限（小时）",
               "超时动作", "可否加签", "可否转交"])
    for r in E.ROUTES:
        ws.append([r["id"], r["cond"], " → ".join(r["chain"]),
                   "；".join("%s %d" % (n, E.NODE_HOURS[n]) for n in r["chain"]),
                   "提醒 + 自动上升一级（不允许自动通过）",
                   "可（加签仅限同级或更高层级）", "可（转交后时限不重置）"])

    ws2 = wb.create_sheet("角色上限")
    ws2.append(["角色", "折扣上限（%）"])
    for k, v in E.CAP.items():
        ws2.append([k, v / 10.0])

    ws3 = wb.create_sheet("边界判定说明")
    rows = [["条件", "判定", "说明"],
            ["超出 = 0（折扣恰好等于角色上限）", "不需审批", "等于上限不触发审批"],
            ["超出 < 0（未超上限）", "不需审批", "直接生效"],
            ["0 < 超出 ≤ 5", "R01 招商主管", "左开右闭：恰好 5 仍在本档"],
            ["5 < 超出 ≤ 10", "R02 运营总监", "左开右闭：恰好 10 仍在本档"],
            ["超出 > 10", "R03 总经理", "无上界"],
            ["含免押金条款", "R04 运营总监", "与折扣路由取层级更高者"],
            ["含延期付款条款", "R05 运营总监", "与折扣路由取层级更高者"],
            ["含免租期超过 30 天", "R06 总经理", "与折扣路由取层级更高者"],
            ["审批首节点 = 发起人角色", "跳过该节点", "从下一节点起，即跳到上一级"],
            ["节点超时", "自动上升一级", "任何情况下不允许自动通过"],
            ["审批中途改价", "重新审批", "原审批作废，按新口径重走"]]
    for r in rows:
        ws3.append(r)

    ws4 = wb.create_sheet("说明")
    for line in ["百分点数值以「百分点 × 10」整数参与运算（51 表示 5.1 个百分点），不使用浮点。",
                 "同时命中折扣与特殊条款时不叠加串行，取层级更高的一条。",
                 "全部企业、产品、角色人员均为虚构，不含真实客户信息。",
                 "本表由 pkg/extras.py 生成，重跑 python tools/gen.py 可完整复现。"]:
        ws4.append([line])

    p2 = os.path.join(docs, "discount_routing.xlsx")
    wb.save(p2)
    xlsx.normalize(p2)

    p1 = T.write_csv_rows(os.path.join(docs, "boundary_rules.csv"),
                          ["rule_id", "condition", "decision", "note"],
                          [[i + 1, r[0], r[1], r[2]] for i, r in enumerate(rows[1:])])
    return [p2, p1]
