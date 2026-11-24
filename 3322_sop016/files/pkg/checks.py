# -*- coding: utf-8 -*-
"""本单 22 条 AC 断言。"""
import csv
import os
import re
from datetime import datetime

import engine as E
from kitlib import sop
from kitlib.checks import check

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
RESULT = re.compile(r"结果：规则 \*\*(R\d\d)\*\* / 岗位 \*\*(.+?)\*\* / 档位 \*\*(.+?)\*\*"
                    r" / 响应截止 \*\*([\d\-T:]+)\*\* / 回写 \*\*(.+?)\*\*")


def rows():
    return list(csv.DictReader(open(os.path.join(DOCS, "cs_expected.csv"), encoding="utf-8")))


def sections(md):
    out, cur, buf = {}, None, []
    for ln in md.splitlines():
        m = re.match(r"^## (P\d\d)[（( ]", ln)
        if m:
            if cur:
                out[cur] = buf
            cur, buf = m.group(1), []
        elif cur:
            buf.append(ln)
    if cur:
        out[cur] = buf
    return {k: "\n".join(v) for k, v in out.items()}


def rp(R, i):
    return [r for r in R if r["example_id"] == i][0]


def main():
    R = rows()
    md = open(os.path.join(DOCS, "cs_transfer_sop.md"), encoding="utf-8").read()
    S = sections(md)
    cov = list(csv.DictReader(open(os.path.join(DOCS, "coverage.csv"), encoding="utf-8")))

    # ---------- AC1 触发条件 ≥5 种，每种写明接手岗位 ----------
    check("V01 转接触发条件不少于 5 种（实测 %d 种）" % len(E.RULES), len(E.RULES) >= 5,
          "规则 %d 条：%s" % (len(E.RULES), [r["id"] for r in E.RULES]))
    check("V02 每条规则都有触发条件文字与接手岗位，且岗位取自已声明岗位表",
          all(r["trigger"].strip() and r["role"] in E.ROLES for r in E.RULES),
          "岗位 %s" % sorted(set(r["role"] for r in E.RULES)))
    check("V03 工单点名的 5 类触发场景全部覆盖（管家答不上来/主动要求/价格/合同/他人信息）",
          all(any(k in r["trigger"] for r in E.RULES) for k in
              ("答不上来", "要求人工", "价格", "合同", "他人信息")),
          "缺失 %s" % [k for k in ("答不上来", "要求人工", "价格", "合同", "他人信息")
                     if not any(k in r["trigger"] for r in E.RULES)] or "无")
    from openpyxl import load_workbook
    wb = load_workbook(os.path.join(DOCS, "transfer_tables.xlsx"))
    ws = wb["转接规则表"]
    hdr = [c.value for c in ws[1]]
    check("V04 转接规则表 xlsx 可读且列含触发条件与接手岗位",
          "触发条件" in hdr and "接手岗位" in hdr and ws.max_row - 1 == len(E.RULES),
          "列 %s；行 %d" % (hdr, ws.max_row - 1))
    check("V05 规则表 Markdown 正文与 xlsx 一致（%d 条全部列出）" % len(E.RULES),
          all(r["id"] in md and r["trigger"][:10] in md for r in E.RULES),
          "缺失 %s" % [r["id"] for r in E.RULES if r["id"] not in md] or "无")

    # ---------- AC2 工作时间与非工作时间分别写明响应时限 ----------
    check("V06 文档分别写明工作时段与非工作时段的响应时限",
          "工作时间内" in md and "非工作时间" in md
          and md.count("非工作时间") >= 3,
          "「工作时间内」=%s；「非工作时间」出现 %d 次"
          % ("工作时间内" in md, md.count("非工作时间")))
    check("V07 双时段表在位：普通 30 分钟、紧急 15 分钟，且给出两种起算点实例",
          "普通转接 | 30 分钟" in md and "紧急转接 | 15 分钟" in md
          and "周三 10:00 → **10:30 前**" in md and "周三 19:00 → **周四 09:30 前**" in md,
          "双时段表述齐备=%s"
          % all(x in md for x in ("普通转接 | 30 分钟", "紧急转接 | 15 分钟",
                                  "周三 10:00 → **10:30 前**", "周三 19:00 → **周四 09:30 前**")))
    p01, p03 = rp(R, "P01"), rp(R, "P03")
    check("V08 工作时间普通档：周三 10:00 → 10:30（就地起算 30 分钟）",
          p01["expected_due"] == "2026-05-06T10:30" and p01["shift"] == "work",
          "P01=%s 时段=%s" % (p01["expected_due"], p01["shift"]))
    check("V09 工作时间紧急档：周三 11:00 → 11:15（15 分钟，不是 30 分钟）",
          p03["expected_due"] == "2026-05-06T11:15" and p03["tier"] == "urgent",
          "P03=%s 档位=%s（若漏了紧急档会得 11:30）" % (p03["expected_due"], p03["tier"]))
    p05 = rp(R, "P05")
    check("V10 非工作时间（周三 19:00）→ 顺延到周四 09:30，不是当晚 19:30",
          p05["expected_due"] == "2026-05-07T09:30" and p05["shift"] == "offwork",
          "P05=%s（若不顺延会得 2026-05-06T19:30）" % p05["expected_due"])
    p06, p07 = rp(R, "P06"), rp(R, "P07")
    check("V11 周末与非工作时间跨周末：周六 10:00 与周五 21:30 都顺延到周一 09:30",
          p06["expected_due"] == "2026-05-11T09:30" and p07["expected_due"] == "2026-05-11T09:30",
          "P06=%s P07=%s" % (p06["expected_due"], p07["expected_due"]))
    check("V12 双时段用同一口径实现：时长只在工作日 9–18 内消耗（用函数直接验四组边界）",
          E.due(datetime(2026, 5, 6, 8, 50), "normal").strftime("%m-%d %H:%M") == "05-06 09:30"
          and E.due(datetime(2026, 5, 6, 17, 40), "normal").strftime("%m-%d %H:%M") == "05-07 09:10"
          and E.due(datetime(2026, 5, 6, 18, 0), "normal").strftime("%m-%d %H:%M") == "05-07 09:30"
          and E.due(datetime(2026, 5, 10, 12, 0), "normal").strftime("%m-%d %H:%M") == "05-11 09:30",
          "8:50→%s；17:40→%s（当日 20 分钟 + 次日 10 分钟）；18:00→%s；周日12:00→%s"
          % (E.due(datetime(2026, 5, 6, 8, 50), "normal").strftime("%m-%d %H:%M"),
             E.due(datetime(2026, 5, 6, 17, 40), "normal").strftime("%m-%d %H:%M"),
             E.due(datetime(2026, 5, 6, 18, 0), "normal").strftime("%m-%d %H:%M"),
             E.due(datetime(2026, 5, 10, 12, 0), "normal").strftime("%m-%d %H:%M")))

    # ---------- AC3 回写知识缺口 ----------
    check("V13 文档有独立的「回写知识缺口」小节且写明必做",
          "回写知识缺口" in md and "必做" in md,
          "小节标题在=%s；含『必做』=%s" % ("回写知识缺口" in md, "必做" in md))
    gap = os.path.join(DOCS, "knowledge_gap.md")
    gt = open(gap, encoding="utf-8").read() if os.path.exists(gap) else ""
    check("V14 知识缺口回写字段表含 %d 个字段且单独成文" % len(E.BACKWRITE_FIELDS),
          os.path.exists(gap) and all(f[1] in gt for f in E.BACKWRITE_FIELDS),
          "字段缺失 %s" % [f[1] for f in E.BACKWRITE_FIELDS if f[1] not in gt] or "无")
    bw_yes = [r["id"] for r in E.RULES if r["backwrite"]]
    check("V15 哪些规则必须回写明确（%s 共 %d 条），且示例 P08 回写为「是」"
          % ("/".join(bw_yes), len(bw_yes)),
          len(bw_yes) >= 1 and rp(R, "P08")["expected_backwrite"] == "是",
          "必回写规则 %s；P08=%s" % (bw_yes, rp(R, "P08")["expected_backwrite"]))
    check("V16 回写责任人与时限写明（接手岗位、处理完成后 1 个工作日内）",
          "1 个工作日内" in md and "接手岗位" in gt,
          "含『1 个工作日内』=%s；knowledge_gap.md 含『接手岗位』=%s"
          % ("1 个工作日内" in md, "接手岗位" in gt))
    check("V17 回写内容要求脱敏（不含姓名/手机号/合同金额）",
          "脱敏" in gt and all(k in gt for k in ("姓名", "手机号", "合同金额")),
          "含脱敏声明=%s" % ("脱敏" in gt))

    # ---------- 升级与流程 ----------
    fl = os.path.join(DOCS, "transfer_flow.md")
    ft = open(fl, encoding="utf-8").read() if os.path.exists(fl) else ""
    check("V18 处理流程图含待办生成、响应、两级升级、回写、关闭等节点且每边带条件",
          "```mermaid" in ft and len(E.FLOW_NODES) >= 9
          and not sop.flow_problems(E.FLOW_NODES, E.FLOW_EDGES),
          "节点 %d；flow 问题 %s" % (len(E.FLOW_NODES),
                                  sop.flow_problems(E.FLOW_NODES, E.FLOW_EDGES) or "无"))
    into_c7 = [a for a, b, _ in E.FLOW_EDGES if b == "C7"]
    into_c8 = [a for a, b, _ in E.FLOW_EDGES if b == "C8"]
    check("V19 升级链结构：C7（值班主管）只从 C6（超时）进入，C8（客服负责人）只从 C7 进入",
          into_c7 == ["C6"] and into_c8 == ["C7"],
          "指向 C7 的边 %s；指向 C8 的边 %s" % (into_c7, into_c8))
    check("V20 待办生成节点存在且写明字段（会话 ID/规则编号/接手岗位/截止）",
          any(n[1].startswith("生成待办") for n in E.FLOW_NODES)
          and all(k in md for k in ("会话 ID", "触发规则编号", "接手岗位", "响应截止")),
          "缺字段 %s" % [k for k in ("会话 ID", "触发规则编号", "接手岗位", "响应截止")
                      if k not in md] or "无")

    # ---------- 一致性与覆盖 ----------
    mm = []
    for r, c in zip(R, E.CASES):
        row = {k: str(v) for k, v in E.row_of(c).items()}
        for k in row:
            if row[k] != r[k]:
                mm.append("%s.%s" % (r["example_id"], k))
                break
    check("V21 引擎重算 %d 行与 CSV 全 %d 列一致" % (len(R), len(R[0]) if R else 0), not mm,
          "不一致 %s" % (mm or "无"))
    bad = []
    for r in R:
        m = RESULT.search(S.get(r["example_id"], ""))
        if not m:
            bad.append(r["example_id"] + ":无结果行")
        elif (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)) != (
                r["rule_id"], r["role"], r["tier"], r["expected_due"], r["expected_backwrite"]):
            bad.append("%s:MD≠CSV" % r["example_id"])
    check("V22 每节结果行与 CSV 一致（%d 行全比）" % len(R), not bad, "不一致 %s" % (bad or "无"))
    idmap = {cid: [E.case_id(c) for c in E.CASES if cid in E.cats_of(c)] for cid, _ in E.CATS}
    check("V23 8 类情形均至少 1 例且并集覆盖全部 %d 例" % len(E.CASES),
          len(idmap) == 8 and all(idmap.values())
          and set(i for v in idmap.values() for i in v) == set(r["example_id"] for r in R),
          "；".join("%s=%d" % (k, len(v)) for k, v in idmap.items()))
