# -*- coding: utf-8 -*-
"""AC4：3 次评审结果不一致时用例带 judge_unstable 标记。

另测「多数投票」与「平票取保守」两条规则。
"""
import json

from point_scorer import scorer

SEM = {"point_id": "P1", "desc": "首次响应须在工作日内完成", "match": "semantic", "weight": 1.0}
CASE = {"case_id": "T-S", "points": [SEM], "forbidden_points": []}
OUT = "首次响应在 2 个工作日内完成。"


def _seq(hits, quotes=None):
    """按轮次依次返回不同结论的 caller。"""
    state = {"i": 0}

    def _c(prompt):
        i = state["i"]
        state["i"] += 1
        hit = hits[min(i, len(hits) - 1)]
        q = (quotes or [OUT] * len(hits))[min(i, len(hits) - 1)]
        return json.dumps({"results": [{"point_id": "P1", "hit": hit, "evidence_quote": q}]},
                          ensure_ascii=False)
    return _c


def test_three_identical_rounds_not_unstable(prompt_path):
    r = scorer.score_points(CASE, OUT, caller=_seq(["yes"]), prompt_path=prompt_path)
    assert r["judge_unstable"] is False
    assert r["judge_rounds"] == 3
    assert r["points"][0]["hit"] == "yes"


def test_inconsistent_rounds_marked_unstable(prompt_path):
    """3 轮给出不同结论 -> judge_unstable=True。"""
    r = scorer.score_points(CASE, OUT, caller=_seq(["yes", "no", "partial"]), prompt_path=prompt_path)
    assert r["judge_unstable"] is True


def test_two_vs_one_majority_wins(prompt_path):
    """2 票 yes、1 票 no -> 取 yes；但仍标记 unstable（因为不是全一致）。"""
    r = scorer.score_points(CASE, OUT, caller=_seq(["yes", "yes", "no"]), prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "yes"
    assert r["judge_unstable"] is True


def test_tie_prefers_conservative(prompt_path):
    """平票时取更保守的一个：no > partial > yes（宁可低估命中率）。"""
    r = scorer.score_points(CASE, OUT, caller=_seq(["yes", "no", "partial"]), prompt_path=prompt_path)
    # yes/no/partial 各 1 票 -> 取 no
    assert r["points"][0]["hit"] == "no"


def test_quote_comes_from_adopted_round(prompt_path):
    """quote 必须来自被判为最终结论的那一轮，不能拿别的轮的原文配结论。"""
    hits = ["yes", "yes", "yes"]
    quotes = [OUT, OUT, "完全不存在的句子"]
    r = scorer.score_points(CASE, OUT, caller=_seq(hits, quotes), prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "yes"
    assert r["points"][0]["evidence_quote"] == OUT


def test_unparseable_output_treated_as_no_and_unstable(prompt_path):
    state = {"i": 0}

    def _c(prompt):
        state["i"] += 1
        return "这不是 JSON" if state["i"] == 1 else json.dumps(
            {"results": [{"point_id": "P1", "hit": "yes", "evidence_quote": OUT}]}, ensure_ascii=False)

    r = scorer.score_points(CASE, OUT, caller=_c, prompt_path=prompt_path)
    assert r["judge_unstable"] is True
    assert r["points"][0]["hit"] == "yes"      # 2 票 yes 胜出


def test_rounds_configurable(prompt_path):
    r = scorer.score_points(CASE, OUT, caller=_seq(["yes"]), prompt_path=prompt_path, rounds=5)
    assert r["judge_rounds"] == 5
