# -*- coding: utf-8 -*-
"""端到端：数据形状、指标达标、两个破坏开关各自触发对应失败。"""
import json
import os
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from multiturn import __main__ as R   # noqa: E402
from multiturn import metrics as M    # noqa: E402


def _cli(*a):
    return subprocess.run([sys.executable, "-m", "multiturn", *a], capture_output=True,
                          cwd=ROOT, text=True, encoding="utf-8", errors="replace")


def test_cases_shape():
    cs = R.load_cases()
    assert len(cs) == 30
    c = Counter(x["kind"] for x in cs)
    assert c == {"coref": 8, "condition_change": 8, "topic_switch": 6, "correction": 8}, c
    for x in cs:
        assert 3 <= len(x["turns"]) <= 5


def test_kb_fixture_reused():
    facts = R.load_facts()
    assert len(facts) == 120
    for c in R.load_cases():
        if c.get("kb_doc"):
            assert c["kb_doc"] in facts


def test_metrics_pass_default():
    cs = R.load_cases()
    facts = R.load_facts()
    rows = [R.evaluate(c, facts) for c in cs]
    m = M.aggregate(rows)
    assert m["final_point_hit"] >= 0.80, m["final_point_hit"]
    assert m["checkpoint_pass"] >= 1.00, m["checkpoint_pass"]
    assert m["forbidden_violations"] == 0
    assert m["fails"] == []


def test_break_history_drops_multi_turn_ability():
    cs = R.load_cases()
    facts = R.load_facts()
    rows = [R.evaluate(c, facts, break_history=True) for c in cs]
    m = M.aggregate(rows)
    assert m["final_point_hit"] < 0.80, m["final_point_hit"]
    assert m["fails"]


def test_break_stale_triggers_forbidden():
    cs = R.load_cases()
    facts = R.load_facts()
    rows = [R.evaluate(c, facts, break_stale=True) for c in cs]
    m = M.aggregate(rows)
    assert m["forbidden_violations"] > 0
    assert any("forbidden" in f for f in m["fails"])


def test_cli_ok_and_breaks():
    assert _cli().returncode == 0
    assert _cli("--break-history", "--tag", "ci1").returncode == 1
    assert _cli("--break-stale", "--tag", "ci2").returncode == 1


def test_report_written():
    _cli()
    md = os.path.join(ROOT, "reports", "mt_v1.md")
    assert os.path.isfile(md)
    t = open(md, encoding="utf-8").read()
    for kw in ("最后一轮要点命中率", "中间检查点通过率", "forbidden 违反次数", "按轮次可见的检查点"):
        assert kw in t, kw
