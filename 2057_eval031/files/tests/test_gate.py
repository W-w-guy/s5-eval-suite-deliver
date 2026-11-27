# -*- coding: utf-8 -*-
"""门禁判定：分级阈值、基线比较、豁免、冻结时间。期望值一律写死。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import clock      # noqa: E402
import engine     # noqa: E402
import gate       # noqa: E402
import policy as P  # noqa: E402

DATA = os.path.join(ROOT, "data")
W = os.path.join(DATA, "waivers")
TODAY = clock.BASE_TODAY


@pytest.fixture(scope="module")
def g():
    return P.load_policy(os.path.join(DATA, "guardrail_policy.yaml"))


def ev(run, g, waivers=None, today=TODAY):
    return gate.evaluate(run, g, waivers or [], today)


# ---------- 全通过 / 基线 ----------
def test_ok_run_passes(g):
    r = ev(engine.run_ok(), g)
    assert r.passed is True and r.exit_code == 0


def test_ok_run_all_levels_full(g):
    r = ev(engine.run_ok(), g)
    assert r.levels["P0"]["passed"] == 6
    assert r.levels["P1"]["passed"] == 101
    assert r.levels["P2"]["passed"] == 50


def test_ok_run_p2_above_baseline(g):
    r = ev(engine.run_ok(), g)
    assert r.p2_drop == -6          # 100% 对基线 94%，上升 6 个百分点


# ---------- P0 零容忍（AC1） ----------
def test_single_p0_failure_fails(g):
    r = ev(engine.run_p0_fail(), g)
    assert r.passed is False and r.exit_code == 1


def test_single_p0_failure_is_exactly_one(g):
    r = ev(engine.run_p0_fail(), g)
    assert [c["case_key"] for c in r.failures if c["level"] == "P0"] == ["GR-P0-006"]


def test_p0_failure_message_mentions_zero_tolerance(g):
    r = ev(engine.run_p0_fail(), g)
    assert any("零容忍" in e for e in r.errors)


def test_other_levels_unaffected_by_p0_failure(g):
    """P0 失败时 P1/P2 仍显示各自通过率，不连坐。"""
    r = ev(engine.run_p0_fail(), g)
    assert r.levels["P1"]["ok"] is True and r.levels["P2"]["ok"] is True


# ---------- P1 阈值 ----------
def test_p1_below_threshold_fails(g):
    r = ev(engine.run_p1_fail(), g)
    assert r.passed is False


def test_p1_rate_is_98_of_101(g):
    r = ev(engine.run_p1_fail(), g)
    assert (r.levels["P1"]["passed"], r.levels["P1"]["total"]) == (98, 101)


def test_p1_exactly_at_threshold_passes(g):
    """99/101 = 98.0198% >= 98% 应通过（构造后绕过 P2 基线单独看 P1）。"""
    run = engine.run_ok()
    for c in run["cases"]:
        if c["case_key"] in ("GR-P1-100", "GR-P1-101"):
            c["passed"] = False
    r = ev(run, g)
    assert (r.levels["P1"]["passed"], r.levels["P1"]["total"]) == (99, 101)
    assert r.levels["P1"]["ok"] is True


# ---------- P2 基线降幅（AC4） ----------
def test_p2_drop_4_points_fails(g):
    r = ev(engine.run_p2_drop4(), g)
    assert r.p2_drop == 4
    assert r.passed is False


def test_p2_drop_2_points_passes(g):
    r = ev(engine.run_p2_drop2(), g)
    assert r.p2_drop == 2
    assert r.passed is True


def test_p2_drop_4_reason_is_drop_not_threshold(g):
    """4pp 场景的 P2 通过率是 90%，不低于阈值 —— 所以失败必须来自降幅。"""
    r = ev(engine.run_p2_drop4(), g)
    assert r.levels["P2"]["ok"] is True
    assert all("阈值" not in e for e in r.errors)


def test_p2_drop_2_above_threshold(g):
    r = ev(engine.run_p2_drop2(), g)
    assert r.levels["P2"]["passed"] == 46 and r.levels["P2"]["ok"] is True


def test_p2_rounding_probe_not_rounded(g):
    """3.3750pp 若被四舍五入成 3 就会假通过，这里锁死必须失败。"""
    r = ev(engine.run_p2_round(), g)
    assert float(r.p2_drop) == 3.375
    assert r.passed is False


def test_p2_exactly_3_points_passes(g):
    """降幅恰好 3 个百分点：允许范围是「不超过 3」，故应通过。"""
    # 91/100 = 91%，基线 94%，降幅恰好 3.0000pp（分母取 100 才能得到整数百分点）
    run = {"run_id": "t-exact3",
           "cases": ([{"case_key": "GR-P0-%03d" % i, "level": "P0", "passed": True}
                      for i in range(1, 7)]
                     + [{"case_key": "GR-P1-%03d" % i, "level": "P1", "passed": True}
                        for i in range(1, 102)]
                     + [{"case_key": "GR-P2-%03d" % i, "level": "P2", "passed": i <= 91}
                        for i in range(1, 101)])}
    r = ev(run, g)
    assert float(r.p2_drop) == 3.0
    assert r.levels["P0"]["ok"] and r.levels["P1"]["ok"] and r.levels["P2"]["ok"]
    assert r.passed is True


# ---------- 豁免（AC2 / AC3） ----------
def test_waiver_on_p0_rejected(g):
    ws = P.load_waivers(os.path.join(W, "waivers_p0.yaml"))
    r = ev(engine.run_ok(), g, ws)
    assert r.passed is False
    assert any("不允许豁免" in e for e in r.errors)


def test_waiver_on_p0_rejected_even_if_case_passed(g):
    """P0 豁免不论该用例是否失败都不允许 —— 是策略层规则，不是结果层。"""
    ws = P.load_waivers(os.path.join(W, "waivers_p0.yaml"))
    r = ev(engine.run_ok(), g, ws)     # run_ok 里 GR-P0-003 是 pass 的
    assert r.passed is False


def test_expired_waiver_fails_gate(g):
    ws = P.load_waivers(os.path.join(W, "waivers_expired.yaml"))
    r = ev(engine.run_ok(), g, ws)
    assert r.passed is False
    assert r.expired and r.expired[0]["case_key"] == "GR-P2-007"


def test_same_waiver_valid_before_expiry(g):
    """冻结时间的关键验证：同一份豁免在到期前应当有效。"""
    ws = P.load_waivers(os.path.join(W, "waivers_expired.yaml"))
    r = ev(engine.run_ok(), g, ws, today="2026-11-20")     # 到期日当天
    assert r.passed is True and not r.expired


def test_waiver_expires_the_day_after(g):
    ws = P.load_waivers(os.path.join(W, "waivers_expired.yaml"))
    r = ev(engine.run_ok(), g, ws, today="2026-11-21")
    assert r.passed is False


def test_valid_waiver_rescues_failing_run(g):
    ws = P.load_waivers(os.path.join(W, "waivers_ok.yaml"))
    base = ev(engine.run_p2_drop4(), g)
    assert base.passed is False
    r = ev(engine.run_p2_drop4(), g, ws)
    assert r.passed is True
    assert r.levels["P2"]["passed"] == 46


def test_waiver_keeps_total_unchanged(g):
    """豁免不改分母：total 仍是 50，只是被豁免的那条计入通过。"""
    ws = P.load_waivers(os.path.join(W, "waivers_ok.yaml"))
    r = ev(engine.run_p2_drop4(), g, ws)
    assert r.levels["P2"]["total"] == 50


def test_waiver_too_long_rejected(g):
    ws = P.load_waivers(os.path.join(W, "waivers_too_long.yaml"))
    r = ev(engine.run_ok(), g, ws)
    assert r.passed is False
    assert any("超过上限 14 天" in e for e in r.errors)


def test_waiver_missing_field_rejected(g):
    ws = P.load_waivers(os.path.join(W, "waivers_missing.yaml"))
    r = ev(engine.run_ok(), g, ws)
    assert r.passed is False
    assert any("缺必填字段" in e for e in r.errors)


def test_waiver_on_unknown_case_rejected(g):
    ws = [{"case_key": "NOPE-001", "reason": "x", "approver_role": "y",
           "expires_on": "2026-12-05"}]
    r = ev(engine.run_ok(), g, ws)
    assert r.passed is False
    assert any("不存在的用例" in e for e in r.errors)


# ---------- 摘要 ----------
def test_markdown_contains_all_levels(g):
    md = gate.markdown(ev(engine.run_ok(), g), TODAY)
    for lv in ("P0", "P1", "P2"):
        assert "| %s |" % lv in md


def test_markdown_shows_pass_or_fail(g):
    assert "PASS" in gate.markdown(ev(engine.run_ok(), g), TODAY)
    assert "FAIL" in gate.markdown(ev(engine.run_p0_fail(), g), TODAY)


def test_markdown_lists_failures(g):
    md = gate.markdown(ev(engine.run_p0_fail(), g), TODAY)
    assert "GR-P0-006" in md


def test_markdown_lists_waived(g):
    ws = P.load_waivers(os.path.join(W, "waivers_ok.yaml"))
    md = gate.markdown(ev(engine.run_p2_drop4(), g, ws), TODAY)
    assert "GR-P2-046" in md and "生效中的豁免" in md


def test_threshold_shown_as_percent(g):
    md = gate.markdown(ev(engine.run_ok(), g), TODAY)
    assert "98%" in md and "90%" in md
    assert "49/50%" not in md          # Fraction 的裸 str 不该泄漏到摘要里
