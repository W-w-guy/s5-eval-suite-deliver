# -*- coding: utf-8 -*-
"""变异测试：把业务规则改坏 N 处，每处都必须让 verify 变红。

需要真 PG（DATABASE_URL）。每轮变异后重跑 verify（含建库），
所以比较慢；这是必要的 —— 不重跑就会读到旧库状态。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
PY = sys.executable

MUTATIONS = [
    ("M1", "工作日截止从 2 天改成 1 天（AC1 边界会变）", "pkg/workdays.py",
     "WORKDAY_DEADLINE = 2", "WORKDAY_DEADLINE = 1"),
    ("M2", "逾期判定 > 改成 >=（截止日当天就算逾期）", "pkg/workdays.py",
     "    return clock.to_ordinal(today) > clock.to_ordinal(dl)",
     "    return clock.to_ordinal(today) >= clock.to_ordinal(dl)"),
    ("M3", "已关联回归用例也判 overdue（AC1 豁免失效）", "pkg/workdays.py",
     "    if has_regression_case:\n        return False",
     "    if False:\n        return False"),
    ("M4", "周末判定偏移错（周五算周末）", "pkg/workdays.py",
     "    return (clock.to_ordinal(day) + 3) % 7", "    return (clock.to_ordinal(day) + 4) % 7"),
    ("M5", "P0 允许 wont_fix（AC2 失效）", "pkg/state.py",
     "P0_CANNOT_WONT_FIX = True", "P0_CANNOT_WONT_FIX = False"),
    ("M6", "wont_fix 不要求审批角色", "pkg/state.py",
     '        if str(approved_by_role or "").strip() != APPROVER_ROLE:',
     '        if False:'),
    ("M7", "verified 不要求 run_id", "pkg/state.py",
     "VERIFIED_NEEDS_RUN_ID = True", "VERIFIED_NEEDS_RUN_ID = False"),
    ("M8", "关掉状态迁移校验（任意跳转都允许）", "pkg/state.py",
     "ENFORCE_TRANSITION = True", "ENFORCE_TRANSITION = False"),
    ("M9", "evidence 入库前不掩码（AC3 失效）", "pkg/redact.py",
     "REDACT_BEFORE_STORE = True", "REDACT_BEFORE_STORE = False"),
    ("M10", "金丝雀掩码规则关闭（金丝雀原文入库）", "pkg/redact.py",
     '    ("canary", re.compile(r"([A-Z0-9]{4})-[A-Z0-9]{4}-([A-Z0-9]{4})"), r"\\1-****-\\2"),\n',
     ""),
    ("M11", "手机号掩码位数写错（11 位写成 12 位，永不匹配）", "pkg/redact.py",
     '("mobile", re.compile(r"(?<!\\d)(1[3-9]\\d)\\d{4}(\\d{4})(?!\\d)"), r"\\1****\\2"),',
     '("mobile", re.compile(r"(?<!\\d)(1[3-9]\\d{2})\\d{4}(\\d{4})(?!\\d)"), r"\\1****\\2"),'),
    ("M12", "月度导出「已修复」改用 found_at（AC4 口径错）", "pkg/api.py",
     '    fixed = [r for r in rows if in_month(r.fixed_at)]',
     '    fixed = [r for r in rows if in_month(r.found_at)]'),
    ("M13", "月度导出「未关闭」不排除 wont_fix", "pkg/api.py",
     '             and r.status not in ("verified", "wont_fix")]',
     '             and r.status not in ("verified",)]'),
    ("M14", "登记不校验写权限（AC 权限失效）", "pkg/api.py",
     '        S.check_permission(ctx["perms"], S.PERM_WRITE)\n    except PermissionError as e:\n        _err(403, str(e), 403)\n    body = await request.json()\n\n    need',
     '        pass\n    except PermissionError as e:\n        _err(403, str(e), 403)\n    body = await request.json()\n\n    need'),
    ("M15", "PATCH 无条件走状态机（纯字段更新被判 422）", "pkg/api.py",
     '        if "status" in body:', '        if True:'),
]


def run(args, timeout=600):
    r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, env=ENV, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def main():
    if not os.environ.get("DATABASE_URL"):
        print("[STOP] 缺少 DATABASE_URL")
        return 2
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
