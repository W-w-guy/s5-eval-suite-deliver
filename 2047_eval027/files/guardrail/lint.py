# -*- coding: utf-8 -*-
"""三张护栏用例集共用的结构校验（eval-lint）。

用法：
    python tools/lint.py 2047 | 2043 | 2048

它检查的是「数据能不能用」，不是「工具防不防得住」：
  · 条数与分布严格对齐单子
  · 每条都有必需的 canaries / severity / entrance
  · 金丝雀短语在文档里真实存在（清单与文档一致）
  · 多轮用例必须有 turns 且不含 prompt
  · 注入用例必须一一对应一份对照文件，且对照文件里**不出现**注入内容
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 项目根
sys.path.insert(0, HERE)
from guardrail import core

DATA = os.path.join(HERE, "data")

SPEC = {
    "2047": {"file": "guardrail_leakage_cases.jsonl", "count": 45,
             "per_key": ("technique", 6), "entrances_min": {"butler": 12, "staff_ai": 12, "sales_ai": 12},
             "entrance_key": "entrance"},
    "2043": {"file": "guardrail_access_cases.jsonl", "count": 40,
             "entrances_min": {"butler": 12, "staff_ai": 12}, "entrance_key": "entrance"},
    "2048": {"file": "guardrail_injection_cases.jsonl", "count": 35,
             "per_key": ("carrier", 7), "entrances_min": {}, "entrance_key": "entrance"},
}


def load(pid):
    return [json.loads(l) for l in
            open(os.path.join(DATA, SPEC[pid]["file"]), encoding="utf-8") if l.strip()]


def lint(pid):
    spec, errs = SPEC[pid], []
    cases = load(pid)
    if len(cases) != spec["count"]:
        errs.append("条数 %d != %d" % (len(cases), spec["count"]))
    if "per_key" in spec:
        key, least = spec["per_key"]
        for k, n in core.distribution(cases, key).items():
            if n < least:
                errs.append("%s=%s 只有 %d 条（要求 ≥%d）" % (key, k, n, least))
    for e, least in spec["entrances_min"].items():
        n = sum(1 for c in cases if c.get(spec["entrance_key"]) == e)
        if n < least:
            errs.append("入口 %s 只有 %d 条（要求 ≥%d）" % (e, n, least))
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids):
        errs.append("case_id 有重复")
    for c in cases:
        for f in ("case_id", "severity", "entrance", "expect"):
            if f not in c:
                errs.append("%s 缺字段 %s" % (c.get("case_id"), f))
        # 注入用例（2048）不埋金丝雀 —— 它比的是「有无注入时字段/置信度是否变化」，
        # 拿 canaries 去要求它是把两套判定混在一起。
        if pid != "2048" and not c.get("canaries"):
            errs.append("%s 没有金丝雀" % c.get("case_id"))
        if c.get("severity") not in ("P0", "P1"):
            errs.append("%s severity 非法：%r" % (c.get("case_id"), c.get("severity")))
    # 2047：多轮用例必须有 turns 且无 prompt
    if pid == "2047":
        multi = [c for c in cases if c.get("technique") == "多轮逐位拼凑"]
        for c in multi:
            if not c.get("turns") or c.get("prompt"):
                errs.append("%s 多轮用例必须只有 turns、没有 prompt" % c["case_id"])
        if not multi:
            errs.append("缺多轮逐位拼凑用例")
    # 2043：金丝雀与文档一致 + 越权/正向分布
    if pid == "2043":
        docs = {d["doc_id"]: d for d in json.load(open(os.path.join(HERE, "fixtures", "docs.json"),
                                                       encoding="utf-8"))}
        for c in cases:
            d = docs.get(c.get("doc_id"))
            if not d:
                errs.append("%s 指向不存在的文档 %s" % (c["case_id"], c.get("doc_id")))
                continue
            if c["canaries"] != [d["canary"]]:
                errs.append("%s 金丝雀与文档不一致" % c["case_id"])
        deny = sum(1 for c in cases if not c["_allowed"])
        allow = sum(1 for c in cases if c["_allowed"])
        if deny != 30:
            errs.append("越权条数 %d != 30" % deny)
        if allow != 10:
            errs.append("正向对照条数 %d != 10" % allow)
    # 2048：注入与对照一一对应，对照文件不含注入文本
    if pid == "2048":
        for c in cases:
            inj = os.path.join(HERE, c["injected_file"])
            ctl = os.path.join(HERE, c["control_file"])
            if not os.path.isfile(inj):
                errs.append("%s 缺注入载体文件" % c["case_id"])
            if not os.path.isfile(ctl):
                errs.append("%s 缺对照文件" % c["case_id"])
                continue
            body = open(ctl, encoding="utf-8").read()
            if c["injection_text"] and c["injection_text"] in body:
                errs.append("%s 对照文件里出现了注入内容" % c["case_id"])
            body_i = open(inj, encoding="utf-8").read() if os.path.isfile(inj) else ""
            if c["injection_text"] not in body_i and \
                    "\u200b".join(list(c["injection_text"])) not in body_i:
                errs.append("%s 注入文件里找不到注入内容" % c["case_id"])
    return errs, cases


def main():
    pid = sys.argv[1] if len(sys.argv) > 1 else "2047"
    errs, cases = lint(pid)
    for e in errs[:30]:
        print("LINT", e)
    print("%s cases=%d errors=%d" % (pid, len(cases), len(errs)))
    print("LINT %s" % ("PASS" if not errs else "FAIL"))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
