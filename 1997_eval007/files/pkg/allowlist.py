# -*- coding: utf-8 -*-
"""allowlist：记录已确认为虚构的条目。每条必须写确认人与日期。

校验在**扫描之前**做：格式不合规直接报错，避免「白名单悄悄失效」。
"""
import os

import clock
import miniyaml

REQUIRED = ("value", "confirmed_by", "confirmed_on")
MIN_CONFIRMERS = 1


class AllowlistError(ValueError):
    pass


def load(path):
    if not os.path.exists(path):
        return [], []
    doc = miniyaml.loads(open(path, encoding="utf-8").read()) or {}
    items = doc.get("allowlist") or []
    if not isinstance(items, list):
        raise AllowlistError("allowlist 必须是列表")
    errs = []
    clean = []
    for i, it in enumerate(items, 1):
        tag = "第 %d 条" % i
        if not isinstance(it, dict):
            errs.append("%s 不是映射" % tag)
            continue
        miss = [k for k in REQUIRED if not str(it.get(k) or "").strip()]
        if miss:
            errs.append("%s 缺必填字段 %s" % (tag, miss))
            continue
        try:
            clock.parse_day(str(it["confirmed_on"]).strip())
        except clock.ClockError as e:
            errs.append("%s 的 confirmed_on 非法: %s" % (tag, e))
            continue
        clean.append({"value": str(it["value"]).strip(),
                      "kind": str(it.get("kind") or "").strip(),
                      "reason": str(it.get("reason") or "").strip(),
                      "confirmed_by": str(it["confirmed_by"]).strip(),
                      "confirmed_on": str(it["confirmed_on"]).strip()})
    return clean, errs


def apply(findings, entries):
    """把命中 allowlist 的 Finding 标为 allowed=True 并从阻断集里剔除。"""
    vals = {(e["kind"], e["value"]) for e in entries}
    bare = {e["value"] for e in entries}
    out = []
    for f in findings:
        hit = ((f["kind"], f["text"]) in vals) or (f["text"] in bare)
        g = dict(f)
        g["allowed"] = bool(hit)
        out.append(g)
    return out


def blocking(findings):
    """需要阻断 CI 的命中：error 级、且未被 allowlist 放行。"""
    return [f for f in findings
            if f["level"] == "error" and not f.get("allowed")]


def warning(findings):
    return [f for f in findings
            if f["level"] == "warn" and not f.get("allowed")]
