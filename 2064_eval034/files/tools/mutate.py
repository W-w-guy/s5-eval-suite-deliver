# -*- coding: utf-8 -*-
"""变异测试：把判定逻辑改坏 N 处，每处都必须让 verify 变红。"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
PY = sys.executable

MUTATIONS = [
    ("M1", "关掉通过率降幅判定（AC1 失效）", "pkg/baseline.py",
     "ENFORCE_PASS_RATE_DROP = True", "ENFORCE_PASS_RATE_DROP = False"),
    ("M2", "降幅阈值 3 → 5 个百分点（4pp 不再失败）", "pkg/baseline.py",
     "    \"max_pass_rate_drop_pp\": 3,", "    \"max_pass_rate_drop_pp\": 5,"),
    ("M2b", "改 engine 里的 SUITE_YAML 阈值 3 → 5（配置文件侧）", "pkg/engine.py",
     "  max_pass_rate_drop_pp: 3", "  max_pass_rate_drop_pp: 5"),
    ("M3", "降幅四舍五入后再比较（3.2 → 3 假通过）", "pkg/baseline.py",
     "        if drop_pp > limit:",
     "        if Fraction(round(float(drop_pp)), 1) > limit:"),
    ("M4", "关掉 flaky 剔除（AC2 失效）", "pkg/baseline.py",
     "FLAKY_EXCLUDED_FROM_REGRESSION = True", "FLAKY_EXCLUDED_FROM_REGRESSION = False"),
    ("M5", "flaky 判定改成「两次都通过才算」（任一次通过不再算 flaky）", "pkg/baseline.py",
     "        if rr and any(rr):", "        if rr and all(rr):"),
    ("M6", "关掉版本交集（AC3 失效，比全部用例）", "pkg/baseline.py",
     "ENFORCE_VERSION_INTERSECTION = True", "ENFORCE_VERSION_INTERSECTION = False"),
    ("M7", "关掉基线合法性校验（AC4 失效）", "pkg/baseline.py",
     "ENFORCE_BASELINE_RUN_VALID = True", "ENFORCE_BASELINE_RUN_VALID = False"),
    ("M8", "must 翻转阈值 >= 改成 >（3 条不再触发）", "pkg/baseline.py",
     '        if len(must_flips) >= int(rules["max_must_flips"]):',
     '        if len(must_flips) > int(rules["max_must_flips"]):'),
    ("M9", "set 不校验 status（failed 运行也能设基线）", "pkg/baseline.py",
     '        if run.get("status") != "completed":',
     '        if False:'),
    ("M10", "set 不校验执行错误（errors 非空也能设基线）", "pkg/baseline.py",
     '        if run.get("errors"):',
     '        if False:'),
    ("M11", "set 不校验理由", "pkg/baseline.py",
     '    if not str(reason or "").strip():',
     '    if False:'),
    ("M12", "set 不校验权限", "pkg/baseline.py",
     '    if SET_PERMISSION not in (permissions or ()):',
     '    if False:'),
]


def run(args):
    r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, env=ENV)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def main():
    rc, out = run(["tools/verify.py"])
    if rc != 0:
        print("[STOP] 原件不绿：")
        print(out[-1200:])
        return 2
    print("[OK] 原件必须全绿 rc=0")

    caught, missed, invalid = [], [], []
    for mid, title, rel, old, new in MUTATIONS:
        fp = os.path.join(ROOT, rel)
        src = open(fp, encoding="utf-8").read()
        if old not in src:
            invalid.append((mid, "锚点没命中"))
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
        print("[STOP] 还原后原件不绿")
        print(out3[-800:])
        return 3
    print("[OK] 还原后原件仍全绿 rc=0")
    print("")
    print("MUTATION CAUGHT %d / MISSED %d / INVALID %d"
          % (len(caught), len(missed), len(invalid)))
    return 0 if (not missed and not invalid) else 1


if __name__ == "__main__":
    sys.exit(main())
