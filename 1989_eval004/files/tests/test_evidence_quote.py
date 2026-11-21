# -*- coding: utf-8 -*-
"""AC2：evidence_quote 不在输出原文中时该要点记为 no（mock 测试通过）。

三种情形都要覆盖：
  1. 正常 quote（能在原文里查到）-> 保留模型给的 hit；
  2. quote 是编的（查不到）-> 即使模型判 yes，也必须降级为 no，并记入 evidence_rejected；
  3. quote 为空（判 yes 却没给引用）-> 同样降级为 no。
"""
import json

import pytest

from point_scorer import scorer


SEM = {"point_id": "P1", "desc": "首次响应须在工作日内完成", "match": "semantic", "weight": 1.0}
CASE = {"case_id": "T-EV", "points": [SEM], "forbidden_points": []}
OUT = "首次响应在 2 个工作日内完成。"


def _caller(hit, quote):
    def _c(prompt):
        return json.dumps({"results": [{"point_id": "P1", "hit": hit, "evidence_quote": quote}]},
                          ensure_ascii=False)
    return _c


def test_valid_quote_keeps_yes(prompt_path):
    r = scorer.score_points(CASE, OUT, caller=_caller("yes", "首次响应在 2 个工作日内完成"),
                            prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "yes"
    assert r["evidence_rejected"] == []


def test_fabricated_quote_downgraded_to_no(prompt_path):
    """模型说 yes 但引用一句原文里根本没有的话 -> 必须降级为 no。"""
    r = scorer.score_points(CASE, OUT, caller=_caller("yes", "本方案承诺 24 小时内响应并赔付"),
                            prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "no"
    assert r["score"] == 0.0
    assert len(r["evidence_rejected"]) == 1
    assert r["evidence_rejected"][0]["judged"] == "yes"


def test_partial_with_fabricated_quote_also_downgraded(prompt_path):
    r = scorer.score_points(CASE, OUT, caller=_caller("partial", "我们会尽力而为"),
                            prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "no"


def test_empty_quote_with_yes_downgraded(prompt_path):
    r = scorer.score_points(CASE, OUT, caller=_caller("yes", ""), prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "no"


def test_quote_tolerates_whitespace_but_not_char_change(prompt_path):
    # 多一个空格仍算命中（空白不敏感）
    r1 = scorer.score_points(CASE, OUT, caller=_caller("yes", "首次响应在 2 个工作日内完成 "),
                             prompt_path=prompt_path)
    assert r1["points"][0]["hit"] == "yes"
    # 改一个字就不算（字符敏感）
    r2 = scorer.score_points(CASE, OUT, caller=_caller("yes", "首次响应在 3 个工作日内完成"),
                             prompt_path=prompt_path)
    assert r2["points"][0]["hit"] == "no"


def test_no_hit_does_not_need_quote(prompt_path):
    """判 no 时允许空 quote，不该被当成「引用缺失」而反复扣分。"""
    r = scorer.score_points(CASE, OUT, caller=_caller("no", ""), prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "no"
    assert r["evidence_rejected"] == []


def test_stub_bad_quote_mode_triggers_downgrade(prompt_path):
    """用桩模型的 bad_quote 模式端到端验证：注入一条查不到的引用 -> 全部降级为 no。"""
    from point_scorer import stub_judge
    r = scorer.score_points(CASE, OUT, caller=stub_judge.make_caller("bad_quote"),
                            prompt_path=prompt_path)
    assert r["points"][0]["hit"] == "no"
    assert len(r["evidence_rejected"]) == 1
