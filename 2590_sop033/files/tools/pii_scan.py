# -*- coding: utf-8 -*-
"""pii 扫描：确认交付包内没有真实个人信息 / 企业信息残留。
扫描范围：包内所有文本类文件（.py/.md/.json/.txt/.yml/.yaml/.csv）。
判据：手机号 / 邮箱 / 18 位身份证 / 统一社会信用代码 四类形态。
退出码 0 = 0 命中；1 = 有命中（并逐条打印位置）。
运行：python tools/pii_scan.py
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTS = {".py", ".md", ".json", ".txt", ".yml", ".yaml", ".csv", ".ini", ".cfg"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}

PATTERNS = [
    ("phone", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("idcard", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("uscc", re.compile(r"(?<![0-9A-Z])[0-9A-Z]{18}(?![0-9A-Z])")),
]

# 显式豁免：只放行在源码行尾标注了 `# pii-scan:allow negative-fixture` 的行。
# 用途与边界：变异测试必须注入"形如真实"的号码/邮箱，才能证明 sop-lint 的 E030 会报错；
# 这些字符串只作为被注入的坏值存在，不属于交付内容。扫描器逐行判定，豁免条数另行打印，
# 不会被静默吞掉。
ALLOW_MARK = "pii-scan:allow negative-fixture"


def main():
    scanned = 0
    hits = []
    allowed = []
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in sorted(files):
            if os.path.splitext(fn)[1].lower() not in EXTS:
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            if rel == "tools/pii_scan.py":
                continue  # 本文件自身含正则字面量，不计入扫描面
            scanned += 1
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for kind, pat in PATTERNS:
                for m in pat.finditer(text):
                    line = text[:m.start()].count("\n") + 1
                    src = text.splitlines()[line - 1] if line - 1 < len(text.splitlines()) else ""
                    if ALLOW_MARK in src:
                        allowed.append(f"{rel}:{line} {kind} {m.group(0)}")
                        continue
                    hits.append(f"{rel}:{line} {kind} {m.group(0)}")
    print(f"pii_scan files={scanned} raw_hits={len(hits) + len(allowed)} "
          f"allowed={len(allowed)} unexpected={len(hits)}")
    for h in allowed:
        print("  ALLOWED", h, "（变异测试注入的坏值，非交付内容）")
    for h in hits:
        print("  HIT", h)
    if not hits:
        print("PII PASS（unexpected=0；手机/邮箱/身份证/信用代码 四类形态均无真实信息）")
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
