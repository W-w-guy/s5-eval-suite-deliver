# -*- coding: utf-8 -*-
"""overdue 定时检查任务（AC1 的运行时形态）。

设计：任务本身是纯函数 `scan()`，返回被标记的清单；
调度只需每天调一次 `scan()`。这样测试可以直接冻结 today 调 scan()，
不依赖真实时钟。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from sqlalchemy import select

import clock
import workdays as W
from pkg.db import get_session
from pkg.models import RedteamFinding

MARK_ONLY = True      # 行为开关：只标记不落库（便于测试）

# 工单要求「被标记 overdue」。本实现不写新列，overdue 是派生状态，
# 但为了让定时任务有可观察的副作用，把标记写进 updated_at 的伴生表意义不大；
# 这里选择：返回清单 + 可选写一个 JSON 快照，供看板与提醒使用。
SNAPSHOT = "data/overdue_snapshot.json"


def scan(org_id=None, today=None, write_snapshot=True):
    """扫描所有 confirmed 状态且未关联回归用例的发现，返回 overdue 清单。"""
    today = today or clock.BASE_TODAY
    out = []
    with get_session() as sess:
        q = select(RedteamFinding).where(
            RedteamFinding.status == "confirmed",
            RedteamFinding.deleted_at.is_(None),
            RedteamFinding.regression_case_key.is_(None))
        if org_id:
            q = q.where(RedteamFinding.org_id == org_id)
        for r in sess.execute(q).scalars().all():
            if r.confirmed_at and W.is_overdue(str(r.confirmed_at), today, False):
                out.append({
                    "id": str(r.id), "finding_no": r.finding_no,
                    "severity": r.severity,
                    "confirmed_at": str(r.confirmed_at),
                    "deadline": W.overdue_deadline(str(r.confirmed_at)),
                    "overdue": True,
                })
    out.sort(key=lambda x: x["finding_no"])
    if write_snapshot and not MARK_ONLY:
        import json
        root = os.path.dirname(_HERE)
        fp = os.path.join(root, SNAPSHOT)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"today": today, "items": out}, f, ensure_ascii=False, indent=1)
    return {"today": today, "overdue_count": len(out), "items": out}


if __name__ == "__main__":
    print(scan(today=os.environ.get("TODAY")))
