"""sopkit · 冻结时钟与工作时段计算（纯标准库，无三方依赖）"""
from datetime import datetime, timedelta, time

WORK_START = time(9, 0)
LUNCH = (time(12, 0), time(13, 0))
WORK_END = time(18, 0)

class FrozenClock:
    """可推进的虚拟时钟。所有时限计算都相对它，测试不依赖真实时间。"""
    def __init__(self, now):
        self._now = now if isinstance(now, datetime) else datetime.fromisoformat(now)
    def now(self):
        return self._now
    def advance(self, **kw):
        self._now = self._now + timedelta(**kw)
        return self._now
    def set(self, s):
        self._now = datetime.fromisoformat(s)


DEFAULT_HOLIDAYS = set()

def _is_workday(d, holidays):
    return d.weekday() < 5 and d.strftime("%Y-%m-%d") not in holidays

def _work_seconds_in_day(holidays=None):
    # 09:00-12:00 + 13:00-18:00 = 8 工作小时
    return 8 * 3600

def is_work_time(dt, holidays=None):
    holidays = holidays or DEFAULT_HOLIDAYS
    if not _is_workday(dt.date(), holidays):
        return False
    t = dt.time()
    if WORK_START <= t < LUNCH[0]:
        return True
    if LUNCH[1] <= t < WORK_END:
        return True
    return False

def next_work_start(dt, holidays=None):
    """把时刻推到下一个工作时段起点。"""
    holidays = holidays or DEFAULT_HOLIDAYS
    cur = dt
    for _ in range(400):
        if _is_workday(cur.date(), holidays):
            t = cur.time()
            if t < WORK_START:
                return cur.replace(hour=9, minute=0, second=0, microsecond=0)
            if LUNCH[0] <= t < LUNCH[1]:
                return cur.replace(hour=13, minute=0, second=0, microsecond=0)
            if t < WORK_END:
                return cur
        cur = (cur + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    raise RuntimeError("next_work_start: no workday found")


def add_work_hours(dt, hours, holidays=None):
    """加 N 个工作小时，跳过午休/夜间/周末/节假日。文档口径 work_hour 0.25 = 15 工作分钟。
    工作时段：09:00-12:00、13:00-18:00，合计 8 工作小时/日。"""
    holidays = holidays or DEFAULT_HOLIDAYS
    remain = float(hours) * 3600.0
    if remain < 0:
        raise ValueError("add_work_hours 只支持非负工作小时；负向请用 due 锚点表达")
    cur = next_work_start(dt, holidays)
    for _ in range(5000):
        t = cur.time()
        if t < WORK_START:
            cur = cur.replace(hour=9, minute=0, second=0, microsecond=0); continue
        if LUNCH[0] <= t < LUNCH[1]:
            cur = cur.replace(hour=13, minute=0, second=0, microsecond=0); continue
        if t >= WORK_END:
            cur = next_work_start(cur.replace(hour=9, minute=0, second=0, microsecond=0)
                                  + timedelta(days=1), holidays)
            continue
        # 当前工作段结束点：上午到 12:00，下午到 18:00
        seg_end = LUNCH[0] if t < LUNCH[0] else WORK_END
        end_dt = cur.replace(hour=seg_end.hour, minute=seg_end.minute, second=0, microsecond=0)
        avail = (end_dt - cur).total_seconds()
        if avail <= 0:
            raise RuntimeError(f"add_work_hours: 非法时段 cur={cur} seg_end={seg_end}")
        if remain <= avail:
            return cur + timedelta(seconds=remain)
        remain -= avail
        cur = next_work_start(end_dt, holidays)
    raise RuntimeError("add_work_hours overflow")


def add_work_days(dt, days, holidays=None):
    """加 N 个工作日，落在同一时分（若当日非工作日则顺延到下一工作日）。"""
    holidays = holidays or DEFAULT_HOLIDAYS
    cur = dt
    n = abs(int(days))
    step = 1 if days >= 0 else -1
    while n > 0:
        cur = cur + timedelta(days=step)
        if _is_workday(cur.date(), holidays):
            n -= 1
    return cur

def add_natural_days(dt, days, holidays=None):
    """加 N 个自然日（不看工作日/节假日）。"""
    return dt + timedelta(days=int(days))

def at_time_of_day(dt, hhmm):
    """把某天换成 HH:MM（用于「每日 09:00 触发」）。"""
    h, m = str(hhmm).split(":")
    return dt.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
