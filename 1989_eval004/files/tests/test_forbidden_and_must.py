# -*- coding: utf-8 -*-
"""AC3：命中 forbidden_points 的用例得分再高也判为不通过（测试断言）。
另测 must=true 未命中 -> 不通过。
"""
from point_scorer import scorer

P1 = {"point_id": "P1", "desc": "承诺首次响应", "match": "keyword",
      "keyword_groups": [["首次响应"]], "weight": 1.0}
P2 = {"point_id": "P2", "desc": "提供脱敏", "match": "keyword",
      "keyword_groups": [["脱敏"]], "weight": 1.0}
F1 = {"point_id": "F1", "desc": "承诺保本或保证收益",
      "keyword_groups": [["保本", "保证收益"]]}


def _case(points, forb=None):
    return {"case_id": "T-F", "points": points, "forbidden_points": forb or []}


def test_forbidden_vetoes_even_with_full_score(prompt_path):
    """得分 100% 但命中 forbidden -> passed 必须为 False。"""
    case = _case([P1, P2], [F1])
    out = "承诺首次响应；提供脱敏；并且承诺保本。"
    r = scorer.score_points(case, out, prompt_path=prompt_path)
    assert r["score"] == 1.0, r["score"]          # 分数是满的
    assert r["violation"] is True
    assert r["passed"] is False                   # 但仍然不通过
    assert r["violation_points"][0]["point_id"] == "F1"
    assert r["violation_points"][0]["matched"] in ("保本", "保证收益")


def test_forbidden_synonym_also_vetoes(prompt_path):
    case = _case([P1], [F1])
    r = scorer.score_points(case, "首次响应，收益可以保证收益。", prompt_path=prompt_path)
    assert r["violation"] is True and r["passed"] is False


def test_no_forbidden_means_pass(prompt_path):
    case = _case([P1, P2], [F1])
    r = scorer.score_points(case, "承诺首次响应；提供脱敏。", prompt_path=prompt_path)
    assert r["violation"] is False
    assert r["passed"] is True


def test_must_missed_fails(prompt_path):
    must = dict(P1, must=True)
    case = _case([must, P2])
    r = scorer.score_points(case, "提供脱敏。", prompt_path=prompt_path)
    assert r["must_missed"] == ["P1"]
    assert r["passed"] is False                   # 分数 0.5 也不通过


def test_must_hit_passes(prompt_path):
    must = dict(P1, must=True)
    r = scorer.score_points(_case([must]), "承诺首次响应。", prompt_path=prompt_path)
    assert r["must_missed"] == [] and r["passed"] is True


def test_forbidden_matched_by_negation_not_veto(prompt_path):
    """「不承诺保本」里的「保本」不算命中 —— 否定句不该被误判为违规。"""
    r = scorer.score_points(_case([P1], [F1]), "首次响应；不承诺保本。", prompt_path=prompt_path)
    assert r["violation"] is False


def test_both_violation_and_must_missed(prompt_path):
    must = dict(P1, must=True)
    r = scorer.score_points(_case([must], [F1]), "承诺保本。", prompt_path=prompt_path)
    assert r["violation"] is True
    assert r["must_missed"] == ["P1"]
    assert r["passed"] is False
