# -*- coding: utf-8 -*-
"""工作日计算（不依赖 datetime、不读系统时间）。

工单要求：confirmed 后 **2 个工作日** 内必须关联回归用例，否则标记 overdue。
「工作日」= 周一至周五，**扣除**法定节假日、**不调休**（节假日表可配置）。

日期运算全部走 clock.py 的整数序数算法，所以可在任意机器、任意时刻复现。
"""
import clock

# ---- 节假日表（虚构示例，接入真实日历时替换此常量即可） ----
HOLIDAYS = {
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",  # 国庆
    "2026-01-01", "2026-01-02",                                            # 元旦
    "2026-05-01", "2026-05-04", "2026-05-05",                             # 劳动节
}
WORKDAY_DEADLINE = 2          # 工单：2 个工作日
SKIP_HOLIDAYS = True          # 行为开关：是否扣除节假日


def weekday_index(day):
    """0=周一 … 6=周日。

    序数 0 = 1970-01-01 = 周四，datetime.weekday() 里周四 = 3，
    所以 (ord + 3) % 7 才对齐。（第一版写成 +4，把周五算成了周末，
    见 tests/test_workdays.py 里对 datetime 的交叉验证。）
    """
    return (clock.to_ordinal(day) + 3) % 7


def is_weekend(day):
    """周六、周日为周末。"""
    return weekday_index(day) >= 5


def is_holiday(day):
    return SKIP_HOLIDAYS and day in HOLIDAYS


def is_workday(day):
    return (not is_weekend(day)) and (not is_holiday(day))


def next_workday(day):
    d = clock.add_days(day, 1)
    guard = 0
    while not is_workday(d):
        d = clock.add_days(d, 1)
        guard += 1
        if guard > 400:
            raise RuntimeError("找不到下一个工作日，节假日表可能填错了")
    return d


def add_workdays(day, n):
    """从 day 起往后推 n 个工作日（day 本身算不算：从下一个工作日起算）。"""
    d = day
    for _ in range(n):
        d = next_workday(d)
    return d


def workdays_between(start, end):
    """[start, end) 之间的工作日天数（不含 end 当天）。"""
    n = 0
    d = start
    while clock.to_ordinal(d) < clock.to_ordinal(end):
        if is_workday(d):
            n += 1
        d = clock.add_days(d, 1)
    return n


def overdue_deadline(confirmed_at):
    """confirmed 当天 + 2 个工作日的截止日（当天不算，从次日起算）。"""
    return add_workdays(confirmed_at, WORKDAY_DEADLINE)


def is_overdue(confirmed_at, today, has_regression_case):
    """已关联回归用例的一律不算 overdue。

    判定：today 已经**超过**截止日（即 today > deadline）才算逾期；
    today == deadline 当天仍不算逾期。
    """
    if has_regression_case:
        return False
    if not confirmed_at:
        return False
    dl = overdue_deadline(confirmed_at)
    return clock.to_ordinal(today) > clock.to_ordinal(dl)
