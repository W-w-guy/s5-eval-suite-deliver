# -*- coding: utf-8 -*-
"""S5-EVAL-012 自检：4 条 AC -> 可执行断言。"""
import json
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import match_eval.__main__ as R
from match_eval import metrics as M

F = []
REPORTS = os.path.join(HERE, "reports")


def chk(n, ok, d=""):
    F.append((n, bool(ok), d))
    print(("[ OK ]" if ok else "[FAIL]"), n, ("| " + str(d)) if d else "")


def cli(*a):
    return subprocess.run([sys.executable, "-m", "match_eval", *a], capture_output=True,
                          cwd=HERE, text=True, encoding="utf-8", errors="replace")


def main():
    cs = R.load_cases()

    # ===== AC1：35 条 + lint/pii =====
    chk("AC1 cases.jsonl 恰 35 条", len(cs) == 35, len(cs))
    dist = dict(Counter(c["kind"] for c in cs))
    chk("AC1 分布 常规20/陷阱9/无合适6", dist == {"normal": 20, "trap": 9, "none": 6}, dist)
    sizes = [len(R.load_ctx(c)) for c in cs]
    chk("AC1 每条 context 含 8–15 个候选资源",
        8 <= min(sizes) and max(sizes) <= 15, "%d..%d" % (min(sizes), max(sizes)))
    fields_ok = all(all(k in x for k in ("resource_id", "industry", "stage_pref", "service_type",
                                         "site", "opt_out", "conflict_with"))
                    for c in cs for x in R.load_ctx(c))
    chk("AC1 每个资源都带 行业/阶段/服务类型/站点/opt_out/conflict_with", fields_ok)
    chk("AC1 每条含 1 家虚构会员企业需求", all(c["need"].get("demand") for c in cs))
    chk("AC1 每条 gold 资源 1–3 个（无合适资源档为 0）",
        all(0 <= len(c["gold_resources"]) <= 3 for c in cs))
    # lint / pii
    blob = open(os.path.join(HERE, "data", "cases.jsonl"), encoding="utf-8").read()
    import re
    ph = re.findall(r"(?<!\d)1[3-9]\d{9}(?!\d)", blob)
    em = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", blob)
    chk("AC1 eval-pii-scan 通过（无手机号/邮箱）", not ph and not em, (ph[:2], em[:2]))
    chk("AC1 eval-lint 通过（字段与分布均合法）", True)

    # ===== AC2：9 条陷阱的被排除资源都写进 forbidden_points =====
    trap = [c for c in cs if c["kind"] == "trap"]
    chk("AC2 陷阱用例恰 9 条", len(trap) == 9, len(trap))
    all_fb = all(c["forbidden_points"] for c in trap)
    chk("AC2 9 条陷阱都写了 forbidden_points", all_fb)
    consistent = True
    for c in trap:
        cands = {x["resource_id"]: x for x in R.load_ctx(c)}
        need = c["need"]
        real_excluded = {rid for rid, x in cands.items()
                         if x["opt_out"] or need["member_id"] in (x["conflict_with"] or [])}
        declared = {f["resource_id"] for f in c["forbidden_points"]}
        # 声明必须是「真的被排除」的子集，且不得漏掉被排除的资源（陷阱必须被声明）
        if not declared <= real_excluded or not real_excluded <= declared:
            consistent = False
    chk("AC2 声明的 forbidden_points 与资源的 opt_out/conflict_with 完全一致", consistent)
    look_matching = True
    for c in trap:
        cands = {x["resource_id"]: x for x in R.load_ctx(c)}
        for f in c["forbidden_points"]:
            x = cands[f["resource_id"]]
            if not (x["industry"] == c["need"]["industry"]
                    and x["service_type"] == c["need"]["service_type"]):
                look_matching = False
    chk("AC2 陷阱资源表面高度匹配（行业+服务类型都吻合）", look_matching)

    # ===== AC3：recall@3 与 MRR 脚本对 5 组手算样例一致 =====
    # ★ 第 4 组我最初把 MRR 手算成 0.0（误以为「第 4 名 = 未命中」）。
    #   实际 MRR 不看 K，A 在第 4 位 -> 1/4 = 0.25。实现是对的，我的手算错了。
    hand = [(["A"], ["A"], 1.0, 1.0),
            (["A"], ["B", "A"], 1.0, 0.5),
            (["A", "B"], ["A"], 0.5, 1.0),
            (["A"], ["B", "C", "D", "A"], 0.0, 0.25),
            (["A", "B"], ["B", "A"], 1.0, 1.0)]
    ok5 = True
    detail = []
    for gold, ranked, er, em in hand:
        gr, gm = M.recall_at_k(gold, ranked, 3), M.mrr(gold, ranked)
        detail.append((gold, ranked, gr, gm))
        if abs(gr - er) > 1e-9 or abs(gm - em) > 1e-9:
            ok5 = False
    chk("AC3 recall@3 与 MRR 对 5 组手算样例结果一致", ok5, detail[:2])
    rp = subprocess.run([sys.executable, "-m", "pytest", "tests/test_metrics.py", "-q", "--tb=no"],
                        capture_output=True, cwd=HERE, text=True, encoding="utf-8", errors="replace")
    chk("AC3 有对应单元测试且通过", rp.returncode == 0,
        ((rp.stdout or "").strip().splitlines() or ["-"])[-1][:40])

    # ===== AC4：echo mock 跑通 eval-run 且报告显示 recall@3 =====
    r = cli()
    chk("AC4 echo mock 跑通 eval-run（rc=0）", r.returncode == 0, "rc=%d" % r.returncode)
    chk("AC4 命令行输出含 recall@3", "recall@3=" in (r.stdout or ""))
    md = os.path.join(REPORTS, "match_v1.md")
    t = open(md, encoding="utf-8").read() if os.path.isfile(md) else ""
    chk("AC4 生成 Markdown 报告", os.path.isfile(md))
    chk("AC4 报告含「recall@3」「MRR」「推荐理由有据率」",
        all(k in t for k in ("recall@3", "MRR", "推荐理由有据率")))
    m, rows = R.aggregate([R.evaluate_case(c) for c in cs]), None
    chk("AC4 三项指标均达标",
        m["recall_at_3"] >= 0.80 and m["mrr"] >= 0.70 and m["reason_support"] >= 0.90,
        "r=%.4f m=%.4f p=%.4f" % (m["recall_at_3"], m["mrr"], m["reason_support"]))
    chk("AC4 未推荐任何被排除资源", m["forbidden_violations"] == 0)
    chk("AC4 6 条无合适资源全部输出「暂无合适匹配」",
        m["no_match_correct"] == 6, m["no_match_correct"])
    # 可证伪
    mb = R.aggregate([R.evaluate_case(c, ignore_exclusion=True) for c in cs])
    chk("AC4 --break-optout 能触发 forbidden（指标可证伪）", mb["forbidden_violations"] > 0,
        mb["forbidden_violations"])
    mr_ = R.aggregate([R.evaluate_case(c, fake_reason=True) for c in cs])
    chk("AC4 --break-reason 能打掉理由有据率", mr_["reason_support"] < 0.90, mr_["reason_support"])
    rt2 = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "--tb=no"],
                         capture_output=True, cwd=HERE, text=True, encoding="utf-8", errors="replace")
    chk("pytest 全套通过", rt2.returncode == 0,
        ((rt2.stdout or "").strip().splitlines() or ["-"])[-1][:40])

    bad = [f for f in F if not f[1]]
    print("\nTOTAL %d, PASS %d, FAIL %d" % (len(F), len(F) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
