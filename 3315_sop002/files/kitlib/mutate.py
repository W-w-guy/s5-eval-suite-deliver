# -*- coding: utf-8 -*-
"""变异测试骨架：把引擎改坏 N 处，每处都必须让 verify 变红。
锚点找不到时**报变异本身失效**（不是安静通过）——否则改坏点没命中也算绿。"""
import os
import shutil
import subprocess
import sys
import tempfile


def _copy(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        "__pycache__", "*.zip", "report", ".pytest_cache", ".git"))


def _run(root, verify_rel):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, verify_rel], cwd=root, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (r.stdout or "").strip().splitlines()[-1:]
    return r.returncode, tail


def run(root, engine_rel, mutations, verify_rel=None):
    """mutations: [(名称, 原字符串, 新字符串)]"""
    verify_rel = verify_rel or os.path.join("tools", "verify.py")
    tmp = tempfile.mkdtemp(prefix="mut_")
    base = os.path.join(tmp, "base")
    _copy(root, base)
    rc, tail = _run(base, verify_rel)
    ok = rc == 0
    print("[%s] 原件必须全绿 rc=%d" % ("OK" if ok else "FAIL", rc))
    bad = 0 if ok else 1
    for name, old, new in mutations:
        d2 = tempfile.mkdtemp(prefix="mut1_")
        cand = os.path.join(d2, "c")
        _copy(root, cand)
        fp = os.path.join(cand, engine_rel)
        src = open(fp, encoding="utf-8").read()
        if old not in src:
            print("[FAIL] %s -> 锚点没命中，变异本身失效" % name)
            bad += 1
            continue
        open(fp, "w", encoding="utf-8").write(src.replace(old, new, 1))
        rc, tail = _run(cand, verify_rel)
        caught = rc != 0
        print("[%s] %s -> %s %s" % (" OK " if caught else "FAIL", name,
                                    "被抓到" if caught else "未被抓到", tail[:1]))
        bad += 0 if caught else 1
    print("MUTATION %s（%d/%d 被抓到）" % ("PASS" if bad == 0 else "FAIL",
                                          len(mutations) - bad, len(mutations)))
    return 1 if bad else 0
