# -*- coding: utf-8 -*-
"""AC3（gold_doc_ids 都能在知识文档中找到）+ AC4（报告显示 recall@5 与引用准确率）
+ 指标本身可被证伪。
"""
import json
import os
import subprocess
import sys

import pytest

import eval_run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_gold_docs_all_exist():
    docs = {d["doc_id"] for d in eval_run.load_docs()}
    cases = [json.loads(l) for l in open(os.path.join(ROOT, "data", "cases.jsonl"),
                                         encoding="utf-8") if l.strip()]
    assert len(cases) == 50
    for c in cases:
        for g in c["gold_doc_ids"]:
            assert g in docs, (c["case_id"], g)


def test_metrics_meet_thresholds():
    m, rows = eval_run.evaluate()
    assert m["recall_at_5"] >= 0.85, m["recall_at_5"]
    assert m["point_hit"] >= 0.80, m["point_hit"]
    assert m["citation_accuracy"] >= 0.95, m["citation_accuracy"]
    assert m["forbidden_cite_not_in_retrieval"] == 0
    assert m["forbidden_number_mismatch"] == 0
    assert m["fails"] == []


def test_report_contains_required_metrics():
    m, rows = eval_run.evaluate()
    md = os.path.join(ROOT, "reports", "kqa_test.md")
    eval_run.write_report(m, rows, md, md[:-3] + ".json")
    t = open(md, encoding="utf-8").read()
    assert "recall@5" in t
    assert "答案要点命中率" in t
    assert "引用准确率" in t
    assert "forbidden_points" in t


def test_break_citation_really_breaks_it():
    """证明引用准确率不是恒等于 1：故意引错文档后必须掉下来且触发 forbidden。"""
    m, _ = eval_run.evaluate(break_citation=True)
    assert m["citation_accuracy"] < 0.95, m["citation_accuracy"]
    assert m["fails"], "应该报未达标"
    assert m["forbidden_number_mismatch"] > 0


def test_support_rejects_wrong_number():
    body = "受理后 2 个工作日内响应。"
    assert eval_run.support(body, "受理后 2 个工作日内响应")
    assert not eval_run.support(body, "受理后 5 个工作日内响应")


def test_support_rejects_unrelated_doc():
    body = "A 区 3 层的开放时间为 07:00-22:00。"
    assert not eval_run.support(body, "财税咨询面向高级会籍会员提供，包含受理与反馈三个环节")


POINT = "受理后 2 个工作日内响应；材料不齐的一次性告知补正"


def test_point_hit_full_coverage():
    """回答里完整包含该要点 -> 命中。"""
    ans = "回答：" + POINT + "。另外还有别的。"
    assert eval_run.point_hit(ans, POINT)


def test_point_hit_rejects_wrong_number():
    """要点里的数字在回答里找不到 -> 一定不命中（数字错就是错）。"""
    assert not eval_run.point_hit("受理后 9 个工作日内响应；材料不齐的一次性告知补正", POINT)


def test_point_hit_strict_on_partial_answer():
    """只答了要点的一半（缺「材料不齐告知补正」）-> 判不命中。

    口径是「偏严」的：宁可低估命中率，也不要放过只答一半的回答。
    这条行为是刻意设计，不是缺陷 —— 评测指标放松比收紧危险得多。
    """
    assert not eval_run.point_hit("受理后 2 个工作日内响应", POINT)


def test_recall_hit_definition():
    """recall@5：gold 里任意一篇进前 5 即算命中。"""
    m, rows = eval_run.evaluate()
    for r in rows:
        expect = bool(set(r["gold_doc_ids"]) & set(r["retrieved"]))
        assert r["recall_hit"] == expect


def test_cli_ok_and_bad_modes():
    ok = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "eval_run.py")],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert ok.returncode == 0 and "THRESHOLD OK" in ok.stdout
    bad = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "eval_run.py"),
                          "--break-citation", "--tag", "ci_bad"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert bad.returncode == 1 and "THRESHOLD NOT MET" in bad.stdout
