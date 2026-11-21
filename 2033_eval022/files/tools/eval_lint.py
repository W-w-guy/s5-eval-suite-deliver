# -*- coding: utf-8 -*-
"""eval-lint：用例与知识库的结构校验（AC2 要求「eval-lint 通过」）。

它检查的是「数据能不能用」，不是「答案对不对」：
  · 50 条、4 类分布严格 20/12/10/8
  · 每条 case_id 唯一、type 合法、question 非空且以问号结尾
  · gold_doc_ids 1~3 个且都真实存在于知识库
  · answer_points 3~5 条且每条都是**文档里的原句**（不能是凭空概括）
  · 每个答案要点必须能在其某个 gold 文档里逐字找到（否则金标不可取证）
"""
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(HERE, "data", "cases.jsonl")
DB = os.path.join(HERE, "data", "kb.sqlite3")
DIST = {"single_doc": 20, "multi_doc": 12, "numeric_date": 10, "paraphrase": 8}
TYPES = tuple(DIST)


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def load_cases(path=CASES):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def bodies(db=DB):
    conn = sqlite3.connect(db)
    return {k: v for k, v in conn.execute("SELECT doc_id, body FROM docs").fetchall()}


def lint(cases=None, db=DB):
    cases = cases if cases is not None else load_cases()
    b = bodies(db)
    errs = []
    if len(cases) != 50:
        errs.append("用例数 %d != 50" % len(cases))
    cnt = {}
    for c in cases:
        cnt[c.get("type")] = cnt.get(c.get("type"), 0) + 1
    for t, n in DIST.items():
        if cnt.get(t, 0) != n:
            errs.append("类型 %s 数量 %d != %d" % (t, cnt.get(t, 0), n))
    seen = set()
    for c in cases:
        cid = c.get("case_id")
        if not cid:
            errs.append("缺 case_id")
            continue
        if cid in seen:
            errs.append("%s case_id 重复" % cid)
        seen.add(cid)
        if c.get("type") not in TYPES:
            errs.append("%s type 非法：%r" % (cid, c.get("type")))
        q = (c.get("question") or "").strip()
        if not q:
            errs.append("%s question 为空" % cid)
        elif not q.endswith(("？", "?")):
            errs.append("%s question 未以问号结尾" % cid)
        gids = c.get("gold_doc_ids") or []
        if not (1 <= len(gids) <= 3):
            errs.append("%s gold_doc_ids 数量 %d 不在 1~3" % (cid, len(gids)))
        for g in gids:
            if g not in b:
                errs.append("%s gold_doc %s 不存在于知识库" % (cid, g))
        aps = c.get("answer_points") or []
        if not (3 <= len(aps) <= 5):
            errs.append("%s answer_points 数量 %d 不在 3~5" % (cid, len(aps)))
        blobs = [_norm(b.get(g, "")) for g in gids]
        for ap in aps:
            if not any(_norm(ap) in blob for blob in blobs):
                errs.append("%s 答案要点无法在任何 gold 文档中逐字找到：%s" % (cid, ap[:24]))
    return errs, {"cases": len(cases), "dist": cnt}


def main():
    errs, stat = lint()
    for e in errs[:40]:
        print("LINT", e)
    print("cases=%d dist=%s errors=%d" % (stat["cases"], stat["dist"], len(errs)))
    print("LINT %s" % ("PASS" if not errs else "FAIL"))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
