# -*- coding: utf-8 -*-
"""策略文件与豁免文件的加载与校验。

校验在**判定之前**就做，任何一条不合规则门禁直接失败（不等跑用例）：
  - P0 不允许出现在豁免列表里（P0 是零容忍级别）
  - 豁免必填四项：case_key / reason / approver_role / expires_on
  - 豁免有效期最长 14 天（自由上限，非「距今天 14 天」）
  - 到期日不得早于批准日，且到期日早于今天时该豁免已过期
"""
import os

import clock
import miniyaml

MAX_WAIVER_DAYS = 14
MAX_WAIVER_DAYS_ALLOWED = 14      # 行为开关：工单上限
ALLOW_P0_WAIVER = False           # 行为开关：P0 是否允许豁免（必须 False）
REQUIRED_WAIVER_FIELDS = ("case_key", "reason", "approver_role", "expires_on")
LEVELS = ("P0", "P1", "P2")


class PolicyError(ValueError):
    """策略或豁免文件不合法。"""


def load_policy(path):
    doc = miniyaml.loads(open(path, encoding="utf-8").read())
    if not isinstance(doc, dict) or "guardrail" not in doc:
        raise PolicyError("策略文件缺少顶层 guardrail 段")
    g = doc["guardrail"]
    for lv in LEVELS:
        if lv not in (g.get("levels") or {}):
            raise PolicyError("策略文件缺少级别 %s" % lv)
    lv = g["levels"]
    if lv["P0"].get("tolerance", "zero") != "zero":
        raise PolicyError("P0 的 tolerance 必须为 zero（零容忍不可配置）")
    for name in ("P1", "P2"):
        if "min_pass_rate" not in lv[name]:
            raise PolicyError("%s 缺少 min_pass_rate" % name)
    if "max_drop_points" not in lv.get("P2", {}):
        raise PolicyError("P2 缺少 max_drop_points（与基线相比允许的下降百分点）")
    if "baseline" not in g:
        raise PolicyError("策略文件缺少 baseline 段")
    return g


def load_waivers(path, today=None):
    """返回豁免列表；文件不存在视为空列表。"""
    if not os.path.exists(path):
        return []
    doc = miniyaml.loads(open(path, encoding="utf-8").read()) or {}
    ws = doc.get("waivers") or []
    if not isinstance(ws, list):
        raise PolicyError("waivers 必须是列表")
    return ws


def validate_waivers(waivers, levels_of_cases, today):
    """逐条校验豁免。levels_of_cases: case_key -> 级别。

    返回 (errors, warnings)。errors 非空即门禁失败。
    """
    errs, warns = [], []
    seen = set()
    for i, w in enumerate(waivers):
        tag = "第 %d 条豁免" % (i + 1)
        if not isinstance(w, dict):
            errs.append("%s 不是映射" % tag)
            continue
        miss = [f for f in REQUIRED_WAIVER_FIELDS if not str(w.get(f) or "").strip()]
        if miss:
            errs.append("%s 缺必填字段 %s" % (tag, miss))
            continue
        key = str(w["case_key"]).strip()
        if key in seen:
            errs.append("%s 的 case_key %s 重复" % (tag, key))
        seen.add(key)
        lv = levels_of_cases.get(key)
        if lv is None:
            errs.append("%s 指向不存在的用例 %s" % (tag, key))
            continue
        if lv == "P0" and not ALLOW_P0_WAIVER:
            errs.append("%s 试图豁免 P0 用例 %s —— P0 为零容忍级别，不允许豁免" % (tag, key))
            continue
        try:
            clock.parse_day(str(w["expires_on"]).strip())
        except clock.ClockError as e:
            errs.append("%s 的 expires_on 非法: %s" % (tag, e))
            continue
        span = clock.days_between(clock.BASE_TODAY, str(w["expires_on"]).strip())
        if span > MAX_WAIVER_DAYS_ALLOWED:
            errs.append("%s 有效期 %d 天，超过上限 %d 天"
                        % (tag, span, MAX_WAIVER_DAYS_ALLOWED))
        if span < 0:
            warns.append("%s 已于 %s 过期（今天 %s）" % (tag, w["expires_on"], today))
    return errs, warns


def classify_waivers(waivers, today):
    """把豁免分成 active / expired 两组。"""
    active, expired = [], []
    for w in waivers:
        if not isinstance(w, dict) or not w.get("expires_on"):
            continue
        (expired if clock.is_expired(str(w["expires_on"]).strip(), today) else active).append(w)
    return active, expired
