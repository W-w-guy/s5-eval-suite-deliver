# -*- coding: utf-8 -*-
"""本单 20 条 AC 断言。"""
import csv
import os
import re
from datetime import datetime

import engine as E
from kitlib import sop
from kitlib.checks import check

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
RESULT = re.compile(r"结果：负责岗位 \*\*(.+?)\*\* / 时限 \*\*(.+?)\*\* / 截止 \*\*([\d\-T:]+)\*\*"
                    r" / 必填输出 \*\*(\d+)\*\* 项 / 检查项 \*\*(\d+)\*\* 条")


def rows():
    return list(csv.DictReader(open(os.path.join(DOCS, "join_expected.csv"), encoding="utf-8")))


def materials():
    return list(csv.DictReader(open(os.path.join(DOCS, "materials.csv"), encoding="utf-8")))


def sections(md):
    out, cur, buf = {}, None, []
    for ln in md.splitlines():
        m = re.match(r"^## (S\d\d)[ （]", ln)
        if m:
            if cur:
                out[cur] = buf
            cur, buf = m.group(1), []
        elif cur:
            buf.append(ln)
    if cur:
        out[cur] = buf
    return {k: "\n".join(v) for k, v in out.items()}


def main():
    R = rows()
    M = materials()
    md = open(os.path.join(DOCS, "join_sop.md"), encoding="utf-8").read()
    S = sections(md)
    cov = list(csv.DictReader(open(os.path.join(DOCS, "coverage.csv"), encoding="utf-8")))

    # ================= AC1 话术 3 版 ≤150 字 + 变量占位 =================
    channels = [s["channel"] for s in E.SCRIPTS]
    check("V01 欢迎话术恰好 3 版，渠道为 企业微信 / 短信 / 邮件（各 1 版，不重复）",
          len(E.SCRIPTS) == 3 and sorted(channels) == sorted(["企业微信", "短信", "邮件"]),
          "渠道 %s" % channels)
    check("V02 每版都使用变量占位（vars 非空且正文真的出现、无未声明变量）",
          not [s["id"] for s in E.SCRIPTS
               if not sop.vars_in(s["body"])
               or [v for v in s["vars"] if v not in sop.vars_in(s["body"])]
               or [v for v in sop.vars_in(s["body"]) if v not in s["vars"]]],
          "各版变量数 %s" % [len(sop.vars_in(s["body"])) for s in E.SCRIPTS])
    over_loose = [(s["id"], sop.char_count(s["body"])) for s in E.SCRIPTS
                  if sop.char_count(s["body"]) > E.SMS_LIMIT]
    over_strict = [(s["id"], len(s["body"])) for s in E.SCRIPTS if len(s["body"]) > E.SMS_LIMIT]
    check("V03 每版都不超过 150 字 —— 乐观口径（变量记 0 字）不过线即判失败", not over_loose,
          "超限 %s；实测 %s" % (over_loose or "无",
                             [(s["id"], sop.char_count(s["body"])) for s in E.SCRIPTS]))
    check("V04 每版都不超过 150 字 —— 严格口径（含变量占位字面长度）也必须过", not over_strict,
          "超限 %s；实测 %s" % (over_strict or "无",
                             [(s["id"], len(s["body"])) for s in E.SCRIPTS]))
    check("V05 两口径同时判：不存在「乐观口径过、严格口径不过」的版本",
          not set(i for i, _ in over_loose) ^ set(i for i, _ in over_strict),
          "乐观超限 %s / 严格超限 %s" % ([i for i, _ in over_loose], [i for i, _ in over_strict]))
    rd = [(s["id"], sop.render_vars(s["body"], {v: "示例值" for v in s["vars"]})[1])
          for s in E.SCRIPTS]
    check("V06 3 版渲染后无残留占位符、无缺失变量",
          all(not sop.vars_in(sop.render_vars(s["body"], {v: "X" for v in s["vars"]})[0])
              for s in E.SCRIPTS) and all(not miss for _, miss in rd),
          "渲染缺失 %s" % [(i, m) for i, m in rd if m] or "无")
    sp = []
    for s in E.SCRIPTS:
        sp += sop.script_problems(s, declared_vars=s["vars"], channel_limit=E.SMS_LIMIT)
    check("V07 script_problems 通用校验（空正文/变量/字数）全过", not sp, "问题 %s" % (sp or "无"))
    check("V08 文档正文写明字数口径（两种口径都要过）与 150 字上限",
          "150" in md and "变量计 0" in md and "原始长度" in md,
          "含 150=%s；含『变量计 0』=%s；含『原始长度』=%s"
          % ("150" in md, "变量计 0" in md, "原始长度" in md))

    # ================= AC2 资料清单写明必填与可选 =================
    req = [m for m in E.MATERIALS if m["required"]]
    opt = [m for m in E.MATERIALS if not m["required"]]
    check("V09 资料清单含 4 项必填（营业执照副本/联系人名单/开票信息/门禁登记信息）",
          len(req) == 4 and all(any(k in m["name"] for m in req) for k in
                                ("营业执照", "联系人名单", "开票信息", "门禁登记")),
          "必填 %s" % [m["name"] for m in req])
    check("V10 资料清单含可选项（至少 1 项，实测 %d 项）" % len(opt), len(opt) >= 1,
          "可选 %s" % [m["name"] for m in opt])
    check("V11 每项材料都写明「必填/可选」标注，且 xlsx/csv 与代码定义一致",
          len(M) == len(E.MATERIALS)
          and all(r["required"] in ("是", "否", "**必填**", "可选") for r in M)
          and sum(1 for r in M if "必填" in r["required"]) == len(req),
          "CSV 行 %d，必填 %d 条" % (len(M), sum(1 for r in M if "必填" in r["required"])))
    check("V12 每项必填材料都给了「不提供时的处理」（替代方案），不是硬性卡住",
          all(m["fallback"].strip() for m in req),
          "缺替代方案 %s" % [m["name"] for m in req if not m["fallback"].strip()] or "无")
    gate = E.MATERIALS[3]
    collect_bad = [k for k in ("证件号", "身份证", "手机号", "住址") if k in gate["why"]]
    decl_ok = "不收" in gate["fallback"]
    check("V13 门禁登记只收最少必要信息：用途段不含证件号/身份证/手机号/住址，且声明段明确「不收」",
          not collect_bad and decl_ok,
          "用途段违规词 %s；声明段含『不收』=%s（两段都必须过，不能靠声明段掩盖用途段）"
          % (collect_bad or "无", decl_ok))
    check("V14 文档资料清单表格与 Markdown 正文一致（全部 %d 项列出）" % len(E.MATERIALS),
          all(m["name"] in md for m in E.MATERIALS),
          "缺失 %s" % [m["name"] for m in E.MATERIALS if m["name"] not in md] or "无")

    # ================= AC3 每步 ≥2 条可勾选检查项 =================
    few = [(s["id"], len(s["checklist"])) for s in E.STEPS if len(s["checklist"]) < 2]
    check("V15 每个步骤至少 2 条可勾选检查项", not few,
          "不足 2 条的步骤 %s；各步条数 %s" % (few or "无", [len(s["checklist"]) for s in E.STEPS]))
    check("V16 检查项条数同时不超 4 条（工单要求 2~4）",
          not [s["id"] for s in E.STEPS if len(s["checklist"]) > 4],
          "超 4 条 %s" % [s["id"] for s in E.STEPS if len(s["checklist"]) > 4] or "无")
    check("V17 检查项在 Markdown 里以可勾选形式（- [ ]）逐条列出，总数与定义一致",
          md.count("- [ ]") >= sum(len(s["checklist"]) for s in E.STEPS)
          + sum(len(s["outputs"]) for s in E.STEPS),
          "复选框 %d 个；检查项 %d + 输出 %d = %d"
          % (md.count("- [ ]"), sum(len(s["checklist"]) for s in E.STEPS),
             sum(len(s["outputs"]) for s in E.STEPS),
             sum(len(s["checklist"]) for s in E.STEPS) + sum(len(s["outputs"]) for s in E.STEPS)))
    chk = os.path.join(DOCS, "checklists.md")
    ct = open(chk, encoding="utf-8").read() if os.path.exists(chk) else ""
    check("V18 检查项表单独成文，%d 个步骤全部在内且逐条可勾选" % len(E.STEPS),
          all(s["id"] in ct for s in E.STEPS) and ct.count("- [ ]") >= sum(len(s["checklist"]) for s in E.STEPS),
          "文件存在=%s；复选框 %d 个" % (os.path.exists(chk), ct.count("- [ ]")))

    # ================= 结构 / 能力卡 / 一致性 =================
    check("V19 能力卡引导问题恰好 10 个且单独成文",
          len(E.CARD_QUESTIONS) == 10
          and all(q in open(os.path.join(DOCS, "card_questions.md"), encoding="utf-8").read()
                  for q in E.CARD_QUESTIONS)
          if os.path.exists(os.path.join(DOCS, "card_questions.md")) else False,
          "问题数 %d" % len(E.CARD_QUESTIONS))
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
        elif (m.group(1), m.group(3), m.group(4), m.group(5)) != (
                r["role"], r["expected_due"], r["output_count"], r["checklist_count"]):
            bad.append("%s:MD≠CSV" % r["step_id"])
    check("V22 每节结果行与 CSV 一致（%d 行全比）" % len(R), not bad, "不一致 %s" % (bad or "无"))
    idmap = {cid: [E.case_id(c) for c in E.CASES if cid in E.cats_of(c)] for cid, _ in E.CATS}
    check("V23 8 类情形均至少 1 步且并集覆盖全部 %d 步" % len(E.STEPS),
          len(idmap) == 8 and all(idmap.values())
          and set(i for v in idmap.values() for i in v) == set(r["step_id"] for r in R),
          "；".join("%s=%d" % (k, len(v)) for k, v in idmap.items()))
    check("V24 S08 30 天回访按 natural 口径，其余按 work 口径（两类口径不混用）",
          [c["id"] for c in E.CASES if c["tmode"] == "natural"] == ["S08"]
          and E.due(E.BASE, 720, "natural").strftime("%Y-%m-%dT%H:%M") == "2026-06-05T10:00",
          "natural 步 %s；S08 截止 %s"
          % ([c["id"] for c in E.CASES if c["tmode"] == "natural"],
             E.due(E.BASE, 720, "natural").strftime("%Y-%m-%dT%H:%M")))
