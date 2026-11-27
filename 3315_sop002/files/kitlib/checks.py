# -*- coding: utf-8 -*-
"""断言器骨架：每条 check 打印 [PASS]/[FAIL]+实测值，末尾 SUMMARY n/m，失败即非零退出。"""
import sys

OUT = []


def check(name, cond, detail=""):
    OUT.append((name, bool(cond), detail))
    print("[%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))
    return bool(cond)


def fail_now(name, detail=""):
    return check(name, False, detail)


def summary():
    bad = [x for x in OUT if not x[1]]
    print("\nSUMMARY %d/%d PASS" % (len(OUT) - len(bad), len(OUT)))
    return 1 if bad else 0


def run(fn):
    """用法：sys.exit(kitlib.run(main))"""
    try:
        fn()
    except Exception as e:  # 断言器自己崩了也必须非零退出，不能静默通过
        import traceback
        traceback.print_exc()
        print("[FAIL] 断言器异常 %s: %s" % (type(e).__name__, e))
        return 2
    return summary()
