# -*- coding: utf-8 -*-
"""指标手算用例（要点命中 / 检查点 / forbidden）。"""
import pytest

from multiturn import metrics as M


# ---------- 要点命中 ----------
def test_point_hit_exact():
    assert M.point_hit("开放时间 07:00-22:00", "该场地开放时间 07:00-22:00。")


def test_point_hit_requires_numbers():
    """要点里的数字必须都在答案里 —— 日期/金额错一位就是错。"""
    assert not M.point_hit("截止 2026-06-15", "截止 2026-06-05")


def test_point_hit_empty_point_is_true():
    assert M.point_hit("", "任意答案")


def test_point_hit_low_overlap_false():
    assert not M.point_hit("示例云栈科技的开放时间", "完全不相干的一句话")


# ---------- 最后一轮命中率 ----------
def test_final_point_hit_rate_handcalc():
    case = {"final_expect": {"answer_points": ["开放时间 07:00-22:00", "容量 20 人"]}}
    r = M.final_point_hit_rate(case, "开放时间 07:00-22:00，容量 20 人。")
    assert r["hit"] == 2 and r["value"] == 1.0


def test_final_point_hit_rate_partial():
    case = {"final_expect": {"answer_points": ["开放时间 07:00-22:00", "容量 20 人"]}}
    r = M.final_point_hit_rate(case, "开放时间 07:00-22:00。")
    assert r["hit"] == 1 and abs(r["value"] - 0.5) < 1e-6
    assert r["missed"] == ["容量 20 人"]


# ---------- 检查点 ----------
def test_checkpoint_pass_all():
    case = {"turns": [{"role": "user", "text": "q", "checkpoint": True,
                       "must_points": ["开放时间 07:00-22:00"]}]}
    r = M.checkpoint_pass_rate(case, {0: "开放时间 07:00-22:00。"})
    assert r["value"] == 1.0 and r["total"] == 1


def test_checkpoint_fail():
    case = {"turns": [{"role": "user", "text": "q", "checkpoint": True,
                       "must_points": ["开放时间 07:00-22:00"]}]}
    r = M.checkpoint_pass_rate(case, {0: "不知道"})
    assert r["value"] == 0.0 and r["failed"]


def test_checkpoint_none_is_vacuous_true():
    """没有检查点时记 1.0（空集不扣分），这是显式约定。"""
    r = M.checkpoint_pass_rate({"turns": []}, {})
    assert r["value"] == 1.0 and r["total"] == 0


# ---------- forbidden ----------
def test_forbidden_stale_value_after_correction():
    case = {"turns": [{"role": "user", "text": "《A》开放时间？"},
                      {"role": "assistant", "text": "（模型回答）"},
                      {"role": "user", "text": "不是这个，我说的是《B》，开放时间是多少？"},
                      {"role": "user", "text": "它容纳多少人？"}],
            "forbidden_points": [{"type": "stale_premise_value",
                                  "wrong_value": "07:00-22:00", "desc": "旧值"}]}
    # 纠正之前出现旧值是正常的
    assert M.forbidden_violations(case, {0: "07:00-22:00"}) == []
    # 纠正之后（第 3 轮）仍出现旧值 -> 违规
    outs_bad = {0: "07:00-22:00", 1: "（模型回答）", 2: "09:00-21:00", 3: "07:00-22:00"}
    v = M.forbidden_violations(case, outs_bad)
    assert v and v[0]["type"] == "stale_premise_value"
    # 纠正之后干净 -> 不违规
    outs_ok = {0: "07:00-22:00", 1: "（模型回答）", 2: "09:00-21:00", 3: "20 人"}
    assert M.forbidden_violations(case, outs_ok) == []


def test_forbidden_stale_entity_after_correction():
    case = {"turns": [{"role": "user", "text": "《A》"},
                      {"role": "user", "text": "不是这个，我说的是《B》"}],
            "forbidden_points": [{"type": "stale_premise", "wrong_entity": "SP-001"}]}
    assert M.forbidden_violations(case, {0: "SP-001", 1: "SP-007"}) == []
    assert M.forbidden_violations(case, {1: "SP-001"}), "纠正后仍提旧实体应判违规"


def test_forbidden_none_when_clean():
    case = {"turns": [{"role": "user", "text": "q"}],
            "forbidden_points": [{"type": "topic_bleed", "desc": "串味"}]}
    assert M.forbidden_violations(case, {0: "干净的答案"}) == []


# ---------- 聚合 ----------
def test_aggregate_flags_below_threshold():
    rows = [{"final_point_hit": 0.1, "checkpoint_pass": 0.1, "violations": []}]
    m = M.aggregate(rows)
    assert m["fails"]


def test_aggregate_all_pass():
    rows = [{"final_point_hit": 1.0, "checkpoint_pass": 1.0, "violations": []}]
    assert M.aggregate(rows)["fails"] == []


def test_aggregate_counts_forbidden():
    rows = [{"final_point_hit": 1.0, "checkpoint_pass": 1.0,
             "violations": [{"type": "x"}]}]
    m = M.aggregate(rows)
    assert m["forbidden_violations"] == 1 and m["fails"]
