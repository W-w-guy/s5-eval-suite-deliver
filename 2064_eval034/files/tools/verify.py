# -*- coding: utf-8 -*-
"""逐条断言本单 AC。任何一条失败即非零退出。"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import baseline as B   # noqa: E402
import clock           # noqa: E402
import engine          # noqa: E402

DATA = os.path.join(ROOT, "data")
RUNS = os.path.join(DATA, "runs")
SUITE = os.path.join(DATA, "suite.yaml")
TODAY = clock.BASE_TODAY
RESULTS = []


def ok(code, title, detail=""):
    RESULTS.append(True)
    print("[PASS] %s %s %s" % (code, title, detail))


def bad(code, title, detail=""):
    RESULTS.append(False)
    print("[FAIL] %s %s %s" % (code, title, detail))


def check(code, cond, title, detail=""):
    (ok if cond else bad)(code, title, detail)


def cli(*args):
    r = subprocess.run([sys.executable, "-m", "pkg.cmd"] + list(args), cwd=ROOT,
                       capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def main():
    base = engine.baseline_run()
    suite, rules, _doc = B.load_suite(SUITE)

    # ---------- 场景判定总览 ----------
    verdicts = {}
    for name, fn, expect, _why in engine.SCENARIOS:
        run = fn()
        if expect == "error":
            try:
                B.compare(run, engine.cur_drop2(), rules)
                verdicts[name] = "no-error"
            except B.BaselineError:
                verdicts[name] = "error"
            continue
        verdicts[name] = B.compare(base, run, rules)["verdict"]
    wrong = [(n, e, verdicts[n]) for n, _f, e, _w in engine.SCENARIOS if verdicts[n] != e]
    check("V01", not wrong and len(engine.SCENARIOS) == 9,
          "9 个场景的判定结果与设计一致", "场景 %d 个；不一致 %s" % (len(engine.SCENARIOS), wrong or []))

    # ---------- AC1：降 4pp 失败 / 降 2pp 通过 ----------
    r4 = B.compare(base, engine.cur_drop4(), rules)
    r2 = B.compare(base, engine.cur_drop2(), rules)
    check("V02", r4["pass_rate"]["drop_pp"] == 4,
          "降 4 个百分点时降幅算得恰好 4", "实测 %s" % B._f(r4["pass_rate"]["drop_pp"]))
    check("V03", r4["verdict"] == "fail", "降 4 个百分点时判定失败",
          "verdict=%s" % r4["verdict"])
    check("V04", float(r2["pass_rate"]["drop_pp"]) == 1.6,
          "降 2pp 场景的降幅是 1.6（125 分母下的精确值）",
          "实测 %s" % B._f(r2["pass_rate"]["drop_pp"]))
    check("V05", r2["verdict"] == "pass", "降幅低于阈值时判定通过",
          "verdict=%s" % r2["verdict"])
    # 两场景的 must 翻转都未达阈值，说明结论只由通过率降幅决定
    check("V06", len(r4["must_flips"]) < 3 and len(r2["must_flips"]) < 3,
          "两场景的 must 翻转都未达 3 条（结论只由通过率降幅决定）",
          "4pp 场景 %d 条 / 2pp 场景 %d 条" % (len(r4["must_flips"]), len(r2["must_flips"])))
    # 阈值 3pp 的边界：恰好 3.0 应通过，3.2 应失败（取整探针）
    rr = B.compare(base, engine.cur_round(), rules)
    check("V07", float(rr["pass_rate"]["drop_pp"]) == 3.2,
          "取整探针：降幅 3.2000 个百分点按精确值参与判定",
          "实测 %s" % B._f(rr["pass_rate"]["drop_pp"]))
    check("V08", rr["verdict"] == "fail",
          "降 3.2 个百分点（>3）时判定失败（若四舍五入成 3 会假通过）",
          "verdict=%s" % rr["verdict"])
    rc, out = cli("compare", "--run", "CUR_DROP4")
    check("V09", rc == 1 and "FAIL" in out,
          "compare 命令实测退出码 1 且摘要标 FAIL", "rc=%d" % rc)
    rc2, _ = cli("compare", "--run", "CUR_DROP2")
    check("V10", rc2 == 0, "通过场景的退出码为 0（正向对照）", "rc=%d" % rc2)

    # ---------- AC2：抖动重跑，2 次中 1 次通过标 flaky 且不计入退化 ----------
    rf = B.compare(base, engine._flaky_cases(), rules)
    check("V11", len(rf["regressions_all"]) == 3,
          "flaky 场景里翻转用例共 3 条", "实测 %d 条 %s"
          % (len(rf["regressions_all"]), rf["regressions_all"]))
    check("V12", len(rf["flaky"]) == 2,
          "其中 2 条被标为 flaky（重跑 2 次里各通过过 1 次）",
          "flaky=%s" % [f["case_key"] for f in rf["flaky"]])
    check("V13", rf["regressions"] == ["KB-115"],
          "只有两次都失败的 KB-115 留在 regression 清单",
          "regressions=%s" % rf["regressions"])
    check("V14", len(rf["must_flips"]) == 1,
          "flaky 剔除后 must 翻转只剩 1 条（未达阈值 3）",
          "must_flips=%s" % rf["must_flips"])
    check("V15", rf["verdict"] == "pass",
          "3 条翻转全部含 must 要点，但剔除 flaky 后不判退化",
          "verdict=%s（若不剔除会是 3 条 -> fail）" % rf["verdict"])
    # 对照：把 flaky 也算进去的话 must 翻转就是 3 条，会判失败
    saved = B.FLAKY_EXCLUDED_FROM_REGRESSION
    try:
        B.FLAKY_EXCLUDED_FROM_REGRESSION = False
        rf2 = B.compare(base, engine._flaky_cases(), rules)
    finally:
        B.FLAKY_EXCLUDED_FROM_REGRESSION = saved
    check("V16", len(rf2["must_flips"]) == 3 and rf2["verdict"] == "fail",
          "反向对照：若把 flaky 计入，must 翻转 3 条即判失败（证明剔除真的起了作用）",
          "must=%d verdict=%s" % (len(rf2["must_flips"]), rf2["verdict"]))
    check("V17", all(f["reruns"] for f in rf["flaky"]),
          "flaky 条目带重跑明细可供复核",
          "%s" % [(f["case_key"], f["reruns"]) for f in rf["flaky"]])
    rc3, _ = cli("compare", "--run", "CUR_FLAKY")
    check("V18", rc3 == 0, "flaky 场景命令退出码为 0", "rc=%d" % rc3)

    # ---------- AC3：suite_version 不同只比共有用例并写明范围 ----------
    rv = B.compare(base, engine.cur_ver_diff(), rules)
    check("V19", rv["scope"]["same_suite_version"] is False,
          "识别出版本不同（基线 v1 / 本次 v2）",
          "same=%s" % rv["scope"]["same_suite_version"])
    check("V20", rv["scope"]["compared_cases"] == 113,
          "只比较共有的 113 条用例", "compared=%d" % rv["scope"]["compared_cases"])
    check("V21", rv["scope"]["only_in_baseline"] == 12
          and rv["scope"]["only_in_current"] == 10,
          "基线独有 12 条、本次独有 10 条被排除在比较之外",
          "only_base=%d only_cur=%d" % (rv["scope"]["only_in_baseline"],
                                        rv["scope"]["only_in_current"]))
    check("V22", "只看共有" in rv["scope"]["note"] or "只比较共有" in rv["scope"]["note"],
          "结果里写明比较范围", "note=%s" % rv["scope"]["note"][:60])
    # 版本相同的运行，比较范围应是全部 125 条
    rs = B.compare(base, engine.cur_drop2(), rules)
    check("V23", rs["scope"]["compared_cases"] == 125
          and rs["scope"]["same_suite_version"] is True,
          "版本相同时比较全部 125 条（对照）", "compared=%d" % rs["scope"]["compared_cases"])
    # 关键：若不做共有用例限制，本次通过率会算成 112/135 从而虚高降幅
    cur_vd = engine.cur_ver_diff()["cases"]
    naive_rate = B.Fraction(sum(1 for c in cur_vd if c["passed"]), len(cur_vd))
    naive_drop = (B.Fraction(115, 125) - naive_rate) * 100
    check("V24", len(cur_vd) == 123 and float(naive_drop) != float(rv["pass_rate"]["drop_pp"]),
          "不做共有用例限制时分母是 123（含新增 10 条），与实际比较的 113 条不同",
          "naive 分母=%d drop=%.4f ｜ 实际分母=%d drop=%.4f"
          % (len(cur_vd), float(naive_drop), rv["scope"]["compared_cases"],
             float(rv["pass_rate"]["drop_pp"])))
    new_fail = [c for c in cur_vd if c["case_key"].startswith("KB-NEW-")]
    check("V25", len(new_fail) == 10 and all(not c["passed"] for c in new_fail)
          and not any(k.startswith("KB-NEW-") for k in rv["regressions"]),
          "新增的 10 条全失败，但不计入本次比较（不出现在 regression 清单里）",
          "新增 %d 条，regression=%s" % (len(new_fail), rv["regressions"]))
    rc4, _ = cli("compare", "--run", "CUR_VER_DIFF")
    check("V26", rc4 == 0, "版本差异场景命令退出码为 0", "rc=%d" % rc4)

    # ---------- AC4：有执行错误的运行不能作基线 ----------
    rc_a, out_a = cli("set", "--run", "BASE_FAILED", "--reason", "试图设为基线",
                      "--permissions", "eval.baseline.set")
    check("V27", rc_a == 2, "set 拒绝 status=failed 的运行（命令报错而非判定失败）",
          "rc=%d" % rc_a)
    check("V28", "拒绝设置基线" in out_a, "set 输出明确的拒绝原因（status=failed）",
          out_a.strip().splitlines()[-1][:70] if out_a.strip() else "")
    rc_b, out_b = cli("set", "--run", "BASE_WITH_ERRORS", "--reason", "试图设为基线",
                      "--permissions", "eval.baseline.set")
    check("V29", rc_b == 2, "set 拒绝 errors 非空的运行", "rc=%d" % rc_b)
    check("V30", "拒绝设置基线" in out_b, "set 输出明确的拒绝原因（errors 非空）",
          out_b.strip().splitlines()[-1][:70] if out_b.strip() else "")
    rc6, _ = cli("set", "--run", "BASE_V1", "--reason", "首版基线",
                 "--permissions", "eval.baseline.set")
    check("V31", rc6 == 0, "合规运行可以被设为基线（正向对照）", "rc=%d" % rc6)
    rc7, _ = cli("set", "--run", "BASE_V1", "--reason", "",
                 "--permissions", "eval.baseline.set")
    check("V32", rc7 == 2, "不填理由时 set 报错", "rc=%d" % rc7)
    rc8, _ = cli("set", "--run", "BASE_V1", "--reason", "x", "--permissions", "other")
    check("V33", rc8 == 2, "缺少 eval.baseline.set 权限时 set 报错", "rc=%d" % rc8)
    try:
        B.compare(engine.run_error_errors(), engine.cur_drop2(), rules)
        raised = False
    except B.BaselineError:
        raised = True
    check("V34", raised, "compare 遇到有执行错误的基线同样报错", "")

    # ---------- 结构与配置 ----------
    check("V35", rules["max_pass_rate_drop_pp"] == 3
          and rules["max_must_flips"] == 3
          and rules["score_drop_warn"] == 0.05,
          "判定规则与工单默认值一致（3pp / 3 条 / 0.05）",
          "%s" % {k: rules[k] for k in ("max_pass_rate_drop_pp", "max_must_flips",
                                        "score_drop_warn")})
    # 两处定义的默认值必须一致（否则「改了代码没改配置」这种情况会被静默吞掉）
    import miniyaml
    yr = (miniyaml.loads(open(SUITE, encoding="utf-8").read()) or {}).get("baseline_rules") or {}
    drift = [k for k in ("max_pass_rate_drop_pp", "max_must_flips",
                         "score_drop_warn", "flaky_reruns")
             if yr.get(k) != B.DEFAULT_RULES[k]]
    check("V43", not drift,
          "suite.yaml 里的默认规则与代码 DEFAULT_RULES 完全一致（两处定义不得漂移）",
          "不一致项 %s ｜ yaml=%s 代码=%s" % (drift or "无", yr.get("max_pass_rate_drop_pp"),
                                            B.DEFAULT_RULES["max_pass_rate_drop_pp"]))
    # 规则可被 suite.yaml 覆盖
    over = dict(rules, max_pass_rate_drop_pp=5)
    check("V36", B.compare(base, engine.cur_drop4(), over)["verdict"] == "pass",
          "suite.yaml 覆盖阈值后按新规则判定（阈值放宽到 5pp，4pp 场景转为通过）",
          "默认 fail ／ 覆盖后 %s" % B.compare(base, engine.cur_drop4(), over)["verdict"])
    rm = B.compare(base, engine.cur_mustflip(), rules)
    check("V37", float(rm["pass_rate"]["drop_pp"]) == 0 and len(rm["must_flips"]) == 3
          and rm["verdict"] == "fail",
          "must 判据可独立触发：通过率不降但 must 翻转 3 条即判失败（CUR_MUSTFLIP）",
          "drop=%s must=%d verdict=%s" % (B._f(rm["pass_rate"]["drop_pp"]),
                                          len(rm["must_flips"]), rm["verdict"]))
    check("V38", float(r4["pass_rate"]["drop_pp"]) == 4 and len(r4["must_flips"]) == 2,
          "4pp 场景的 must 翻转只有 2 条（<3），失败只能归因于通过率降幅",
          "must=%d" % len(r4["must_flips"]))
    su = B.suggest_update([{"better_than_baseline": True}] * 3, "BASE_V1")
    check("V39", su["suggested"] is True and su["auto_update"] is False,
          "连续 3 次优于基线时建议更新但不自动更新",
          "%s" % {k: su[k] for k in ("consecutive_better", "suggested", "auto_update")})
    su2 = B.suggest_update([{"better_than_baseline": True}] * 2, "BASE_V1")
    check("V40", su2["suggested"] is False, "只连续 2 次时不给建议", "")
    check("V41", all(os.path.exists(os.path.join(RUNS, n + ".json"))
                     for n, _f, _e, _w in engine.SCENARIOS),
          "9 个场景的运行记录全部落盘", "")

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    pr = subprocess.run([sys.executable, "-m", "pytest", "tests", "-v", "--no-header",
                         "-p", "no:cacheprovider", "-o", "addopts="],
                        cwd=ROOT, capture_output=True, env=env)
    out = (pr.stdout + pr.stderr).decode("utf-8", "replace")
    npass = out.count("PASSED")
    check("V42", pr.returncode == 0 and npass >= 30,
          "pytest 全绿且用例数不少于 30", "PASSED=%d rc=%d" % (npass, pr.returncode))

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r)
    print("")
    print("SUMMARY %d/%d PASS" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
