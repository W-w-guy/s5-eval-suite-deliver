# -*- coding: utf-8 -*-
"""AC1 的时间基础：工作日计算（与 datetime 交叉验证）。"""
import datetime
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import workdays as W   # noqa: E402


@pytest.mark.parametrize("s", ["2026-11-27", "2026-11-28", "2026-11-30",
                               "2026-01-01", "2024-02-29", "2026-12-31"])
def test_weekday_index_matches_datetime(s):
    y, m, d = map(int, s.split("-"))
    assert W.weekday_index(s) == datetime.date(y, m, d).weekday()


def test_friday_is_workday():
    # 2026-11-27 是周五。第一版把偏移写成 +4，把它算成了周末
    assert not W.is_weekend("2026-11-27")
    assert W.is_workday("2026-11-27")


def test_saturday_sunday_are_weekend():
    assert W.is_weekend("2026-11-28")     # 周六
    assert W.is_weekend("2026-11-29")     # 周日


def test_holiday_is_not_workday():
    assert "2026-10-01" in W.HOLIDAYS
    assert not W.is_workday("2026-10-01")


def test_next_workday_skips_weekend():
    # 周五(11-27) -> 下一个工作日是周一(11-30)，跳过 11-28/11-29
    assert W.next_workday("2026-11-27") == "2026-11-30"


def test_next_workday_skips_holiday():
    # 2026-09-30 是周三，次日 10-01 是节假日 -> 跳到 10-08? 实际表里 10-01/02/05/06/07 是假
    assert W.next_workday("2026-09-30") == "2026-10-08"


def test_add_two_workdays_from_wed():
    # confirmed 2026-11-25（周三）+2 工作日 = 11-26(四) / 11-27(五)
    assert W.overdue_deadline("2026-11-25") == "2026-11-27"


def test_add_two_workdays_from_fri_crosses_weekend():
    # confirmed 2026-11-27（周五）+2 工作日 = 11-30(一) / 12-01(二)
    assert W.overdue_deadline("2026-11-27") == "2026-12-01"


def test_add_workdays_matches_datetime_walk():
    """与手写的 datetime 遍历交叉验证：跳过周末与节假日。"""
    hol = W.HOLIDAYS

    def ref_next(d):
        d = d + datetime.timedelta(days=1)
        while d.weekday() >= 5 or d.isoformat() in hol:
            d += datetime.timedelta(days=1)
        return d

    for start in ("2026-11-20", "2026-11-25", "2026-11-27", "2026-09-29"):
        y, m, d = map(int, start.split("-"))
        cur = datetime.date(y, m, d)
        for _ in range(3):
            cur = ref_next(cur)
        assert W.add_workdays(start, 3) == cur.isoformat()


def test_deadline_day_not_overdue():
    # 截止日当天 2026-11-27 不算逾期
    assert not W.is_overdue("2026-11-25", "2026-11-27", False)


def test_day_after_deadline_is_overdue():
    assert W.is_overdue("2026-11-25", "2026-11-28", False)


def test_has_regression_case_never_overdue():
    assert not W.is_overdue("2026-11-01", "2026-12-31", True)


def test_no_confirmed_at_not_overdue():
    assert not W.is_overdue(None, "2026-12-31", False)


def test_business_days_between():
    # 11-25(三) 到 11-28(六) 之间：[25,26,27] 三个工作日
    assert W.workdays_between("2026-11-25", "2026-11-28") == 3
