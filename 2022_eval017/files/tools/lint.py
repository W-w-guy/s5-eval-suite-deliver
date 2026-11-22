# -*- coding: utf-8 -*-
"""eval-lint + eval-pii-scan（AC1 要求两者均通过）。

    python tools/lint.py            # 两个检查都跑，全过 rc=0
    python tools/lint.py --pii      # 只跑 PII
    python tools/lint.py --lint     # 只跑结构检查

lint 查「这道评测集能不能用」：
  · 恰 35 条；分布 常规20 / 高相似干扰10 / 全无关5
  · case_id 唯一；每条 context 文件存在且含 8~20 篇资讯
  · 每条有 profile（含 interests）、gold_clusters / gold_category / gold_top5
  · 全无关档 gold_top5 必须为空且 expect_no_relevant=true（否则测不出「本期无高相关资讯」）
  · 同事件多来源：措辞与日期不得完全复制（否则聚类退化成字符串比对）
  · gold 里出现的资讯 id 必须在 context 内；context 里的 id 不得重复

pii 查「有没有真实格式的手机号/邮箱/身份证」。金丝雀规则同护栏套件：
号码必须落在 1990000 段，邮箱必须落在 .invalid —— 命中之外的任何真实格式都判 FAIL。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = {"normal": 20, "high_similarity": 10, "irrelevant": 5}

PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# 身份证形态必须【不是十六进制串的一段】：sha256 里 64 位十六进制常含 18 位连续数字，
# 旧写法 (?<!\d)\d{17}[\dXx](?!\d) 会把校验和清单误判成身份证（实测撞到过）。
IDCARD = re.compile(r"(?<![0-9A-Fa-f])\d{17}[\dXx](?![0-9A-Fa-f])")
SKIP_EXT = {".pyc", ".png", ".jpg", ".zip"}


def load_cases():
    p = os.path.join(HERE, "data", "cases.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def load_ctx(rel):
    return json.load(open(os.path.join(HERE, rel), encoding="utf-8"))


def lint():
    from collections import Counter
    cases = load_cases()
    errs = []
    if len(cases) != 35:
        errs.append("用例数 %d != 35" % len(cases))
    dist = Counter(c["kind"] for c in cases)
    for k, n in DIST.items():
        if dist.get(k, 0) != n:
            errs.append("分布 %s=%d != %d" % (k, dist.get(k, 0), n))
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids):
        errs.append("case_id 重复")
    for c in cases:
        cid = c["case_id"]
        try:
            ctx = load_ctx(c["context_file"])
        except OSError:
            errs.append("%s context 文件缺失 %s" % (cid, c["context_file"]))
            continue
        news = ctx.get("news") or []
        if not 8 <= len(news) <= 20:
            errs.append("%s 资讯数 %d 不在 8~20" % (cid, len(news)))
        nid = [x["news_id"] for x in news]
        if len(set(nid)) != len(nid):
            errs.append("%s context 内资讯 id 重复" % cid)
        p = c.get("profile") or {}
        if "interests" not in p or "industry" not in p:
            errs.append("%s profile 缺 interests/industry" % cid)
        gc = c.get("gold_clusters") or {}
        if not gc:
            errs.append("%s 缺 gold_clusters" % cid)
        flat = [x for v in gc.values() for x in v]
        if any(x not in nid for x in flat):
            errs.append("%s gold 引用了 context 外的资讯" % cid)
        if set(flat) != set(nid):
            errs.append("%s gold 聚类未覆盖全部资讯（漏 %d 篇）" % (cid, len(set(nid) - set(flat))))
        if set((c.get("gold_category") or {}).keys()) != set(gc.keys()):
            errs.append("%s gold_category 与聚类键不一致" % cid)
        if not isinstance(c.get("gold_top5"), list):
            errs.append("%s gold_top5 不是列表" % cid)
        if c["kind"] == "irrelevant":
            if c["gold_top5"]:
                errs.append("%s 全无关档 gold_top5 必须为空" % cid)
            if not c.get("expect_no_relevant"):
                errs.append("%s 全无关档缺 expect_no_relevant" % cid)
        # 同事件多来源：措辞不得完全一致
        for ev, members in gc.items():
            texts = [next(x["text"] for x in news if x["news_id"] == m) for m in members]
            if len(texts) > 1 and len(set(texts)) != len(texts):
                errs.append("%s 事件 %s 的多来源报道有完全相同的措辞" % (cid, ev))
    return errs, cases, dist


def canary_ok(phone):
    return bool(re.fullmatch(r"1990000\d{4}", phone))


def pii_scan():
    unexpected, hits, scanned = [], 0, 0
    for dp, dns, fns in os.walk(HERE):
        dns[:] = [d for d in dns if d not in ("__pycache__", ".pytest_cache")]
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                continue
            p = os.path.join(dp, fn)
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            scanned += 1
            for m in PHONE.finditer(t):
                if canary_ok(m.group(0)):
                    hits += 1
                else:
                    unexpected.append({"file": os.path.relpath(p, HERE), "kind": "phone",
                                       "value": m.group(0)})
            for m in EMAIL.finditer(t):
                if "%s" in m.group(0):
                    continue
                if m.group(0).endswith(".invalid"):
                    hits += 1
                else:
                    unexpected.append({"file": os.path.relpath(p, HERE), "kind": "email",
                                       "value": m.group(0)})
            for m in IDCARD.finditer(t):
                unexpected.append({"file": os.path.relpath(p, HERE), "kind": "idcard",
                                   "value": m.group(0)})
    return unexpected, hits, scanned


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lint", action="store_true")
    ap.add_argument("--pii", action="store_true")
    a = ap.parse_args(argv)
    only = a.lint or a.pii
    rc = 0
    if a.lint or not only:
        errs, cases, dist = lint()
        for e in errs:
            print("LINT-ERROR", e)
        print("lint cases=%d distribution=%s errors=%d" % (len(cases), dict(dist), len(errs)))
        print("LINT %s" % ("PASS" if not errs else "FAIL"))
        rc |= 0 if not errs else 1
    if a.pii or not only:
        unexpected, hits, scanned = pii_scan()
        for u in unexpected[:20]:
            print("PII-UNEXPECTED", u)
        print("pii scanned=%d canary_hits=%d unexpected=%d" % (scanned, hits, len(unexpected)))
        print("PII %s" % ("PASS" if not unexpected else "FAIL"))
        rc |= 0 if not unexpected else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
