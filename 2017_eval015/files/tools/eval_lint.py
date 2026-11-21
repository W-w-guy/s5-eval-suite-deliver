# -*- coding: utf-8 -*-
"""eval-lint：结构校验（AC1 要求「eval-lint 通过」，输出可作为命令证据）。

    python tools/eval_lint.py       # 通过 rc=0，打印 LINT PASS
"""
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(HERE, "data", "cases.jsonl")


def load():
    return [json.loads(l) for l in open(CASES, encoding="utf-8") if l.strip()]


def lint(cases=None):
    cs = cases if cases is not None else load()
    errs = []
    if len(cs) != 30:
        errs.append("条数 %d != 30" % len(cs))
    dist = Counter(c.get("kind") for c in cs)
    if dict(dist) != {"outline": 12, "summary": 18}:
        errs.append("分布 %s != outline 12 / summary 18" % dict(dist))
    ids = [c.get("case_id") for c in cs]
    if len(set(ids)) != len(ids):
        errs.append("case_id 重复")
    for c in cs:
        cid = c.get("case_id")
        if not c.get("forbidden_points"):
            errs.append("%s 缺 forbidden_points" % cid)
        if c.get("kind") == "outline":
            for k in ("guest", "background", "topic", "off_limit_topic"):
                if not c.get(k):
                    errs.append("%s 缺字段 %s" % (cid, k))
        elif c.get("kind") == "summary":
            f = c.get("input_file")
            if not f or not os.path.isfile(os.path.join(HERE, f)):
                errs.append("%s 转写稿不存在 %s" % (cid, f))
            if len(c.get("gold_quotes") or []) != 3:
                errs.append("%s 金标金句不是 3 条" % cid)
            if not (3000 <= (c.get("char_count") or 0) <= 6000):
                errs.append("%s 字数 %s 不在 3000-6000" % (cid, c.get("char_count")))
        else:
            errs.append("%s kind 非法 %s" % (cid, c.get("kind")))
    return errs, dict(dist)


def main():
    errs, dist = lint()
    for e in errs[:20]:
        print("LINT", e)
    print("cases=30 dist=%s errors=%d" % (dist, len(errs)))
    print("LINT %s" % ("PASS" if not errs else "FAIL"))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
