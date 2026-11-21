# -*- coding: utf-8 -*-
"""端到端：分布、指标达标、三个破坏方向都能被抓到。"""
import json
import os
import subprocess
import sys

import match_eval.__main__ as R
from match_eval import metrics as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_dataset_shape():
    cs = R.load_cases()
    assert len(cs) == 35
    from collections import Counter
    c = Counter(x["kind"] for x in cs)
    assert c == {"normal": 20, "trap": 9, "none": 6}, c
    sizes = [len(R.load_ctx(x)) for x in cs]
    assert min(sizes) >= 8 and max(sizes) <= 15, (min(sizes), max(sizes))


def test_nine_cases_have_forbidden_points():
    cs = R.load_cases()
    with_f = [x for x in cs if x["forbidden_points"]]
    assert len(with_f) == 9
    for x in with_f:
        assert x["forbidden_points"], x["case_id"]


def test_trap_resource_really_looks_matching():
    """陷阱资源必须「看起来非常匹配」——否则不构成陷阱。"""
    for c in R.load_cases():
        if c["kind"] != "trap":
            continue
        cands = {x["resource_id"]: x for x in R.load_ctx(c)}
        need = c["need"]
        for f in c["forbidden_points"]:
            x = cands[f["resource_id"]]
            assert x["industry"] == need["industry"]
            assert x["service_type"] == need["service_type"]
            assert x["opt_out"] or need["member_id"] in x["conflict_with"]


def test_metrics_pass_default():
    cs = R.load_cases()
    m = R.aggregate([R.evaluate_case(c) for c in cs])
    assert m["recall_at_3"] >= 0.80, m["recall_at_3"]
    assert m["mrr"] >= 0.70, m["mrr"]
    assert m["reason_support"] >= 0.90, m["reason_support"]
    assert m["forbidden_violations"] == 0
    assert m["no_match_correct"] == m["no_gold"] == 6
    assert m["fails"] == []


def test_break_optout_triggers_forbidden():
    cs = R.load_cases()
    m = R.aggregate([R.evaluate_case(c, ignore_exclusion=True) for c in cs])
    assert m["forbidden_violations"] > 0
    assert any("被排除的资源" in f for f in m["fails"])


def test_break_reason_drops_reason_score():
    cs = R.load_cases()
    m = R.aggregate([R.evaluate_case(c, fake_reason=True) for c in cs])
    assert m["reason_support"] < 0.90, m["reason_support"]


def test_core_match_required_for_no_match_cases():
    """无合适资源时必须输出「暂无合适匹配」：核心匹配是必要条件。"""
    for c in R.load_cases():
        if not c["expect_no_match"]:
            continue
        need = c["need"]
        for x in R.load_ctx(c):
            core = int(x["industry"] == need["industry"]) + int(x["service_type"] == need["service_type"])
            assert core == 0, (c["case_id"], x["resource_id"])


def test_report_has_required_sections():
    cs = R.load_cases()
    rows = [R.evaluate_case(c) for c in cs]
    m = R.aggregate(rows)
    md = os.path.join(ROOT, "reports", "match_test.md")
    R.write_report(m, rows, md, md[:-3] + ".json")
    t = open(md, encoding="utf-8").read()
    for kw in ("recall@3", "MRR", "推荐理由有据率", "被排除资源", "暂无合适匹配"):
        assert kw in t, kw


def test_cli_ok_and_breaks():
    def _cli(*args):
        return subprocess.run([sys.executable, "-m", "match_eval", *args],
                              capture_output=True, cwd=ROOT, text=True,
                              encoding="utf-8", errors="replace")
    ok = _cli()
    assert ok.returncode == 0 and "THRESHOLD OK" in ok.stdout
    b1 = _cli("--break-optout", "--tag", "ci")
    assert b1.returncode == 1
    b2 = _cli("--break-reason", "--tag", "ci2")
    assert b2.returncode == 1
