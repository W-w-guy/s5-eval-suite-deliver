# -*- coding: utf-8 -*-
"""PII 扫描：手机号 / 邮箱 / 身份证 / 银行卡 四类正则。

虚构数据里刻意使用掩码与不含真实号段的写法，因此 hits 应为 0。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", "report", "verify_logs"}
TEXT_EXT = {".py", ".md", ".json", ".jsonl", ".csv", ".yaml", ".yml", ".txt"}

PATTERNS = [
    ("mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("idcard", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("bankcard", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
]


def scan(root=ROOT):
    scanned, hits = 0, []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in sorted(fns):
            if os.path.splitext(fn)[1].lower() not in TEXT_EXT:
                continue
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, root).replace(os.sep, "/")
            scanned += 1
            try:
                txt = open(fp, encoding="utf-8").read()
            except UnicodeDecodeError:
                continue
            for name, rx in PATTERNS:
                for m in rx.finditer(txt):
                    hits.append({"file": rel, "kind": name, "sample": m.group(0)[:6] + "***"})
    return scanned, hits


def main():
    scanned, hits = scan()
    print("scanned=%d hits=%d" % (scanned, len(hits)))
    for h in hits[:10]:
        print("  HIT %s %s %s" % (h["file"], h["kind"], h["sample"]))
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
