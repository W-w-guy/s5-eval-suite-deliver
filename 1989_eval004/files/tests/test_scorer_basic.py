# -*- coding: utf-8 -*-
"""三种 match 方式的基本行为。"""
import pytest

from point_scorer import scorer, stub_judge

KW = {"point_id": "P1", "desc": "承诺首次响应时限", "match": "keyword",
      "keyword_groups": [["首次响应", "首响"]], "weight": 1.0}


def _case(points, forbidden=None):
    return {"case_id": "T-1", "points": points, "forbidden_points": forbidden or []}


def test_keyword_hit(prompt_path):
    r = scorer.score_points(_case([KW]), "承诺首次响应在 2 个工作日内", prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "yes"
    assert r["score"] == 1.0


def test_keyword_miss(prompt_path):
    r = scorer.score_points(_case([KW]), "本方案聚焦性能优化", prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "no"
    assert r["score"] == 0.0
    assert r["passed"] is False


def test_keyword_synonym(prompt_path):
    """同义词表生效：「首响」应等同「首次响应」。"""
    r = scorer.score_points(_case([KW]), "首响 1 个工作日内", prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "yes"


def test_keyword_negation_not_hit(prompt_path):
    """「不涉及脱敏」里确实有「脱敏」两个字，但不能算命中。"""
    p = {"point_id": "P1", "desc": "提供脱敏", "match": "keyword",
         "keyword_groups": [["脱敏"]], "weight": 1.0}
    r = scorer.score_points(_case([p]), "本方案不涉及脱敏", prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "no"


def test_exact_field_strict(prompt_path):
    p = {"point_id": "P1", "desc": "报价金额（分）", "match": "exact_field",
         "field": "amount_cents", "expected_value": 12800000, "weight": 1.0}
    ok = scorer.score_points(_case([p]), {"amount_cents": 12800000}, prompt_path=prompt_path)
    assert ok["points"][0]["hit"] == "yes"
    # 少两个 0 必须判 no（金额类绝不做四舍五入或宽松比较）
    bad = scorer.score_points(_case([p]), {"amount_cents": 128000}, prompt_path=prompt_path)
    assert bad["points"][0]["hit"] == "no"
    # 字符串 "12800000" != 整数 12800000
    s = scorer.score_points(_case([p]), {"amount_cents": "12800000"}, prompt_path=prompt_path)
    assert s["points"][0]["hit"] == "no"


def test_semantic_partial_counts_half(prompt_path):
    p = {"point_id": "P1", "desc": "首次响应须在工作日内完成", "match": "semantic", "weight": 1.0}
    r = scorer.score_points(_case([p]), "收到需求后尽快响应", prompt_path=prompt_path,
                            caller=stub_judge.make_caller())
    assert r["points"][0]["hit"] == "partial"
    assert abs(r["score"] - 0.5) < 1e-9


def test_unknown_match_raises(prompt_path):
    p = {"point_id": "P1", "desc": "x", "match": "magic", "weight": 1.0}
    with pytest.raises(ValueError):
        scorer.score_points(_case([p]), "x", prompt_path=prompt_path)


def test_score_is_weighted(prompt_path):
    """得分 = Σ 命中权重 ÷ 要点数权重（yes=1、partial=0.5）。"""
    a = {"point_id": "P1", "desc": "承诺首次响应", "match": "keyword",
         "keyword_groups": [["首次响应"]], "weight": 2.0}
    b = {"point_id": "P2", "desc": "提供脱敏", "match": "keyword",
         "keyword_groups": [["脱敏"]], "weight": 1.0}
    r = scorer.score_points(_case([a, b]), "承诺首次响应；不做脱敏", prompt_path=prompt_path)
    # 命中 2.0 / 总权重 3.0
    assert abs(r["score"] - 2.0 / 3.0) < 1e-6
