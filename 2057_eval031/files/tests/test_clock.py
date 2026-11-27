# -*- coding: utf-8 -*-
"""冻结时钟：序数换算与 datetime 交叉验证，避免「读系统时间」这类不可复现缺陷。"""
import datetime
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import clock  # noqa: E402


@pytest.mark.parametrize("s", ["1970-01-01", "2024-02-29", "2026-11-27",
                               "1999-12-31", "2100-03-01", "2000-01-01"])
def test_ordinal_matches_datetime(s):
    y, m, d = map(int, s.split("-"))
    ref = (datetime.date(y, m, d) - datetime.date(1970, 1, 1)).days
    assert clock.to_ordinal(s) == ref


@pytest.mark.parametrize("day,n", [("2026-11-27", 14), ("2026-11-27", -1),
                                   ("2024-02-28", 1), ("2026-12-31", 1)])
def test_add_days_matches_datetime(day, n):
    y, m, d = map(int, day.split("-"))
    ref = (datetime.date(y, m, d) + datetime.timedelta(days=n)).isoformat()
    assert clock.add_days(day, n) == ref


def test_days_between_sign():
    assert clock.days_between("2026-11-27", "2026-12-11") == 14
    assert clock.days_between("2026-12-11", "2026-11-27") == -14
    assert clock.days_between("2026-11-27", "2026-11-27") == 0


def test_expired_same_day_is_not_expired():
    assert clock.is_expired("2026-11-27", "2026-11-27") is False


def test_expired_next_day():
    assert clock.is_expired("2026-11-27", "2026-11-28") is True


def test_not_expired_before():
    assert clock.is_expired("2026-12-05", "2026-11-27") is False


@pytest.mark.parametrize("bad", ["2026/11/27", "20261127", "2026-13-01", "", None, 20261127])
def test_bad_date_rejected(bad):
    with pytest.raises(clock.ClockError):
        clock.parse_day(bad)


def test_base_today_is_fixed():
    """基准日必须是常量，不能是 datetime.now()。"""
    assert clock.BASE_TODAY == "2026-11-27"


def test_no_now_call_in_source():
    """源码里不允许真的调用 now()/today() 之类读系统时间的函数。

    用 ast 遍历而不是字符串匹配 —— 字符串匹配会被 docstring/注释里的
    文字误伤（第一版就是这么错的：文档里写了「绝不读 datetime.now()」
    反而让断言失败）。
    """
    import ast
    src = open(os.path.join(ROOT, "pkg", "clock.py"), encoding="utf-8").read()
    bad = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("now", "today", "utcnow", "time"):
                bad.append(node.func.attr)
    assert bad == []


def test_imported_datetime_not_used_for_logic():
    """clock.py 甚至可以完全不 import datetime（序数换算纯整数自算）。"""
    src = open(os.path.join(ROOT, "pkg", "clock.py"), encoding="utf-8").read()
    import ast
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert "datetime" not in mods
