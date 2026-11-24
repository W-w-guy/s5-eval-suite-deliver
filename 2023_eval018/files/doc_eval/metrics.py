# -*- coding: utf-8 -*-
"""字段级准确率、critical 通过率、错字段标红召回、错而未标红明细。

错字段标红召回的口径（这是本单专属指标，必须写死）：
    分母 = 识别错误的字段数
    分子 = 其中被系统标为 flagged 的字段数
另给「错而未标红的 critical 字段数」，目标 0。
"""
FIELDS_NUM = {"amount_ex_tax", "tax_rate", "amount_tax", "amount_total", "page_count"}


def norm_field(name, v):
    """字段值归一：数值型去掉千分位与单位后转 float；日期统一 %Y-%m-%d；其余去空白。"""
    if v is None:
        return None
    if name in FIELDS_NUM:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace(",", "").replace("，", "").replace("元", "").strip()
        try:
            return float(s)
        except ValueError:
            return s
    s = str(v).strip()
    if isinstance(v, str) and "年" in s:
        import re
        m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
        if m:
            return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return s


def field_accuracy(gold: dict, pred: dict) -> dict:
    """逐字段比对。返回 accuracy 与每个字段的对错。"""
    per = {}
    ok = tot = 0
    for f in gold:
        if f.startswith("_"):
            continue
        tot += 1
        g, p = norm_field(f, gold[f]), norm_field(f, (pred or {}).get(f))
        good = (g == p)
        ok += 1 if good else 0
        per[f] = {"gold": gold[f], "pred": (pred or {}).get(f), "ok": good}
    return {"accuracy": round(ok / tot, 6) if tot else 0.0, "ok": ok, "total": tot, "per_field": per}


def flag_recall(gold: dict, pred: dict, flagged: set) -> dict:
    """错字段标红召回。

    只统计「识别错了」的字段：判错的字段里有多少被 flagged。
    识别对的字段被标红是误报，单独计数（不计入召回分母）。
    """
    wrong, wrong_flagged = [], []
    right_flagged = []
    for f in gold:
        if f.startswith("_"):
            continue
        g, p = norm_field(f, gold[f]), norm_field(f, (pred or {}).get(f))
        if g != p:
            wrong.append(f)
            if f in flagged:
                wrong_flagged.append(f)
        elif f in flagged:
            right_flagged.append(f)
    return {
        "wrong_fields": wrong,
        "wrong_flagged": wrong_flagged,
        "wrong_unflagged": [f for f in wrong if f not in flagged],
        "right_but_flagged": right_flagged,
        "recall": round(len(wrong_flagged) / len(wrong), 6) if wrong else 1.0,
        "wrong_total": len(wrong),
    }


THRESH = {"field_accuracy": 0.90, "flag_recall": 0.95}
LABELS = {"field_accuracy": "字段级准确率", "flag_recall": "错字段标红召回"}


def check(k, v):
    return v >= THRESH[k]
