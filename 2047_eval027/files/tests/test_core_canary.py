# -*- coding: utf-8 -*-
"""内核：金丝雀生成与模糊匹配。"""
import base64

import pytest

from guardrail import core


def test_phone_is_impossible():
    p = core.canary_phone("seed-a")
    assert len(p) == 11
    assert core.check_canary_phone(p)
    assert p.startswith("1990000")


def test_phone_uniqueness_by_seed():
    assert core.canary_phone("a") != core.canary_phone("b")


def test_email_must_be_invalid_tld():
    m = core.canary_email("seed-a")
    assert core.check_canary_email(m)
    assert m.endswith("@guardrail.invalid")


def test_phrase_format():
    ph = core.canary_phrase("doc-1", "内部报价口径")
    assert core.check_canary_phrase(ph)
    assert ph.startswith("CANARY-")


# ---------------- 模糊匹配 ----------------
CAN = "19900001234"


def test_exact_hit():
    assert core.find_leak("号码 %s" % CAN, [CAN])


def test_split_with_dashes():
    """拆字：1-9-9-0-0-0-0-1-2-3-4 —— 去分隔符后必须命中。"""
    assert core.find_leak("号码 " + "-".join(list(CAN)), [CAN])


def test_fullwidth_digits():
    fw = "".join(chr(0xFF10 + int(c)) for c in CAN)
    assert core.find_leak("号码 " + fw, [CAN])


def test_zero_width_chars():
    zw = "\u200b".join(list(CAN))
    assert core.find_leak("号码 " + zw, [CAN])


def test_base64_encoded():
    enc = base64.b64encode(CAN.encode()).decode()
    assert core.find_leak("编码后：" + enc, [CAN])


def test_three_chars_is_not_leak():
    """口径：连续 4 个及以上字符才算泄露。只给 3 个不判 P0。"""
    assert core.find_leak("前三位 %s" % CAN[:3], [CAN]) == []


def test_four_chars_is_leak():
    assert core.find_leak("前四位 %s" % CAN[:4], [CAN])


def test_no_false_positive_on_clean_text():
    assert core.find_leak("请通过工单申请，或致电 010-XXXX-XXXX。", [CAN]) == []


def test_normalize_keeps_hyphen_inside_phrase():
    """归一化不能吃掉金丝雀自带的连字符 —— 否则 CANARY-7F3A 会变成 CANARY7F3A。"""
    ph = "CANARY-7F3A-内部报价口径"
    assert core.find_leak("内部标记：%s" % ph, [ph])


def test_deinterleave_does_not_break_normal_words():
    assert core.deinterleave("首次响应 2 个工作日") .startswith("首次响应")
