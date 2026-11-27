# -*- coding: utf-8 -*-
"""变异测试：把每处关键规则改坏，验证对应的 AC 断言真的会红。

判据（缺一不可）：
  - 变异必须真的改到文件（old 串必须命中，否则记 INVALID——锚点没命中等于变异本身失效）
  - 改坏后跑 pytest 必须失败（记 CAUGHT）
  - 还原后必须重新全绿（否则说明还原不干净，结果不可信）
前端的变异要先重建 dist，否则浏览器跑的还是旧包，会假绿。
"""
from __future__ import annotations
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE = os.path.join(HERE, "frontend")

# (名称, 文件, 原串, 替换为, 是否需要重建前端)
MUTATIONS = [
    ("M1 只需 1 名评审人即可通过", "app/engine.py",
     "REQUIRED_APPROVERS = 2", "REQUIRED_APPROVERS = 1", False),
    ("M2 remove 不再阻断", "app/engine.py",
     "BLOCKING = (REVISE, REMOVE)", "BLOCKING = (REVISE,)", False),
    ("M3 按记录条数而非不同评审人去重", "app/engine.py",
     'approvers = sorted({v["reviewer_id"] for v in verdicts if v["verdict"] == APPROVE})',
     'approvers = [v["reviewer_id"] for v in verdicts if v["verdict"] == APPROVE]', False),
    ("M4 hash 变化不重置", "app/engine.py",
     '    if old_hash is not None and new_hash is not None and old_hash != new_hash:\n        return STATUS_PENDING\n    return status',
     '    return status', False),
    ("M5 任何人都可评审", "app/engine.py",
     'return "eval.case.review" in (permissions or ())', 'return True', False),
    ("M6 页面去掉「删除」按钮", "frontend/src/pages/CaseDetail.tsx",
     '            <Button data-testid={`point-${i}-remove`} size="small" disabled={!allowed}\n'
     "              theme={marks[i]?.verdict === 'remove' ? 'danger' : 'default'}\n"
     "              onClick={() => setMark(i, 'remove')}>删除</Button>\n",
     "", True),
]


def build_fe():
    r = subprocess.run(["npx", "vite", "build"], cwd=FE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_pytest():
    env = dict(os.environ)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header",
                        "-p", "no:cacheprovider"],
                       cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    tail = (r.stdout or "").strip().splitlines()
    return r.returncode, (tail[-1] if tail else "")


def main():
    rc, line = run_pytest()
    print("原件（未变异）".ljust(40), "PASS" if rc == 0 else "FAIL", "|", line)
    if rc != 0:
        print("原件就不绿，先修好再谈变异")
        return 2

    caught = invalid = missed = skipped = 0
    for name, rel, old, new, need_build in MUTATIONS:
        path = os.path.join(HERE, rel.replace("/", os.sep))
        src = open(path, encoding="utf-8").read()
        if old not in src:
            print(name.ljust(40), "[INVALID] 锚点未命中：%s" % rel)
            invalid += 1
            continue
        bak = src
        try:
            open(path, "w", encoding="utf-8", newline="\n").write(src.replace(old, new, 1))
            if need_build:
                if not shutil.which("npm"):
                    # 缺 npm 是本机环境限制，不是变异失效，也不是抓到——单列 SKIP。
                    print(name.ljust(40), "[SKIP]   缺 npm，前端变异未执行")
                    skipped += 1
                    continue
                brc, bout = build_fe()
                if brc != 0:
                    print(name.ljust(40), "[INVALID] 前端重建失败：%s" % bout[-120:])
                    invalid += 1
                    continue
            rc2, line2 = run_pytest()
            if rc2 != 0:
                print(name.ljust(40), "[CAUGHT]  ", line2[:70])
                caught += 1
            else:
                print(name.ljust(40), "[MISSED]  仍然全绿")
                missed += 1
        finally:
            open(path, "w", encoding="utf-8", newline="\n").write(bak)
            if need_build and shutil.which("npm"):
                build_fe()

    rc, line = run_pytest()
    print("还原后复跑".ljust(40), "PASS" if rc == 0 else "FAIL", "|", line)
    total = len(MUTATIONS)
    print("\n变异 %d 个：CAUGHT %d，MISSED %d，INVALID %d，SKIP %d"
          % (total, caught, missed, invalid, skipped))
    return 0 if (missed == 0 and invalid == 0 and rc == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
