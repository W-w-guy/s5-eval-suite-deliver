# -*- coding: utf-8 -*-
"""字段准确率与错字段标红召回的手算用例。"""
import pytest

from doc_eval import metrics as M

GOLD = {"a": 1, "b": 2, "c": "x"}


@pytest.mark.parametrize("pred,expect", [
    ({"a": 1, "b": 2, "c": "x"}, 1.0),               # 3/3
    ({"a": 1, "b": 2, "c": "y"}, 2 / 3),             # 2/3
    ({"a": 0, "b": 0, "c": "y"}, 0.0),
])
def test_field_accuracy_handcalc(pred, expect):
    # 实现把 accuracy round 到 6 位小数，容差要匹配这个精度（不是 1e-9）
    assert abs(M.field_accuracy(GOLD, pred)["accuracy"] - expect) < 1e-6


def test_norm_field_number_strips_units():
    assert M.norm_field("amount_total", "1,234.50 元") == 1234.5
    assert M.norm_field("amount_total", 1234.5) == 1234.5


def test_norm_field_chinese_date():
    assert M.norm_field("service_start", "2026年3月1日") == "2026-03-01"
    assert M.norm_field("service_start", "2026-03-01") == "2026-03-01"


def test_flag_recall_handcalc():
    """3 个错字段（a, c 错，b 对），标红 a -> 召回 1/2。"""
    gold = {"a": 1, "b": 2, "c": "x"}
    pred = {"a": 9, "b": 2, "c": "y"}
    r = M.flag_recall(gold, pred, {"a"})
    assert r["wrong_total"] == 2
    assert abs(r["recall"] - 0.5) < 1e-9
    assert r["wrong_unflagged"] == ["c"]


def test_flag_recall_full():
    gold = {"a": 1, "c": "x"}
    pred = {"a": 9, "c": "y"}
    r = M.flag_recall(gold, pred, {"a", "c"})
    assert r["recall"] == 1.0 and not r["wrong_unflagged"]


def test_flag_recall_no_wrong_fields_is_one():
    """没有识别错误时召回记 1.0（空集不扣分），这是口径约定。"""
    r = M.flag_recall({"a": 1}, {"a": 1}, set())
    assert r["recall"] == 1.0 and r["wrong_total"] == 0


def test_false_flag_counted_separately():
    """识别正确却被标红 -> 记在 right_but_flagged，不进召回分母。"""
    r = M.flag_recall({"a": 1, "b": 2}, {"a": 1, "b": 9}, {"a", "b"})
    assert r["wrong_total"] == 1
    assert r["recall"] == 1.0
    assert r["right_but_flagged"] == ["a"]
