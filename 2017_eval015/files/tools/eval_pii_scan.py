# -*- coding: utf-8 -*-
"""eval-pii-scan：扫描 18 份转写稿 + 用例里的手机号 / 邮箱 / 身份证形态（AC1 要求）。

    python tools/eval_pii_scan.py   # 0 命中 rc=0，打印 PII PASS
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = {
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "邮箱": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "身份证": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
}
SAFE = ("example.invalid", "xxx", "XXXX")


def targets():
    out = [os.path.join(HERE, "data", "cases.jsonl")]
    for root, dirs, files in os.walk(os.path.join(HERE, "data", "transcripts")):
        for f in sorted(files):
            if f.endswith(".txt"):
                out.append(os.path.join(root, f))
    return out


def scan():
    hits, n = [], 0
    for p in targets():
        if not os.path.isfile(p):
            continue
        n += 1
        t = open(p, encoding="utf-8", errors="ignore").read()
        for kind, rx in PAT.items():
            for m in rx.finditer(t):
                seg = m.group(0)
                if any(s in seg for s in SAFE):
                    continue
                hits.append({"file": os.path.relpath(p, HERE), "kind": kind, "value": seg[:32]})
    return hits, n


def main():
    h, n = scan()
    for x in h[:20]:
        print("PII", x)
    print("scanned_files=%d" % n)
    print("hits=%d" % len(h))
    print("PII %s" % ("PASS" if not h else "FAIL"))
    return 0 if not h else 1


if __name__ == "__main__":
    sys.exit(main())
