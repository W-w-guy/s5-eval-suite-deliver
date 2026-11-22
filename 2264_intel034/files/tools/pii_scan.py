# -*- coding: utf-8 -*-
"""pii 扫描：确认交付包内没有真实个人信息 / 企业信息残留。
扫描范围：包内全部文本类文件（.py/.md/.json/.jsonl/.txt/.yml/.html/.xml）。
判据：手机号 / 邮箱 / 18 位身份证 / 统一社会信用代码 四类形态。

为什么放在本包里而不是靠人工检查：工单要求「只用虚构的测试数据」，
这是一条可以被机器判定的要求，就该由脚本判定并在 CI 里跑。

退出码 0 = 0 命中；1 = 有命中（逐条打印位置）。
运行：python tools/pii_scan.py
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTS = {".py", ".md", ".json", ".jsonl", ".txt", ".yml", ".yaml", ".html", ".xml", ".ini", ".cfg"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}

PATTERNS = [
    ("phone", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("idcard", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("uscc", re.compile(r"(?<![0-9A-Z])[0-9A-Z]{18}(?![0-9A-Z])")),
]

# 显式豁免：只放行源码行尾标注了 `# pii-scan:allow negative-fixture` 的行。
# 用途：单元测试必须注入"形如真实"的号码/邮箱，才能证明检测函数真的会报；
# 这些字符串只作为被注入的坏值存在。豁免条数单独打印，不会被静默吞掉。
ALLOW_MARK = "pii-scan:allow negative-fixture"

# 邮箱白名单：仅 RFC 2606 / 6761 保留域可放行（真实域名一律视为命中）
#   · 保留 TLD：.example / .invalid / .test / .localhost  —— 任何子域都不可解析
#   · 保留二级域：example.com / example.net / example.org
# 早先只写了精确匹配 {example.com, mail.invalid...}，漏掉 a@b.example 这类保留 TLD 下的子域，
# 导致扫描器把「本就虚构」的地址报成命中。这里按 TLD 判定，避免同类漏配。
RESERVED_TLDS = {"example", "invalid", "test", "localhost"}
RESERVED_DOMAINS = {"example.com", "example.net", "example.org"}


def _reserved_domain(dom: str) -> bool:
    dom = dom.lower().rstrip(".")
    return dom in RESERVED_DOMAINS or dom.rsplit(".", 1)[-1] in RESERVED_TLDS


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
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
            for ln, src in enumerate(lines, 1):
                for kind, pat in PATTERNS:
                    for m in pat.finditer(src):
                        if ALLOW_MARK in src:
                            allowed.append(f"{rel}:{ln} {kind} {m.group(0)}")
                            continue
                        if kind == "email" and _reserved_domain(m.group(0).rsplit("@", 1)[-1]):
                            allowed.append(f"{rel}:{ln} {kind} {m.group(0)}（RFC 2606 保留域）")
                            continue
                        hits.append(f"{rel}:{ln} {kind} {m.group(0)}")
    print(f"pii_scan files={scanned} raw_hits={len(hits) + len(allowed)} "
          f"allowed={len(allowed)} unexpected={len(hits)}")
    for h in allowed:
        print("  ALLOWED", h)
    for h in hits:
        print("  HIT", h)
    if not hits:
        print("PII PASS（unexpected=0；手机/邮箱/身份证/信用代码 四类形态均无真实信息）")
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
