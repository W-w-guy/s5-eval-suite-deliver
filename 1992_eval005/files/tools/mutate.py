# -*- coding: utf-8 -*-
"""变异测试：把引擎改坏 N 处，每处都必须让 verify 变红。

三条防假绿规则（本套件实测踩过）：
  1) 改坏后先重跑 gen.py 再 verify —— 否则 verify 读到的是旧产物，变异安静通过；
  2) 锚点必须命中，没命中要报「变异本身失效」，不能算 MISSED 掩饰；
  3) 还原后必须再验一次原件全绿，否则说明还原没成功。
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
PY = sys.executable

MUTATIONS = [
    ("M1", "金额容差 0 → 1 分（AC3：1 分必须判 wrong）", "pkg/scorer.py",
     "MONEY_TOLERANCE_FEN = 0", "MONEY_TOLERANCE_FEN = 1"),
    ("M2", "费率容差 0 → 1 基点", "pkg/scorer.py",
     "RATE_TOLERANCE_BP = 0", "RATE_TOLERANCE_BP = 1"),
    ("M3", "critical 强制失效（AC3：critical 错必须不通过）", "pkg/scorer.py",
     "ENFORCE_CRITICAL = True", "ENFORCE_CRITICAL = False"),
    ("M4", "wrong 不计入任何分母（改坏 P/R/F1 口径）", "pkg/scorer.py",
     'WRONG_COUNTS_AS = "both"', 'WRONG_COUNTS_AS = "none"'),
    ("M5", "通过阈值 0.8 → 0.0（多错用例也会通过）", "pkg/scorer.py",
     "PASS_F1_THRESHOLD = 0.8", "PASS_F1_THRESHOLD = 0.0"),
    ("M6", "list 多出的项记成 missing（AC2：应记 extra）", "pkg/scorer.py",
     'fs.add(name, "extra", {key: k})', 'fs.add(name, "missing", {key: k})'),
    ("M7", "list 同 key 但值不同也判 correct（逐项比对失效）", "pkg/scorer.py",
     '            fs.add(name, "wrong", {key: k,', '            fs.add(name, "correct", {key: k,'),
    ("M8", "uscc 不转大写（小写合法值被判错）", "pkg/normalize.py",
     "    s = re.sub(r\"\\s+\", \"\", s).upper()", "    s = re.sub(r\"\\s+\", \"\", s)"),
    ("M9", "date 不做 ISO 归一（多写法被判错）", "pkg/normalize.py",
     '    return "%04d-%02d-%02d" % (y, mo, d)', "    return s"),
    ("M10", "string 不折叠大小写", "pkg/normalize.py",
     "    return s.casefold()", "    return s"),
    ("M11", "金额允许浮点（精度防线失效）", "pkg/normalize.py",
     '        raise NormalizeError("%s 不接受浮点数（浮点会引入精度误差）: %r" % (name, v))',
     "        return int(v)"),
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
            invalid.append((mid, "锚点没命中：%r" % old[:40]))
            print("[INVALID] %s %s -> 锚点没命中，变异本身失效" % (mid, title))
            continue
        open(fp, "w", encoding="utf-8", newline="\n").write(src.replace(old, new, 1))
        try:
            run(["tools/gen.py"])
            rc2, out2 = run(["tools/verify.py"])
        finally:
            open(fp, "w", encoding="utf-8", newline="\n").write(src)
        if rc2 != 0:
            hit = [l for l in out2.splitlines() if l.startswith("[FAIL]")]
            caught.append(mid)
            print("[ OK ] %s %s -> 被抓到 %s" % (mid, title, hit[:1]))
        else:
            missed.append((mid, title))
            print("[MISS] %s %s -> 仍然全绿，变异未被抓到" % (mid, title))

    # 还原后再跑一次原件 + 重新生成产物
    run(["tools/gen.py"])
    rc3, out3 = run(["tools/verify.py"])
    if rc3 != 0:
        print("[STOP] 还原后原件不绿，说明还原失败")
        print(out3[-800:])
        return 3
    print("[OK] 还原后原件仍全绿 rc=0")

    print("")
    print("MUTATION CAUGHT %d / MISSED %d / INVALID %d" % (len(caught), len(missed), len(invalid)))
    return 0 if (not missed and not invalid) else 1


if __name__ == "__main__":
    sys.exit(main())
