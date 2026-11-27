# -*- coding: utf-8 -*-
"""评分器行为：list 对齐、extra/missing、critical 判定、指标口径。

期望值全部写死，不调用被测函数自己算自己。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import engine  # noqa: E402
import scorer  # noqa: E402

S = engine.SCHEMA
BEST = engine.BEST


def by_id(cid):
    return [c for c in engine.build_cases() if c["id"] == cid][0]


def run(cid):
    c = by_id(cid)
    return scorer.score_fields(c["expected"], c["actual"], S)


# ---------- list 对齐（AC2） ----------
def test_list_plus_one_counts_extra():
    f = run("C20").fields["pay_nodes"]
    assert (f["correct"], f["wrong"], f["missing"], f["extra"]) == (3, 0, 0, 1)


def test_list_minus_one_counts_missing():
    f = run("C21").fields["pay_nodes"]
    assert (f["correct"], f["wrong"], f["missing"], f["extra"]) == (2, 0, 1, 0)


def test_list_same_key_diff_value_is_wrong():
    f = run("C22").fields["pay_nodes"]
    assert (f["correct"], f["wrong"], f["missing"], f["extra"]) == (2, 1, 0, 0)


def test_list_aligned_by_seq_not_by_position():
    """顺序打乱不影响结论 —— 证明是按 seq 对齐而不是按下标。"""
    rev = list(reversed(engine.NODES3))
    fs = scorer.score_fields({"pay_nodes": engine.NODES3}, {"pay_nodes": rev}, S)
    f = fs.fields["pay_nodes"]
    assert (f["correct"], f["wrong"], f["extra"], f["missing"]) == (3, 0, 0, 0)


def test_list_both_empty_no_counts():
    fs = scorer.score_fields({"pay_nodes": []}, {"pay_nodes": []}, S)
    assert "pay_nodes" not in fs.fields or not any(fs.fields["pay_nodes"].values())


def test_list_expected_empty_actual_two_all_extra():
    f = run("C34").fields["pay_nodes"]
    assert (f["correct"], f["extra"]) == (0, 2)


# ---------- 金额 / critical（AC3） ----------
def test_money_one_fen_is_wrong():
    f = run("C09").fields["total_amount"]
    assert (f["correct"], f["wrong"]) == (0, 1)


def test_money_equal_is_correct():
    assert run("C08").fields["total_amount"]["correct"] == 1


param_crit = ["C09", "C10", "C15", "C28", "C29"]


@pytest.mark.parametrize("cid", param_crit)
def test_critical_error_fails_case(cid):
    assert run(cid).passed() is False


@pytest.mark.parametrize("cid", param_crit)
def test_critical_hit_recorded(cid):
    assert run(cid).critical_hit


def test_critical_missing_counts_missing():
    f = run("C28").fields["total_amount"]
    assert (f["correct"], f["missing"]) == (0, 1)


def test_noncritical_single_error_still_passes():
    """正向对照：非 critical 单错时 F1 仍高于 0.8，用例通过。"""
    fs = run("C04")
    assert fs.critical_hit == []
    assert fs.passed() is True


def test_many_errors_fails_by_threshold():
    fs = run("C31")
    assert fs.critical_hit == []
    assert fs.passed() is False


# ---------- summary ----------
def test_summary_structured_all_hit():
    f = run("C23").fields["summary"]
    assert (f["correct"], f["missing"], f["extra"]) == (3, 0, 0)


def test_summary_structured_missing_point():
    f = run("C24").fields["summary"]
    assert (f["correct"], f["missing"]) == (2, 1)


def test_summary_structured_extra_point():
    f = run("C26").fields["summary"]
    assert (f["correct"], f["extra"]) == (3, 1)


def test_summary_free_text_counts_recall_only():
    f = run("C25").fields["summary"]
    assert f["correct"] == 3 and f["missing"] == 0


def test_summary_free_text_notes_precision_not_applicable():
    assert any("precision 不适用" in n for n in run("C25").notes)


# ---------- 指标口径（AC4 的自证侧） ----------
def test_metrics_formula_hand_checked():
    """correct=6,wrong=2,missing=2,extra=0 → P=.75 R=.6 F1=2/3=0.666666..."""
    m = scorer.FieldScore.metrics(6, 2, 2, 0)
    assert round(m["precision"], 12) == 0.75
    assert round(m["recall"], 12) == 0.6
    assert round(m["f1"], 12) == 0.666666666667


def test_metrics_wrong_counts_in_both_denominators():
    m = scorer.FieldScore.metrics(0, 4, 0, 0)
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0


def test_metrics_all_correct_is_one():
    m = scorer.FieldScore.metrics(9, 0, 0, 0)
    assert (m["precision"], m["recall"], m["f1"]) == (1.0, 1.0, 1.0)


def test_metrics_empty_is_zero_not_error():
    m = scorer.FieldScore.metrics(0, 0, 0, 0)
    assert (m["precision"], m["recall"], m["f1"]) == (0.0, 0.0, 0.0)


def test_overall_equals_sum_of_fields():
    fs = run("C31")
    tot = sum(sum(fs.fields[k].values()) for k in fs.fields)
    o = fs.overall()
    assert tot == o["correct"] + o["wrong"] + o["missing"] + o["extra"]


def test_unknown_field_type_notes_not_crash():
    fs = scorer.score_fields({"x": 1}, {"x": 1}, {"x": {"type": "weird"}})
    assert any("未知字段类型" in n for n in fs.notes)
