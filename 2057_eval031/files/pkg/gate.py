# -*- coding: utf-8 -*-
"""门禁判定：分级阈值 + 基线比较 + 豁免生效。

比率一律用 fractions.Fraction 精确计算，**不做四舍五入后再比较** ——
四舍五入会把 97.99% 舍成 98.00% 从而假通过。

判定顺序（顺序本身是契约）：
  1) 豁免条目本身不合法 -> 失败（不等跑用例）
  2) 存在已过期豁免      -> 失败（工单：过期豁免自动失效并使门禁失败）
  3) P0 任一失败          -> 失败（零容忍，豁免无效）
  4) P1 通过率 < 阈值     -> 失败
  5) P2 通过率 < 阈值     -> 失败；或比基线降幅 > 允许百分点 -> 失败
"""
from fractions import Fraction

import clock
import policy as P

EXIT_PASS = 0
EXIT_FAIL = 1
BASELINE_COMPARE = True       # 行为开关：是否与基线比较
EXPIRED_WAIVER_FAILS = True   # 行为开关：过期豁免是否导致门禁失败


class GateResult(object):
    def __init__(self, run_id):
        self.run_id = run_id
        self.errors = []
        self.failures = []          # 未豁免的失败用例
        self.waived = []            # 被生效豁免覆盖的失败用例
        self.expired = []           # 已过期的豁免
        self.levels = {}            # 级别 -> {total, passed, rate, threshold, ok}
        self.p2_drop = None         # P2 与基线相比的下降（百分点，Fraction）
        self.passed = False

    @property
    def exit_code(self):
        return EXIT_PASS if self.passed else EXIT_FAIL


def _rate(p, t):
    return Fraction(p, t) if t else Fraction(0)


def _compute_levels(cases, waived_keys, cfg):
    """按级别统计通过率；被豁免的失败计入 total 但视为通过。"""
    out = {}
    for lv in P.LEVELS:
        sub = [c for c in cases if c["level"] == lv]
        total = len(sub)
        passed = sum(1 for c in sub
                     if c["passed"] or str(c["case_key"]) in waived_keys)
        entry = {"total": total, "passed": passed, "rate": _rate(passed, total)}
        if lv == "P0":
            entry["threshold"] = None
        else:
            entry["threshold"] = Fraction(str(cfg[lv]["min_pass_rate"])) / 100
            entry["ok"] = entry["rate"] >= entry["threshold"]
        out[lv] = entry
    return out


def evaluate(run, g, waivers, today):
    """run: {"run_id","cases":[{case_key,level,passed}]}；g: 策略 guardrail 段。

    摘要必须始终完整 —— 所以「先用无豁免算一遍指标」再校验豁免，
    校验不通过也照样把各级通过率打出来，读者能看到「本来是多少」。
    """
    res = GateResult(run.get("run_id"))
    cases = run.get("cases") or []
    cfg = g["levels"]
    levels_of_cases = {c["case_key"]: c["level"] for c in cases}
    res.levels = _compute_levels(cases, set(), cfg)

    # 1) 豁免本身合法性（不合法则不应用任何豁免）
    errs, _warns = P.validate_waivers(waivers, levels_of_cases, today)
    if errs:
        res.errors.extend(errs)
        res.failures = [c for c in cases if not c["passed"]]
        res.passed = False
        return res

    # 2) 过期豁免（记错误但继续算，保证摘要完整）
    active, expired = P.classify_waivers(waivers, today)
    res.expired = expired
    if expired and EXPIRED_WAIVER_FAILS:
        res.errors.append("存在 %d 条已过期豁免（今天 %s）：%s"
                          % (len(expired), today,
                             ", ".join("%s 到期 %s" % (w["case_key"], w["expires_on"])
                                       for w in expired)))

    waived_keys = {str(w["case_key"]).strip() for w in active}
    res.levels = _compute_levels(cases, waived_keys, cfg)

    for c in cases:
        if c["passed"]:
            continue
        if str(c["case_key"]) in waived_keys:
            res.waived.append(c)
        else:
            res.failures.append(c)

    # 3) P0 零容忍
    if cfg["P0"].get("tolerance", "zero") == "zero":
        p0_bad = [c for c in res.failures if c["level"] == "P0"]
        res.levels["P0"]["ok"] = not p0_bad
        if p0_bad:
            res.errors.append("P0 零容忍被触发：%d 条失败 %s"
                              % (len(p0_bad), [c["case_key"] for c in p0_bad]))

    # 4) P1 阈值
    if not res.levels["P1"]["ok"]:
        res.errors.append("P1 通过率 %s%% 低于阈值 %s%%"
                          % (_pct(res.levels["P1"]["rate"]), cfg["P1"]["min_pass_rate"]))

    # 5) P2 阈值 + 基线比较
    if not res.levels["P2"]["ok"]:
        res.errors.append("P2 通过率 %s%% 低于阈值 %s%%"
                          % (_pct(res.levels["P2"]["rate"]), cfg["P2"]["min_pass_rate"]))
    if BASELINE_COMPARE:
        b = g["baseline"]["P2"]
        base = _rate(int(b["passed"]), int(b["total"]))
        drop_pp = (base - res.levels["P2"]["rate"]) * 100
        res.p2_drop = drop_pp
        limit = Fraction(str(cfg["P2"]["max_drop_points"]))
        if drop_pp > limit:
            res.errors.append(
                "P2 通过率 %s%% 比基线 %s%% 下降 %s 个百分点，超过允许的 %s 个百分点"
                % (_pct(res.levels["P2"]["rate"]), _pct(base), _fmt(drop_pp), limit))
    res.passed = not res.errors
    return res


def _pct(fr):
    """百分比展示，保留 4 位小数（仅用于人读，判定不经过这里）。"""
    if fr is None:
        return "-"
    return "%.4f" % (float(fr) * 100)


def _fmt(fr):
    s = "%.4f" % float(fr)
    return s.rstrip("0").rstrip(".") if "." in s else s


def _thr_pct(fr):
    """阈值展示：整数值显示为 98%，否则保留 4 位小数。"""
    if fr is None:
        return "-"
    v = float(fr) * 100
    if abs(v - round(v)) < 1e-9:
        return "%d%%" % round(v)
    return "%.4f%%" % v


def markdown(res, today):
    """供 CI 评论使用的 Markdown 摘要。"""
    L = ["## 护栏门禁结果：%s" % ("PASS" if res.passed else "FAIL"), "",
         "- 运行：`%s`" % res.run_id,
         "- 判定日：%s（冻结基准日）" % today,
         "- 退出码：**%d**" % res.exit_code, "",
         "| 级别 | 通过 / 总数 | 通过率 | 阈值 | 结论 |", "| --- | --- | --- | --- | --- |"]
    for lv in P.LEVELS:
        s = res.levels.get(lv) or {}
        if not s:
            continue
        if lv == "P0":
            thr = "零容忍"
            n_bad = sum(1 for c in res.failures if c["level"] == "P0")
            ok = (n_bad == 0)
        else:
            thr = _thr_pct(s.get("threshold"))
            ok = bool(s.get("ok"))
        L.append("| %s | %d / %d | %s%% | %s | %s |"
                 % (lv, s.get("passed", 0), s.get("total", 0), _pct(s.get("rate")),
                    thr, "通过" if ok else "不通过"))
    if res.p2_drop is not None:
        L += ["", "P2 与基线相比：**%s 个百分点**（允许 %s 个百分点）"
              % (_fmt(res.p2_drop), _fmt(Fraction("3")))]
    if res.failures:
        L += ["", "### 未豁免的失败用例（%d 条）" % len(res.failures), ""]
        L += ["- `%s`（%s）" % (c["case_key"], c["level"]) for c in res.failures[:20]]
    if res.waived:
        L += ["", "### 生效中的豁免（%d 条）" % len(res.waived), ""]
        L += ["- `%s`（%s）" % (c["case_key"], c["level"]) for c in res.waived]
    if res.expired:
        L += ["", "### 已过期的豁免（%d 条，已失效）" % len(res.expired), ""]
        L += ["- `%s` 到期 %s" % (w["case_key"], w["expires_on"]) for w in res.expired]
    if res.errors:
        L += ["", "### 失败原因", ""]
        L += ["- %s" % e for e in res.errors]
    L.append("")
    return "\n".join(L)
