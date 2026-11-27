# -*- coding: utf-8 -*-
"""基线管理（set / show）与退化判定（compare）。

判定顺序本身是契约：
  1) 基线运行合法性 -> 不合法直接抛 BaselineError（命令 rc=2），不是「判定失败」
  2) suite_version 不同 -> 只在共有的 case_key 上比较，并在结果里写明范围
  3) 抖动处理 -> regression 用例重跑 N 次，任意一次通过即标 flaky、不计入退化
  4) 通过率降幅 > 阈值（默认 3pp）-> 失败
  5) must 翻转用例数 >= 阈值（默认 3）-> 失败          （flaky 已剔除）
  6) 平均分降幅 > 阈值（默认 0.05）-> warn
比率与分数差一律用 Fraction 精确计算，**不先四舍五入再比较**。
"""
from fractions import Fraction

import clock
import miniyaml

DEFAULT_RULES = {
    "max_pass_rate_drop_pp": 3,
    "max_must_flips": 3,
    "score_drop_warn": 0.05,
    "flaky_reruns": 2,
}
SET_PERMISSION = "eval.baseline.set"
SUGGEST_AFTER_BETTER_RUNS = 3

# ---- 行为开关（集中在此文件，变异锚点稳定） ----
ENFORCE_BASELINE_RUN_VALID = True
ENFORCE_VERSION_INTERSECTION = True
FLAKY_EXCLUDED_FROM_REGRESSION = True
ENFORCE_PASS_RATE_DROP = True
ENFORCE_MUST_FLIPS = True


class BaselineError(ValueError):
    """基线不合法 / 权限不足 / 理由缺失。"""


def load_suite(path):
    doc = miniyaml.loads(open(path, encoding="utf-8").read()) or {}
    if "suite" not in doc:
        raise BaselineError("套件配置缺少 suite 段")
    rules = dict(DEFAULT_RULES)
    rules.update(doc.get("baseline_rules") or {})
    return doc["suite"], rules, doc


def check_settable(run, suite_version, permissions, reason):
    """set 的门槛。返回 None 表示可以设为基线，否则抛 BaselineError。"""
    if SET_PERMISSION not in (permissions or ()):
        raise BaselineError("缺少权限 %s，不能设置基线" % SET_PERMISSION)
    if not str(reason or "").strip():
        raise BaselineError("设置基线必须填写理由")
    if run.get("suite") != suite_version.get("name"):
        raise BaselineError("运行属于套件 %r，与当前套件 %r 不符"
                            % (run.get("suite"), suite_version.get("name")))
    if ENFORCE_BASELINE_RUN_VALID:
        if run.get("status") != "completed":
            raise BaselineError("运行 status=%r，只有 completed 的运行可作基线"
                                % run.get("status"))
        if run.get("errors"):
            raise BaselineError("运行存在执行错误 %s，不能作为基线"
                                % (run.get("errors"),))
        if run.get("suite_version") != suite_version.get("version"):
            raise BaselineError("运行 suite_version=%r 与当前 %r 不同，不能作为基线"
                                % (run.get("suite_version"), suite_version.get("version")))
    return None


def show(baseline_file):
    doc = miniyaml.loads(open(baseline_file, encoding="utf-8").read()) or {}
    if not doc.get("baseline_run"):
        raise BaselineError("基线文件里没有 baseline_run")
    return doc


def _rate(cases):
    if not cases:
        return Fraction(0)
    return Fraction(sum(1 for c in cases if c["passed"]), len(cases))


def _avg(cases):
    if not cases:
        return Fraction(0)
    # 分数先转成「千分之一」整数再加总，避免浮点漂移
    total = sum(int(round(float(c.get("score", 0.0)) * 1000)) for c in cases)
    return Fraction(total, len(cases) * 1000)


def _must_broken(base_case, cur_case):
    """该用例里是否有 must 要点从 hit=True 变成 hit=False。"""
    bp = {p["key"]: p for p in (base_case.get("points") or []) if p.get("must")}
    cp = {p["key"]: p for p in (cur_case.get("points") or []) if p.get("must")}
    for k, b in bp.items():
        if b.get("hit") and k in cp and not cp[k].get("hit", False):
            return True
    return False


def compare(base_run, cur_run, rules=None):
    """返回结果字典。base_run 不合法时抛 BaselineError。"""
    rules = dict(DEFAULT_RULES, **(rules or {}))
    if ENFORCE_BASELINE_RUN_VALID:
        if base_run.get("status") != "completed":
            raise BaselineError("基线运行 status=%r，不能用于比较" % base_run.get("status"))
        if base_run.get("errors"):
            raise BaselineError("基线运行存在执行错误 %s，不能用于比较"
                                % (base_run.get("errors"),))

    bmap = {c["case_key"]: c for c in base_run.get("cases") or []}
    cmap = {c["case_key"]: c for c in cur_run.get("cases") or []}
    only_b = sorted(set(bmap) - set(cmap))
    only_c = sorted(set(cmap) - set(bmap))
    both = sorted(set(bmap) & set(cmap))

    same_version = base_run.get("suite_version") == cur_run.get("suite_version")
    keys = both if (ENFORCE_VERSION_INTERSECTION and not same_version) else sorted(set(bmap) | set(cmap))
    if same_version and ENFORCE_VERSION_INTERSECTION is False:
        keys = sorted(set(bmap) | set(cmap))

    b_used = [bmap[k] for k in keys if k in bmap]
    c_used = [cmap[k] for k in keys if k in cmap]

    rate_b = _rate(b_used)
    rate_c = _rate(c_used)
    drop_pp = (rate_b - rate_c) * 100

    regressions, fixes = [], []
    for k in keys:
        b, c = bmap.get(k), cmap.get(k)
        if b is None or c is None:
            continue
        if b["passed"] and not c["passed"]:
            regressions.append(k)
        elif (not b["passed"]) and c["passed"]:
            fixes.append(k)

    # 抖动：regression 用例重跑，任一次通过即 flaky
    reruns = cur_run.get("reruns") or {}
    flaky, real_regressions = [], []
    for k in regressions:
        rr = reruns.get(k)
        if rr and any(rr):
            flaky.append({"case_key": k, "reruns": list(rr)})
        else:
            real_regressions.append(k)
    effective = [k for k in regressions
                 if (not FLAKY_EXCLUDED_FROM_REGRESSION) or k not in {f["case_key"] for f in flaky}]

    must_flips = [k for k in effective
                  if _must_broken(bmap[k], cmap[k])]

    # 按 tag 的通过率差
    tag_delta = {}
    for tag in sorted({t for k in keys for t in ((bmap.get(k) or {}).get("tags") or [])}):
        bt = [bmap[k] for k in keys if k in bmap and tag in (bmap[k].get("tags") or [])]
        ct = [cmap[k] for k in keys if k in cmap and tag in (cmap[k].get("tags") or [])]
        tag_delta[tag] = {"baseline": _rate(bt), "current": _rate(ct),
                          "delta_pp": (_rate(ct) - _rate(bt)) * 100}

    score_b, score_c = _avg(b_used), _avg(c_used)
    score_delta = score_c - score_b

    reasons = []
    verdict = "pass"
    if ENFORCE_PASS_RATE_DROP:
        limit = Fraction(str(rules["max_pass_rate_drop_pp"]))
        if drop_pp > limit:
            verdict = "fail"
            reasons.append("通过率 %s%% 比基线 %s%% 下降 %s 个百分点，超过允许的 %s"
                           % (_p(rate_c), _p(rate_b), _f(drop_pp), rules["max_pass_rate_drop_pp"]))
    if ENFORCE_MUST_FLIPS:
        if len(must_flips) >= int(rules["max_must_flips"]):
            verdict = "fail"
            reasons.append("must 要点翻转用例 %d 条，达到阈值 %d"
                           % (len(must_flips), rules["max_must_flips"]))
    if score_delta < -Fraction(str(rules["score_drop_warn"])):
        if verdict == "pass":
            verdict = "warn"
        reasons.append("平均分下降 %s，超过告警线 %s"
                       % (_f(-score_delta, 4), rules["score_drop_warn"]))

    return {
        "base_run": base_run.get("run_id"),
        "cur_run": cur_run.get("run_id"),
        "scope": {
            "same_suite_version": same_version,
            "compared_cases": len(keys),
            "only_in_baseline": len(only_b),
            "only_in_current": len(only_c),
            "note": ("suite_version 相同，比较全部用例"
                     if same_version else
                     "suite_version 不同（基线 %s / 本次 %s），只比较共有的 %d 条用例；"
                     "基线独有 %d 条、本次独有 %d 条不参与比较"
                     % (base_run.get("suite_version"), cur_run.get("suite_version"),
                        len(keys), len(only_b), len(only_c))),
            "only_in_baseline_keys": only_b[:5],
            "only_in_current_keys": only_c[:5],
        },
        "pass_rate": {"baseline": rate_b, "current": rate_c, "drop_pp": drop_pp},
        "score": {"baseline": score_b, "current": score_c, "delta": score_delta},
        "tag_delta": tag_delta,
        "regressions": real_regressions,
        "regressions_all": regressions,
        "flaky": flaky,
        "fixes": fixes,
        "must_flips": must_flips,
        "verdict": verdict,
        "reasons": reasons,
    }


def suggest_update(history, base_run_id):
    """连续 N 次运行都优于基线则建议更新基线（不自动更新）。"""
    if len(history) < SUGGEST_AFTER_BETTER_RUNS:
        return {"suggested": False, "consecutive_better": len(history),
                "need": SUGGEST_AFTER_BETTER_RUNS}
    n = 0
    for item in reversed(history):
        if item.get("better_than_baseline"):
            n += 1
        else:
            break
    return {"suggested": n >= SUGGEST_AFTER_BETTER_RUNS,
            "consecutive_better": n, "need": SUGGEST_AFTER_BETTER_RUNS,
            "auto_update": False}


def _p(fr):
    return "%.4f" % (float(fr) * 100)


def _f(fr, nd=4):
    s = "%.*f" % (nd, float(fr))
    return s.rstrip("0").rstrip(".") if "." in s else s


def markdown(res, today=None):
    L = ["## 回归退化判定：%s" % res["verdict"].upper(), "",
         "- 基线运行：`%s`　本次运行：`%s`" % (res["base_run"], res["cur_run"])]
    if today:
        L.append("- 判定日：%s（冻结基准日）" % today)
    sc = res["scope"]
    L += ["- 比较范围：%s" % sc["note"], "",
          "| 指标 | 基线 | 本次 | 变化 |", "| --- | --- | --- | --- |",
          "| 通过率 | %s%% | %s%% | %s 个百分点 |"
          % (_p(res["pass_rate"]["baseline"]), _p(res["pass_rate"]["current"]),
             _f(res["pass_rate"]["drop_pp"])),
          "| 平均分 | %s | %s | %s |"
          % (_f(res["score"]["baseline"]), _f(res["score"]["current"]),
             _f(res["score"]["delta"]))]
    if res["tag_delta"]:
        L += ["", "### 按 tag 的通过率变化", "",
              "| tag | 基线 | 本次 | 变化(pp) |", "| --- | --- | --- | --- |"]
        for tag, d in sorted(res["tag_delta"].items()):
            L.append("| %s | %s%% | %s%% | %s |"
                     % (tag, _p(d["baseline"]), _p(d["current"]), _f(d["delta_pp"])))
    L += ["", "### 翻转用例", "",
          "- regression（基线通过、本次失败）：**%d** 条%s"
          % (len(res["regressions"]),
             ("：" + ", ".join(res["regressions"][:8])) if res["regressions"] else ""),
          "- fix（基线失败、本次通过）：**%d** 条%s"
          % (len(res["fixes"]), ("：" + ", ".join(res["fixes"][:8])) if res["fixes"] else "")]
    if res["flaky"]:
        L.append("- flaky（重跑中通过过，**不计入退化**）：**%d** 条 —— %s"
                 % (len(res["flaky"]),
                    ", ".join("%s(重跑 %s)" % (f["case_key"], f["reruns"]) for f in res["flaky"])))
    if res["must_flips"]:
        L.append("- must 要点翻转：**%d** 条 —— %s"
                 % (len(res["must_flips"]), ", ".join(res["must_flips"][:8])))
    if res["reasons"]:
        L += ["", "### 判定原因", ""] + ["- %s" % r for r in res["reasons"]]
    L.append("")
    return "\n".join(L)
