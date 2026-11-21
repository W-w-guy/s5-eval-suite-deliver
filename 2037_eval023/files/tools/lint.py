# -*- coding: utf-8 -*-
"""eval-lint + eval-pii-scan（AC2 要求两者均通过）。

    python tools/lint.py            # 两个检查都跑
    python tools/lint.py --pii      # 只跑 PII

lint 查「数据能不能用」：
  · 30 组、每组 3–5 轮、四类分布 8/8/6/8
  · 每题有 checkpoint 且 must_points 非空；检查点必须在 user 轮上
  · 最后一轮有 answer_points
  · 纠正类 8 组都含 stale_premise* 的 forbidden_points（AC3）
  · 引用的 kb_doc 都必须存在于知识库
pii 查「有没有真实格式的手机号/邮箱/身份证」。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = {"coref": 8, "condition_change": 8, "topic_switch": 6, "correction": 8}
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
IDCARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


def load_cases():
    p = os.path.join(HERE, "data", "cases.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def load_docs():
    p = os.path.join(HERE, "data", "facts_mt.json")
    if not os.path.isfile(p):
        p = os.path.join(HERE, "data", "facts.json")
    return {r["doc_id"] for r in json.load(open(p, encoding="utf-8"))}


def lint():
    cases = load_cases()
    docs = load_docs()
    errs = []
    if len(cases) != 30:
        errs.append("组数 %d != 30" % len(cases))
    from collections import Counter
    dist = Counter(c["kind"] for c in cases)
    for k, n in DIST.items():
        if dist.get(k, 0) != n:
            errs.append("类型 %s 数量 %d != %d" % (k, dist.get(k, 0), n))
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids):
        errs.append("case_id 重复")
    for c in cases:
        cid = c["case_id"]
        turns = c.get("turns") or []
        if not 3 <= len(turns) <= 5:
            errs.append("%s 轮数 %d 不在 3–5" % (cid, len(turns)))
        if c.get("kb_doc") and c["kb_doc"] not in docs:
            errs.append("%s kb_doc %s 不存在" % (cid, c["kb_doc"]))
        cps = [t for t in turns if t.get("checkpoint")]
        if not cps:
            errs.append("%s 没有检查点" % cid)
        for t in cps:
            if t.get("role") != "user":
                errs.append("%s 检查点挂在非 user 轮（应挂在被检查答案对应的提问轮）" % cid)
            if not (t.get("must_points") or []):
                errs.append("%s 检查点缺 must_points" % cid)
        if not ((c.get("final_expect") or {}).get("answer_points")):
            errs.append("%s 缺 final_expect.answer_points" % cid)
        if not c.get("forbidden_points"):
            errs.append("%s 缺 forbidden_points" % cid)
    corr = [c for c in cases if c["kind"] == "correction"]
    if len(corr) != 8:
        errs.append("纠正类 %d != 8" % len(corr))
    bad_corr = [c["case_id"] for c in corr
                if not any(f["type"].startswith("stale_premise") for f in c["forbidden_points"])]
    if bad_corr:
        errs.append("纠正类未写被纠正前提的 forbidden_points：%s" % bad_corr)
    return errs, cases, dist


def pii_scan():
    blob = ""
    for f in ("cases.jsonl", "facts_mt.json", "facts.json"):
        p = os.path.join(HERE, "data", f)
        if os.path.isfile(p):
            blob += open(p, encoding="utf-8").read()
    hits = []
    for m in PHONE.finditer(blob):
        if not m.group(0).startswith("1990000"):
            hits.append(("phone", m.group(0)))
    for m in EMAIL.finditer(blob):
        s = m.group(0)
        if "%s" in s or s.endswith(".invalid"):
            continue
        hits.append(("email", s))
    for m in IDCARD.finditer(blob):
        hits.append(("idcard", m.group(0)))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pii", action="store_true")
    a = ap.parse_args()
    ok = True
    if not a.pii:
        errs, cases, dist = lint()
        for e in errs[:20]:
            print("LINT", e)
        print("cases=%d dist=%s errors=%d" % (len(cases), dict(dist), len(errs)))
        print("LINT %s" % ("PASS" if not errs else "FAIL"))
        ok = ok and not errs
    hits = pii_scan()
    for h in hits[:10]:
        print("PII", h)
    print("PII hits=%d" % len(hits))
    print("PII %s" % ("PASS" if not hits else "FAIL"))
    ok = ok and not hits
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
