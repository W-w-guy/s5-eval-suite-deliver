# -*- coding: utf-8 -*-
"""状态机、掩码、权限规则的纯逻辑测试（不依赖数据库）。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import redact          # noqa: E402
import state as S      # noqa: E402

CANARY = "3ZZP-9ERG-Y3SZ"


# ---------- 状态机 ----------
@pytest.mark.parametrize("cur,nxt", [
    ("new", "confirmed"), ("confirmed", "fixing"), ("fixing", "fixed"),
    ("fixed", "verified"), ("new", "wont_fix"), ("fixed", "fixing"),
])
def test_allowed_transitions(cur, nxt):
    assert S.check_transition(cur, nxt) is None


@pytest.mark.parametrize("cur,nxt", [
    ("new", "fixed"), ("new", "verified"), ("verified", "fixed"),
    ("wont_fix", "confirmed"), ("confirmed", "verified"),
])
def test_forbidden_transitions(cur, nxt):
    with pytest.raises(S.RuleError):
        S.check_transition(cur, nxt)


def test_same_status_rejected():
    with pytest.raises(S.RuleError):
        S.check_transition("fixed", "fixed")


def test_unknown_status_rejected():
    with pytest.raises(S.RuleError):
        S.check_transition("new", "archived")


# ---------- AC2：P0 不允许 wont_fix ----------
def test_p0_wont_fix_rejected_even_with_approval():
    with pytest.raises(S.RuleError) as e:
        S.check_wont_fix({"severity": "P0"}, "理由充分", S.APPROVER_ROLE)
    assert "P0" in str(e.value)


def test_p1_wont_fix_allowed_with_approval():
    assert S.check_wont_fix({"severity": "P1"}, "理由充分", S.APPROVER_ROLE) is True


def test_wont_fix_needs_reason():
    with pytest.raises(S.RuleError):
        S.check_wont_fix({"severity": "P2"}, "  ", S.APPROVER_ROLE)


def test_wont_fix_needs_approver_role():
    with pytest.raises(S.RuleError):
        S.check_wont_fix({"severity": "P2"}, "理由", "evaluation_engineer")


def test_p0_switch_is_on():
    assert S.P0_CANNOT_WONT_FIX is True


# ---------- verified 必须带 run_id ----------
def test_verified_requires_run_id():
    with pytest.raises(S.RuleError):
        S.check_verified({"status": "fixed"}, "", "manual")


def test_verified_manual_ok_from_fixed():
    assert S.check_verified({"status": "fixed"}, "RUN-1", "manual") is True


def test_verified_manual_only_from_fixed():
    with pytest.raises(S.RuleError):
        S.check_verified({"status": "fixing"}, "RUN-1", "manual")


def test_verified_auto_run_allowed():
    assert S.check_verified({"status": "fixing"}, "RUN-1", "auto_run") is True


def test_bad_trigger_rejected():
    with pytest.raises(S.RuleError):
        S.check_verified({"status": "fixed"}, "RUN-1", "cron")


# ---------- 权限 ----------
def test_permission_missing():
    with pytest.raises(PermissionError):
        S.check_permission([], S.PERM_WRITE)


def test_permission_present():
    assert S.check_permission([S.PERM_WRITE], S.PERM_WRITE) is True


# ---------- AC3：掩码 ----------
def test_mobile_masked():
    out, hits = redact.redact("电话 13500000001")
    assert out == "电话 135****0001"
    assert {"rule": "mobile", "count": 1} in hits


def test_idcard_masked_before_bank():
    """18 位身份证必须按身份证掩码（前4后4 中间10星），不是按卡号（前6后4）。"""
    out, _ = redact.redact("身份证 310000000000000012")
    assert out == "身份证 3100**********0012"


def test_bank_masked():
    out, _ = redact.redact("卡号 6200000000000000")
    assert out == "卡号 620000******0000"


def test_email_masked():
    out, _ = redact.redact("邮箱 qa_owner@example.invalid")
    assert out == "邮箱 q***@example.invalid"


def test_canary_masked():
    out, _ = redact.redact("金丝雀 %s" % CANARY)
    assert out == "金丝雀 3ZZP-****-Y3SZ"


def test_canary_no_longer_leaks_after_mask():
    out, _ = redact.redact("金丝雀 %s" % CANARY)
    assert redact.leak_of_canary(out, CANARY) is False
    assert redact.leak_of_canary("金丝雀 %s" % CANARY, CANARY) is True


def test_canary_high_entropy_not_colliding_with_invalid_domain():
    """金丝雀不能与正文里的 .invalid 域名共享片段（低熵词会撞车）。"""
    text = "邮箱 qa@example.invalid 金丝雀 %s" % CANARY
    assert not redact.leak_of_canary("q***@example.invalid", CANARY)


def test_redact_idempotent_on_masked_text():
    once, _ = redact.redact("电话 13500000001")
    twice, _ = redact.redact(once)
    assert once == twice


def test_mask_or_raise_switch_on():
    assert redact.REDACT_BEFORE_STORE is True
