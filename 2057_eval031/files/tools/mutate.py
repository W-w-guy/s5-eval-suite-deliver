# -*- coding: utf-8 -*-
"""变异测试：把引擎改坏 N 处，每处都必须让 verify 变红。

三条防假绿规则：
  1) 改坏后先重跑 gen.py 再 verify（否则读到旧产物，变异安静通过）；
  2) 锚点必须命中，没命中要报「变异本身失效」，不能算 MISSED 掩饰；
  3) 还原后必须再验一次原件全绿。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
PY = sys.executable

MUTATIONS = [
    ("M1", "P0 零容忍被关掉（AC1：1 条 P0 失败必须拦）", "pkg/gate.py",
     'if cfg["P0"].get("tolerance", "zero") == "zero":',
     'if False:'),
    ("M2", "P1 阈值 98% 被放宽到 90%（P1 失败场景会通过）", "pkg/gate.py",
     'entry["threshold"] = Fraction(str(cfg[lv]["min_pass_rate"])) / 100',
     'entry["threshold"] = Fraction(str(cfg[lv]["min_pass_rate"])) / 100 * Fraction(90, 98)'),
    ("M3", "P2 允许降幅 3 → 5 个百分点（4pp 场景会通过，AC4 失效）", "pkg/gate.py",
     '        limit = Fraction(str(cfg["P2"]["max_drop_points"]))',
     '        limit = Fraction(str(cfg["P2"]["max_drop_points"])) + 2'),
    ("M4", "降幅四舍五入（3.3750 → 3，取整探针会假通过）", "pkg/gate.py",
     'drop_pp = (base - res.levels["P2"]["rate"]) * 100',
     'drop_pp = Fraction(round(float((base - res.levels["P2"]["rate"]) * 100)), 1)'),
    ("M5", "关掉基线比较（只剩阈值判定）", "pkg/gate.py",
     "BASELINE_COMPARE = True", "BASELINE_COMPARE = False"),
    ("M6", "过期豁免不再导致失败（AC3 失效）", "pkg/gate.py",
     "EXPIRED_WAIVER_FAILS = True", "EXPIRED_WAIVER_FAILS = False"),
    ("M7", "允许豁免 P0（AC2 失效）", "pkg/policy.py",
     "ALLOW_P0_WAIVER = False", "ALLOW_P0_WAIVER = True"),
    ("M8", "豁免有效期上限 14 → 21 天（15 天不再被拒）", "pkg/policy.py",
     "MAX_WAIVER_DAYS_ALLOWED = 14", "MAX_WAIVER_DAYS_ALLOWED = 21"),
    ("M9", "到期日当天就算过期（应次日失效）", "pkg/clock.py",
     "    return days_between(expires_on, today) > 0",
     "    return days_between(expires_on, today) >= 0"),
    ("M10", "豁免不计为通过（豁免语义退化成只是「不在失败列表里」）", "pkg/gate.py",
     '        passed = sum(1 for c in sub\n'
     '                     if c["passed"] or str(c["case_key"]) in waived_keys)',
     '        passed = sum(1 for c in sub if c["passed"])'),
    ("M11", "豁免必填字段少查一项（approver_role 可缺）", "pkg/policy.py",
     'REQUIRED_WAIVER_FIELDS = ("case_key", "reason", "approver_role", "expires_on")',
     'REQUIRED_WAIVER_FIELDS = ("case_key", "reason", "expires_on")'),
]


def run(args):
    r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, env=ENV)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def main():
    rc, out = run(["tools/verify.py"])
    if rc != 0:
        print("[STOP] 原件不绿，先修原件：")
        print(out[-1200:])
        return 2
    print("[OK] 原件必须全绿 rc=0")

    caught, missed, invalid = [], [], []
    for mid, title, rel, old, new in MUTATIONS:
        fp = os.path.join(ROOT, rel)
        src = open(fp, encoding="utf-8").read()
        if old not in src:
            invalid.append((mid, "锚点没命中：%r" % old[:50]))
            print("[INVALID] %s %s -> 锚点没命中，变异本身失效" % (mid, title))
            continue
        open(fp, "w", encoding="utf-8", newline="\n").write(src.replace(old, new, 1))
        try:
            run(["pkg/engine.py"])
            rc2, out2 = run(["tools/verify.py"])
        finally:
            open(fp, "w", encoding="utf-8", newline="\n").write(src)
        if rc2 != 0:
            hit = [l for l in out2.splitlines() if l.startswith("[FAIL]")]
            caught.append(mid)
            print("[ OK ] %s %s -> 被抓到 %s" % (mid, title, hit[:1]))
        else:
            missed.append((mid, title))
            print("[MISS] %s %s -> 仍然全绿" % (mid, title))

    run(["pkg/engine.py"])
    rc3, out3 = run(["tools/verify.py"])
    if rc3 != 0:
        print("[STOP] 还原后原件不绿，还原失败")
        print(out3[-800:])
        return 3
    print("[OK] 还原后原件仍全绿 rc=0")
    print("")
    print("MUTATION CAUGHT %d / MISSED %d / INVALID %d"
          % (len(caught), len(missed), len(invalid)))
    return 0 if (not missed and not invalid) else 1


if __name__ == "__main__":
    sys.exit(main())
