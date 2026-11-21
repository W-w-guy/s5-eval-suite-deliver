# -*- coding: utf-8 -*-
"""模型地址禁境外（单子硬要求）+ 金额类要点只走 exact_field。"""
import pytest

from point_scorer import model, scorer


@pytest.mark.parametrize("url,ok", [
    ("http://127.0.0.1:8080", True),
    ("http://localhost:8080", True),
    ("http://10.1.2.3:8080", True),
    ("http://192.168.1.9:8080", True),
    ("http://172.17.0.2:8080", True),
    ("http://judge.internal:8080", True),
    ("http://judge.lan:8080", True),
    ("https://api.openai.com", False),
    ("https://api.anthropic.com/v1", False),
    ("http://8.8.8.8:8080", False),
    ("https://judge.example.com", False),
    ("ftp://127.0.0.1", False),
    ("", False),
])
def test_endpoint_policy(url, ok):
    if ok:
        assert model.check_endpoint(url) == url
    else:
        with pytest.raises(model.RejectEndpoint):
            model.check_endpoint(url)


def test_unset_env_is_rejected_not_defaulted(monkeypatch):
    """未设置也必须拒绝 —— 静默 fallback 到某个默认公有云是最危险的行为。"""
    monkeypatch.delenv(model.ENV_URL, raising=False)
    with pytest.raises(model.RejectEndpoint):
        model.check_endpoint()


def test_foreign_endpoint_blocks_scoring_before_request(monkeypatch, prompt_path):
    """走真实 HTTP 路径时，境外地址必须在校验阶段就失败，不能先发请求再说。"""
    monkeypatch.setenv(model.ENV_URL, "https://api.openai.com/v1")
    sem = {"point_id": "P1", "desc": "首次响应时限", "match": "semantic", "weight": 1.0}
    case = {"case_id": "T-E", "points": [sem], "forbidden_points": []}
    with pytest.raises(model.RejectEndpoint):
        scorer.score_points(case, "首次响应 2 个工作日", prompt_path=prompt_path)


def test_amount_point_must_use_exact_field(prompt_path):
    """评审模型不判金额：语义要点若判金额，模型按提示词必须给 no，由程序接管。"""
    from point_scorer import stub_judge
    sem = {"point_id": "P1", "desc": "报价金额为 128000 元", "match": "semantic", "weight": 1.0}
    case = {"case_id": "T-A", "points": [sem], "forbidden_points": []}
    r = scorer.score_points(case, "报价金额为 128000 元", caller=stub_judge.make_caller(),
                            prompt_path=prompt_path)
    # 模型侧一律 no，且不该因为「原文里有这个数字」而被当成命中
    assert r["points"][0]["hit"] == "no"


def test_prompt_forbids_amount_judgement():
    """提示词里必须显式写「不判断金额」，否则约束只存在于代码里。"""
    import os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "prompts", "judge_prompt_v1.2.0.txt")
    t = open(p, encoding="utf-8").read()
    assert "不判断金额" in t
    assert "exact_field" in t or "严格相等" in t
    assert "evidence_quote" in t and "逐字" in t
