# -*- coding: utf-8 -*-
"""退化判定：通过率降幅、must 翻转、抖动重跑、版本交集。期望值一律写死。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import baseline as B   # noqa: E402
import engine          # noqa: E402

SUITE = os.path.join(ROOT, "data", "suite.yaml")


@pytest.fixture(scope="module")
def base():
    return engine.baseline_run()


@pytest.fixture(scope="module")
def rules():
    return B.load_suite(SUITE)[1]


# ---------- AC1：通过率降幅 ----------
def test_drop4_is_exactly_4(base, rules):
    r = B.compare(base, engine.cur_drop4(), rules)
    assert float(r["pass_rate"]["drop_pp"]) == 4.0


def test_drop4_fails(base, rules):
    assert B.compare(base, engine.cur_drop4(), rules)["verdict"] == "fail"


def test_drop2_is_1_6(base, rules):
    r = B.compare(base, engine.cur_drop2(), rules)
    assert float(r["pass_rate"]["drop_pp"]) == 1.6


def test_drop2_passes(base, rules):
    assert B.compare(base, engine.cur_drop2(), rules)["verdict"] == "pass"


def test_rounding_probe_3_2_fails(base, rules):
    """3.2 > 3 必须失败；若写成 round(drop) -> 3 就会假通过。"""
    r = B.compare(base, engine.cur_round(), rules)
    assert float(r["pass_rate"]["drop_pp"]) == 3.2
    assert r["verdict"] == "fail"


def test_better_run_passes(base, rules):
    r = B.compare(base, engine.cur_better(), rules)
    assert r["verdict"] == "pass"
    assert float(r["pass_rate"]["drop_pp"]) < 0


def test_drop_reason_names_both_rates(base, rules):
    r = B.compare(base, engine.cur_drop4(), rules)
    msg = [x for x in r["reasons"] if "通过率" in x]
    assert msg and "92.0000" in msg[0]


# ---------- AC2：抖动重跑 ----------
def test_flaky_three_flips_total(base, rules):
    assert len(B.compare(base, engine._flaky_cases(), rules)["regressions_all"]) == 3


def test_flaky_two_marked(base, rules):
    r = B.compare(base, engine._flaky_cases(), rules)
    assert sorted(f["case_key"] for f in r["flaky"]) == ["KB-113", "KB-114"]


def test_flaky_only_double_fail_stays(base, rules):
    r = B.compare(base, engine._flaky_cases(), rules)
    assert r["regressions"] == ["KB-115"]


def test_flaky_not_counted_in_must_flips(base, rules):
    r = B.compare(base, engine._flaky_cases(), rules)
    assert r["must_flips"] == ["KB-115"]
    assert len(r["must_flips"]) == 1


def test_flaky_scenario_passes(base, rules):
    assert B.compare(base, engine._flaky_cases(), rules)["verdict"] == "pass"


def test_if_flaky_counted_it_would_fail(base, rules, monkeypatch):
    """反向对照：把 flaky 算进退化，must 翻转就是 3 条 -> 失败。"""
    monkeypatch.setattr(B, "FLAKY_EXCLUDED_FROM_REGRESSION", False)
    r = B.compare(base, engine._flaky_cases(), rules)
    assert len(r["must_flips"]) == 3
    assert r["verdict"] == "fail"


def test_flaky_reruns_recorded(base, rules):
    r = B.compare(base, engine._flaky_cases(), rules)
    for f in r["flaky"]:
        assert len(f["reruns"]) == 2 and any(f["reruns"])


# ---------- AC3：版本不同只比共有 ----------
def test_version_diff_detected(base, rules):
    assert B.compare(base, engine.cur_ver_diff(), rules)["scope"]["same_suite_version"] is False


def test_version_diff_compares_113(base, rules):
    r = B.compare(base, engine.cur_ver_diff(), rules)
    assert r["scope"]["compared_cases"] == 113


def test_version_diff_counts(base, rules):
    sc = B.compare(base, engine.cur_ver_diff(), rules)["scope"]
    assert (sc["only_in_baseline"], sc["only_in_current"]) == (12, 10)


def test_version_diff_note_written(base, rules):
    note = B.compare(base, engine.cur_ver_diff(), rules)["scope"]["note"]
    assert "共有" in note and "v1" in note and "v2" in note


def test_same_version_compares_all(base, rules):
    r = B.compare(base, engine.cur_drop2(), rules)
    assert r["scope"]["compared_cases"] == 125 and r["scope"]["same_suite_version"] is True


def test_naive_version_diff_uses_wrong_denominator(base, rules):
    """不做共有用例限制时分母是 123（含新增 10 条），而不是 113。"""
    r = B.compare(base, engine.cur_ver_diff(), rules)
    cur = engine.cur_ver_diff()["cases"]
    assert len(cur) == 123
    naive = (B.Fraction(115, 125) - B.Fraction(sum(1 for c in cur if c["passed"]), len(cur))) * 100
    assert float(naive) != float(r["pass_rate"]["drop_pp"])
    assert r["scope"]["compared_cases"] == 113


def test_new_cases_not_in_comparison(base, rules):
    """新增的 10 条全失败，但因不在共有集合里，不进 regression 清单。"""
    r = B.compare(base, engine.cur_ver_diff(), rules)
    assert not any(k.startswith("KB-NEW-") for k in r["regressions_all"])


# ---------- AC4：基线合法性 ----------
def test_failed_status_rejected(rules):
    with pytest.raises(B.BaselineError):
        B.compare(engine.run_error_status(), engine.cur_drop2(), rules)


def test_errors_rejected(rules):
    with pytest.raises(B.BaselineError):
        B.compare(engine.run_error_errors(), engine.cur_drop2(), rules)


def test_settable_rejects_failed():
    suite = B.load_suite(SUITE)[0]
    with pytest.raises(B.BaselineError) as e:
        B.check_settable(engine.run_error_status(), suite, ["eval.baseline.set"], "x")
    assert "completed" in str(e.value)


def test_settable_rejects_errors():
    suite = B.load_suite(SUITE)[0]
    with pytest.raises(B.BaselineError) as e:
        B.check_settable(engine.run_error_errors(), suite, ["eval.baseline.set"], "x")
    assert "执行错误" in str(e.value)


def test_settable_requires_permission():
    suite = B.load_suite(SUITE)[0]
    with pytest.raises(B.BaselineError):
        B.check_settable(engine.baseline_run(), suite, [], "x")


def test_settable_requires_reason():
    suite = B.load_suite(SUITE)[0]
    with pytest.raises(B.BaselineError):
        B.check_settable(engine.baseline_run(), suite, ["eval.baseline.set"], "  ")


def test_settable_accepts_valid():
    suite = B.load_suite(SUITE)[0]
    assert B.check_settable(engine.baseline_run(), suite, ["eval.baseline.set"], "首版") is None


def test_settable_rejects_version_mismatch():
    suite = B.load_suite(SUITE)[0]
    run = engine.baseline_run()
    run["suite_version"] = "v9"
    with pytest.raises(B.BaselineError):
        B.check_settable(run, suite, ["eval.baseline.set"], "x")


# ---------- 规则覆盖与建议更新 ----------
def test_rules_default(base):
    rules = B.load_suite(SUITE)[1]
    assert rules["max_pass_rate_drop_pp"] == 3
    assert rules["max_must_flips"] == 3
    assert rules["score_drop_warn"] == 0.05


def test_rule_override_takes_effect(base, rules):
    over = dict(rules, max_pass_rate_drop_pp=5)
    r = B.compare(base, engine.cur_drop4(), over)
    assert not any("通过率" in x for x in r["reasons"])     # 4pp < 5pp 不再因通过率失败


def test_suggest_after_three(base):
    s = B.suggest_update([{"better_than_baseline": True}] * 3, "BASE_V1")
    assert s["suggested"] is True and s["auto_update"] is False


def test_no_suggest_after_two(base):
    assert B.suggest_update([{"better_than_baseline": True}] * 2, "BASE_V1")["suggested"] is False


def test_suggest_needs_consecutive(base):
    h = [{"better_than_baseline": True}, {"better_than_baseline": False},
         {"better_than_baseline": True}, {"better_than_baseline": True}]
    assert B.suggest_update(h, "BASE_V1")["suggested"] is False
    assert B.suggest_update(h, "BASE_V1")["consecutive_better"] == 2


# ---------- 摘要 ----------
def test_markdown_has_levels(base, rules):
    md = B.markdown(B.compare(base, engine.cur_drop4(), rules), "2026-11-27")
    assert "通过率" in md and "平均分" in md and "FAIL" in md


def test_markdown_lists_flaky(base, rules):
    md = B.markdown(B.compare(base, engine._flaky_cases(), rules), "2026-11-27")
    assert "flaky" in md and "KB-113" in md


def test_markdown_writes_scope(base, rules):
    md = B.markdown(B.compare(base, engine.cur_ver_diff(), rules), "2026-11-27")
    assert "比较范围" in md and "共有" in md
