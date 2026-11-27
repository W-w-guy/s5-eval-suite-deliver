# -*- coding: utf-8 -*-
"""字段级比对与指标计算。

口径（全部显式写在 README，不靠默契）：
  correct = 期望有、实际有、归一化后相等
  wrong   = 期望有、实际有、归一化后不等（既算误报也算漏报）
  missing = 期望有、实际没有
  extra   = 期望没有、实际有
  precision = correct / (correct + wrong + extra)
  recall    = correct / (correct + wrong + missing)
  F1        = 2PR / (P + R)，P+R=0 时 F1 记 0.0
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import normalize as N  # noqa: E402

# ---- 行为开关（刻意集中在此文件，便于变异测试锚定） ----
WRONG_COUNTS_AS = "both"      # both | recall_only | precision_only | none
ENFORCE_CRITICAL = True       # critical 字段出错即判用例不通过
LIST_ALIGN_KEY_DEFAULT = "seq"
MONEY_TOLERANCE_FEN = 0       # 金额容差，必须为 0
RATE_TOLERANCE_BP = 0
PASS_F1_THRESHOLD = 0.8       # 非 critical 字段的用例通过线（critical 单独判）


class FieldScore(object):
    """一个用例的比对结果：逐字段计数 + 整体/分字段指标 + 是否通过。"""

    def __init__(self):
        self.fields = {}        # name -> dict(correct,wrong,missing,extra)
        self.critical_hit = []  # 出错的 critical 字段名
        self.notes = []
        self.items = {}         # name -> 明细列表（list/summary 用）

    # --- 计数 ---
    def _bump(self, name, kind):
        f = self.fields.setdefault(name, {"correct": 0, "wrong": 0,
                                          "missing": 0, "extra": 0})
        f[kind] += 1

    def add(self, name, kind, detail=None):
        self._bump(name, kind)
        if detail is not None:
            self.items.setdefault(name, []).append({"kind": kind, "detail": detail})

    # --- 指标 ---
    @staticmethod
    def metrics(c, w, m, e):
        if WRONG_COUNTS_AS == "both":
            wp, wr = w, w
        elif WRONG_COUNTS_AS == "recall_only":
            wp, wr = 0, w
        elif WRONG_COUNTS_AS == "precision_only":
            wp, wr = w, 0
        else:
            wp, wr = 0, 0
        pden, rden = c + wp + e, c + wr + m
        p = c / pden if pden else 0.0
        r = c / rden if rden else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
        return {"precision": p, "recall": r, "f1": f1,
                "pden": pden, "rden": rden}

    def per_field(self):
        out = {}
        for name, f in sorted(self.fields.items()):
            out[name] = dict(f, **self.metrics(f["correct"], f["wrong"],
                                               f["missing"], f["extra"]))
        return out

    def overall(self):
        tot = {"correct": 0, "wrong": 0, "missing": 0, "extra": 0}
        for f in self.fields.values():
            for k in tot:
                tot[k] += f[k]
        return dict(tot, **self.metrics(tot["correct"], tot["wrong"],
                                        tot["missing"], tot["extra"]))

    def passed(self):
        """critical 字段一出错即不通过；否则看整体 F1 是否达到阈值。"""
        if ENFORCE_CRITICAL and self.critical_hit:
            return False
        return self.overall()["f1"] >= PASS_F1_THRESHOLD

    def to_dict(self):
        return {"fields": self.per_field(), "overall": self.overall(),
                "critical_hit": sorted(self.critical_hit),
                "passed": self.passed(), "notes": self.notes,
                "items": self.items}


def _canon_item(item):
    """list 元素规范化：dict 按键排序后逐值做轻量规范化，供逐项相等比较。"""
    if isinstance(item, dict):
        out = {}
        for k in sorted(item):
            v = item[k]
            if isinstance(v, str):
                out[k] = N.norm_string(v)
            elif isinstance(v, bool):
                out[k] = v
            elif isinstance(v, (int, float)):
                out[k] = v
            else:
                out[k] = json.dumps(v, sort_keys=True, ensure_ascii=False)
        return out
    if isinstance(item, str):
        return N.norm_string(item)
    return item


def _score_list(name, exp, act, entry, fs):
    key = entry.get("key") or LIST_ALIGN_KEY_DEFAULT
    e_items = exp or []
    a_items = act or []
    if not isinstance(e_items, list) or not isinstance(a_items, list):
        fs.notes.append("%s 期望/实际必须是数组" % name)
        fs.add(name, "wrong", "类型不是数组")
        return
    emap, amap = {}, {}
    for it in e_items:
        k = it.get(key) if isinstance(it, dict) else None
        emap[k] = it
    for it in a_items:
        k = it.get(key) if isinstance(it, dict) else None
        amap[k] = it
    for k in emap:
        if k not in amap:
            fs.add(name, "missing", {key: k})
        elif _canon_item(emap[k]) == _canon_item(amap[k]):
            fs.add(name, "correct", {key: k})
        else:
            fs.add(name, "wrong", {key: k,
                                   "expected": _canon_item(emap[k]),
                                   "actual": _canon_item(amap[k])})
    for k in amap:
        if k not in emap:
            fs.add(name, "extra", {key: k})


def _score_summary(name, exp, act, entry, fs):
    """summary：期望为要点数组。实际为数组时三者都有意义；为文本时只报 recall。"""
    points = [N.norm_string(x) for x in (exp or [])]
    if isinstance(act, str):
        text = N.norm_string(act)
        for pt in points:
            fs.add(name, "correct" if pt in text else "missing", pt)
        fs.notes.append("%s 实际为自由文本，precision 不适用（只报 recall）" % name)
        return
    acts = [N.norm_string(x) for x in (act or [])]
    for pt in points:
        if pt in acts:
            fs.add(name, "correct", pt)
        elif any(pt in a or a in pt for a in acts):
            fs.add(name, "wrong", pt)
        else:
            fs.add(name, "missing", pt)
    for a in acts:
        if not any(a == pt or a in pt or pt in a for pt in points):
            fs.add(name, "extra", a)


def _close_enough(ftype, ev, av):
    if ftype == "money_fen":
        return abs(ev - av) <= MONEY_TOLERANCE_FEN
    if ftype == "rate_bp":
        return abs(ev - av) <= RATE_TOLERANCE_BP
    return ev == av


def _score_scalar(name, exp, act, entry, fs):
    ftype = entry["type"]
    try:
        ev = N.norm_scalar(ftype, exp, entry)
    except N.NormalizeError as e:
        fs.notes.append("%s 期望值无法归一化: %s" % (name, e))
        return
    if act is None:
        fs.add(name, "missing", str(exp))
        return
    try:
        av = N.norm_scalar(ftype, act, entry)
    except N.NormalizeError as e:
        fs.notes.append("%s 实际值无法归一化: %s" % (name, e))
        fs.add(name, "wrong", {"expected": str(exp), "actual": str(act), "why": str(e)})
        return
    if _close_enough(ftype, ev, av):
        fs.add(name, "correct", str(exp))
    else:
        fs.add(name, "wrong", {"expected": ev, "actual": av})


def score_fields(expected, actual, field_schema):
    """expected/actual 为 dict，field_schema 为「字段名 -> 类型定义」的 dict。

    返回 FieldScore；不做异常抛出，问题记为 note。
    """
    fs = FieldScore()
    for name, entry in field_schema.items():
        ftype = entry["type"]
        if ftype not in N.ALL_TYPES:
            fs.notes.append("%s 未知字段类型 %r" % (name, ftype))
            continue
        exp = (expected or {}).get(name)
        act = (actual or {}).get(name)
        if ftype == "list":
            _score_list(name, exp, act, entry, fs)
        elif ftype == "summary":
            _score_summary(name, exp, act, entry, fs)
        else:
            _score_scalar(name, exp, act, entry, fs)
        if entry.get("critical") and fs.fields.get(name):
            bad = sum(fs.fields[name][k] for k in ("wrong", "missing", "extra"))
            if bad:
                fs.critical_hit.append(name)
    return fs
