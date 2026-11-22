# -*- coding: utf-8 -*-
"""端到端：指标达标、报告字段齐、三个破坏开关都能把指标打下来。"""
import json
import os
import subprocess
import sys

import eval_run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_dataset_shape():
    cases = eval_run.load_cases()
    assert len(cases) == 35
    from collections import Counter
    c = Counter(x["kind"] for x in cases)
    assert c == {"normal": 20, "high_similarity": 10, "irrelevant": 5}
    for x in cases:
        ctx = eval_run.load_context(x)
        assert 8 <= len(ctx) <= 20, (x["case_id"], len(ctx))


def test_metrics_pass_default():
    m = eval_run.aggregate([eval_run.evaluate_case(c) for c in eval_run.load_cases()])
    assert m["pairwise_f1"] >= 0.80, m["pairwise_f1"]
    assert m["category_accuracy"] >= 0.80, m["category_accuracy"]
    assert m["ndcg_at_5"] >= 0.80, m["ndcg_at_5"]
    assert m["forbidden_same_event_twice"] == 0
    assert m["forbidden_outside_context"] == 0
    assert m["irrelevant_empty_top5"] == m["irrelevant_cases"]
    assert m["fails"] == []


def test_break_cluster_drops_f1():
    m = eval_run.aggregate([eval_run.evaluate_case(c, break_cluster=True)
                            for c in eval_run.load_cases()])
    assert m["pairwise_f1"] < 0.80, m["pairwise_f1"]
    assert m["fails"]


def test_break_order_drops_ndcg():
    m = eval_run.aggregate([eval_run.evaluate_case(c, break_order=True)
                            for c in eval_run.load_cases()])
    assert m["ndcg_at_5"] < 0.80, m["ndcg_at_5"]


def test_leak_triggers_forbidden_outside_context():
    m = eval_run.aggregate([eval_run.evaluate_case(c, leak=True) for c in eval_run.load_cases()])
    assert m["forbidden_outside_context"] >= 35
    assert any("context 之外" in f for f in m["fails"])


def test_report_has_all_sections():
    cases = eval_run.load_cases()
    rows = [eval_run.evaluate_case(c) for c in cases]
    m = eval_run.aggregate(rows)
    md = os.path.join(ROOT, "reports", "triage_test.md")
    eval_run.write_report(m, rows, md, md[:-3] + ".json")
    t = open(md, encoding="utf-8").read()
    for kw in ("聚类 pairwise F1", "分类准确率", "排序 NDCG@5",
               "同一事件在简报中出现两次", "引入 context 之外的资讯",
               "误合并", "漏合并", "阈值敏感性"):
        assert kw in t, kw


def test_cli_ok_and_broken():
    ok = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "eval_run.py")],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert ok.returncode == 0 and "THRESHOLD OK" in ok.stdout
    bad = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "eval_run.py"),
                          "--tag", "ci", "--break-cluster"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert bad.returncode == 1 and "THRESHOLD NOT MET" in bad.stdout


def test_threshold_actually_takes_effect():
    """默认参数陷阱回归测试：改模块级阈值必须真的改变聚类结果。"""
    old = eval_run.SIM_THRESHOLD
    try:
        eval_run.SIM_THRESHOLD = 0.99
        high = eval_run.aggregate([eval_run.evaluate_case(c) for c in eval_run.load_cases()])
        eval_run.SIM_THRESHOLD = 0.10
        low = eval_run.aggregate([eval_run.evaluate_case(c) for c in eval_run.load_cases()])
        assert high["pairwise_f1"] != low["pairwise_f1"]
    finally:
        eval_run.SIM_THRESHOLD = old
