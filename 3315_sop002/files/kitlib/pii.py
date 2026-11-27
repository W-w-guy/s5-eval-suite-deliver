# -*- coding: utf-8 -*-
"""PII 扫描。扫描文件数必须等于包内可扫描文件数，否则 provenance 里就是假声明。"""
import os
import re
import sys

EXT = {".py", ".md", ".csv", ".txt", ".json", ".yml", ".yaml", ".cfg", ".ini", ".html"}
SKIP_DIRS = {"__pycache__", ".git", "report", ".pytest_cache"}
PAT = [
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("身份证", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("银行卡", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
]


def files(root, skip_files=("SHA256SUMS.txt",)):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            if fn in skip_files:
                continue
            if os.path.splitext(fn)[1].lower() in EXT:
                yield os.path.join(dp, fn)


def scan(root):
    scanned, hits = 0, []
    for fp in files(root):
        scanned += 1
        txt = open(fp, encoding="utf-8", errors="ignore").read()
        for name, pat in PAT:
            for m in pat.findall(txt):
                hits.append((os.path.relpath(fp, root), name, m[:4] + "***"))
    print("scanned=%d hits=%d" % (scanned, len(hits)))
    for h in hits[:20]:
        print("HIT", h)
    return scanned, hits


def main(root):
    scanned, hits = scan(root)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
