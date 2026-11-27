# -*- coding: utf-8 -*-
"""变异测试：把检测逻辑改坏 N 处，每处都必须让 verify 变红。"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
PY = sys.executable

MUTATIONS = [
    ("M1", "身份证不做校验位（反例会误报，AC1 失效）", "pkg/detect.py",
     "        if checksum.id_card_ok(s):", "        if True:"),
    ("M2", "银行卡不做 Luhn（反例会误报）", "pkg/detect.py",
     "        if checksum.luhn_ok(s):", "        if True:"),
    ("M3", "信用代码不排除 999999 占位号段（占位会被报成疑似真实）", "pkg/detect.py",
     '        if s[lo:hi] == placeholder:\n            continue',
     '        if False:\n            continue'),
    ("M4", "手机号不校验第二位 3~9（反例 12x 会误报）", "pkg/rules.py",
     'MOBILE_PREFIX = "1[3-9]"', 'MOBILE_PREFIX = "1[0-9]"'),
    ("M5", "身份证级别从 error 降为 warn（AC2 失效：该阻断的不阻断）", "pkg/rules.py",
     '    "id_card": "error",', '    "id_card": "warn",'),
    ("M6", "银行卡级别从 error 降为 warn", "pkg/rules.py",
     '    "bank_card": "error",', '    "bank_card": "warn",'),
    ("M7", "信用代码级别从 error 降为 warn", "pkg/rules.py",
     '    "uscc": "error",', '    "uscc": "warn",'),
    ("M8", "退出码恒为 0（AC2 失效）", "pkg/cmd.py",
     '    return RC_BLOCK if stats["blocking"] else RC_OK',
     '    return RC_OK'),
    ("M9", "allowlist 不再生效（AC3 失效）", "pkg/allowlist.py",
     '        g["allowed"] = bool(hit)', '        g["allowed"] = False'),
    ("M10", "allowlist 不校验确认人（缺字段也能放行）", "pkg/allowlist.py",
     'REQUIRED = ("value", "confirmed_by", "confirmed_on")',
     'REQUIRED = ("value",)'),
    ("M11", "阻断集不再排除已放行条目（白名单失效）", "pkg/allowlist.py",
     '    return [f for f in findings\n'
     '            if f["level"] == "error" and not f.get("allowed")]',
     '    return [f for f in findings if f["level"] == "error"]'),
    ("M12", "地址只要出现路号就算命中（不要求省市区，反例会误报）", "pkg/detect.py",
     '        if len(seg) >= R.ADDRESS_MIN_LEN and ("市" in seg or "区" in seg or "省" in seg\n'
     '                                              or any(p in seg for p in PROVINCES)):',
     '        if True:'),
    ("M13", "人名不再检查（虚构）后缀（反例会误报）", "pkg/detect.py",
     '            if R.PERSON_SUFFIX in tail or "(虚构)" in tail:\n                continue',
     '            if False:\n                continue'),
    ("M14", "企业名不再检查虚构标记（反例会误报）", "pkg/detect.py",
     "        if any(mk in ctx for mk in R.ORG_MARKERS):\n            continue",
     "        if False:\n            continue"),
]


def run(args):
    r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, env=ENV)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def main():
    rc, out = run(["tools/verify.py"])
    if rc != 0:
        print("[STOP] 原件不绿：")
        print(out[-1500:])
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
            caught.append((mid, hit[:1]))
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
