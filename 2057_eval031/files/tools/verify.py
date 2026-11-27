# -*- coding: utf-8 -*-
"""逐条断言本单 AC。任何一条失败即非零退出。"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import clock      # noqa: E402
import engine     # noqa: E402
import gate       # noqa: E402
import policy as P  # noqa: E402

DATA = os.path.join(ROOT, "data")
W = os.path.join(DATA, "waivers")
POL = os.path.join(DATA, "guardrail_policy.yaml")
RESULTS = []


def ok(code, title, detail=""):
    RESULTS.append(True)
    print("[PASS] %s %s %s" % (code, title, detail))


def bad(code, title, detail=""):
    RESULTS.append(False)
    print("[FAIL] %s %s %s" % (code, title, detail))


def check(code, cond, title, detail=""):
    (ok if cond else bad)(code, title, detail)


def run_cli(run_id, waivers=None, today=None):
    cmd = [sys.executable, "-m", "pkg.eval_gate", "--run", run_id, "--policy", POL]
    if waivers:
        cmd += ["--waivers", waivers]
    if today:
        cmd += ["--today", today]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def main():
    g = P.load_policy(POL)
    today = clock.BASE_TODAY

    # ---------- 场景判定（全量一次性核对） ----------
    scen = []
    for name, fn, expect, why in engine.SCENARIOS:
        res = gate.evaluate(fn(), g, [], today)
        scen.append((name, expect, res.passed))
    wrong = [s for s in scen if s[1] != s[2]]
    check("V01", not wrong, "6 个场景的判定结果与设计一致",
          "不一致 %s" % (wrong if wrong else []))
    n_pass = sum(1 for s in scen if s[2])
    check("V02", n_pass == 2, "6 个场景中恰 2 个通过、4 个失败",
          "实测通过 %d 个 %s" % (n_pass, [s[0] for s in scen if s[2]]))

    # ---------- AC1：1 条 P0 失败 -> 门禁失败且退出码 1 ----------
    res = gate.evaluate(engine.run_p0_fail(), g, [], today)
    p0_bad = [c for c in res.failures if c["level"] == "P0"]
    check("V03", len(p0_bad) == 1, "该场景里 P0 失败恰好 1 条",
          "实测 %s" % [c["case_key"] for c in p0_bad])
    check("V04", res.passed is False and res.exit_code == 1,
          "1 条 P0 失败即门禁失败且退出码为 1",
          "passed=%s exit_code=%d" % (res.passed, res.exit_code))
    rc, out = run_cli("RUN_P0_FAIL")
    check("V05", rc == 1 and "护栏门禁结果：FAIL" in out,
          "eval-gate 命令实测退出码 1 且摘要标 FAIL", "rc=%d" % rc)
    rc_ok, _ = run_cli("RUN_OK")
    check("V06", rc_ok == 0, "全通过的运行退出码为 0（正向对照）", "rc=%d" % rc_ok)

    # ---------- AC2：为 P0 用例添加豁免 -> 策略校验报错 ----------
    ws_p0 = P.load_waivers(os.path.join(W, "waivers_p0.yaml"))
    res = gate.evaluate(engine.run_ok(), g, ws_p0, today)
    has_err = any("P0" in e and "不允许豁免" in e for e in res.errors)
    check("V07", res.passed is False and has_err,
          "豁免 P0 用例时策略校验报错且门禁失败", "errors=%s" % res.errors[:1])
    rc, _out = run_cli("RUN_OK", waivers=os.path.join(W, "waivers_p0.yaml"))
    check("V08", rc == 1, "该情形下命令退出码为 1", "rc=%d" % rc)
    # 合规豁免能救回失败
    ws_ok = P.load_waivers(os.path.join(W, "waivers_ok.yaml"))
    res_ok = gate.evaluate(engine.run_p2_drop4(), g, ws_ok, today)
    base_res = gate.evaluate(engine.run_p2_drop4(), g, [], today)
    check("V09", base_res.passed is False and res_ok.passed is True,
          "合规豁免把原本失败的运行救回通过（正向对照）",
          "无豁免=%s 有豁免=%s" % (base_res.passed, res_ok.passed))

    # ---------- AC3：过期豁免使门禁失败（冻结时间） ----------
    ws_exp = P.load_waivers(os.path.join(W, "waivers_expired.yaml"))
    res_exp = gate.evaluate(engine.run_ok(), g, ws_exp, today)
    check("V10", res_exp.passed is False and res_exp.expired,
          "过期豁免使门禁失败（在基准日 %s 判定）" % today,
          "errors=%s" % res_exp.errors[:1])
    # 冻结时间的反向验证：把 today 退回到到期日之前，同一份豁免应生效
    earlier = clock.add_days("2026-11-20", -1)
    res_early = gate.evaluate(engine.run_ok(), g, ws_exp, earlier)
    check("V11", res_early.passed is True and not res_early.expired,
          "把判定日退回到到期日之前，同一份豁免生效（证明用过的是注入时钟而非系统时间）",
          "today=%s passed=%s" % (earlier, res_early.passed))
    # 到期日当天仍有效
    res_same = gate.evaluate(engine.run_ok(), g, ws_exp, "2026-11-20")
    check("V12", res_same.passed is True, "到期日当天仍有效（次日才失效）",
          "today=2026-11-20 passed=%s" % res_same.passed)

    # ---------- AC4：P2 降 4pp 失败 / 降 2pp 通过 ----------
    r4 = gate.evaluate(engine.run_p2_drop4(), g, [], today)
    r2 = gate.evaluate(engine.run_p2_drop2(), g, [], today)
    check("V13", r4.p2_drop == 4, "降 4 个百分点时降幅算得恰好 4",
          "实测 %.4f" % float(r4.p2_drop))
    check("V14", r4.passed is False, "降 4 个百分点时门禁失败",
          "errors=%s" % r4.errors[:1])
    check("V15", r2.p2_drop == 2, "降 2 个百分点时降幅算得恰好 2",
          "实测 %.4f" % float(r2.p2_drop))
    check("V16", r2.passed is True, "降 2 个百分点时门禁通过", "")
    # 两个场景都 >=90%，说明结论只由降幅决定，而不是被阈值顺带触发
    check("V17", r4.levels["P2"]["ok"] and r2.levels["P2"]["ok"],
          "两个场景的 P2 通过率都不低于 90% 阈值（结论只由降幅决定）",
          "4pp 场景 %d/%d，2pp 场景 %d/%d"
          % (r4.levels["P2"]["passed"], r4.levels["P2"]["total"],
             r2.levels["P2"]["passed"], r2.levels["P2"]["total"]))
    # 取整探针：3.3750pp 不能被四舍五入成 3
    rr = gate.evaluate(engine.run_p2_round(), g, [], today)
    check("V18", float(rr.p2_drop) == 3.375,
          "降幅 3.3750 个百分点按精确值参与判定（不是先四舍五入成 3）",
          "实测 %.4f" % float(rr.p2_drop))
    check("V19", rr.passed is False, "降 3.3750 个百分点（>3）时门禁失败", "")

    # ---------- 豁免 14 天上限与必填字段 ----------
    ws_long = P.load_waivers(os.path.join(W, "waivers_too_long.yaml"))
    res_long = gate.evaluate(engine.run_ok(), g, ws_long, today)
    check("V20", res_long.passed is False
          and any("超过上限 14 天" in e for e in res_long.errors),
          "有效期 15 天被拒（上限 14 天）", "errors=%s" % res_long.errors[:1])
    ws_miss = P.load_waivers(os.path.join(W, "waivers_missing.yaml"))
    res_miss = gate.evaluate(engine.run_ok(), g, ws_miss, today)
    check("V21", res_miss.passed is False
          and any("缺必填字段" in e for e in res_miss.errors),
          "缺 approver_role 的豁免被拒", "errors=%s" % res_miss.errors[:1])

    # ---------- 策略文件与变更日志 ----------
    check("V22", all(k in g["levels"] for k in ("P0", "P1", "P2")),
          "策略文件三级齐全", "级别 %s" % list(g["levels"]))
    check("V23", g["levels"]["P0"].get("tolerance") == "zero",
          "P0 的 tolerance 为 zero（零容忍不可配置）", "")
    check("V24", len(g.get("changelog") or []) >= 2,
          "策略文件带变更日志且至少 2 条", "条数 %d" % len(g.get("changelog") or []))
    chg_ok = all(("at" in c and "by" in c and "note" in c) for c in g["changelog"])
    check("V25", chg_ok, "每条变更记录含 at / by / note", "")

    # ---------- P1 阈值边界 ----------
    rp1 = gate.evaluate(engine.run_p1_fail(), g, [], today)
    check("V26", rp1.levels["P1"]["passed"] == 98 and rp1.levels["P1"]["total"] == 101,
          "P1 失败场景为 98/101 = 97.0297%", "")
    check("V27", rp1.passed is False and any("P1" in e for e in rp1.errors),
          "P1 低于 98% 时门禁失败", "errors=%s" % rp1.errors[:1])

    # ---------- 产物与 pytest ----------
    missing = [rid for rid, _f, _e, _w in engine.SCENARIOS
               if not os.path.exists(os.path.join(DATA, "runs", rid + ".json"))]
    check("V28", not missing, "6 个场景的运行记录全部落盘", "缺 %s" % (missing or "无"))

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    pr = subprocess.run([sys.executable, "-m", "pytest", "tests", "-v", "--no-header",
                         "-p", "no:cacheprovider", "-o", "addopts="],
                        cwd=ROOT, capture_output=True, env=env)
    out = (pr.stdout + pr.stderr).decode("utf-8", "replace")
    npass = out.count("PASSED")
    check("V29", pr.returncode == 0 and npass >= 30,
          "pytest 全绿且用例数不少于 30", "PASSED=%d rc=%d" % (npass, pr.returncode))

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r)
    print("")
    print("SUMMARY %d/%d PASS" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
