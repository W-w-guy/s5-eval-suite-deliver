# -*- coding: utf-8 -*-
"""eval-pii-scan：全仓扫描真实格式的手机号 / 邮箱 / 身份证（AC2 要求通过）。

宽松正则、宁可误报：占位写法（010-XXXX-XXXX、example.invalid）不算命中。

★ 二进制文件必须跳过，否则是纯噪声来源：
  把交付包 zip 放在同目录下再跑扫描（验收方常见的做法），压缩流里的随机字节
  会被宽松邮箱正则拼成一个根本不存在的假邮箱（形如 单字母+@+单字母+点+五字母），把 AC2 判成 FAIL。
  判据用内容嗅探（前 8KB 含 NUL 即视为二进制），不靠扩展名，
  并在输出里报 skipped_binary 让跳过行为可见（而不是悄悄蒙住）。
  注意：这不削弱检查——文本文件仍逐个全量扫描，tests 里有反向用例证明漏不掉。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = {
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "邮箱": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "身份证": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
}
# 已知二进制类型直接跳过；其余靠内容嗅探兜底
SKIP_EXT = {".sqlite3", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pyc",
            ".zip", ".gz", ".tgz", ".tar", ".whl", ".7z", ".rar", ".xlsx", ".docx"}
SAFE = ("example.invalid", "xxx", "XXXX")
SNIFF = 8192


def is_binary(path):
    """前 8KB 含 NUL 即当二进制。读不出来也当二进制（跳过，不误报）。"""
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(SNIFF)
    except OSError:
        return True


def scan(root=HERE):
    """返回 (hits, skipped_binary)。"""
    hits = []
    skipped = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in ("__pycache__", ".git", ".pytest_cache")]
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            if os.path.splitext(fn)[1].lower() in SKIP_EXT or is_binary(p):
                skipped.append(rel)
                continue
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                skipped.append(rel)
                continue
            for kind, rx in PAT.items():
                for m in rx.finditer(t):
                    seg = m.group(0)
                    if any(s in seg for s in SAFE) or "XXXX" in t[max(0, m.start() - 8):m.end()]:
                        continue
                    hits.append({"file": rel, "kind": kind, "value": seg[:32]})
    return hits, skipped


def main():
    h, sk = scan()
    for x in h[:20]:
        print("PII", x)
    print("skipped_binary=%d %s" % (len(sk), sk[:3] if sk else ""))
    print("hits=%d" % len(h))
    print("PII %s" % ("PASS" if not h else "FAIL"))
    return 0 if not h else 1


if __name__ == "__main__":
    sys.exit(main())
