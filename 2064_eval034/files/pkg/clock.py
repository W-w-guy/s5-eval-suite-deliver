# -*- coding: utf-8 -*-
"""可注入时钟。

设计要点：**绝不读 datetime.now()**。所有日期判定都用显式传入的 today（或模块常量
BASE_TODAY），这样「过期豁免」这类逻辑在测试里可以冻结时间、可复现。
接入真实 CI 时只把 today 换成真实日期，其余代码不动。
"""
import re

BASE_TODAY = "2026-11-27"          # 固定基准日，产物与断言都以此为准
ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class ClockError(ValueError):
    pass


def parse_day(s):
    """返回 (y, m, d)；格式必须是 YYYY-MM-DD。"""
    if not isinstance(s, str):
        raise ClockError("日期必须是字符串: %r" % (s,))
    m = ISO_RE.match(s)
    if not m:
        raise ClockError("日期必须是 YYYY-MM-DD: %r" % (s,))
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        raise ClockError("日期越界: %r" % (s,))
    return (y, mo, d)


def to_ordinal(s):
    """转成自 1970-01-01 起的天数序数（纯整数运算，不依赖 datetime/时区）。"""
    y, m, d = parse_day(s)
    if m <= 2:
        y -= 1
        m += 12
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m - 3) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def days_between(a, b):
    """b - a 的天数（正数表示 b 晚于 a）。"""
    return to_ordinal(b) - to_ordinal(a)


def add_days(day, n):
    """在 day 上加 n 天，返回 YYYY-MM-DD（用序数换算，避开时区）。"""
    z = to_ordinal(day) + n
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return "%04d-%02d-%02d" % (y + (1 if m <= 2 else 0), m, d)


def is_expired(expires_on, today):
    """到期日当天仍有效，次日起失效。"""
    return days_between(expires_on, today) > 0
