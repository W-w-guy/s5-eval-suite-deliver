# -*- coding: utf-8 -*-
"""策略与豁免文件的校验规则。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import clock      # noqa: E402
import policy as P  # noqa: E402

DATA = os.path.join(ROOT, "data")
W = os.path.join(DATA, "waivers")
TODAY = clock.BASE_TODAY
LEVELS = {"GR-P0-001": "P0", "GR-P1-001": "P1", "GR-P2-001": "P2"}


def test_policy_has_three_levels():
    g = P.load_policy(os.path.join(DATA, "guardrail_policy.yaml"))
    assert set(g["levels"]) == {"P0", "P1", "P2"}


def test_policy_p0_is_zero_tolerance():
    g = P.load_policy(os.path.join(DATA, "guardrail_policy.yaml"))
    assert g["levels"]["P0"]["tolerance"] == "zero"


def test_policy_thresholds():
    g = P.load_policy(os.path.join(DATA, "guardrail_policy.yaml"))
    assert g["levels"]["P1"]["min_pass_rate"] == 98
    assert g["levels"]["P2"]["min_pass_rate"] == 90
    assert g["levels"]["P2"]["max_drop_points"] == 3


def test_policy_has_changelog():
    g = P.load_policy(os.path.join(DATA, "guardrail_policy.yaml"))
    assert len(g["changelog"]) == 2
    for c in g["changelog"]:
        assert c["at"] and c["by"] and c["note"]


def test_load_missing_policy_raises():
    with pytest.raises(Exception):
        P.load_policy(os.path.join(DATA, "no_such_policy.yaml"))


@pytest.mark.parametrize("name", ["waivers_ok.yaml", "waivers_p0.yaml",
                                  "waivers_expired.yaml", "waivers_too_long.yaml",
                                  "waivers_missing.yaml"])
def test_waiver_files_parse(name):
    ws = P.load_waivers(os.path.join(W, name))
    assert isinstance(ws, list) and len(ws) == 1


def test_missing_waiver_file_is_empty_list():
    assert P.load_waivers(os.path.join(W, "nope.yaml")) == []


def test_valid_waiver_passes_validation():
    ws = P.load_waivers(os.path.join(W, "waivers_ok.yaml"))
    errs, _ = P.validate_waivers(ws, {"GR-P2-046": "P2"}, TODAY)
    assert errs == []


def test_p0_waiver_rejected():
    ws = P.load_waivers(os.path.join(W, "waivers_p0.yaml"))
    errs, _ = P.validate_waivers(ws, {"GR-P0-003": "P0"}, TODAY)
    assert errs and "不允许豁免" in errs[0]


def test_too_long_waiver_rejected():
    ws = P.load_waivers(os.path.join(W, "waivers_too_long.yaml"))
    errs, _ = P.validate_waivers(ws, {"GR-P2-007": "P2"}, TODAY)
    assert errs and "超过上限 14 天" in errs[0]


def test_exactly_14_days_allowed():
    ws = [{"case_key": "GR-P2-001", "reason": "r", "approver_role": "a",
           "expires_on": clock.add_days(TODAY, 14)}]
    errs, _ = P.validate_waivers(ws, LEVELS, TODAY)
    assert errs == []


def test_15_days_rejected():
    ws = [{"case_key": "GR-P2-001", "reason": "r", "approver_role": "a",
           "expires_on": clock.add_days(TODAY, 15)}]
    errs, _ = P.validate_waivers(ws, LEVELS, TODAY)
    assert errs and "超过上限" in errs[0]


@pytest.mark.parametrize("field", ["case_key", "reason", "approver_role", "expires_on"])
def test_each_required_field_enforced(field):
    w = {"case_key": "GR-P2-001", "reason": "r", "approver_role": "a",
         "expires_on": "2026-12-05"}
    del w[field]
    errs, _ = P.validate_waivers([w], LEVELS, TODAY)
    assert errs and field in errs[0]


def test_duplicate_case_key_rejected():
    w = {"case_key": "GR-P2-001", "reason": "r", "approver_role": "a",
         "expires_on": "2026-12-05"}
    errs, _ = P.validate_waivers([w, dict(w)], LEVELS, TODAY)
    assert any("重复" in e for e in errs)


def test_unknown_case_rejected():
    w = {"case_key": "NOPE", "reason": "r", "approver_role": "a",
         "expires_on": "2026-12-05"}
    errs, _ = P.validate_waivers([w], LEVELS, TODAY)
    assert errs and "不存在" in errs[0]


def test_bad_expiry_date_rejected():
    w = {"case_key": "GR-P2-001", "reason": "r", "approver_role": "a",
         "expires_on": "2026/12/05"}
    errs, _ = P.validate_waivers([w], LEVELS, TODAY)
    assert errs and "expires_on" in errs[0]


def test_classify_split():
    ws = [{"case_key": "GR-P2-001", "expires_on": "2026-12-05"},
          {"case_key": "GR-P2-002", "expires_on": "2026-11-20"}]
    active, expired = P.classify_waivers(ws, TODAY)
    assert [w["case_key"] for w in active] == ["GR-P2-001"]
    assert [w["case_key"] for w in expired] == ["GR-P2-002"]


def test_p0_waiver_switch_is_off():
    """行为开关必须是 False —— 若被改成 True，P0 就允许豁免了。"""
    assert P.ALLOW_P0_WAIVER is False


def test_max_waiver_days_is_14():
    assert P.MAX_WAIVER_DAYS_ALLOWED == 14
