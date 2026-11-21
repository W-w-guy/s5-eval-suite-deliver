# -*- coding: utf-8 -*-
"""recall@3 / MRR / 理由有据 的手算用例（期望值在注释里写出算式）。"""
import pytest

from match_eval import metrics as M


# ---------- recall@K ----------
@pytest.mark.parametrize("gold,ranked,k,expect", [
    (["A"], ["A"], 3, 1.0),                       # 1/1
    (["A"], ["B", "A"], 3, 1.0),                  # 命中 1 个 / gold 1 个
    (["A", "B"], ["A"], 3, 0.5),                  # 命中 1 / gold 2
    (["A", "B"], ["A", "B"], 3, 1.0),
    (["A", "B"], ["B", "A"], 3, 1.0),             # 顺序不影响 recall
    (["A"], ["B", "C", "D", "A"], 3, 0.0),        # 第 4 名不算进 @3
    (["A"], ["B", "C", "D", "A"], 4, 1.0),
])
def test_recall_at_k(gold, ranked, k, expect):
    assert abs(M.recall_at_k(gold, ranked, k) - expect) < 1e-9


# ---------- MRR ----------
@pytest.mark.parametrize("gold,ranked,expect", [
    (["A"], ["A"], 1.0),                          # 1/1
    (["A"], ["B", "A"], 0.5),                     # 1/2
    (["A"], ["B", "C", "A"], 1 / 3),
    (["A"], ["B", "C"], 0.0),                     # 无命中
    (["A", "B"], ["B", "A"], 1.0),                # 第一个命中在第 1 位
])
def test_mrr(gold, ranked, expect):
    assert abs(M.mrr(gold, ranked) - expect) < 1e-9


# ---------- 理由有据 ----------
CANDS = {
    "R1": {"industry": "节能环保工程", "service_type": "股权投资",
           "stage_pref": "A轮", "site": "站点一"},
}


def test_reason_grounded_when_all_fields_match():
    r = "行业：节能环保工程，服务类型：股权投资，阶段：A轮，站点：站点一。"
    g = M.grounded(r, CANDS["R1"])
    assert g["ok"] and not g["unsupported"], g


def test_reason_unsupported_when_field_wrong():
    r = "行业：医疗器械代理，服务类型：股权投资。"
    g = M.grounded(r, CANDS["R1"])
    assert not g["ok"]
    assert g["unsupported"][0]["field"] == "industry"
    assert g["unsupported"][0]["cited"] == "医疗器械代理"


def test_reason_unsupported_when_value_not_present():
    g = M.grounded("行业：节能环保工程，服务类型：法律咨询。", CANDS["R1"])
    assert not g["ok"]
    assert any(x["field"] == "service_type" for x in g["unsupported"])


def test_point_score_counts_missing_and_unsupported():
    reasons = {"R1": "行业：节能环保工程，服务类型：股权投资，阶段：A轮，站点：站点一。"}
    ps = M.point_score(reasons, CANDS, ["R1", "R2"])
    assert ps["ok"] == 1 and ps["missing"] == 1
    assert abs(ps["score"] - 0.5) < 1e-9


def test_point_score_all_missing_is_zero():
    ps = M.point_score({}, CANDS, ["R1"])
    assert ps["score"] == 0.0 and ps["missing"] == 1
