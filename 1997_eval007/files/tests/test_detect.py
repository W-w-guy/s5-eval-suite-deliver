# -*- coding: utf-8 -*-
"""AC1：8 类检测项各有一组「命中」与「不命中」夹具，结果符合预期。

期望值全部写死，不调用被测函数自己算自己。
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import detect      # noqa: E402
import engine      # noqa: E402
import rules as R  # noqa: E402

FIX = json.load(open(os.path.join(ROOT, "data", "fixtures", "cases.json"),
                     encoding="utf-8"))
PN = {c["kind"] + ("|hit" if c["hit"] else "|miss"): c for c in FIX["positive_negative"]}
EXTRA = {c["kind"] + ("|hit" if c["hit"] else "|miss"): c for c in FIX["extra"]}


def kinds_in(text):
    return {f["kind"] for f in detect.scan_text(text)}


def test_exactly_eight_check_kinds():
    """AC1 的前提：检测项恰好 8 类。"""
    assert len(R.CHECK_KINDS) == 8
    assert len(detect.FINDERS) == 8


@pytest.mark.parametrize("kind", list(R.CHECK_KINDS))
def test_each_kind_has_positive_and_negative(kind):
    assert kind + "|hit" in PN, "%s 缺命中夹具" % kind
    assert kind + "|miss" in PN, "%s 缺不命中夹具" % kind


@pytest.mark.parametrize("kind", list(R.CHECK_KINDS))
def test_positive_fixture_hits(kind):
    c = PN[kind + "|hit"]
    assert kind in kinds_in(c["text"]), "%s 正例未命中：%s" % (kind, c["why"])


@pytest.mark.parametrize("kind", list(R.CHECK_KINDS))
def test_negative_fixture_misses(kind):
    c = PN[kind + "|miss"]
    assert kind not in kinds_in(c["text"]), "%s 反例误命中：%s" % (kind, c["why"])


@pytest.mark.parametrize("kind", ["org_name", "person_name"])
def test_extra_positive_hits(kind):
    assert kind in kinds_in(EXTRA[kind + "|hit"]["text"])


@pytest.mark.parametrize("kind", ["org_name", "person_name"])
def test_extra_negative_misses(kind):
    assert kind not in kinds_in(EXTRA[kind + "|miss"]["text"])


@pytest.mark.parametrize("text", FIX["clean"])
def test_clean_texts_have_no_findings(text):
    assert detect.scan_text(text) == []


# ---- 校验位细节：正反例的差别必须来自校验位本身 ----
def test_id_card_differs_only_by_check_digit():
    assert detect.find_id_card("身份证 " + engine.ID_OK)
    assert not detect.find_id_card("身份证 " + engine.ID_BAD)
    assert engine.ID_OK[:-1] == engine.ID_BAD[:-1]


def test_bank_card_differs_only_by_check_digit():
    assert detect.find_bank_card("卡号 " + engine.BANK_OK)
    assert not detect.find_bank_card("卡号 " + engine.BANK_BAD)


def test_uscc_dummy_marker_excluded_even_if_checksum_ok():
    """样例填充号段的校验位是合法的，但它不该被报成「疑似真实」。"""
    import checksum
    assert checksum.uscc_ok(engine.USCC_OK)
    assert detect.find_uscc("主体 " + engine.USCC_OK)
    assert not detect.find_uscc("主体 " + engine.USCC_DUMMY)


def test_mobile_requires_second_digit_3_to_9():
    assert detect.find_mobile("电话 13900000000")
    assert not detect.find_mobile("编号 12900000000")


def test_address_needs_region_plus_road_number():
    assert detect.find_address("地址：上海市浦东新区示例路 128 号")
    assert not detect.find_address("在示例路的某处")


@pytest.mark.parametrize("kind,exp", [("mobile", "error"), ("id_card", "error"),
                                      ("bank_card", "error"), ("uscc", "error"),
                                      ("landline", "warn"), ("email", "warn"),
                                      ("address", "warn"), ("plate", "warn")])
def test_levels_match_spec(kind, exp):
    """工单：error = 手机号/身份证/银行卡/疑似真实信用代码；其余 warn。"""
    assert R.LEVEL[kind] == exp
