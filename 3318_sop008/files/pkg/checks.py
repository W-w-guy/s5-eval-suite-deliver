# -*- coding: utf-8 -*-
"""本单 20 条 AC 断言。"""
import csv
import json
import os
import re

import engine as E
from kitlib import sop
from kitlib.checks import check

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
RESULT = re.compile(r"结果：负责岗位 \*\*(.+?)\*\* / 口径 \*\*(.+?)\*\* / 时限 \*\*(.+?)\*\*"
                    r" / 截止 \*\*([\d\-T:]+)\*\* / 必填输出 \*\*(\d+)\*\* 项 / 检查项 \*\*(\d+)\*\* 条")


def rows():
    return list(csv.DictReader(open(os.path.join(DOCS, "match_expected.csv"), encoding="utf-8")))


def sections(md):
    out, cur, buf = {}, None, []
    for ln in md.splitlines():
        m = re.match(r"^## (S\d\d) ", ln)
        if m:
            if cur:
                out[cur] = buf
            cur, buf = m.group(1), []
        elif cur:
            buf.append(ln)
    if cur:
        out[cur] = buf
    return {k: "\n".join(v) for k, v in out.items()}


NEG = ("不提供", "不会提供", "不互通", "不予提供", "无法提供", "不透露")


def rp(R, i):
    return [r for r in R if r["step_id"] == i][0]


def main():
    R = rows()
    md = open(os.path.join(DOCS, "match_sop.md"), encoding="utf-8").read()
    S = sections(md)
    cov = list(csv.DictReader(open(os.path.join(DOCS, "coverage.csv"), encoding="utf-8")))

    # ---------- 结构 ----------
    check("V01 步骤不少于 7 个（实测 %d 个）" % len(E.STEPS), len(E.STEPS) >= 7, "步骤 %d" % len(E.STEPS))
    check("V02 每步岗位/时限/说明/输出/检查项齐全",
          not sop.fields_problems(E.STEPS) and not sop.checklist_problems(E.STEPS),
          "缺字段 %s；检查项问题 %s"
          % (sop.fields_problems(E.STEPS) or "无", sop.checklist_problems(E.STEPS) or "无"))
    check("V03 每步岗位取自已声明岗位表", all(s["role"] in E.ROLES for s in E.STEPS),
          "岗位 %s" % sorted(set(s["role"] for s in E.STEPS)))

    # ---------- AC1 话术 3 类 × 2 版，均用变量占位 ----------
    scenes = ["向需求方介绍候选方", "向供给方说明需求", "洽谈邀约"]
    by = {}
    for s in E.SCRIPTS:
        by.setdefault(s["scene"], []).append(s)
    check("V04 话术共 6 条、3 类各 2 版（实测 %d 条）" % len(E.SCRIPTS),
          len(E.SCRIPTS) == 6 and all(len(by.get(x, [])) == 2 for x in scenes),
          "条数 %d；分类 %s" % (len(E.SCRIPTS), {k: len(v) for k, v in by.items()}))
    check("V05 每条话术都使用变量占位（vars 非空且正文真的出现）",
          not [s["id"] for s in E.SCRIPTS if not sop.vars_in(s["body"])
               or [v for v in s["vars"] if v not in sop.vars_in(s["body"])]],
          "各条变量数 %s" % [len(sop.vars_in(s["body"])) for s in E.SCRIPTS])
    check("V06 每类 2 版的版本名不重复（正式版/简短版）",
          all(len({i["version"] for i in v}) == 2 for v in by.values()),
          "版本 %s" % {k: [i["version"] for i in v] for k, v in by.items()})
    check("V07 话术渲染后不残留变量占位",
          all(not sop.vars_in(sop.render_vars(s["body"], {v: "X" for v in s["vars"]})[0])
              for s in E.SCRIPTS),
          "逐条渲染 6 条均无残留")

    # ---------- AC2 双方同意前不透露联系方式 ----------
    forbid_bad = sop.vars_problems(E.SCRIPTS, forbid_vars=E.FORBID_VARS,
                                   forbid_words=E.FORBID_WORDS, scenes=scenes)
    check("V08 话术中不含任何联系方式类变量或硬编码号码", not forbid_bad,
          "问题 %s" % (forbid_bad or "无"))
    up = [s for s in E.SCRIPTS if s["scene"] == "向供给方说明需求"]
    check("V09 向供给方说明需求的两版都显式声明「同意前不提供对方联系方式」",
          all("同意" in s["body"] and any(w in s["body"] for w in NEG)
              for s in up),
          "两版声明：%s" % [any(w in s["body"] for w in NEG) for s in up])
    check("V10 正文写明铁律：双方同意前不透露联系方式（多处出现）",
          md.count("双方同意前不透露") + md.count("双方都明确同意之前") >= 2,
          "关键句出现 %d 次" % (md.count("双方同意前不透露") + md.count("双方都明确同意之前")))
    s03 = rp(R, "S03")
    check("V11 S03 的必填输出写明「不含联系方式与企业全称」且检查项含对应反向校验",
          "不含" in s03["expected_outputs"]
          and any("不含" in k for k in E.STEPS[2]["checklist"]),
          "S03 输出：%s" % s03["expected_outputs"][:70])

    # ---------- AC3 首次联系时限与超时升级 ----------
    s09 = rp(R, "S09")
    exp = sop.workdays_after(E.BASE, 3, work=E.WORK, holidays=E.HOLIDAYS)
    check("V12 S09 口径为 workdays 且 3 个工作日从周三 10:00 推得 %s" % exp.strftime("%Y-%m-%dT%H:%M"),
          s09["tmode"] == "workdays" and s09["expected_due"] == exp.strftime("%Y-%m-%dT%H:%M"),
          "S09 口径=%s 截止=%s（若误按 work 24 小时会得到 %s）"
          % (s09["tmode"], s09["expected_due"],
             sop.deadline(E.BASE, 24, work=E.WORK).strftime("%Y-%m-%dT%H:%M")))
    fr = E.due4 = None
    from datetime import datetime
    fri = datetime(2026, 5, 8, 10, 0)
    cross = sop.workdays_after(fri, 3, work=E.WORK, holidays=E.HOLIDAYS)
    check("V13 跨周末推算：周五 10:00 + 3 工作日 = 下周二 %s（周末不计）" % cross.strftime("%m-%d %H:%M"),
          cross.strftime("%Y-%m-%dT%H:%M") == "2026-05-12T10:00",
          "周五起算 3 工作日 → %s" % cross.strftime("%Y-%m-%d %H:%M"))
    s10 = rp(R, "S10")
    check("V14 超时升级链写明：一级招商主管 8 工作小时、二次升运营总监",
          s10["role"] == "招商主管" and "运营总监" in s10["expected_outputs"]
          and "运营总监" in md and "二级升级" in md,
          "S10 岗位=%s；正文含升级表=%s" % (s10["role"], "二级升级" in md))
    check("V15 S08 会后 24 小时为 natural 口径（自然时间，不是工作时段）",
          rp(R, "S08")["tmode"] == "natural"
          and rp(R, "S08")["expected_due"] == "2026-05-07T10:00",
          "S08 口径=%s 截止=%s" % (rp(R, "S08")["tmode"], rp(R, "S08")["expected_due"]))

    # ---------- 流程图：不透露联系方式的结构性保证 ----------
    fl = os.path.join(DOCS, "referral_flow.md")
    ft = open(fl, encoding="utf-8").read() if os.path.exists(fl) else ""
    check("V16 流程图含引荐全链路 9 个节点且每条边标注条件",
          len(E.FLOW_NODES) == 9 and "```mermaid" in ft
          and not sop.flow_problems(E.FLOW_NODES, E.FLOW_EDGES),
          "节点 %d；flow 问题 %s" % (len(E.FLOW_NODES),
                                  sop.flow_problems(E.FLOW_NODES, E.FLOW_EDGES) or "无"))
    n4_out = [b for a, b, _ in E.FLOW_EDGES if a == "N4"]
    into_n5 = [a for a, b, _ in E.FLOW_EDGES if b == "N5"]
    check("V17 交换联系方式（N5）的唯一入口是「双方均同意」（N4）",
          into_n5 == ["N4"] and "N5" in n4_out,
          "指向 N5 的边来自 %s；N4 的出边 %s" % (into_n5, n4_out))
    check("V18 供给方拒绝时回到需求登记（存在 N3→N1 的拒绝环路）",
          any(a == "N3" and b == "N1" for a, b, _ in E.FLOW_EDGES),
          "N3 出边 %s" % [b for a, b, _ in E.FLOW_EDGES if a == "N3"])

    # ---------- 交付物齐备 ----------
    sj = os.path.join(DOCS, "match_steps.json")
    st = json.load(open(sj, encoding="utf-8")) if os.path.exists(sj) else {}
    check("V19 步骤 JSON 可解析且条目数=步骤数",
          len(st.get("steps", [])) == len(E.STEPS)
          and all(all(k in s for k in ("id", "role", "tmode", "sla_value", "outputs", "checklist"))
                  for s in st.get("steps", [])),
          "条目 %d" % len(st.get("steps", [])))
    bt = os.path.join(DOCS, "pre_brief_template.md")
    btx = open(bt, encoding="utf-8").read() if os.path.exists(bt) else ""
    check("V20 会前简报模板含两版（需求方版/供给方版）且 7 个字段齐全",
          "需求方版" in btx and "供给方版" in btx
          and all(f[1] in btx for f in E.BRIEF_FIELDS),
          "字段缺失 %s" % [f[1] for f in E.BRIEF_FIELDS if f[1] not in btx] or "无")

    # ---------- 一致性 ----------
    mm = []
    for r, c in zip(R, E.CASES):
        row = {k: str(v) for k, v in E.row_of(c).items()}
        for k in row:
            if row[k] != r[k]:
                mm.append("%s.%s" % (r["step_id"], k))
                break
    check("V21 引擎重算 %d 行与 CSV 全 %d 列一致" % (len(R), len(R[0]) if R else 0), not mm,
          "不一致 %s" % (mm or "无"))
    bad = []
    for r in R:
        m = RESULT.search(S.get(r["step_id"], ""))
        if not m:
            bad.append(r["step_id"] + ":无结果行")
        elif (m.group(1), m.group(2), m.group(4)) != (r["role"], r["tmode"], r["expected_due"]):
            bad.append("%s:MD≠CSV" % r["step_id"])
    check("V22 每节结果行与 CSV 一致（%d 行全比）" % len(R), not bad, "不一致 %s" % (bad or "无"))
    idmap = {cid: [E.case_id(c) for c in E.CASES if cid in E.cats_of(c)] for cid, _ in E.CATS}
    check("V23 8 类情形均至少 1 步且并集覆盖全部 %d 步" % len(E.STEPS),
          len(idmap) == 8 and all(idmap.values())
          and set(i for v in idmap.values() for i in v) == set(r["step_id"] for r in R),
          "；".join("%s=%d" % (k, len(v)) for k, v in idmap.items()))
