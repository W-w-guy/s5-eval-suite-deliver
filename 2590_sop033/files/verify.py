# -*- coding: utf-8 -*-
"""一键验证（本包只含 2590 续约预警一个模板）：
1) sop-lint 静态校验
2) AC 集成测试
3) 变异测试（证明校验器与引擎不是「怎么改都通过」）
退出码 0 = 全通过。运行：python verify.py
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
STEPS = [
    ("1/3 sop-lint 静态校验（templates/renewal.json）",
     [sys.executable, "-m", "sop.lint", "templates/renewal.json"]),
    ("2/3 AC 集成测试（2590 续约预警）",
     [sys.executable, "tests/test_renewal_ac.py"]),
    ("3/3 变异测试（校验器盲区）",
     [sys.executable, "tests/mutate.py"]),
]


def main():
    ok = 0
    for title, cmd in STEPS:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", env=ENV)
        lines = [l for l in p.stdout.strip().splitlines() if l.strip()]
        tail = lines[-1] if lines else ""
        status = "通过" if p.returncode == 0 else "失败"
        print(f"{title}: {status}   {tail}")
        if p.returncode != 0:
            print(p.stdout[-3000:])
            print(p.stderr[-1500:])
        else:
            ok += 1
    print("=" * 50)
    print(f"verify {ok}/{len(STEPS)} 通过")
    return 0 if ok == len(STEPS) else 1


if __name__ == "__main__":
    sys.exit(main())
