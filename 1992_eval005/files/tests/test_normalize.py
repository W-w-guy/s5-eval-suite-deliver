# -*- coding: utf-8 -*-
"""8 种字段类型的归一化：每种都给正例与反例，期望值一律写死。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import normalize as N  # noqa: E402


# ---------- string ----------
def test_string_fullwidth_equals_halfwidth():
    assert N.norm_string("HT－2026－0011") == N.norm_string("HT-2026-0011")


def test_string_case_insensitive():
    assert N.norm_string("Ht-2026") == "ht-2026"


def test_string_collapses_inner_space():
    assert N.norm_string("  a   b  ") == "a b"


def test_string_strips_zero_width():
    assert N.norm_string("a\u200bb") == "ab"


def test_string_none_rejected():
    with pytest.raises(N.NormalizeError):
        N.norm_string(None)


def test_string_different_is_not_equal():
    assert N.norm_string("HT-1") != N.norm_string("HT-2")


# ---------- date ----------
@pytest.mark.parametrize("raw", ["2026-05-06", "2026/5/6", "2026年5月6日",
                                 "20260506", "2026.5.6"])
def test_date_formats_unify(raw):
    assert N.norm_date(raw) == "2026-05-06"


def test_date_pads_single_digit():
    assert N.norm_date("2026-1-2") == "2026-01-02"


def test_date_bad_format_rejected():
    with pytest.raises(N.NormalizeError):
        N.norm_date("五月六日")


def test_date_out_of_range_rejected():
    with pytest.raises(N.NormalizeError):
        N.norm_date("2026-13-01")


def test_date_one_day_apart_differs():
    assert N.norm_date("2026-05-06") != N.norm_date("2026-05-07")


# ---------- money_fen / rate_bp ----------
def test_money_int_accepted():
    assert N.norm_money_fen(1280000) == 1280000


def test_money_one_fen_differs():
    assert N.norm_money_fen(1280000) != N.norm_money_fen(1280001)


def test_money_float_rejected():
    with pytest.raises(N.NormalizeError):
        N.norm_money_fen(12800.0)


def test_money_bool_rejected():
    with pytest.raises(N.NormalizeError):
        N.norm_money_fen(True)


def test_money_numeric_string_accepted():
    assert N.norm_money_fen("1280000") == 1280000


def test_rate_bp_int_accepted():
    assert N.norm_rate_bp(600) == 600


def test_rate_bp_one_bp_differs():
    assert N.norm_rate_bp(600) != N.norm_rate_bp(601)


def test_rate_bp_float_rejected():
    with pytest.raises(N.NormalizeError):
        N.norm_rate_bp(6.0)


# ---------- uscc ----------
def test_uscc_lowercase_upper():
    assert N.norm_uscc("91310000ma1fl2xy3k") == "91310000MA1FL2XY3K"


def test_uscc_strips_space():
    assert N.norm_uscc(" 91310000MA1FL2XY3K ") == "91310000MA1FL2XY3K"


def test_uscc_wrong_length_rejected():
    with pytest.raises(N.NormalizeError):
        N.norm_uscc("91310000MA")


def test_uscc_one_char_differs():
    assert N.norm_uscc("91310000MA1FL2XY3M") != N.norm_uscc("91310000MA1FL2XY3K")


# ---------- enum ----------
MAP = {"月结": "monthly", "月结30天": "monthly", "季度": "quarterly"}


@pytest.mark.parametrize("raw,exp", [("月结", "monthly"), ("月结30天", "monthly"),
                                     ("季度", "quarterly"), ("monthly", "monthly")])
def test_enum_maps_to_canonical(raw, exp):
    assert N.norm_enum(raw, MAP) == exp


def test_enum_unknown_keeps_casefolded():
    assert N.norm_enum("Other", MAP) == "other"


def test_enum_different_canonical_differs():
    assert N.norm_enum("月结", MAP) != N.norm_enum("季度", MAP)


# ---------- 分派 ----------
def test_scalar_dispatch_all_six():
    assert N.norm_scalar("string", " A ", {}) == "a"
    assert N.norm_scalar("date", "2026/1/2", {}) == "2026-01-02"
    assert N.norm_scalar("money_fen", 1, {}) == 1
    assert N.norm_scalar("rate_bp", 2, {}) == 2
    assert N.norm_scalar("uscc", "9" * 18, {}) == "9" * 18
    assert N.norm_scalar("enum", "月结", {"mapping": MAP}) == "monthly"


def test_scalar_dispatch_rejects_container_type():
    with pytest.raises(N.NormalizeError):
        N.norm_scalar("list", [], {})


def test_all_types_is_eight():
    assert len(N.ALL_TYPES) == 8
