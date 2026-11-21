# -*- coding: utf-8 -*-
"""AC1：一致性自检 ≥90% + 逐条对照表；不达标时评分器拒绝启用。"""
import json
import os
import subprocess
import sys

import pytest

import check_consistency as CC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_consistency_meets_threshold():
    rep = CC.run()
    assert rep["samples"] == 30
    assert rep["agreement"] >= 0.90, rep["agreement"]
    assert rep["eligible"] is True


def test_report_has_row_by_row_table():
    rep = CC.run()
    CC.write_report(rep)
    md = open(os.path.join(ROOT, "reports", "consistency.md"), encoding="utf-8").read()
    assert "逐条对照表" in md
    assert md.count("| CONS-") >= 45          # 每条判断一行
    assert "合计一致率" in md


def test_agreement_is_not_perfect_by_construction():
    """一致率不该是 100%：留了真实口径分歧，否则说明样本在迁就实现。"""
    rep = CC.run()
    assert rep["agreement"] < 1.0
    assert rep["total_agree"] < rep["total_judgements"]


def test_gate_raises_when_below_threshold():
    rep = CC.run()
    bad = dict(rep, eligible=False, agreement=0.5)
    with pytest.raises(CC.ScorerNotEligible):
        CC.assert_eligible(bad)


def test_gate_passes_on_real_report():
    assert CC.assert_eligible()["eligible"] is True


def test_cli_exit_code():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_consistency.py")],
                       capture_output=True, cwd=ROOT, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "eligible=True" in r.stdout


def test_human_labels_are_hand_written_not_computed():
    """人工标注必须写死在数据文件里，不能由代码现算 —— 现算等于自己判自己。"""
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "data", "consistency_30.jsonl"),
                                       encoding="utf-8") if l.strip()]
    assert len(rows) == 30
    for r in rows:
        assert "human" in r and r["human"], r["case_id"]
        assert set(r["human"].values()) <= {"yes", "no", "partial"}
    # 人工标签里必须同时出现三档，否则「一致率」只是在测 yes/no
    allv = set()
    for r in rows:
        allv |= set(r["human"].values())
    assert allv == {"yes", "no", "partial"}
